"""
Tests for DHCPServer control socket configuration.

Covers:
- Model field defaults and creation
- Validation (clean) for control socket fields
- get_control_sockets() helper method
- to_kea_dict() integration with control sockets
- API serializer inclusion of control socket fields
- Form field presence and fieldset layout
- Import form fields
- Filter form and filterset fields
- Table columns
- Detail template rendering (HTTP and Unix socket display)

Run with:
    cd /path/to/netbox-dhcp-kea-plugin
    pytest tests/test_control_sockets.py -v
"""

import pytest
from django.core.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctrl_ip(db):
    """Create an IP address for control socket tests."""
    from ipam.models import IPAddress

    return IPAddress.objects.create(address="10.20.30.1/24")


@pytest.fixture
def ctrl_service_template(db):
    """Create a service template for control socket tests."""
    from ipam.models import ServiceTemplate

    template, _ = ServiceTemplate.objects.get_or_create(
        name="dhcp-ctrl-test",
        defaults={"protocol": "udp", "ports": [67, 68]},
    )
    return template


@pytest.fixture
def server_no_sockets(db, ctrl_ip, ctrl_service_template):
    """Create a DHCPServer with no control sockets enabled (defaults)."""
    from netbox_dhcp_kea_plugin.models import DHCPServer

    return DHCPServer.objects.create(
        name="ctrl-server-none",
        ip_address=ctrl_ip,
        service_template=ctrl_service_template,
        status="active",
    )


@pytest.fixture
def server_http_socket(db, ctrl_service_template):
    """Create a DHCPServer with HTTP control socket enabled."""
    from ipam.models import IPAddress

    from netbox_dhcp_kea_plugin.models import DHCPServer

    ip = IPAddress.objects.create(address="10.20.30.2/24")
    return DHCPServer.objects.create(
        name="ctrl-server-http",
        ip_address=ip,
        service_template=ctrl_service_template,
        status="active",
        ctrl_socket_http_enabled=True,
        ctrl_socket_http_address="127.0.0.1",
        ctrl_socket_http_port=8000,
    )


@pytest.fixture
def server_unix_socket(db, ctrl_service_template):
    """Create a DHCPServer with Unix control socket enabled."""
    from ipam.models import IPAddress

    from netbox_dhcp_kea_plugin.models import DHCPServer

    ip = IPAddress.objects.create(address="10.20.30.3/24")
    return DHCPServer.objects.create(
        name="ctrl-server-unix",
        ip_address=ip,
        service_template=ctrl_service_template,
        status="active",
        ctrl_socket_unix_enabled=True,
        ctrl_socket_unix_path="/var/run/kea/kea-dhcp4-socket",
    )


@pytest.fixture
def server_both_sockets(db, ctrl_service_template):
    """Create a DHCPServer with both control sockets enabled."""
    from ipam.models import IPAddress

    from netbox_dhcp_kea_plugin.models import DHCPServer

    ip = IPAddress.objects.create(address="10.20.30.4/24")
    return DHCPServer.objects.create(
        name="ctrl-server-both",
        ip_address=ip,
        service_template=ctrl_service_template,
        status="active",
        ctrl_socket_http_enabled=True,
        ctrl_socket_http_address="0.0.0.0",
        ctrl_socket_http_port=8080,
        ctrl_socket_unix_enabled=True,
        ctrl_socket_unix_path="/tmp/kea-ctrl.sock",
    )


@pytest.fixture
def ctrl_admin_user(db):
    """Create an admin user for API tests."""
    from users.models import User

    user, _ = User.objects.get_or_create(
        username="ctrl_socket_admin",
        defaults={
            "email": "ctrl@test.com",
            "is_superuser": True,
            "is_active": True,
        },
    )
    return user


@pytest.fixture
def ctrl_api_client(db, ctrl_admin_user):
    """Return a DRF API client authenticated as admin."""
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=ctrl_admin_user)
    return client


# ===========================================================================
# Model Field Defaults
# ===========================================================================


