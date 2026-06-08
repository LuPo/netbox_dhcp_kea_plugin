"""GraphQL smoke + traversal tests for the plugin schema.

Verifies the plugin's query roots are registered in NetBox's merged schema and
that a query traverses from the plugin Subnet type into native NetBox objects
(prefix → role, server → ip_address) and reverse relations (subnet_pools).
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


pytestmark = pytest.mark.django_db


@pytest.fixture
def gql_client(db):
    user = get_user_model().objects.create_superuser(
        username="gql-admin", email="gql@example.com", password="x"
    )
    client = Client()
    client.force_login(user)
    return client


def _gql(client, query):
    resp = client.post(
        "/graphql/",
        data=json.dumps({"query": query}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    payload = resp.json()
    assert "errors" not in payload, payload.get("errors")
    return payload["data"]


def test_plugin_query_roots_registered(gql_client):
    data = _gql(gql_client, "{ __schema { queryType { fields { name } } } }")
    names = {f["name"] for f in data["__schema"]["queryType"]["fields"]}
    assert {
        "netbox_dhcp_kea_dhcp_server_list",
        "netbox_dhcp_kea_subnet_list",
        "netbox_dhcp_kea_subnet_pool_list",
        "netbox_dhcp_kea_client_class_list",
    } <= names


def test_subnet_traverses_to_native_prefix_and_server(
    gql_client, subnet_factory, dhcp_server_factory, prefix_factory
):
    from ipam.models import Role

    role = Role.objects.create(name="End Users", slug="end-users")
    prefix = prefix_factory(network="10.77.0.0/24")
    prefix.role = role
    prefix.save()
    server = dhcp_server_factory(ip_suffix=77)
    subnet_factory(server=server, prefix=prefix)

    data = _gql(
        gql_client,
        """
        query {
          netbox_dhcp_kea_subnet_list {
            prefix { prefix role { name } }
            server { name ip_address { address } }
            subnet_pools { id }
          }
        }
        """,
    )
    subnets = data["netbox_dhcp_kea_subnet_list"]
    target = next(s for s in subnets if s["server"]["name"] == server.name)
    assert target["prefix"]["prefix"].startswith("10.77.0.0")
    assert target["prefix"]["role"]["name"] == "End Users"
    assert target["server"]["ip_address"]["address"].startswith("192.168.1.77")
    assert target["subnet_pools"] == []


def test_subnet_available_out_of_pool_count(
    gql_client, subnet_factory, dhcp_server_factory, prefix_factory
):
    from ipam.models import IPRange
    from netaddr import IPNetwork

    prefix = prefix_factory(network="10.78.0.0/24")
    server = dhcp_server_factory(ip_suffix=78)
    subnet_factory(server=server, prefix=prefix)
    # Dynamic pool .10-.50 (41 addrs); /24 usable = 254 → out-of-pool = 213.
    IPRange.objects.create(
        start_address=IPNetwork("10.78.0.10/24"),
        end_address=IPNetwork("10.78.0.50/24"),
    )

    data = _gql(
        gql_client,
        """
        query {
          netbox_dhcp_kea_subnet_list {
            prefix { prefix }
            available_out_of_pool_count
          }
        }
        """,
    )
    target = next(
        s for s in data["netbox_dhcp_kea_subnet_list"]
        if s["prefix"]["prefix"].startswith("10.78.0.0")
    )
    assert target["available_out_of_pool_count"] == 213


def test_subnet_pools_field_configured_flag(
    gql_client, subnet_factory, dhcp_server_factory, prefix_factory
):
    from ipam.models import IPRange
    from netaddr import IPNetwork

    from netbox_dhcp_kea_plugin.models import SubnetPool

    prefix = prefix_factory(network="10.79.0.0/24")
    server = dhcp_server_factory(ip_suffix=79)
    subnet = subnet_factory(server=server, prefix=prefix)
    r_cfg = IPRange.objects.create(
        start_address=IPNetwork("10.79.0.10/24"), end_address=IPNetwork("10.79.0.50/24")
    )
    IPRange.objects.create(
        start_address=IPNetwork("10.79.0.100/24"), end_address=IPNetwork("10.79.0.150/24")
    )
    SubnetPool.objects.create(subnet=subnet, ip_range=r_cfg)  # only r_cfg is configured

    data = _gql(
        gql_client,
        """
        query {
          netbox_dhcp_kea_subnet_list {
            prefix { prefix }
            pools {
              pool_range
              configured
              ip_range { start_address end_address }
              config { id }
            }
          }
        }
        """,
    )
    target = next(
        s for s in data["netbox_dhcp_kea_subnet_list"]
        if s["prefix"]["prefix"].startswith("10.79.0.0")
    )
    pools = {p["pool_range"]: p for p in target["pools"]}

    configured = pools["10.79.0.10 - 10.79.0.50"]
    assert configured["configured"] is True
    assert configured["ip_range"]["start_address"] == "10.79.0.10/24"
    assert configured["config"]["id"] is not None

    bare = pools["10.79.0.100 - 10.79.0.150"]
    assert bare["configured"] is False
    assert bare["config"] is None
    assert bare["ip_range"]["end_address"] == "10.79.0.150/24"
