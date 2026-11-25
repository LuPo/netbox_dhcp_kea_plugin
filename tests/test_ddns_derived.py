"""D2 domains derived from what each DHCP server hands out.

A server's D2 configuration holds a forward domain for every qualifying
suffix its subnets and pools send updates with, a reverse domain for every
reverse zone its prefixes overlap, and nothing else — so one site's zones and
keys never reach another site's host.
"""

# ruff: noqa: F811 — test parameters shadow the fixtures imported for pytest.

import pytest
from django.core.exceptions import ValidationError

from tests.test_ddns_models import (  # noqa: F401
    _make_zone,
    d2_daemon,
    d2_listener_ip,
    name_server,
    tsig_key,
)


pytestmark = pytest.mark.django_db


def _key(name):
    from netbox_dhcp_kea_plugin.models import TSIGKey

    return TSIGKey.objects.create(
        name=name,
        algorithm="HMAC-SHA256",
        secret_backend="vault",
        secret_ref=f"dhcp/{name}/tsig-key#key",
    )


def _policy(name, **fields):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    return DDNSPolicy.objects.create(name=name, **fields)


@pytest.fixture
def zone(name_server):
    """Build a zone served by the resolvable test nameserver."""

    def make(name):
        created = _make_zone(name)
        created.nameservers.add(name_server)
        return created

    return make


@pytest.fixture
def domain(zone):
    """Create a DDNS domain; scope and key are keyword arguments."""
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    def make(zone_name, **fields):
        return DDNSDomain.objects.create(zone=zone(zone_name), **fields)

    return make


@pytest.fixture
def server(dhcp_server_factory, d2_daemon):
    """Create a server on the local D2 daemon."""

    def make(**fields):
        created = dhcp_server_factory(**fields)
        created.d2_daemon = d2_daemon
        created.save()
        return created

    return make


@pytest.fixture
def subnet(subnet_factory, prefix_factory):
    """Create a subnet with a DDNS policy on the given server."""

    def make(srv, network, policy=None):
        created = subnet_factory(server=srv, prefix=prefix_factory(network=network))
        created.ddns_policy = policy
        created.save()
        return created

    return make


def _zones(derived):
    return [entry.domain.zone_name for entry in derived.domains]


# ---------------------------------------------------------------------------
# Forward domains
# ---------------------------------------------------------------------------


class TestForward:
    def test_a_subnets_suffix_brings_in_its_zone(self, server, subnet, domain):
        srv = server()
        subnet(srv, "10.1.0.0/24", _policy("a", ddns_qualifying_suffix="lab.example.org"))
        domain("lab.example.org")
        domain("other.example.org")

        derived = srv.derived_ddns()

        assert _zones(derived) == ["lab.example.org"]
        assert "qualifying suffix 'lab.example.org' (subnet 10.1.0.0/24)" in derived.domains[0].reasons

    def test_the_longest_covering_zone_wins(self, server, subnet, domain):
        srv = server()
        subnet(srv, "10.1.0.0/24", _policy("a", ddns_qualifying_suffix="hosts.lab.example.org."))
        domain("example.org")
        domain("lab.example.org")

        assert _zones(srv.derived_ddns()) == ["lab.example.org"]

    def test_the_server_policy_suffix_is_inherited(self, server, subnet, domain):
        srv = server()
        srv.ddns_policy = _policy("srv", ddns_qualifying_suffix="lab.example.org")
        srv.save()
        subnet(srv, "10.1.0.0/24")
        domain("lab.example.org")

        assert _zones(srv.derived_ddns()) == ["lab.example.org"]

    def test_a_pool_suffix_is_its_own(self, server, subnet, domain):
        from ipam.models import IPRange
        from netaddr import IPNetwork

        from netbox_dhcp_kea_plugin.models import SubnetPool

        srv = server()
        sub = subnet(srv, "10.1.0.0/24", _policy("sub", ddns_qualifying_suffix="lab.example.org"))
        ip_range = IPRange.objects.create(
            start_address=IPNetwork("10.1.0.100/24"), end_address=IPNetwork("10.1.0.150/24")
        )
        SubnetPool.objects.create(
            subnet=sub, ip_range=ip_range, ddns_policy=_policy("pool", ddns_qualifying_suffix="iot.example.org")
        )
        domain("lab.example.org")
        domain("iot.example.org")

        assert _zones(srv.derived_ddns()) == ["iot.example.org", "lab.example.org"]

    def test_a_subnet_that_sends_no_updates_brings_in_nothing(self, server, subnet, domain):
        srv = server()
        subnet(srv, "10.1.0.0/24", _policy("off", ddns_send_updates=False, ddns_qualifying_suffix="lab.example.org"))
        domain("lab.example.org")

        assert srv.derived_ddns().domains == []

    def test_an_uncovered_suffix_is_a_warning(self, server, subnet):
        srv = server()
        subnet(srv, "10.1.0.0/24", _policy("a", ddns_qualifying_suffix="nowhere.example.org"))

        derived = srv.derived_ddns()

        assert derived.domains == []
        assert any("'nowhere.example.org'" in w for w in derived.warnings)

    def test_no_suffix_is_a_warning(self, server, subnet):
        srv = server()
        subnet(srv, "10.1.0.0/24")

        assert any("no qualifying suffix" in w for w in srv.derived_ddns().warnings)


