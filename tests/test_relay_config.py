"""Relay-config surface — shared Subnet.get_relay_config() and the
prefix-lookup API view (regression guard for the token-auth AssertionError).
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client(db):
    user = get_user_model().objects.create_superuser(
        username="relay-admin", email="relay@example.com", password="x"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_get_relay_config_standalone(subnet_factory, dhcp_server_factory):
    server = dhcp_server_factory(ip_suffix=20)
    subnet = subnet_factory(server=server)

    cfg = subnet.get_relay_config()
    assert cfg["server"]["name"] == server.name
    assert cfg["relay_targets"] == ["192.168.1.20"]


def test_get_relay_config_ha_returns_all_peers(subnet_factory, dhcp_server_factory):
    from netbox_dhcp_kea_plugin.models import DHCPHARelationship

    ha = DHCPHARelationship.objects.create(name="relay-ha", mode="hot-standby")
    primary = dhcp_server_factory(
        ip_suffix=30, ha_relationship=ha, ha_role="primary", ha_address="192.168.1.30"
    )
    dhcp_server_factory(
        ip_suffix=31, ha_relationship=ha, ha_role="secondary", ha_address="192.168.1.31"
    )
    subnet = subnet_factory(server=primary)

    cfg = subnet.get_relay_config()
    assert sorted(cfg["relay_targets"]) == ["192.168.1.30", "192.168.1.31"]


def test_prefix_relay_config_view_authenticated(api_client, subnet_factory, dhcp_server_factory, prefix_factory):
    """Regression: the view used to raise AssertionError under token auth
    because it set no .queryset. It must now resolve and return the config."""
    server = dhcp_server_factory(ip_suffix=40)
    prefix = prefix_factory(network="10.55.0.0/24")
    subnet_factory(server=server, prefix=prefix)

    url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:relay-config")
    resp = api_client.get(url, {"prefix": "10.55.0.0/24"})

    assert resp.status_code == 200, resp.data
    assert resp.data["prefix"] == "10.55.0.0/24"
    assert resp.data["dhcp_config"]["relay_targets"] == ["192.168.1.40"]


def test_prefix_relay_config_view_missing_prefix_param(api_client):
    url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:relay-config")
    resp = api_client.get(url)
    assert resp.status_code == 400