@pytest.mark.django_db
class TestControlSocketDefaults:
    """Tests for control socket field default values."""

    def test_http_socket_disabled_by_default(self, server_no_sockets):
        """Test that HTTP control socket is disabled by default."""
        assert server_no_sockets.ctrl_socket_http_enabled is False

    def test_http_socket_default_address(self, server_no_sockets):
        """Test that HTTP socket address defaults to 127.0.0.1."""
        assert server_no_sockets.ctrl_socket_http_address == "127.0.0.1"

    def test_http_socket_default_port(self, server_no_sockets):
        """Test that HTTP socket port defaults to 8000."""
        assert server_no_sockets.ctrl_socket_http_port == 8000

    def test_unix_socket_disabled_by_default(self, server_no_sockets):
        """Test that Unix control socket is disabled by default."""
        assert server_no_sockets.ctrl_socket_unix_enabled is False

    def test_unix_socket_default_path(self, server_no_sockets):
        """Test that Unix socket path has a sensible default."""
        assert server_no_sockets.ctrl_socket_unix_path == "/var/run/kea/kea-dhcp4-socket"

    def test_all_defaults_persist_after_save(self, server_no_sockets):
        """Test that defaults persist after fetching from DB."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = DHCPServer.objects.get(pk=server_no_sockets.pk)
        assert server.ctrl_socket_http_enabled is False
        assert server.ctrl_socket_http_address == "127.0.0.1"
        assert server.ctrl_socket_http_port == 8000
        assert server.ctrl_socket_unix_enabled is False
        assert server.ctrl_socket_unix_path == "/var/run/kea/kea-dhcp4-socket"


# ===========================================================================
# Model Creation with Control Sockets
# ===========================================================================


@pytest.mark.django_db
class TestControlSocketCreation:
    """Tests for creating DHCPServer with various control socket configurations."""

    def test_create_with_http_socket(self, server_http_socket):
        """Test creating a server with HTTP control socket."""
        assert server_http_socket.pk is not None
        assert server_http_socket.ctrl_socket_http_enabled is True
        assert server_http_socket.ctrl_socket_http_address == "127.0.0.1"
        assert server_http_socket.ctrl_socket_http_port == 8000

    def test_create_with_unix_socket(self, server_unix_socket):
        """Test creating a server with Unix control socket."""
        assert server_unix_socket.pk is not None
        assert server_unix_socket.ctrl_socket_unix_enabled is True
        assert server_unix_socket.ctrl_socket_unix_path == "/var/run/kea/kea-dhcp4-socket"

    def test_create_with_both_sockets(self, server_both_sockets):
        """Test creating a server with both control sockets."""
        assert server_both_sockets.pk is not None
        assert server_both_sockets.ctrl_socket_http_enabled is True
        assert server_both_sockets.ctrl_socket_http_address == "0.0.0.0"
        assert server_both_sockets.ctrl_socket_http_port == 8080
        assert server_both_sockets.ctrl_socket_unix_enabled is True
        assert server_both_sockets.ctrl_socket_unix_path == "/tmp/kea-ctrl.sock"

    def test_create_with_no_sockets(self, server_no_sockets):
        """Test creating a server with no control sockets."""
        assert server_no_sockets.pk is not None
        assert server_no_sockets.ctrl_socket_http_enabled is False
        assert server_no_sockets.ctrl_socket_unix_enabled is False

    def test_http_socket_custom_address(self, db, ctrl_service_template):
        """Test creating with a custom HTTP socket address."""
        from ipam.models import IPAddress

        from netbox_dhcp_kea_plugin.models import DHCPServer

        ip = IPAddress.objects.create(address="10.20.30.50/24")
        server = DHCPServer.objects.create(
            name="ctrl-custom-addr",
            ip_address=ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=True,
            ctrl_socket_http_address="192.168.1.100",
            ctrl_socket_http_port=9000,
        )
        assert server.ctrl_socket_http_address == "192.168.1.100"
        assert server.ctrl_socket_http_port == 9000

    def test_unix_socket_custom_path(self, db, ctrl_service_template):
        """Test creating with a custom Unix socket path."""
        from ipam.models import IPAddress

        from netbox_dhcp_kea_plugin.models import DHCPServer

        ip = IPAddress.objects.create(address="10.20.30.51/24")
        server = DHCPServer.objects.create(
            name="ctrl-custom-path",
            ip_address=ip,
            service_template=ctrl_service_template,
            ctrl_socket_unix_enabled=True,
            ctrl_socket_unix_path="/opt/kea/run/dhcp4.sock",
        )
        assert server.ctrl_socket_unix_path == "/opt/kea/run/dhcp4.sock"

    def test_update_enable_http_socket(self, server_no_sockets):
        """Test enabling HTTP socket on existing server."""
        server_no_sockets.ctrl_socket_http_enabled = True
        server_no_sockets.ctrl_socket_http_address = "10.0.0.1"
        server_no_sockets.ctrl_socket_http_port = 8888
        server_no_sockets.save()
        server_no_sockets.refresh_from_db()
        assert server_no_sockets.ctrl_socket_http_enabled is True
        assert server_no_sockets.ctrl_socket_http_address == "10.0.0.1"
        assert server_no_sockets.ctrl_socket_http_port == 8888

    def test_update_disable_http_socket(self, server_http_socket):
        """Test disabling HTTP socket on existing server."""
        server_http_socket.ctrl_socket_http_enabled = False
        server_http_socket.save()
        server_http_socket.refresh_from_db()
        assert server_http_socket.ctrl_socket_http_enabled is False

    def test_update_enable_unix_socket(self, server_no_sockets):
        """Test enabling Unix socket on existing server."""
        server_no_sockets.ctrl_socket_unix_enabled = True
        server_no_sockets.ctrl_socket_unix_path = "/run/kea/ctrl.sock"
        server_no_sockets.save()
        server_no_sockets.refresh_from_db()
        assert server_no_sockets.ctrl_socket_unix_enabled is True
        assert server_no_sockets.ctrl_socket_unix_path == "/run/kea/ctrl.sock"


# ===========================================================================
# Validation (clean)
# ===========================================================================


@pytest.mark.django_db
class TestControlSocketValidation:
    """Tests for control socket clean() validation."""

    def test_http_enabled_without_address_raises(self, db, ctrl_ip, ctrl_service_template):
        """Test that enabling HTTP socket without address raises ValidationError."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = DHCPServer(
            name="ctrl-val-http-no-addr",
            ip_address=ctrl_ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=True,
            ctrl_socket_http_address="",
            ctrl_socket_http_port=8000,
        )
        with pytest.raises(ValidationError) as exc_info:
            server.clean()
        assert "ctrl_socket_http_address" in exc_info.value.message_dict

    def test_http_enabled_without_port_raises(self, db, ctrl_ip, ctrl_service_template):
        """Test that enabling HTTP socket without port raises ValidationError."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = DHCPServer(
            name="ctrl-val-http-no-port",
            ip_address=ctrl_ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=True,
            ctrl_socket_http_address="127.0.0.1",
            ctrl_socket_http_port=None,
        )
        with pytest.raises(ValidationError) as exc_info:
            server.clean()
        assert "ctrl_socket_http_port" in exc_info.value.message_dict

    def test_unix_enabled_without_path_raises(self, db, ctrl_ip, ctrl_service_template):
        """Test that enabling Unix socket without path raises ValidationError."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = DHCPServer(
            name="ctrl-val-unix-no-path",
            ip_address=ctrl_ip,
            service_template=ctrl_service_template,
            ctrl_socket_unix_enabled=True,
            ctrl_socket_unix_path="",
        )
        with pytest.raises(ValidationError) as exc_info:
            server.clean()
        assert "ctrl_socket_unix_path" in exc_info.value.message_dict

    def test_http_disabled_allows_empty_address(self, db, ctrl_ip, ctrl_service_template):
        """Test that disabled HTTP socket allows empty address without error."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = DHCPServer(
            name="ctrl-val-http-disabled-ok",
            ip_address=ctrl_ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=False,
            ctrl_socket_http_address="",
            ctrl_socket_http_port=None,
        )
        # Should not raise
        server.clean()

    def test_unix_disabled_allows_empty_path(self, db, ctrl_ip, ctrl_service_template):
        """Test that disabled Unix socket allows empty path without error."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = DHCPServer(
            name="ctrl-val-unix-disabled-ok",
            ip_address=ctrl_ip,
            service_template=ctrl_service_template,
            ctrl_socket_unix_enabled=False,
            ctrl_socket_unix_path="",
        )
        # Should not raise
        server.clean()

    def test_both_enabled_with_valid_config_passes(self, db, ctrl_ip, ctrl_service_template):
        """Test that both sockets enabled with valid config passes validation."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = DHCPServer(
            name="ctrl-val-both-ok",
            ip_address=ctrl_ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=True,
            ctrl_socket_http_address="0.0.0.0",
            ctrl_socket_http_port=8000,
            ctrl_socket_unix_enabled=True,
            ctrl_socket_unix_path="/var/run/kea/kea-dhcp4-socket",
        )
        # Should not raise
        server.clean()

    def test_neither_enabled_passes(self, db, ctrl_ip, ctrl_service_template):
        """Test that neither socket enabled passes validation."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = DHCPServer(
            name="ctrl-val-none-ok",
            ip_address=ctrl_ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=False,
            ctrl_socket_unix_enabled=False,
        )
        # Should not raise
        server.clean()

    def test_http_enabled_port_zero_raises(self, db, ctrl_ip, ctrl_service_template):
        """Test that port 0 is treated as falsy and raises when HTTP is enabled."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = DHCPServer(
            name="ctrl-val-http-port-zero",
            ip_address=ctrl_ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=True,
            ctrl_socket_http_address="127.0.0.1",
            ctrl_socket_http_port=0,
        )
        with pytest.raises(ValidationError) as exc_info:
            server.clean()
        assert "ctrl_socket_http_port" in exc_info.value.message_dict


# ===========================================================================
# get_control_sockets() Method
# ===========================================================================


@pytest.mark.django_db
class TestGetControlSockets:
    """Tests for the get_control_sockets() helper method."""

    def test_no_sockets_returns_empty_list(self, server_no_sockets):
        """Test that no sockets returns an empty list."""
        result = server_no_sockets.get_control_sockets()
        assert result == []

    def test_http_only_returns_one_item(self, server_http_socket):
        """Test that HTTP-only returns a single-element list."""
        result = server_http_socket.get_control_sockets()
        assert len(result) == 1
        assert result[0]["socket-type"] == "http"

    def test_http_socket_structure(self, server_http_socket):
        """Test the structure of an HTTP control socket entry."""
        result = server_http_socket.get_control_sockets()
        socket = result[0]
        assert socket == {
            "socket-type": "http",
            "socket-address": "127.0.0.1",
            "socket-port": 8000,
        }

    def test_unix_only_returns_one_item(self, server_unix_socket):
        """Test that Unix-only returns a single-element list."""
        result = server_unix_socket.get_control_sockets()
        assert len(result) == 1
        assert result[0]["socket-type"] == "unix"

    def test_unix_socket_structure(self, server_unix_socket):
        """Test the structure of a Unix control socket entry."""
        result = server_unix_socket.get_control_sockets()
        socket = result[0]
        assert socket == {
            "socket-type": "unix",
            "socket-name": "/var/run/kea/kea-dhcp4-socket",
        }

    def test_both_sockets_returns_two_items(self, server_both_sockets):
        """Test that both sockets enabled returns a two-element list."""
        result = server_both_sockets.get_control_sockets()
        assert len(result) == 2

    def test_both_sockets_http_first(self, server_both_sockets):
        """Test that HTTP socket comes first in the list."""
        result = server_both_sockets.get_control_sockets()
        assert result[0]["socket-type"] == "http"
        assert result[1]["socket-type"] == "unix"

    def test_both_sockets_correct_values(self, server_both_sockets):
        """Test that both sockets have correct values."""
        result = server_both_sockets.get_control_sockets()
        assert result[0] == {
            "socket-type": "http",
            "socket-address": "0.0.0.0",
            "socket-port": 8080,
        }
        assert result[1] == {
            "socket-type": "unix",
            "socket-name": "/tmp/kea-ctrl.sock",
        }

    def test_http_socket_has_no_socket_name(self, server_http_socket):
        """Test that HTTP socket dict doesn't contain socket-name."""
        result = server_http_socket.get_control_sockets()
        assert "socket-name" not in result[0]

    def test_unix_socket_has_no_socket_address(self, server_unix_socket):
        """Test that Unix socket dict doesn't contain socket-address or socket-port."""
        result = server_unix_socket.get_control_sockets()
        assert "socket-address" not in result[0]
        assert "socket-port" not in result[0]

    def test_return_type_is_list(self, server_no_sockets):
        """Test that the return type is always a list."""
        result = server_no_sockets.get_control_sockets()
        assert isinstance(result, list)


