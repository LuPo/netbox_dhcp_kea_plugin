"""HA-relationship precedence rules for the D2 daemon and DDNS sender block.

When a DHCPServer belongs to an HA relationship and that relationship has its
own ``d2_daemon`` set, the relationship's d2_daemon and ddns_enable_updates
win and the server's own values for those two are ignored. Sender IP/port are
per-server (the local source endpoint) and are not overridden by the HA
relationship. Removing the relationship reverts the server to its own
d2_daemon/enable_updates values.
"""

import pytest


pytestmark = pytest.mark.django_db


@pytest.fixture
def d2_a(db):
    from ipam.models import IPAddress

    from netbox_dhcp_kea_plugin.models import D2Daemon

    ip = IPAddress.objects.create(address="10.0.1.50/24")
    return D2Daemon.objects.create(name="d2-a", ip_address=ip)


@pytest.fixture
def d2_b(db):
    from ipam.models import IPAddress

    from netbox_dhcp_kea_plugin.models import D2Daemon

    ip = IPAddress.objects.create(address="10.0.1.51/24")
    return D2Daemon.objects.create(name="d2-b", ip_address=ip)


@pytest.fixture
def ha_relationship(db):
    from netbox_dhcp_kea_plugin.models import DHCPHARelationship

    return DHCPHARelationship.objects.create(
        name="ha-1",
        mode="hot-standby",
    )


def _eff_pk(server):
    eff = server.effective_d2_daemon
    return eff.pk if eff is not None else None


def test_effective_returns_own_when_no_ha(dhcp_server, d2_a):
    dhcp_server.d2_daemon = d2_a
    dhcp_server.save()
    assert _eff_pk(dhcp_server) == d2_a.pk


def test_effective_returns_ha_d2_when_relationship_set(
    dhcp_server_factory, ha_relationship, d2_a, d2_b
):
    server = dhcp_server_factory(ha_relationship=ha_relationship, ha_role="primary")
    server.d2_daemon = d2_a
    server.save()
    ha_relationship.d2_daemon = d2_b
    ha_relationship.save()
    server.refresh_from_db()
    assert _eff_pk(server) == d2_b.pk


def test_effective_falls_back_to_own_when_ha_has_no_d2(
    dhcp_server_factory, ha_relationship, d2_a
):
    server = dhcp_server_factory(ha_relationship=ha_relationship, ha_role="primary")
    server.d2_daemon = d2_a
    server.save()
    assert ha_relationship.d2_daemon_id is None
    assert _eff_pk(server) == d2_a.pk


def test_effective_toggles_when_server_added_to_ha(
    dhcp_server, ha_relationship, d2_a, d2_b
):
    dhcp_server.d2_daemon = d2_a
    dhcp_server.save()
    assert _eff_pk(dhcp_server) == d2_a.pk

    ha_relationship.d2_daemon = d2_b
    ha_relationship.save()
    dhcp_server.ha_relationship = ha_relationship
    dhcp_server.ha_role = "primary"
    dhcp_server.save()
    dhcp_server.refresh_from_db()
    assert _eff_pk(dhcp_server) == d2_b.pk


def test_effective_reverts_when_server_removed_from_ha(
    dhcp_server, ha_relationship, d2_a, d2_b
):
    ha_relationship.d2_daemon = d2_b
    ha_relationship.save()
    dhcp_server.d2_daemon = d2_a
    dhcp_server.ha_relationship = ha_relationship
    dhcp_server.ha_role = "primary"
    dhcp_server.save()
    assert _eff_pk(dhcp_server) == d2_b.pk

    dhcp_server.ha_relationship = None
    dhcp_server.ha_role = ""
    dhcp_server.save()
    assert _eff_pk(dhcp_server) == d2_a.pk


def test_dhcpserver_to_kea_dict_uses_ha_d2_block(
    dhcp_server_factory, ha_relationship, d2_a, d2_b
):
    server = dhcp_server_factory(ha_relationship=ha_relationship, ha_role="primary")
    server.d2_daemon = d2_a
    server.ddns_sender_ip = "192.0.2.10"
    server.ddns_sender_port = 5555
    server.save()
    ha_relationship.d2_daemon = d2_b
    ha_relationship.ddns_enable_updates = False
    ha_relationship.save()
    server.refresh_from_db()

    cfg = server.to_kea_dict()
    dhcp4 = cfg.get("Dhcp4", {})
    block = dhcp4.get("dhcp-ddns")
    assert block is not None
    # HA relationship wins for d2_daemon target + enable_updates flag
    assert block["server-ip"] == str(d2_b.ip_address.address.ip)
    assert block["server-port"] == d2_b.port
    assert block["enable-updates"] is False
    # Sender stays per-server — never overridden by HA
    assert block["sender-ip"] == "192.0.2.10"
    assert block["sender-port"] == 5555


def test_effective_ddns_policy_returns_ha_when_set(
    dhcp_server_factory, ha_relationship
):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    own = DDNSPolicy.objects.create(name="own", ddns_qualifying_suffix="own.example.com")
    ha_pol = DDNSPolicy.objects.create(name="ha", ddns_qualifying_suffix="ha.example.com")
    server = dhcp_server_factory(ha_relationship=ha_relationship, ha_role="primary")
    server.ddns_policy = own
    server.save()
    ha_relationship.ddns_policy = ha_pol
    ha_relationship.save()
    server.refresh_from_db()
    assert server.effective_ddns_policy.pk == ha_pol.pk


def test_effective_ddns_policy_falls_back_to_own(dhcp_server_factory, ha_relationship):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    own = DDNSPolicy.objects.create(name="own2", ddns_qualifying_suffix="own.example.com")
    server = dhcp_server_factory(ha_relationship=ha_relationship, ha_role="primary")
    server.ddns_policy = own
    server.save()
    assert ha_relationship.ddns_policy_id is None
    assert server.effective_ddns_policy.pk == own.pk


def test_dhcpserver_to_kea_dict_uses_ha_ddns_policy(
    dhcp_server_factory, ha_relationship
):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    own = DDNSPolicy.objects.create(name="srv", ddns_qualifying_suffix="srv.example.com")
    ha_pol = DDNSPolicy.objects.create(name="hap", ddns_qualifying_suffix="ha.example.com")
    server = dhcp_server_factory(ha_relationship=ha_relationship, ha_role="primary")
    server.ddns_policy = own
    server.save()
    ha_relationship.ddns_policy = ha_pol
    ha_relationship.save()
    server.refresh_from_db()

    dhcp4 = server.to_kea_dict().get("Dhcp4", {})
    assert dhcp4.get("ddns-qualifying-suffix") == "ha.example.com"