# ---------------------------------------------------------------------------
# Reverse domains
# ---------------------------------------------------------------------------


class TestReverse:
    def test_a_22_brings_in_its_four_24_zones(self, server, subnet, domain):
        srv = server()
        subnet(srv, "10.41.200.0/22", _policy("a", ddns_qualifying_suffix="lab.example.org"))
        for third in (199, 200, 201, 202, 203, 204):
            domain(f"{third}.41.10.in-addr.arpa")

        reverse = [e.domain.zone_name for e in srv.derived_ddns().domains if e.domain.is_reverse]

        assert sorted(reverse) == [f"{third}.41.10.in-addr.arpa" for third in (200, 201, 202, 203)]

    def test_a_subnet_without_a_reverse_zone_is_a_warning(self, server, subnet, domain):
        srv = server()
        subnet(srv, "10.1.0.0/24", _policy("a", ddns_qualifying_suffix="lab.example.org"))
        domain("lab.example.org")

        assert any("No reverse DDNS domain covers subnet 10.1.0.0/24" in w for w in srv.derived_ddns().warnings)


# ---------------------------------------------------------------------------
# Scope: which entry, and so which key, a server uses
# ---------------------------------------------------------------------------


class TestScope:
    def test_another_servers_entry_and_key_stay_off_this_host(self, server, subnet, domain):
        site_a = server(name="site-a")
        site_b = server(name="site-b")
        for srv, network in ((site_a, "10.1.0.0/24"), (site_b, "10.2.0.0/24")):
            subnet(srv, network, _policy(f"p-{srv.name}", ddns_qualifying_suffix="lab.example.org"))
        domain("lab.example.org", dhcp_server=site_b, tsig_key=_key("site-b-key"))

        config = site_a.d2_kea_dict()["DhcpDdns"]

        assert config["forward-ddns"]["ddns-domains"] == []
        assert "tsig-keys" not in config
        assert "site-b-key" in str(site_b.d2_kea_dict())

    def test_the_narrowest_entry_wins(self, server, subnet, domain, dhcp_server_factory):
        from netbox_dhcp_kea_plugin.models import DDNSDomain, DHCPHARelationship

        ha = DHCPHARelationship.objects.create(name="pair", mode="hot-standby")
        primary = server(ha_relationship=ha, ha_role="primary", ha_address="192.168.1.60")
        subnet(primary, "10.1.0.0/24", _policy("a", ddns_qualifying_suffix="lab.example.org"))
        everyone = domain("lab.example.org", tsig_key=_key("global-key"))
        pair = DDNSDomain.objects.create(zone=everyone.zone, ha_relationship=ha, tsig_key=_key("pair-key"))

        assert primary.derived_ddns().domain_list == [pair]

        own = DDNSDomain.objects.create(zone=everyone.zone, dhcp_server=primary, tsig_key=_key("own-key"))

        assert primary.derived_ddns().domain_list == [own]

    def test_ha_peers_share_the_pairs_entries(self, server, subnet, domain):
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        ha = DHCPHARelationship.objects.create(name="pair", mode="hot-standby")
        primary = server(ha_relationship=ha, ha_role="primary", ha_address="192.168.1.70")
        standby = server(ha_relationship=ha, ha_role="standby", ha_address="192.168.1.71")
        subnet(primary, "10.1.0.0/24", _policy("a", ddns_qualifying_suffix="lab.example.org"))
        domain("lab.example.org", ha_relationship=ha, tsig_key=_key("pair-key"))

        assert primary.d2_kea_dict() == standby.d2_kea_dict()
        assert "pair-key" in str(standby.d2_kea_dict())

    def test_a_scoped_entry_can_be_always_included(self, server, domain):
        srv = server()
        domain("clients.example.org", dhcp_server=srv, always_include=True)

        derived = srv.derived_ddns()

        assert _zones(derived) == ["clients.example.org"]
        assert derived.domains[0].reasons == ["always included"]

    def test_one_key_can_serve_several_servers(self, server, subnet, domain):
        shared = _key("shared-key")
        site_a = server(name="site-a")
        site_b = server(name="site-b")
        subnet(site_a, "10.1.0.0/24", _policy("a", ddns_qualifying_suffix="a.example.org"))
        subnet(site_b, "10.2.0.0/24", _policy("b", ddns_qualifying_suffix="b.example.org"))
        domain("a.example.org", dhcp_server=site_a, tsig_key=shared)
        domain("b.example.org", dhcp_server=site_b, tsig_key=shared)

        assert "shared-key" in str(site_a.d2_kea_dict())
        assert "shared-key" in str(site_b.d2_kea_dict())