# ===========================================================================
# to_kea_dict() Integration
# ===========================================================================


@pytest.mark.django_db
class TestControlSocketKeaDict:
    """Tests for control socket inclusion in to_kea_dict() output."""

    def test_no_sockets_no_key(self, server_no_sockets):
        """Test that no control-sockets key when neither socket is enabled."""
        config = server_no_sockets.to_kea_dict()
        dhcp4 = config["Dhcp4"]
        assert "control-sockets" not in dhcp4

    def test_http_socket_in_config(self, server_http_socket):
        """Test that HTTP control socket appears in KEA config."""
        config = server_http_socket.to_kea_dict()
        dhcp4 = config["Dhcp4"]
        assert "control-sockets" in dhcp4
        sockets = dhcp4["control-sockets"]
        assert len(sockets) == 1
        assert sockets[0]["socket-type"] == "http"
        assert sockets[0]["socket-address"] == "127.0.0.1"
        assert sockets[0]["socket-port"] == 8000

    def test_unix_socket_in_config(self, server_unix_socket):
        """Test that Unix control socket appears in KEA config."""
        config = server_unix_socket.to_kea_dict()
        dhcp4 = config["Dhcp4"]
        assert "control-sockets" in dhcp4
        sockets = dhcp4["control-sockets"]
        assert len(sockets) == 1
        assert sockets[0]["socket-type"] == "unix"
        assert sockets[0]["socket-name"] == "/var/run/kea/kea-dhcp4-socket"

    def test_both_sockets_in_config(self, server_both_sockets):
        """Test that both control sockets appear in KEA config."""
        config = server_both_sockets.to_kea_dict()
        dhcp4 = config["Dhcp4"]
        assert "control-sockets" in dhcp4
        sockets = dhcp4["control-sockets"]
        assert len(sockets) == 2
        types = [s["socket-type"] for s in sockets]
        assert "http" in types
        assert "unix" in types

    def test_control_sockets_coexist_with_interfaces(self, server_http_socket):
        """Test that control-sockets and interfaces-config coexist."""
        config = server_http_socket.to_kea_dict()
        dhcp4 = config["Dhcp4"]
        assert "interfaces-config" in dhcp4
        assert "control-sockets" in dhcp4

    def test_config_is_valid_json_structure(self, server_both_sockets):
        """Test that the full config is a valid JSON-serializable structure."""
        import json

        config = server_both_sockets.to_kea_dict()
        json_str = json.dumps(config, indent=2)
        parsed = json.loads(json_str)
        assert "Dhcp4" in parsed
        assert "control-sockets" in parsed["Dhcp4"]

    def test_control_sockets_position_in_config(self, server_http_socket):
        """Test that control-sockets appears at the Dhcp4 level."""
        config = server_http_socket.to_kea_dict()
        # control-sockets should be a direct child of Dhcp4
        assert "control-sockets" in config["Dhcp4"]
        # It should NOT be nested inside interfaces-config
        assert "control-sockets" not in config["Dhcp4"]["interfaces-config"]


