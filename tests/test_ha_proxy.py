"""
Tests for the HA reverse-proxy plan (Envoy in front of KEA).

When the relationship's ha_proxy_enabled is set, KEA must speak plain HTTP over loopback in both
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
        pki_fqdn="kea-a.pki.example.net",
    )
    standby = dhcp_server_factory(
        name="kea-b",
        ha_relationship=relationship,
        ha_role="standby",
        ha_address="10.0.0.2",
        ha_port=8080,
        pki_fqdn="kea-b.pki.example.net",
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
        relationship.ha_proxy_enabled = True
        relationship.save()

        peers = {peer["name"]: peer for peer in relationship.to_kea_dict(this_server=primary)["peers"]}

        assert peers["kea-a"]["url"] == "http://127.0.0.1:8080/"

    def test_partner_is_reached_through_a_local_egress_port(self, ha_pair):
        relationship, primary, _ = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()

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
        relationship.ha_proxy_enabled = True
        relationship.save()

        # Ordered by peer name, so the assignment does not move when a server
        # is added or the query order changes.
        assert [peer["egress_port"] for peer in primary.ha_proxy["peers"]] == [18080, 18081]
        assert [peer["name"] for peer in primary.ha_proxy["peers"]] == ["kea-b", "kea-c"]

    def test_basic_auth_survives_proxying(self, ha_pair, dhcp_server_factory):
        """Rewriting URLs to loopback must not disturb the shared credentials.

        Both concerns land on the same peer entries, so they are asserted
        together: every entry keeps the relationship's secret, and every entry
        still points at the proxy.
        """
        relationship, primary, _ = ha_pair
        relationship.ha_basic_auth_user = "kea_ha"
        relationship.ha_basic_auth_password = "secret"
        relationship.save()
        relationship.ha_proxy_enabled = True
        relationship.save()

        peers = {peer["name"]: peer for peer in relationship.to_kea_dict(this_server=primary)["peers"]}

        assert peers["kea-a"]["url"] == "http://127.0.0.1:8080/"
        assert peers["kea-b"]["url"] == "http://127.0.0.1:18080/"
        for peer in peers.values():
            assert peer["basic-auth-user"] == "kea_ha"
            assert peer["basic-auth-password"] == "secret"

    def test_the_flag_reaches_every_member(self, ha_pair):
        """The whole point of moving it: no member can disagree.

        A cluster proxied on one side only fails in both directions — the
        unproxied peer dials plain HTTP at the other's Envoy listener, while
        that Envoy originates TLS to a KEA that speaks none.
        """
        relationship, primary, standby = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()

        assert primary.ha_proxy_enabled is True
        assert standby.ha_proxy_enabled is True

        # Both members render an all-loopback peer list, not just the one edited.
        for member in (primary, standby):
            peers = relationship.to_kea_dict(this_server=member)["peers"]
            assert all(peer["url"].startswith("http://127.0.0.1:") for peer in peers)

    def test_a_server_outside_a_relationship_is_never_proxied(self, dhcp_server_factory):
        standalone = dhcp_server_factory(name="kea-solo")

        assert standalone.ha_proxy_enabled is False
        assert standalone.ha_proxy == {"enabled": False}

    def test_no_tls_parameters_are_emitted(self, ha_pair):
        """TLS belongs to the proxy — KEA must stay plain HTTP."""
        relationship, primary, _ = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()

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
        relationship, primary, _ = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()

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
                "fqdn": "kea-b.pki.example.net",
                "sni": "kea-b.pki.example.net",
            }
        ]

    def test_control_socket_port_is_published_when_proxied(self, ha_pair):
        relationship, primary, _ = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()
        primary.ctrl_socket_type = "http"
        primary.ctrl_socket_http_address = "127.0.0.1"
        primary.ctrl_socket_http_port = 8000
        primary.ctrl_socket_proxy_enabled = True
        primary.save()

        assert primary.ha_proxy["ctrl_port"] == 8000

    def test_control_socket_port_is_absent_when_not_proxied(self, ha_pair):
        relationship, primary, _ = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()
        primary.ctrl_socket_type = "http"
        primary.ctrl_socket_http_port = 8000
        primary.save()

        assert primary.ha_proxy["ctrl_port"] is None


@pytest.mark.django_db
class TestHAProxyValidation:
    """clean() guards the combinations that cannot work."""

    def test_ha_tls_and_proxy_are_mutually_exclusive(self, ha_pair):
        relationship, primary, _ = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()
        primary.ha_tls = True

        with pytest.raises(ValidationError) as exc:
            primary.clean()

        assert "ha_tls" in exc.value.message_dict

    def test_proxy_requires_an_ha_address(self, ha_pair):
        relationship, primary, _ = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()
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


@pytest.mark.django_db
class TestPKIIdentity:
    """The PKI identity peers pin each other by.

    Envoy uses one string as the egress cluster address, the TLS SNI, and the
    exact SAN matcher, so it has to be a DNS name and it has to be normalised
    identically everywhere it is set.
    """

    def test_every_peer_entry_carries_an_fqdn(self, ha_pair):
        relationship, primary, _ = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()

        peers = primary.ha_proxy["peers"]

        assert [peer["fqdn"] for peer in peers] == ["kea-b.pki.example.net"]
        # An IP here was the defect: SNI cannot carry an address (RFC 6066).
        assert peers[0]["sni"] == "kea-b.pki.example.net"

    def test_an_ip_address_is_rejected_as_an_identity(self, ha_pair):
        _, primary, _ = ha_pair
        primary.pki_fqdn = "10.0.0.2"

        with pytest.raises(ValidationError) as exc:
            primary.clean()

        assert "pki_fqdn" in exc.value.message_dict

    def test_an_ipv6_address_is_rejected_too(self, ha_pair):
        _, primary, _ = ha_pair
        primary.pki_fqdn = "2001:db8::1"

        with pytest.raises(ValidationError) as exc:
            primary.clean()

        assert "pki_fqdn" in exc.value.message_dict

    def test_a_proxied_member_must_have_an_identity(self, ha_pair):
        relationship, primary, _ = ha_pair
        relationship.ha_proxy_enabled = True
        relationship.save()
        primary.pki_fqdn = ""

        with pytest.raises(ValidationError) as exc:
            primary.clean()

        assert "pki_fqdn" in exc.value.message_dict

    def test_an_unproxied_member_may_have_no_identity(self, ha_pair):
        """Only the proxy needs the name, so plain HA stays valid without one."""
        _, primary, _ = ha_pair
        primary.pki_fqdn = ""

        primary.clean()

    def test_case_and_trailing_dot_are_normalised(self, dhcp_server_factory):
        """A record's absolute, mixed-case name and a typed one must agree.

        Two spellings of the same name would otherwise produce two different
        pins, and the handshake would fail on a dot.
        """
        from netbox_dhcp_kea_plugin.models import DHCPServer

        assert DHCPServer.normalize_pki_fqdn("Kea-A01.PKI.Example.NET.") == "kea-a01.pki.example.net"
        assert DHCPServer.normalize_pki_fqdn("  kea-a01.pki.example.net  ") == "kea-a01.pki.example.net"
        assert DHCPServer.normalize_pki_fqdn("") == ""
        assert DHCPServer.normalize_pki_fqdn(None) == ""

        server = dhcp_server_factory(name="kea-norm", pki_fqdn="Kea-A01.PKI.Example.NET.")

        assert server.pki_fqdn == "kea-a01.pki.example.net"

    def test_normalisation_survives_a_round_trip(self, dhcp_server_factory):
        server = dhcp_server_factory(name="kea-roundtrip", pki_fqdn="KEA-B01.PKI.EXAMPLE.NET.")
        server.refresh_from_db()

        assert server.pki_fqdn == "kea-b01.pki.example.net"

    def test_clusters_do_not_leak_into_each_others_pin_lists(self, ha_pair, dhcp_server_factory):
        """The property the whole design rests on.

        Cluster isolation is enforced by what each Envoy accepts, so a peer
        list that mentioned another cluster's member would silently re-open
        exactly the cross-cluster acceptance the exact-match pins prevent.
        """
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship_a, primary_a, standby_a = ha_pair
        relationship_a.ha_proxy_enabled = True
        relationship_a.save()

        relationship_b = DHCPHARelationship.objects.create(
            name="other-cluster", mode="hot-standby", ha_proxy_enabled=True
        )
        primary_b = dhcp_server_factory(
            name="kea-c",
            ha_relationship=relationship_b,
            ha_role="primary",
            ha_address="10.9.0.1",
            ha_port=8080,
            pki_fqdn="kea-c.pki.example.net",
        )
        dhcp_server_factory(
            name="kea-d",
            ha_relationship=relationship_b,
            ha_role="standby",
            ha_address="10.9.0.2",
            ha_port=8080,
            pki_fqdn="kea-d.pki.example.net",
        )

        a_names = {peer["fqdn"] for peer in primary_a.ha_proxy["peers"]}
        b_names = {peer["fqdn"] for peer in primary_b.ha_proxy["peers"]}

        assert a_names == {"kea-b.pki.example.net"}
        assert b_names == {"kea-d.pki.example.net"}
        assert a_names.isdisjoint(b_names)
        # And the HA peer list itself stays scoped the same way.
        assert {p["name"] for p in relationship_a.to_kea_dict(this_server=primary_a)["peers"]} == {
            "kea-a",
            "kea-b",
        }


@pytest.mark.django_db
class TestPKIZoneEnforcement:
    """pki_allowed_zone_suffixes is opt-in, but enforced once it is set."""

    def test_no_configured_zones_means_no_check(self, ha_pair):
        """The default is empty, so any name saves."""
        _, primary, _ = ha_pair
        primary.pki_fqdn = "kea-a.somewhere-else.test"

        primary.clean()

    def test_a_name_outside_the_issuable_zones_is_rejected(self, ha_pair, settings, monkeypatch):
        _, primary, _ = ha_pair
        monkeypatch.setitem(
            settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "pki_allowed_zone_suffixes", [".pki.example.net"]
        )
        primary.pki_fqdn = "kea-a.not-issuable.test"

        with pytest.raises(ValidationError) as exc:
            primary.clean()

        message = exc.value.message_dict["pki_fqdn"][0]
        assert "pki.example.net" in message
        # The error has to say how to proceed, not just refuse.
        assert "pki_allowed_zone_suffixes" in message

    def test_a_name_inside_the_issuable_zones_is_accepted(self, ha_pair, settings, monkeypatch):
        _, primary, _ = ha_pair
        monkeypatch.setitem(
            settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "pki_allowed_zone_suffixes", [".pki.example.net"]
        )

        primary.clean()

    def test_the_leading_dot_in_a_suffix_is_optional(self, ha_pair, settings, monkeypatch):
        _, primary, _ = ha_pair
        monkeypatch.setitem(
            settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "pki_allowed_zone_suffixes", ["pki.example.net"]
        )

        primary.clean()


@pytest.mark.django_db
class TestPKIIdentityAdvisories:
    """Shown on the detail page, never raised — netbox_dns is optional."""

    def test_no_identity_produces_no_advisories(self, dhcp_server_factory):
        server = dhcp_server_factory(name="kea-noid")

        assert server.pki_identity_advisories() == []

    def test_a_name_with_no_matching_dns_record_is_flagged(self, ha_pair):
        """Advisory, not an error: DNS may simply be managed elsewhere."""
        _, primary, _ = ha_pair

        advisories = primary.pki_identity_advisories()

        # netbox_dns is installed in this environment, and no record exists.
        assert len(advisories) == 1
        assert "kea-a.pki.example.net" in advisories[0]
        # Saving must still be allowed.
        primary.clean()