class TestScopeValidation:
    def test_both_scopes_at_once_are_refused(self, domain, dhcp_server):
        from netbox_dhcp_kea_plugin.models import DDNSDomain, DHCPHARelationship

        ha = DHCPHARelationship.objects.create(name="pair", mode="hot-standby")
        entry = DDNSDomain(zone=domain("lab.example.org").zone, dhcp_server=dhcp_server, ha_relationship=ha)

        with pytest.raises(ValidationError) as exc:
            entry.full_clean()

        assert "ha_relationship" in exc.value.message_dict

    def test_a_global_entry_cannot_be_always_included(self, zone):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        entry = DDNSDomain(zone=zone("lab.example.org"), always_include=True)

        with pytest.raises(ValidationError) as exc:
            entry.full_clean()

        assert "always_include" in exc.value.message_dict

    def test_a_zone_can_have_a_global_and_a_server_entry(self, domain, dhcp_server):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        everyone = domain("lab.example.org")

        DDNSDomain(zone=everyone.zone, dhcp_server=dhcp_server).full_clean()

    def test_a_second_global_entry_is_refused(self, domain):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        everyone = domain("lab.example.org")

        with pytest.raises(ValidationError):
            DDNSDomain(zone=everyone.zone).full_clean()


# ---------------------------------------------------------------------------
# Which hosts run D2
# ---------------------------------------------------------------------------


class TestWhoRunsD2:
    def test_a_server_with_updates_off_runs_no_d2(self, server):
        srv = server()
        srv.ddns_enable_updates = False
        srv.save()

        assert srv.d2_kea_dict() is None
        assert srv.derived_ddns().enabled is False

    def test_a_server_on_a_remote_daemon_runs_no_d2_of_its_own(self, server, d2_daemon):
        d2_daemon.listener_mode = "remote"
        d2_daemon.save()

        assert server().d2_kea_dict() is None

    def test_a_local_daemon_has_no_single_configuration(self, d2_daemon):
        from netbox_dhcp_kea_plugin.models import LocalD2DaemonError

        with pytest.raises(LocalD2DaemonError):
            d2_daemon.to_kea_dict()

    def test_a_remote_daemon_serves_every_servers_domains(self, server, subnet, domain, d2_daemon):
        d2_daemon.listener_mode = "remote"
        d2_daemon.save()
        site_a = server(name="site-a")
        site_b = server(name="site-b")
        subnet(site_a, "10.1.0.0/24", _policy("a", ddns_qualifying_suffix="a.example.org"))
        subnet(site_b, "10.2.0.0/24", _policy("b", ddns_qualifying_suffix="b.example.org"))
        domain("a.example.org")
        domain("b.example.org")

        names = [d["name"] for d in d2_daemon.to_kea_dict()["DhcpDdns"]["forward-ddns"]["ddns-domains"]]

        assert names == ["a.example.org.", "b.example.org."]

    def test_a_shared_daemon_cannot_hold_two_entries_for_one_zone(self, server, subnet, domain, d2_daemon):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        d2_daemon.listener_mode = "remote"
        d2_daemon.save()
        site_a = server(name="site-a")
        site_b = server(name="site-b")
        for srv, network in ((site_a, "10.1.0.0/24"), (site_b, "10.2.0.0/24")):
            subnet(srv, network, _policy(f"p-{srv.name}", ddns_qualifying_suffix="lab.example.org"))
        everyone = domain("lab.example.org")
        DDNSDomain.objects.create(zone=everyone.zone, dhcp_server=site_b)

        assert any("'lab.example.org' would be served by 2" in e for e in d2_daemon.configuration_errors())


# ---------------------------------------------------------------------------
# OpenBao reference format
# ---------------------------------------------------------------------------


