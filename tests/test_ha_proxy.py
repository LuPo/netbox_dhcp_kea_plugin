"""
Tests for the HA reverse-proxy plan (Envoy in front of KEA).

When ha_proxy_enabled is set, KEA must speak plain HTTP over loopback in both
directions: its own peer entry points at the loopback listener, and every other
peer points at a local egress port that the proxy forwards from. The proxy plan
published to Ansible has to agree with those URLs, since the two configurations
are generated from it.
"""

import pytest
from django.core.exceptions import ValidationError


@pytest.fixture
def ha_pair(dhcp_server_factory):
    """A hot-standby relationship with two members, proxy disabled."""
    from netbox_dhcp_kea_plugin.models import DHCPHARelationship

    relationship = DHCPHARelationship.objects.create(name="ha-proxy-cluster", mode="hot-standby")
    primary = dhcp_server_factory(
        name="kea-a",
        ha_relationship=relationship,
        ha_role="primary",
        ha_address="10.0.0.1",
        ha_port=8080,
    )
    standby = dhcp_server_factory(
        name="kea-b",
        ha_relationship=relationship,
        ha_role="standby",
        ha_address="10.0.0.2",
        ha_port=8080,
    )
    return relationship, primary, standby


@pytest.mark.django_db
class TestHAProxyPeerURLs:
    """to_kea_dict() rewrites peer URLs when the proxy is enabled."""

    def test_peers_use_public_urls_without_proxy(self, ha_pair):
        relationship, primary, _ = ha_pair

        peers = relationship.to_kea_dict(this_server=primary)["peers"]

        assert {peer["url"] for peer in peers} == {
            "http://10.0.0.1:8080/",
            "http://10.0.0.2:8080/",
        }

    def test_own_entry_moves_to_loopback(self, ha_pair):
        relationship, primary, _ = ha_pair
        primary.ha_proxy_enabled = True
        primary.save()

        peers = {peer["name"]: peer for peer in relationship.to_kea_dict(this_server=primary)["peers"]}

        assert peers["kea-a"]["url"] == "http://127.0.0.1:8080/"

    def test_partner_is_reached_through_a_local_egress_port(self, ha_pair):
        relationship, primary, _ = ha_pair
        primary.ha_proxy_enabled = True
        primary.save()

        peers = {peer["name"]: peer for peer in relationship.to_kea_dict(this_server=primary)["peers"]}

        assert peers["kea-b"]["url"] == "http://127.0.0.1:18080/"

    def test_egress_ports_are_stable_and_per_peer(self, ha_pair, dhcp_server_factory):
        relationship, primary, _ = ha_pair
        dhcp_server_factory(
            name="kea-c",
            ha_relationship=relationship,
            ha_role="backup",
            ha_address="10.0.0.3",
            ha_port=8080,
        )
        primary.ha_proxy_enabled = True
        primary.save()

        # Ordered by peer name, so the assignment does not move when a server
        # is added or the query order changes.
        assert [peer["egress_port"] for peer in primary.ha_proxy["peers"]] == [18080, 18081]
        assert [peer["name"] for peer in primary.ha_proxy["peers"]] == ["kea-b", "kea-c"]

    def test_basic_auth_survives_proxying(self, ha_pair, dhcp_server_factory):
        relationship, primary, standby = ha_pair
        standby.ha_basic_auth_user = "kea_ha"
        standby.ha_basic_auth_password = "secret"
        standby.save()
        primary.ha_proxy_enabled = True
        primary.save()

        peers = {peer["name"]: peer for peer in relationship.to_kea_dict(this_server=primary)["peers"]}

        assert peers["kea-b"]["basic-auth-user"] == "kea_ha"
        assert peers["kea-b"]["basic-auth-password"] == "secret"

    def test_no_tls_parameters_are_emitted(self, ha_pair):
        """TLS belongs to the proxy — KEA must stay plain HTTP."""
        relationship, primary, _ = ha_pair
        primary.ha_proxy_enabled = True
        primary.save()

        peers = relationship.to_kea_dict(this_server=primary)["peers"]

        for peer in peers:
            assert "trust-anchor" not in peer
            assert "cert-file" not in peer
            assert "key-file" not in peer
            assert peer["url"].startswith("http://")


@pytest.mark.django_db
class TestHAProxyPlan:
    """The ha_proxy plan handed to Ansible."""

    def test_disabled_plan_is_inert(self, ha_pair):
        _, primary, _ = ha_pair

        assert primary.ha_proxy == {"enabled": False}

    def test_plan_describes_both_directions(self, ha_pair):
        _, primary, _ = ha_pair
        primary.ha_proxy_enabled = True
        primary.save()

        plan = primary.ha_proxy

        assert plan["enabled"] is True
        # Envoy binds the public address; KEA moves to loopback on the same port.
        assert plan["public_address"] == "10.0.0.1"
        assert plan["public_port"] == 8080
        assert plan["internal_address"] == "127.0.0.1"
        assert plan["internal_port"] == 8080
        assert plan["peers"] == [
            {
                "name": "kea-b",
                "egress_port": 18080,
                "upstream_address": "10.0.0.2",
                "upstream_port": 8080,
                "sni": "10.0.0.2",
            }
        ]

    def test_control_socket_port_is_published_when_proxied(self, ha_pair):
        _, primary, _ = ha_pair
        primary.ha_proxy_enabled = True
        primary.ctrl_socket_type = "http"
        primary.ctrl_socket_http_address = "127.0.0.1"
        primary.ctrl_socket_http_port = 8000
        primary.ctrl_socket_proxy_enabled = True
        primary.save()

        assert primary.ha_proxy["ctrl_port"] == 8000

    def test_control_socket_port_is_absent_when_not_proxied(self, ha_pair):
        _, primary, _ = ha_pair
        primary.ha_proxy_enabled = True
        primary.ctrl_socket_type = "http"
        primary.ctrl_socket_http_port = 8000
        primary.save()

        assert primary.ha_proxy["ctrl_port"] is None


@pytest.mark.django_db
class TestHAProxyValidation:
    """clean() guards the combinations that cannot work."""

    def test_ha_tls_and_proxy_are_mutually_exclusive(self, ha_pair):
        _, primary, _ = ha_pair
        primary.ha_proxy_enabled = True
        primary.ha_tls = True

        with pytest.raises(ValidationError) as exc:
            primary.clean()

        assert "ha_tls" in exc.value.message_dict

    def test_proxy_requires_an_ha_address(self, ha_pair):
        _, primary, _ = ha_pair
        primary.ha_proxy_enabled = True
        primary.ha_address = ""

        with pytest.raises(ValidationError) as exc:
            primary.clean()

        assert "ha_address" in exc.value.message_dict

    def test_control_socket_proxy_requires_a_loopback_bind(self, ha_pair):
        _, primary, _ = ha_pair
        primary.ctrl_socket_type = "http"
        primary.ctrl_socket_http_address = "10.0.0.1"
        primary.ctrl_socket_http_port = 8000
        primary.ctrl_socket_proxy_enabled = True

        with pytest.raises(ValidationError) as exc:
            primary.clean()

        assert "ctrl_socket_http_address" in exc.value.message_dict