# ===========================================================================
# API Serializer
# ===========================================================================


@pytest.mark.django_db
class TestControlSocketAPI:
    """Tests for control socket fields in the API."""

    def test_list_includes_control_socket_fields(self, ctrl_api_client, server_http_socket):
        """Test that list endpoint includes control socket fields."""
        response = ctrl_api_client.get("/api/plugins/netbox_dhcp_kea_plugin/dhcp-servers/")
        assert response.status_code == 200
        if response.data["count"] > 0:
            server_data = response.data["results"][0]
            assert "ctrl_socket_http_enabled" in server_data
            assert "ctrl_socket_http_address" in server_data
            assert "ctrl_socket_http_port" in server_data
            assert "ctrl_socket_unix_enabled" in server_data
            assert "ctrl_socket_unix_path" in server_data

    def test_detail_http_socket_values(self, ctrl_api_client, server_http_socket):
        """Test that detail endpoint returns correct HTTP socket values."""
        response = ctrl_api_client.get(f"/api/plugins/netbox_dhcp_kea_plugin/dhcp-servers/{server_http_socket.pk}/")
        assert response.status_code == 200
        assert response.data["ctrl_socket_http_enabled"] is True
        assert response.data["ctrl_socket_http_address"] == "127.0.0.1"
        assert response.data["ctrl_socket_http_port"] == 8000
        assert response.data["ctrl_socket_unix_enabled"] is False

    def test_detail_unix_socket_values(self, ctrl_api_client, server_unix_socket):
        """Test that detail endpoint returns correct Unix socket values."""
        response = ctrl_api_client.get(f"/api/plugins/netbox_dhcp_kea_plugin/dhcp-servers/{server_unix_socket.pk}/")
        assert response.status_code == 200
        assert response.data["ctrl_socket_unix_enabled"] is True
        assert response.data["ctrl_socket_unix_path"] == "/var/run/kea/kea-dhcp4-socket"
        assert response.data["ctrl_socket_http_enabled"] is False

    def test_detail_both_sockets_values(self, ctrl_api_client, server_both_sockets):
        """Test that detail endpoint returns correct values for both sockets."""
        response = ctrl_api_client.get(f"/api/plugins/netbox_dhcp_kea_plugin/dhcp-servers/{server_both_sockets.pk}/")
        assert response.status_code == 200
        assert response.data["ctrl_socket_http_enabled"] is True
        assert response.data["ctrl_socket_http_address"] == "0.0.0.0"
        assert response.data["ctrl_socket_http_port"] == 8080
        assert response.data["ctrl_socket_unix_enabled"] is True
        assert response.data["ctrl_socket_unix_path"] == "/tmp/kea-ctrl.sock"

    def test_detail_no_sockets_values(self, ctrl_api_client, server_no_sockets):
        """Test that detail endpoint returns defaults when no sockets configured."""
        response = ctrl_api_client.get(f"/api/plugins/netbox_dhcp_kea_plugin/dhcp-servers/{server_no_sockets.pk}/")
        assert response.status_code == 200
        assert response.data["ctrl_socket_http_enabled"] is False
        assert response.data["ctrl_socket_unix_enabled"] is False

    def test_kea_config_endpoint_includes_control_sockets(self, ctrl_api_client, server_http_socket):
        """Test that KEA config API endpoint includes control-sockets."""
        response = ctrl_api_client.get(
            f"/api/plugins/netbox_dhcp_kea_plugin/dhcp-servers/{server_http_socket.pk}/kea-config/"
        )
        assert response.status_code == 200
        dhcp4 = response.data.get("Dhcp4", {})
        assert "control-sockets" in dhcp4

    def test_kea_config_endpoint_no_sockets(self, ctrl_api_client, server_no_sockets):
        """Test that KEA config API endpoint omits control-sockets when disabled."""
        response = ctrl_api_client.get(
            f"/api/plugins/netbox_dhcp_kea_plugin/dhcp-servers/{server_no_sockets.pk}/kea-config/"
        )
        assert response.status_code == 200
        dhcp4 = response.data.get("Dhcp4", {})
        assert "control-sockets" not in dhcp4

    def test_serializer_fields_present(self):
        """Test that control socket fields are declared in the serializer Meta.fields."""
        from netbox_dhcp_kea_plugin.api.serializers import DHCPServerSerializer

        fields = DHCPServerSerializer.Meta.fields
        assert "ctrl_socket_http_enabled" in fields
        assert "ctrl_socket_http_address" in fields
        assert "ctrl_socket_http_port" in fields
        assert "ctrl_socket_unix_enabled" in fields
        assert "ctrl_socket_unix_path" in fields


