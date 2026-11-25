"""The HA basic-auth password: stored in NetBox and gated, or an OpenBao reference.

Every peer entry of the HA hook carries the relationship's password, so the
DHCP server's whole Dhcp4 config is as sensitive as a TSIG secret when NetBox
holds it — and a template to substitute when it does not.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

PASSWORD = "s3cret-ha-pass"


def _grant(user, model, *actions):
    from core.models import ObjectType
    from users.models import ObjectPermission

    permission = ObjectPermission.objects.create(
        name=f"perm-{user.pk}-{model.__name__}-{'-'.join(actions)}", actions=list(actions)
    )
    permission.users.add(user)
    permission.object_types.add(ObjectType.objects.get_for_model(model))


@pytest.fixture
def pair(dhcp_server_factory):
    """A hot-standby pair whose relationship holds a plaintext password."""
    from netbox_dhcp_kea_plugin.models import DHCPHARelationship

    ha = DHCPHARelationship.objects.create(
        name="auth-pair", mode="hot-standby", ha_basic_auth_user="kea", ha_basic_auth_password=PASSWORD
    )
    primary = dhcp_server_factory(
        name="auth-1", ip_suffix=110, ha_relationship=ha, ha_role="primary", ha_address="10.60.0.1"
    )
    dhcp_server_factory(name="auth-2", ip_suffix=111, ha_relationship=ha, ha_role="standby", ha_address="10.60.0.2")
    return ha, primary


def _use_openbao(ha, ref="dhcp/site-a/ha-auth#password"):
    ha.ha_basic_auth_password = ""
    ha.ha_basic_auth_password_backend = "vault"
    ha.ha_basic_auth_password_ref = ref
    ha.save()


def _peer_passwords(server, **kwargs):
    hooks = server.to_kea_dict(**kwargs)["Dhcp4"]["hooks-libraries"]
    (ha_hook,) = [hook for hook in hooks if "high-availability" in hook.get("parameters", {})]
    return {peer.get("basic-auth-password") for peer in ha_hook["parameters"]["high-availability"][0]["peers"]}


class TestRendering:
    def test_a_stored_password_is_rendered_and_gated(self, pair):
        ha, primary = pair

        assert _peer_passwords(primary) == {PASSWORD}
        assert primary.contains_secrets() is True
        assert primary.requires_secret_substitution() is False

    def test_it_is_redacted_on_request(self, pair):
        ha, primary = pair

        assert _peer_passwords(primary, redact_secrets=True) == {ha.REDACTED_SECRET}

    def test_an_openbao_password_is_a_reference(self, pair):
        ha, primary = pair
        _use_openbao(ha)

        assert _peer_passwords(primary) == {"${BAO:dhcp/site-a/ha-auth#password}"}
        # A reference is not a secret, so redaction leaves it for the deployment.
        assert _peer_passwords(primary, redact_secrets=True) == {"${BAO:dhcp/site-a/ha-auth#password}"}
        assert primary.contains_secrets() is False
        assert primary.requires_secret_substitution() is True


class TestValidation:
    def test_openbao_needs_a_reference_when_a_user_is_set(self, pair):
        ha, _primary = pair
        ha.ha_basic_auth_password = ""
        ha.ha_basic_auth_password_backend = "vault"

        with pytest.raises(ValidationError) as exc:
            ha.full_clean()

        assert "ha_basic_auth_password_ref" in exc.value.message_dict

    def test_a_malformed_reference_is_refused(self, pair):
        ha, _primary = pair
        ha.ha_basic_auth_password = ""
        ha.ha_basic_auth_password_backend = "vault"
        ha.ha_basic_auth_password_ref = "kv/dhcp/site-a/ha-auth#password"

        with pytest.raises(ValidationError) as exc:
            ha.full_clean()

        assert "ha_basic_auth_password_ref" in exc.value.message_dict

    def test_a_stored_password_left_behind_is_refused(self, pair):
        ha, _primary = pair
        ha.ha_basic_auth_password_backend = "vault"
        ha.ha_basic_auth_password_ref = "dhcp/site-a/ha-auth#password"

        with pytest.raises(ValidationError) as exc:
            ha.full_clean()

        assert "ha_basic_auth_password" in exc.value.message_dict

    def test_a_reference_without_a_user_is_refused(self, pair):
        ha, _primary = pair
        _use_openbao(ha)
        ha.ha_basic_auth_user = ""

        with pytest.raises(ValidationError) as exc:
            ha.full_clean()

        assert "ha_basic_auth_user" in exc.value.message_dict

    def test_a_valid_openbao_pair_passes(self, pair):
        ha, _primary = pair
        _use_openbao(ha)

        ha.full_clean()


class TestPermission:
    @pytest.fixture
    def viewer(self, db):
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship, DHCPServer

        user = get_user_model().objects.create_user(username="ha-viewer", password="x")
        _grant(user, DHCPServer, "view")
        _grant(user, DHCPHARelationship, "view")
        return user

    @pytest.fixture
    def secret_viewer(self, viewer):
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        _grant(viewer, DHCPHARelationship, "view", "view_secret")
        return viewer

    @staticmethod
    def _api(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_the_api_refuses_the_config_without_the_permission(self, viewer, pair):
        _ha, primary = pair
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:dhcpserver-kea-config", args=[primary.pk])

        resp = self._api(viewer).get(url)

        assert resp.status_code == 403
        assert "view_secret_dhcpharelationship" in str(resp.data)

    def test_the_api_renders_it_with_the_permission(self, secret_viewer, pair):
        _ha, primary = pair
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:dhcpserver-kea-config", args=[primary.pk])

        resp = self._api(secret_viewer).get(url)

        assert resp.status_code == 200
        assert PASSWORD in str(resp.data)

    def test_an_openbao_password_needs_no_permission(self, viewer, pair):
        ha, primary = pair
        _use_openbao(ha)
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:dhcpserver-kea-config", args=[primary.pk])

        resp = self._api(viewer).get(url)

        assert resp.status_code == 200
        assert "${BAO:dhcp/site-a/ha-auth#password}" in str(resp.data)

    def test_the_relationship_hides_the_password_without_the_permission(self, viewer, pair):
        ha, _primary = pair
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:dhcpharelationship-detail", args=[ha.pk])

        assert "ha_basic_auth_password" not in self._api(viewer).get(url).data

    def test_the_relationship_shows_it_with_the_permission(self, secret_viewer, pair):
        ha, _primary = pair
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:dhcpharelationship-detail", args=[ha.pk])

        assert self._api(secret_viewer).get(url).data["ha_basic_auth_password"] == PASSWORD

    def test_the_config_tab_redacts_without_the_permission(self, client, viewer, pair):
        _ha, primary = pair
        client.force_login(viewer)

        resp = client.get(reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_kea_config", args=[primary.pk]))

        assert resp.status_code == 200
        assert resp.context["secrets_redacted"] is True
        assert PASSWORD not in resp.content.decode()

    def test_the_config_tab_shows_it_with_the_permission(self, client, secret_viewer, pair):
        _ha, primary = pair
        client.force_login(secret_viewer)

        resp = client.get(reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_kea_config", args=[primary.pk]))

        assert resp.context["secrets_redacted"] is False
        assert PASSWORD in resp.content.decode()

    def test_the_download_is_refused_without_the_permission(self, client, viewer, pair):
        _ha, primary = pair
        client.force_login(viewer)
        url = reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_kea_config", args=[primary.pk])

        assert client.get(url, {"export": "kea-config"}).status_code == 403


class TestForm:
    """The form shows the password or the reference, whichever the backend uses."""

    @staticmethod
    def _form(**data):
        from netbox_dhcp_kea_plugin.forms import DHCPHARelationshipForm

        base = {
            "name": "form-pair",
            "mode": "hot-standby",
            "heartbeat_delay": 10000,
            "max_response_delay": 60000,
            "max_ack_delay": 10000,
            "max_unacked_clients": 10,
            "max_rejected_lease_updates": 10,
            "http_listener_threads": 0,
            "http_client_threads": 0,
            "ha_basic_auth_user": "kea",
        }
        return DHCPHARelationshipForm(data={**base, **data})

    def test_plaintext_shows_only_the_password(self):
        form = self._form(ha_basic_auth_password_backend="plaintext")

        assert "ha_basic_auth_password" in form.fields
        assert "ha_basic_auth_password_ref" not in form.fields

    def test_openbao_shows_only_the_reference(self):
        form = self._form(ha_basic_auth_password_backend="vault")

        assert "ha_basic_auth_password_ref" in form.fields
        assert "ha_basic_auth_password" not in form.fields

    def test_switching_to_openbao_drops_the_stored_password(self, pair):
        from netbox_dhcp_kea_plugin.forms import DHCPHARelationshipForm

        ha, _primary = pair
        data = {
            "name": ha.name,
            "mode": ha.mode,
            "heartbeat_delay": ha.heartbeat_delay,
            "max_response_delay": ha.max_response_delay,
            "max_ack_delay": ha.max_ack_delay,
            "max_unacked_clients": ha.max_unacked_clients,
            "max_rejected_lease_updates": ha.max_rejected_lease_updates,
            "http_listener_threads": ha.http_listener_threads,
            "http_client_threads": ha.http_client_threads,
            "ha_basic_auth_user": ha.ha_basic_auth_user,
            "ha_basic_auth_password_backend": "vault",
            "ha_basic_auth_password_ref": "dhcp/site-a/ha-auth#password",
        }
        form = DHCPHARelationshipForm(data=data, instance=ha)

        assert form.is_valid(), form.errors
        form.save()
        ha.refresh_from_db()
        assert ha.ha_basic_auth_password == ""
        assert ha.ha_basic_auth_password_ref == "dhcp/site-a/ha-auth#password"
