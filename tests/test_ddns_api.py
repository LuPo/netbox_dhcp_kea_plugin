"""DDNS API surface — CRUD, perm-gated TSIG secret, per-daemon kea-config."""

import base64

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from netbox.plugins.utils import get_plugin_config
from rest_framework.test import APIClient


pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"),
        reason="enable_ddns plugin flag is off — DDNS API routes not registered",
    ),
]


def _grant(user, *actions):
    """Attach an ObjectPermission for TSIGKey to ``user`` with the given actions."""
    from core.models import ObjectType
    from users.models import ObjectPermission

    from netbox_dhcp_kea_plugin.models import TSIGKey

    op = ObjectPermission.objects.create(name=f"perm-{user.pk}-{'-'.join(actions)}", actions=list(actions))
    op.users.add(user)
    op.object_types.add(ObjectType.objects.get_for_model(TSIGKey))
    return op


@pytest.fixture
def admin_user(db):
    return get_user_model().objects.create_superuser(
        username="admin", email="admin@example.com", password="x"
    )


@pytest.fixture
def viewer_user(db):
    user = get_user_model().objects.create_user(username="viewer", password="x")
    _grant(user, "view")
    return user


@pytest.fixture
def secret_viewer_user(db):
    user = get_user_model().objects.create_user(username="secretviewer", password="x")
    _grant(user, "view", "view_secret")
    return user


@pytest.fixture
def api_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def tsig_key(db):
    from netbox_dhcp_kea_plugin.models import TSIGKey

    return TSIGKey.objects.create(
        name="api-test.",
        algorithm="HMAC-SHA256",
        secret_backend="plaintext",
        secret_plaintext=base64.b64encode(b"api-secret").decode(),
    )


@pytest.fixture
def d2_daemon(db):
    from ipam.models import IPAddress

    from netbox_dhcp_kea_plugin.models import D2Daemon

    ip = IPAddress.objects.create(address="10.0.2.50/24")
    return D2Daemon.objects.create(name="d2-api", ip_address=ip)


def test_tsig_key_serializer_hides_secret_without_perm(tsig_key, viewer_user):
    client = APIClient()
    client.force_authenticate(user=viewer_user)
    url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:tsigkey-detail", args=[tsig_key.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    assert "secret_plaintext" not in resp.data


def test_tsig_key_serializer_shows_secret_with_perm(tsig_key, secret_viewer_user):
    client = APIClient()
    client.force_authenticate(user=secret_viewer_user)
    url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:tsigkey-detail", args=[tsig_key.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.data.get("secret_plaintext") == tsig_key.secret_plaintext


def test_d2daemon_kea_config_endpoint(api_client, d2_daemon):
    url = reverse(
        "plugins-api:netbox_dhcp_kea_plugin-api:d2daemon-kea-config",
        args=[d2_daemon.pk],
    )
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert "DhcpDdns" in resp.data
    assert resp.data["DhcpDdns"]["port"] == d2_daemon.port


def test_ddns_policy_create(api_client):
    url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:ddnspolicy-list")
    resp = api_client.post(
        url,
        {
            "name": "p1",
            "description": "",
            "ddns_send_updates": True,
            "ddns_qualifying_suffix": "lab.example.com",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["ddns_qualifying_suffix"] == "lab.example.com"