# ===========================================================================
# Forms
# ===========================================================================


@pytest.mark.django_db
class TestControlSocketForms:
    """Tests for control socket fields in forms."""

    def test_dhcp_server_form_has_control_socket_fields(self):
        """Test that DHCPServerForm includes control socket fields."""
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        form = DHCPServerForm()
        assert "ctrl_socket_http_enabled" in form.fields
        assert "ctrl_socket_http_address" in form.fields
        assert "ctrl_socket_http_port" in form.fields
        assert "ctrl_socket_unix_enabled" in form.fields
        assert "ctrl_socket_unix_path" in form.fields

    def test_dhcp_server_form_meta_fields(self):
        """Test that control socket fields are in Meta.fields."""
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        fields = DHCPServerForm.Meta.fields
        assert "ctrl_socket_http_enabled" in fields
        assert "ctrl_socket_http_address" in fields
        assert "ctrl_socket_http_port" in fields
        assert "ctrl_socket_unix_enabled" in fields
        assert "ctrl_socket_unix_path" in fields

    def test_dhcp_server_form_has_control_sockets_fieldset(self):
        """Test that DHCPServerForm has a 'Control Sockets' fieldset."""
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        fieldsets = DHCPServerForm.fieldsets
        fieldset_names = [fs.name for fs in fieldsets]
        assert "Control Sockets" in fieldset_names

    def test_control_sockets_fieldset_contains_correct_fields(self):
        """Test that the Control Sockets fieldset contains all 5 fields.

        Some fields are grouped via InlineFields, so we collect field names
        from both top-level strings and InlineFields.fields tuples.
        """
        from utilities.forms.rendering import InlineFields

        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        fieldsets = DHCPServerForm.fieldsets
        ctrl_fieldset = None
        for fs in fieldsets:
            if fs.name == "Control Sockets":
                ctrl_fieldset = fs
                break
        assert ctrl_fieldset is not None

        # Collect all field names, including those nested inside InlineFields
        field_names = []
        for item in ctrl_fieldset.items:
            if isinstance(item, str):
                field_names.append(item)
            elif isinstance(item, InlineFields):
                field_names.extend(item.fields)

        assert "ctrl_socket_http_enabled" in field_names
        assert "ctrl_socket_http_address" in field_names
        assert "ctrl_socket_http_port" in field_names
        assert "ctrl_socket_unix_enabled" in field_names
        assert "ctrl_socket_unix_path" in field_names

    def test_control_sockets_fieldset_order(self):
        """Test that Control Sockets fieldset comes after Hook Libraries and before Stork/HA."""
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        fieldsets = DHCPServerForm.fieldsets
        fieldset_names = [fs.name for fs in fieldsets]
        hook_idx = fieldset_names.index("Hook Libraries")
        ctrl_idx = fieldset_names.index("Control Sockets")
        ha_idx = fieldset_names.index("High Availability")
        assert hook_idx < ctrl_idx < ha_idx

    def test_import_form_has_control_socket_fields(self):
        """Test that DHCPServerImportForm includes control socket fields."""
        from netbox_dhcp_kea_plugin.forms import DHCPServerImportForm

        fields = DHCPServerImportForm.Meta.fields
        assert "ctrl_socket_http_enabled" in fields
        assert "ctrl_socket_http_address" in fields
        assert "ctrl_socket_http_port" in fields
        assert "ctrl_socket_unix_enabled" in fields
        assert "ctrl_socket_unix_path" in fields

    def test_filter_form_has_control_socket_filters(self):
        """Test that DHCPServerFilterForm includes control socket filter fields."""
        from netbox_dhcp_kea_plugin.forms import DHCPServerFilterForm

        form = DHCPServerFilterForm()
        assert "ctrl_socket_http_enabled" in form.fields
        assert "ctrl_socket_unix_enabled" in form.fields


