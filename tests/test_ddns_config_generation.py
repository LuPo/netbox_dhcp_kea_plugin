"""Kea config emission for DDNS — server, subnet, and pool layers.

Verifies that DDNSPolicy.to_kea_overrides() output is spread verbatim into the
correct JSON level and that *no* Python-side merging happens between layers
(Kea handles inheritance at packet-processing time).
"""

import pytest


pytestmark = pytest.mark.django_db


@pytest.fixture
def policy_server(db):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    return DDNSPolicy.objects.create(
        name="server-policy",
        ddns_send_updates=True,
        ddns_qualifying_suffix="srv.example.com",
    )


@pytest.fixture
def policy_subnet(db):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    return DDNSPolicy.objects.create(
        name="subnet-policy",
        ddns_qualifying_suffix="sub.example.com",
        ddns_ttl=600,
    )


@pytest.fixture
def policy_pool(db):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    return DDNSPolicy.objects.create(
        name="pool-policy",
        ddns_generated_prefix="myhost",
        hostname_char_set="[^A-Za-z0-9.-]",
    )


@pytest.fixture
def ddns_pool(db, subnet_factory, prefix_factory):
    from ipam.models import IPRange
    from netaddr import IPNetwork

    from netbox_dhcp_kea_plugin.models import SubnetPool

    subnet = subnet_factory(prefix=prefix_factory("10.77.0.0/24"))
    ip_range = IPRange.objects.create(
        start_address=IPNetwork("10.77.0.10/24"),
        end_address=IPNetwork("10.77.0.50/24"),
    )
    return SubnetPool.objects.create(subnet=subnet, ip_range=ip_range)


def test_server_policy_emits_at_dhcp4_top_level(dhcp_server, policy_server):
    dhcp_server.ddns_policy = policy_server
    dhcp_server.save()

    dhcp4 = dhcp_server.to_kea_dict()["Dhcp4"]
    assert dhcp4["ddns-send-updates"] is True
    assert dhcp4["ddns-qualifying-suffix"] == "srv.example.com"


def test_subnet_policy_emits_inside_subnet_dict(subnet_factory, policy_subnet):
    subnet = subnet_factory()
    subnet.ddns_policy = policy_subnet
    subnet.save()

    server = subnet.server
    dhcp4 = server.to_kea_dict()["Dhcp4"]
    subnets = dhcp4.get("subnet4", [])
    assert subnets, "expected at least one subnet emitted"
    target = next((s for s in subnets if s.get("id") == subnet.id or s.get("subnet")), subnets[0])
    assert target.get("ddns-qualifying-suffix") == "sub.example.com"
    assert target.get("ddns-ttl") == 600


def test_subnet_policy_does_not_leak_into_server_top_level(
    subnet_factory, policy_subnet
):
    subnet = subnet_factory()
    subnet.ddns_policy = policy_subnet
    subnet.save()

    dhcp4 = subnet.server.to_kea_dict()["Dhcp4"]
    # Subnet-level override must not appear at the top level.
    assert dhcp4.get("ddns-qualifying-suffix") != "sub.example.com"


def test_no_python_side_merging_between_server_and_subnet(
    subnet_factory, policy_server, policy_subnet
):
    subnet = subnet_factory()
    server = subnet.server
    server.ddns_policy = policy_server
    server.save()
    subnet.ddns_policy = policy_subnet
    subnet.save()

    dhcp4 = server.to_kea_dict()["Dhcp4"]
    # Top level keeps server policy verbatim
    assert dhcp4["ddns-qualifying-suffix"] == "srv.example.com"
    assert dhcp4["ddns-send-updates"] is True

    target = dhcp4["subnet4"][0]
    # Subnet level keeps its own policy verbatim, NOT a merge of server+subnet.
    assert target["ddns-qualifying-suffix"] == "sub.example.com"
    assert "ddns-send-updates" not in target


def test_pool_policy_emits_inside_pool_dict(ddns_pool, policy_pool):
    ddns_pool.ddns_policy = policy_pool
    ddns_pool.save()

    pool = ddns_pool.to_kea_dict()
    assert pool["ddns-generated-prefix"] == "myhost"
    assert pool["hostname-char-set"] == "[^A-Za-z0-9.-]"


def test_pool_policy_does_not_leak_into_subnet(ddns_pool, policy_pool):
    ddns_pool.ddns_policy = policy_pool
    ddns_pool.save()

    subnet = ddns_pool.subnet.to_kea_dict()
    assert "ddns-generated-prefix" not in subnet
    pools = subnet["pools"]
    assert any(p.get("ddns-generated-prefix") == "myhost" for p in pools)


def test_client_class_never_carries_ddns_keys(dhcp_server, client_class):
    # KEA's client-class grammar has no ddns-* keys and refuses the whole
    # configuration on one, so the model offers no way to attach a policy.
    from netbox_dhcp_kea_plugin.models import ClientClass

    assert "ddns_policy" not in {f.name for f in ClientClass._meta.get_fields()}

    client_class.servers.add(dhcp_server)
    dhcp4 = dhcp_server.to_kea_dict()["Dhcp4"]
    target = next(c for c in dhcp4["client-classes"] if c["name"] == client_class.name)
    assert not [key for key in target if key.startswith("ddns-") or key.startswith("hostname-char")]


def test_no_ddns_keys_when_no_policy_attached(dhcp_server):
    dhcp4 = dhcp_server.to_kea_dict()["Dhcp4"]
    for key in dhcp4:
        assert not key.startswith("ddns-"), f"unexpected DDNS key {key} at top level"


def test_dhcp_ddns_block_absent_without_connection(dhcp_server):
    dhcp4 = dhcp_server.to_kea_dict()["Dhcp4"]
    assert "dhcp-ddns" not in dhcp4