class TestSecretReference:
    def _key(self, ref):
        from netbox_dhcp_kea_plugin.models import TSIGKey

        return TSIGKey(name="ref-test.", algorithm="HMAC-SHA256", secret_backend="vault", secret_ref=ref)

    @pytest.mark.parametrize("ref", ["dhcp/site-a/tsig-key#key", "tsig#secret", "a.b/c_d/e-f#g"])
    def test_a_path_and_field_are_accepted(self, ref):
        self._key(ref).full_clean()

    @pytest.mark.parametrize(
        "ref",
        [
            "dhcp/site-a/tsig-key",
            "dhcp/site-a/tsig-key#",
            "#key",
            "dhcp/a#b#c",
            "kv/dhcp/site-a/tsig-key#key",
            "${BAO:dhcp/site-a/tsig-key#key}",
            "/dhcp/site-a#key",
            "dhcp/site a#key",
        ],
    )
    def test_anything_else_is_refused(self, ref):
        with pytest.raises(ValidationError) as exc:
            self._key(ref).full_clean()

        assert "secret_ref" in exc.value.message_dict

    @staticmethod
    def _set_pattern(monkeypatch, pattern):
        from django.conf import settings

        # setitem, so the plugin's live config is restored after the test.
        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "ddns_secret_reference_pattern", pattern)

    def test_the_pattern_is_configurable(self, monkeypatch):
        self._set_pattern(monkeypatch, r"secret/[a-z]+")

        self._key("secret/abc").full_clean()
        with pytest.raises(ValidationError) as exc:
            self._key("dhcp/site-a/tsig-key#key").full_clean()

        assert "secret/[a-z]+" in str(exc.value.message_dict["secret_ref"])

    def test_an_empty_pattern_turns_the_check_off(self, monkeypatch):
        self._set_pattern(monkeypatch, "")

        self._key("anything at all").full_clean()


# ---------------------------------------------------------------------------
# Servers & Domains tab: one group per HA relationship
# ---------------------------------------------------------------------------


class TestGrouping:
    @pytest.fixture
    def pair(self, server, subnet, domain):
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        ha = DHCPHARelationship.objects.create(name="pair", mode="hot-standby")
        primary = server(name="pair-1", ha_relationship=ha, ha_role="primary", ha_address="192.168.1.80")
        standby = server(name="pair-2", ha_relationship=ha, ha_role="standby", ha_address="192.168.1.81")
        subnet(primary, "10.1.0.0/24", _policy("a", ddns_qualifying_suffix="lab.example.org"))
        domain("lab.example.org", ha_relationship=ha)
        return ha, primary, standby

    @staticmethod
    def _groups(d2_daemon):
        from netbox_dhcp_kea_plugin.ddns import group_by_relationship

        return group_by_relationship([(s, s.derived_ddns()) for s in d2_daemon.servers_using()])

    def test_ha_peers_with_the_same_domains_are_shown_once(self, pair, server, d2_daemon):
        ha, primary, standby = pair
        server(name="standalone")

        groups = self._groups(d2_daemon)

        assert [(g.ha_relationship, [s.name for s in g.servers]) for g in groups] == [
            (ha, ["pair-1", "pair-2"]),
            (None, ["standalone"]),
        ]
        ((servers, _derived),) = groups[0].variants
        assert servers == [primary, standby]
        assert groups[0].domain_count == 1

    def test_peers_that_differ_are_shown_apart(self, pair, zone, d2_daemon):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        _ha, primary, standby = pair
        DDNSDomain.objects.create(zone=zone("extra.example.org"), dhcp_server=standby, always_include=True)

        (group,) = self._groups(d2_daemon)

        assert [servers for servers, _derived in group.variants] == [[primary], [standby]]
        assert group.domain_count == 2

    @pytest.mark.skipif(
        not __import__("netbox.plugins.utils", fromlist=["get_plugin_config"]).get_plugin_config(
            "netbox_dhcp_kea_plugin", "enable_ddns"
        ),
        reason="enable_ddns plugin flag is off — DDNS routes not registered",
    )
    def test_the_tab_renders(self, pair, d2_daemon, client):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        client.force_login(get_user_model().objects.create_superuser(username="d2-tab", password="x"))

        resp = client.get(reverse("plugins:netbox_dhcp_kea_plugin:d2daemon_domains", args=[d2_daemon.pk]))

        assert resp.status_code == 200
        # One table for the pair, not one per peer.
        assert resp.content.decode().count("(subnet 10.1.0.0/24)") == 1