# ===========================================================================
# FilterSet
# ===========================================================================


@pytest.mark.django_db
class TestControlSocketFilterSet:
    """Tests for control socket fields in the filterset."""

    def test_filterset_meta_includes_control_socket_fields(self):
        """Test that DHCPServerFilterSet.Meta.fields includes control socket booleans."""
        from netbox_dhcp_kea_plugin.filtersets import DHCPServerFilterSet

        fields = DHCPServerFilterSet.Meta.fields
        assert "ctrl_socket_http_enabled" in fields
        assert "ctrl_socket_unix_enabled" in fields

    def test_filter_by_http_enabled(self, server_http_socket, server_no_sockets):
        """Test filtering servers by HTTP control socket enabled."""
        from netbox_dhcp_kea_plugin.filtersets import DHCPServerFilterSet
        from netbox_dhcp_kea_plugin.models import DHCPServer

        qs = DHCPServer.objects.all()
        fs = DHCPServerFilterSet({"ctrl_socket_http_enabled": True}, queryset=qs)
        results = fs.qs
        assert server_http_socket in results
        assert server_no_sockets not in results

    def test_filter_by_http_disabled(self, server_http_socket, server_no_sockets):
        """Test filtering servers by HTTP control socket disabled."""
        from netbox_dhcp_kea_plugin.filtersets import DHCPServerFilterSet
        from netbox_dhcp_kea_plugin.models import DHCPServer

        qs = DHCPServer.objects.all()
        fs = DHCPServerFilterSet({"ctrl_socket_http_enabled": False}, queryset=qs)
        results = fs.qs
        assert server_no_sockets in results
        assert server_http_socket not in results

    def test_filter_by_unix_enabled(self, server_unix_socket, server_no_sockets):
        """Test filtering servers by Unix control socket enabled."""
        from netbox_dhcp_kea_plugin.filtersets import DHCPServerFilterSet
        from netbox_dhcp_kea_plugin.models import DHCPServer

        qs = DHCPServer.objects.all()
        fs = DHCPServerFilterSet({"ctrl_socket_unix_enabled": True}, queryset=qs)
        results = fs.qs
        assert server_unix_socket in results
        assert server_no_sockets not in results

    def test_filter_by_both_enabled(self, server_both_sockets, server_http_socket, server_no_sockets):
        """Test filtering servers with both control sockets enabled."""
        from netbox_dhcp_kea_plugin.filtersets import DHCPServerFilterSet
        from netbox_dhcp_kea_plugin.models import DHCPServer

        qs = DHCPServer.objects.all()
        fs = DHCPServerFilterSet(
            {"ctrl_socket_http_enabled": True, "ctrl_socket_unix_enabled": True},
            queryset=qs,
        )
        results = fs.qs
        assert server_both_sockets in results
        assert server_http_socket not in results
        assert server_no_sockets not in results


# ===========================================================================
# Table
# ===========================================================================


@pytest.mark.django_db
class TestControlSocketTable:
    """Tests for control socket columns in the DHCPServerTable."""

    def test_table_has_http_column(self):
        """Test that DHCPServerTable has HTTP socket column."""
        from netbox_dhcp_kea_plugin.tables import DHCPServerTable

        assert "ctrl_socket_http_enabled" in DHCPServerTable.Meta.fields

    def test_table_has_unix_column(self):
        """Test that DHCPServerTable has Unix socket column."""
        from netbox_dhcp_kea_plugin.tables import DHCPServerTable

        assert "ctrl_socket_unix_enabled" in DHCPServerTable.Meta.fields

    def test_table_renders_with_data(self, server_both_sockets):
        """Test that table renders without errors with control socket data."""
        from netbox_dhcp_kea_plugin.models import DHCPServer
        from netbox_dhcp_kea_plugin.tables import DHCPServerTable

        qs = DHCPServer.objects.all()
        table = DHCPServerTable(qs)
        assert len(table.rows) > 0

    def test_columns_not_in_default_columns(self):
        """Test that control socket columns are not in default_columns."""
        from netbox_dhcp_kea_plugin.tables import DHCPServerTable

        defaults = DHCPServerTable.Meta.default_columns
        assert "ctrl_socket_http_enabled" not in defaults
        assert "ctrl_socket_unix_enabled" not in defaults


# ===========================================================================
# Edge Cases
# ===========================================================================


@pytest.mark.django_db
class TestControlSocketEdgeCases:
    """Edge case tests for control socket feature."""

    def test_http_address_ipv6(self, db, ctrl_service_template):
        """Test HTTP socket with IPv6 address."""
        from ipam.models import IPAddress

        from netbox_dhcp_kea_plugin.models import DHCPServer

        ip = IPAddress.objects.create(address="10.20.30.60/24")
        server = DHCPServer.objects.create(
            name="ctrl-ipv6-addr",
            ip_address=ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=True,
            ctrl_socket_http_address="::1",
            ctrl_socket_http_port=8000,
        )
        sockets = server.get_control_sockets()
        assert sockets[0]["socket-address"] == "::1"

    def test_http_high_port(self, db, ctrl_service_template):
        """Test HTTP socket with a high port number."""
        from ipam.models import IPAddress

        from netbox_dhcp_kea_plugin.models import DHCPServer

        ip = IPAddress.objects.create(address="10.20.30.61/24")
        server = DHCPServer.objects.create(
            name="ctrl-high-port",
            ip_address=ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=True,
            ctrl_socket_http_address="127.0.0.1",
            ctrl_socket_http_port=65535,
        )
        sockets = server.get_control_sockets()
        assert sockets[0]["socket-port"] == 65535

    def test_unix_long_path(self, db, ctrl_service_template):
        """Test Unix socket with a long path."""
        from ipam.models import IPAddress

        from netbox_dhcp_kea_plugin.models import DHCPServer

        ip = IPAddress.objects.create(address="10.20.30.62/24")
        long_path = "/var/run/" + "subdir/" * 20 + "kea.sock"
        server = DHCPServer.objects.create(
            name="ctrl-long-path",
            ip_address=ip,
            service_template=ctrl_service_template,
            ctrl_socket_unix_enabled=True,
            ctrl_socket_unix_path=long_path,
        )
        sockets = server.get_control_sockets()
        assert sockets[0]["socket-name"] == long_path

    def test_multiple_servers_independent_sockets(self, server_http_socket, server_unix_socket):
        """Test that control socket configs are independent per server."""
        http_sockets = server_http_socket.get_control_sockets()
        unix_sockets = server_unix_socket.get_control_sockets()
        assert len(http_sockets) == 1
        assert http_sockets[0]["socket-type"] == "http"
        assert len(unix_sockets) == 1
        assert unix_sockets[0]["socket-type"] == "unix"

    def test_toggle_socket_on_and_off(self, server_no_sockets):
        """Test toggling a socket on and off."""
        # Enable
        server_no_sockets.ctrl_socket_http_enabled = True
        server_no_sockets.save()
        server_no_sockets.refresh_from_db()
        assert len(server_no_sockets.get_control_sockets()) == 1

        # Disable
        server_no_sockets.ctrl_socket_http_enabled = False
        server_no_sockets.save()
        server_no_sockets.refresh_from_db()
        assert len(server_no_sockets.get_control_sockets()) == 0

    def test_kea_dict_control_sockets_is_list(self, server_http_socket):
        """Test that control-sockets in KEA config is always a list."""
        config = server_http_socket.to_kea_dict()
        sockets = config["Dhcp4"]["control-sockets"]
        assert isinstance(sockets, list)

    def test_get_control_sockets_does_not_modify_model(self, server_both_sockets):
        """Test that calling get_control_sockets() has no side effects on the model."""
        original_http = server_both_sockets.ctrl_socket_http_enabled
        original_unix = server_both_sockets.ctrl_socket_unix_enabled
        server_both_sockets.get_control_sockets()
        assert server_both_sockets.ctrl_socket_http_enabled == original_http
        assert server_both_sockets.ctrl_socket_unix_enabled == original_unix

    def test_kea_dict_with_sockets_still_has_standard_keys(self, server_both_sockets):
        """Test that enabling control sockets doesn't remove standard KEA config keys."""
        config = server_both_sockets.to_kea_dict()
        dhcp4 = config["Dhcp4"]
        assert "interfaces-config" in dhcp4
        assert "valid-lifetime" in dhcp4
        assert "max-valid-lifetime" in dhcp4

    def test_disabled_socket_values_preserved_in_db(self, db, ctrl_service_template):
        """Test that address/port/path values are preserved even when socket is disabled."""
        from ipam.models import IPAddress

        from netbox_dhcp_kea_plugin.models import DHCPServer

        ip = IPAddress.objects.create(address="10.20.30.70/24")
        server = DHCPServer.objects.create(
            name="ctrl-preserved",
            ip_address=ip,
            service_template=ctrl_service_template,
            ctrl_socket_http_enabled=False,
            ctrl_socket_http_address="192.168.0.1",
            ctrl_socket_http_port=9999,
            ctrl_socket_unix_enabled=False,
            ctrl_socket_unix_path="/custom/path.sock",
        )
        server.refresh_from_db()
        # Values should be stored even though disabled
        assert server.ctrl_socket_http_address == "192.168.0.1"
        assert server.ctrl_socket_http_port == 9999
        assert server.ctrl_socket_unix_path == "/custom/path.sock"
        # But get_control_sockets should return empty
        assert server.get_control_sockets() == []
