"""
Tests for DHCP High Availability (HA) models.

TDD approach: These tests define the expected behavior for HA support.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError


@pytest.mark.django_db
class TestDHCPHARelationshipModel:
    """Tests for the DHCPHARelationship model."""

    def test_create_hot_standby_relationship(self, dhcp_server_factory):
        """Test creating a hot-standby HA relationship."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="ha-cluster-1",
            mode="hot-standby",
            heartbeat_delay=10000,
            max_response_delay=60000,
            max_ack_delay=5000,
            max_unacked_clients=5,
        )

        assert relationship.pk is not None
        assert relationship.name == "ha-cluster-1"
        assert relationship.mode == "hot-standby"
        assert relationship.heartbeat_delay == 10000
        assert relationship.max_response_delay == 60000
        assert relationship.max_ack_delay == 5000
        assert relationship.max_unacked_clients == 5
        assert relationship.max_rejected_lease_updates == 10  # default
        assert relationship.enable_multi_threading is True  # default
        assert str(relationship) == "ha-cluster-1"

    def test_create_load_balancing_relationship(self, dhcp_server_factory):
        """Test creating a load-balancing HA relationship."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="ha-lb-cluster",
            mode="load-balancing",
        )

        assert relationship.mode == "load-balancing"

    def test_create_passive_backup_relationship(self, dhcp_server_factory):
        """Test creating a passive-backup HA relationship."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="ha-backup-cluster",
            mode="passive-backup",
        )

        assert relationship.mode == "passive-backup"

    def test_relationship_name_unique(self, dhcp_server_factory):
        """Test that relationship names must be unique."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        DHCPHARelationship.objects.create(name="unique-cluster", mode="hot-standby")

        with pytest.raises(IntegrityError):
            DHCPHARelationship.objects.create(name="unique-cluster", mode="load-balancing")

    def test_relationship_defaults(self, dhcp_server_factory):
        """Test default values for HA relationship."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="defaults-test",
            mode="hot-standby",
        )

        assert relationship.heartbeat_delay == 10000
        assert relationship.max_response_delay == 60000
        assert relationship.max_ack_delay == 5000
        assert relationship.max_unacked_clients == 5
        assert relationship.max_rejected_lease_updates == 10
        assert relationship.enable_multi_threading is True
        assert relationship.http_dedicated_listener is True
        assert relationship.http_listener_threads == 4
        assert relationship.http_client_threads == 4

    def test_relationship_get_absolute_url(self, dhcp_server_factory):
        """Test get_absolute_url returns correct URL."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="url-test",
            mode="hot-standby",
        )

        url = relationship.get_absolute_url()
        assert f"/plugins/netbox_dhcp_kea_plugin/ha-relationships/{relationship.pk}/" in url


@pytest.mark.django_db
class TestDHCPServerHAFields:
    """Tests for DHCPServer HA fields."""

    def test_server_with_ha_relationship(self, dhcp_server_factory):
        """Test creating a server with HA relationship."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="server-ha-test",
            mode="hot-standby",
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        assert server.ha_relationship == relationship
        assert server.ha_role == "primary"
        assert server.ha_url == "http://192.168.1.1:8000/"
        assert server.ha_auto_failover is True  # default
        assert server.ha_basic_auth_user == ""
        assert server.ha_basic_auth_password == ""

    def test_server_with_standby_role(self, dhcp_server_factory):
        """Test creating a standby server for hot-standby mode."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="standby-test",
            mode="hot-standby",
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        assert server.ha_role == "standby"

    def test_server_with_secondary_role(self, dhcp_server_factory):
        """Test creating a secondary server for load-balancing mode."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="lb-test",
            mode="load-balancing",
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="secondary",
            ha_url="http://192.168.1.2:8000/",
        )

        assert server.ha_role == "secondary"

    def test_server_with_backup_role(self, dhcp_server_factory):
        """Test creating a backup server."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="backup-test",
            mode="hot-standby",
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="backup",
            ha_url="http://192.168.1.3:8000/",
            ha_auto_failover=False,
        )

        assert server.ha_role == "backup"
        assert server.ha_auto_failover is False

    def test_server_with_basic_auth(self, dhcp_server_factory):
        """Test creating a server with HA basic authentication."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="auth-test",
            mode="hot-standby",
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
            ha_basic_auth_user="kea-admin",
            ha_basic_auth_password="secret123",
        )

        assert server.ha_basic_auth_user == "kea-admin"
        assert server.ha_basic_auth_password == "secret123"

    def test_server_without_ha(self, dhcp_server_factory):
        """Test that a server without HA has None/empty HA fields."""
        server = dhcp_server_factory()

        assert server.ha_relationship is None
        assert server.ha_role == ""
        assert server.ha_url == ""
        assert server.ha_auto_failover is True
        assert server.ha_basic_auth_user == ""
        assert server.ha_basic_auth_password == ""


@pytest.mark.django_db
class TestHARelationshipValidation:
    """Tests for HA relationship validation logic."""

    def test_hot_standby_requires_primary_and_standby(self, dhcp_server_factory):
        """Test that hot-standby mode requires exactly one primary and one standby."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="validation-test",
            mode="hot-standby",
        )

        # Add primary server
        dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        # Add standby server
        dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        # Validation should pass
        assert relationship.is_valid_configuration() is True

    def test_hot_standby_invalid_without_standby(self, dhcp_server_factory):
        """Test that hot-standby without standby is invalid."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="invalid-test",
            mode="hot-standby",
        )

        dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        # Should be invalid - missing standby
        assert relationship.is_valid_configuration() is False

    def test_load_balancing_requires_primary_and_secondary(self, dhcp_server_factory):
        """Test that load-balancing mode requires primary and secondary."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="lb-validation",
            mode="load-balancing",
        )

        dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="secondary",
            ha_url="http://192.168.1.2:8000/",
        )

        assert relationship.is_valid_configuration() is True


@pytest.mark.django_db
class TestDHCPServerHAConfiguration:
    """Tests for DHCPServer HA configuration generation."""

    def test_server_without_ha_returns_none(self, dhcp_server_factory):
        """Test that a server without HA returns None for HA config."""
        server = dhcp_server_factory()

        assert server.get_ha_config() is None

    def test_server_with_ha_returns_config(self, dhcp_server_factory):
        """Test that a server with HA returns proper configuration."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="config-test",
            mode="hot-standby",
            heartbeat_delay=10000,
            max_response_delay=60000,
        )

        server1 = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        ha_config = server1.get_ha_config()

        assert ha_config is not None
        assert ha_config["this-server-name"] == server1.name
        assert ha_config["mode"] == "hot-standby"
        assert ha_config["heartbeat-delay"] == 10000
        assert ha_config["max-response-delay"] == 60000
        assert "peers" in ha_config
        assert len(ha_config["peers"]) == 2

    def test_ha_config_includes_all_servers(self, dhcp_server_factory):
        """Test that HA config includes all servers in the relationship."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="multi-server-test",
            mode="hot-standby",
        )

        server1 = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        server2 = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        server3 = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="backup",
            ha_url="http://192.168.1.3:8000/",
            ha_auto_failover=False,
        )

        ha_config = server1.get_ha_config()

        assert len(ha_config["peers"]) == 3

        peer_names = [p["name"] for p in ha_config["peers"]]
        assert server1.name in peer_names
        assert server2.name in peer_names
        assert server3.name in peer_names

    def test_ha_config_includes_multi_threading(self, dhcp_server_factory):
        """Test that HA config includes multi-threading settings."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="mt-test",
            mode="hot-standby",
            enable_multi_threading=True,
            http_dedicated_listener=True,
            http_listener_threads=8,
            http_client_threads=8,
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        ha_config = server.get_ha_config()

        assert "multi-threading" in ha_config
        assert ha_config["multi-threading"]["enable-multi-threading"] is True
        assert ha_config["multi-threading"]["http-dedicated-listener"] is True
        assert ha_config["multi-threading"]["http-listener-threads"] == 8
        assert ha_config["multi-threading"]["http-client-threads"] == 8

    def test_ha_config_excludes_multi_threading_when_disabled(self, dhcp_server_factory):
        """Test that multi-threading is excluded when disabled."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="no-mt-test",
            mode="hot-standby",
            enable_multi_threading=False,
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        ha_config = server.get_ha_config()

        assert "multi-threading" not in ha_config

    def test_server_config_includes_basic_auth(self, dhcp_server_factory):
        """Test that server config includes basic auth when set."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="auth-config-test",
            mode="hot-standby",
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
            ha_basic_auth_user="admin",
            ha_basic_auth_password="secret",
        )

        ha_config = server.get_ha_config()

        peer = ha_config["peers"][0]
        assert peer["basic-auth-user"] == "admin"
        assert peer["basic-auth-password"] == "secret"

    def test_server_config_excludes_empty_basic_auth(self, dhcp_server_factory):
        """Test that server config excludes basic auth when not set."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="no-auth-test",
            mode="hot-standby",
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        ha_config = server.get_ha_config()

        peer = ha_config["peers"][0]
        assert "basic-auth-user" not in peer
        assert "basic-auth-password" not in peer


@pytest.mark.django_db
class TestDHCPServerToKeaDictWithHA:
    """Tests for DHCPServer.to_kea_dict() with HA configuration."""

    def test_to_kea_dict_includes_hooks_libraries_for_ha(self, dhcp_server_factory):
        """Test that to_kea_dict includes hooks-libraries when HA is configured."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="kea-dict-test",
            mode="hot-standby",
        )

        server1 = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        kea_config = server1.to_kea_dict()

        assert "Dhcp4" in kea_config
        assert "hooks-libraries" in kea_config["Dhcp4"]

        hooks = kea_config["Dhcp4"]["hooks-libraries"]
        assert len(hooks) == 2

        ha_hook = next((h for h in hooks if "libdhcp_ha.so" in h.get("library", "")), None)
        assert ha_hook is not None
        assert "parameters" in ha_hook
        assert "high-availability" in ha_hook["parameters"]

    def test_to_kea_dict_ha_hook_has_correct_parameters(self, dhcp_server_factory):
        """Test that HA hook has correct parameters."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="params-test",
            mode="hot-standby",
            heartbeat_delay=15000,
        )

        server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        kea_config = server.to_kea_dict()

        ha_hook = next(
            (h for h in kea_config["Dhcp4"]["hooks-libraries"] if "libdhcp_ha.so" in h.get("library", "")), None
        )

        ha_config = ha_hook["parameters"]["high-availability"][0]
        assert ha_config["this-server-name"] == server.name
        assert ha_config["mode"] == "hot-standby"
        assert ha_config["heartbeat-delay"] == 15000

    def test_to_kea_dict_without_ha_has_no_hooks_libraries(self, dhcp_server_factory):
        """Test that to_kea_dict without HA has no hooks-libraries."""
        server = dhcp_server_factory()

        kea_config = server.to_kea_dict()

        assert "hooks-libraries" not in kea_config.get("Dhcp4", {})


@pytest.mark.django_db
class TestHARelationshipToKeaDict:
    """Tests for DHCPHARelationship.to_kea_dict()."""

    def test_relationship_to_kea_dict_hot_standby(self, dhcp_server_factory):
        """Test to_kea_dict for hot-standby relationship."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="to-kea-test",
            mode="hot-standby",
            heartbeat_delay=10000,
            max_response_delay=60000,
        )

        server1 = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        server2 = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        kea_dict = relationship.to_kea_dict(this_server=server1)

        assert kea_dict["this-server-name"] == server1.name
        assert kea_dict["mode"] == "hot-standby"
        assert kea_dict["heartbeat-delay"] == 10000
        assert kea_dict["max-response-delay"] == 60000
        assert len(kea_dict["peers"]) == 2

        peer_names = [p["name"] for p in kea_dict["peers"]]
        assert server1.name in peer_names
        assert server2.name in peer_names

    def test_relationship_to_kea_dict_load_balancing(self, dhcp_server_factory):
        """Test to_kea_dict for load-balancing relationship."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="lb-kea-test",
            mode="load-balancing",
        )

        server1 = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        server2 = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="secondary",
            ha_url="http://192.168.1.2:8000/",
        )

        kea_dict = relationship.to_kea_dict(this_server=server1)

        assert kea_dict["mode"] == "load-balancing"

        roles = [p["role"] for p in kea_dict["peers"]]
        assert "primary" in roles
        assert "secondary" in roles


@pytest.mark.django_db
class TestHASyncFunctionality:
    """Tests for HA synchronization functionality."""

    def test_get_ha_primary_returns_primary_for_secondary(self, dhcp_server_factory):
        """Test that get_ha_primary returns the primary server for secondary/standby."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="sync-test",
            mode="hot-standby",
        )

        primary_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        standby_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        # Standby should return primary
        assert standby_server.get_ha_primary() == primary_server

        # Primary should return None (it IS the primary)
        assert primary_server.get_ha_primary() is None

    def test_get_ha_primary_returns_none_for_non_ha_server(self, dhcp_server_factory):
        """Test that get_ha_primary returns None for non-HA server."""
        server = dhcp_server_factory()

        assert server.get_ha_primary() is None

    def test_is_ha_primary_returns_true_for_primary(self, dhcp_server_factory):
        """Test that is_ha_primary returns True for primary server."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="primary-check",
            mode="hot-standby",
        )

        primary_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        standby_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        assert primary_server.is_ha_primary() is True
        assert standby_server.is_ha_primary() is False

    def test_is_ha_primary_returns_true_for_non_ha_server(self, dhcp_server_factory):
        """Test that is_ha_primary returns True for non-HA server."""
        server = dhcp_server_factory()

        assert server.is_ha_primary() is True

    def test_get_effective_prefix_configs_syncs_from_primary(self, dhcp_server_factory, prefix_factory):
        """Test that get_effective_prefix_configs syncs from primary."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship, PrefixDHCPConfig

        relationship = DHCPHARelationship.objects.create(
            name="prefix-sync-test",
            mode="hot-standby",
        )

        primary_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        standby_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        # Create prefix config on primary
        prefix = prefix_factory()
        PrefixDHCPConfig.objects.create(
            prefix=prefix,
            server=primary_server,
            valid_lifetime=3600,
            max_lifetime=7200,
        )

        # Primary should have its own config
        assert primary_server.get_effective_prefix_configs().count() == 1

        # Standby should get configs from primary
        assert standby_server.get_effective_prefix_configs().count() == 1

    def test_get_effective_prefix_configs_returns_own_for_non_ha(self, dhcp_server_factory, prefix_factory):
        """Test that get_effective_prefix_configs returns own configs for non-HA."""
        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        server = dhcp_server_factory()
        prefix = prefix_factory()

        PrefixDHCPConfig.objects.create(
            prefix=prefix,
            server=server,
            valid_lifetime=3600,
            max_lifetime=7200,
        )

        assert server.get_effective_prefix_configs().count() == 1

    def test_to_kea_dict_syncs_subnets_for_secondary(self, dhcp_server_factory, prefix_factory):
        """Test that to_kea_dict syncs subnets from primary for secondary server."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship, PrefixDHCPConfig

        relationship = DHCPHARelationship.objects.create(
            name="subnet-sync-test",
            mode="hot-standby",
        )

        primary_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        standby_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        # Create prefix config on primary
        prefix = prefix_factory()
        PrefixDHCPConfig.objects.create(
            prefix=prefix,
            server=primary_server,
            valid_lifetime=3600,
            max_lifetime=7200,
        )

        # Both servers should have the subnet in their KEA config
        primary_config = primary_server.to_kea_dict()
        standby_config = standby_server.to_kea_dict()

        primary_subnets = primary_config["Dhcp4"].get("subnet4", [])
        standby_subnets = standby_config["Dhcp4"].get("subnet4", [])

        assert len(primary_subnets) == len(standby_subnets)


@pytest.mark.django_db
class TestHARelationshipHelpers:
    """Tests for DHCPHARelationship helper methods."""

    def test_get_primary_server(self, dhcp_server_factory):
        """Test get_primary_server returns the primary server."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        relationship = DHCPHARelationship.objects.create(
            name="helper-test",
            mode="hot-standby",
        )

        primary_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        assert relationship.get_primary_server() == primary_server

    def test_get_synced_prefix_count(self, dhcp_server_factory, prefix_factory):
        """Test get_synced_prefix_count returns count from primary."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship, PrefixDHCPConfig

        relationship = DHCPHARelationship.objects.create(
            name="count-test",
            mode="hot-standby",
        )

        primary_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        # Create prefix configs on primary
        for i in range(3):
            prefix = prefix_factory()
            PrefixDHCPConfig.objects.create(
                prefix=prefix,
                server=primary_server,
                valid_lifetime=3600,
                max_lifetime=7200,
            )

        assert relationship.get_synced_prefix_count() == 3

    def test_migrate_configs_to_new_primary(self, dhcp_server_factory, prefix_factory):
        """Test migrate_configs_to_new_primary transfers configs."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship, PrefixDHCPConfig

        relationship = DHCPHARelationship.objects.create(
            name="migration-test",
            mode="hot-standby",
        )

        old_primary = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        new_primary = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        # Create prefix config on old primary
        prefix = prefix_factory()
        PrefixDHCPConfig.objects.create(
            prefix=prefix,
            server=old_primary,
            valid_lifetime=3600,
            max_lifetime=7200,
        )

        # Migrate configs
        result = relationship.migrate_configs_to_new_primary(new_primary)

        assert result["prefixes"] == 1

        # Config should now be on new primary
        assert new_primary.prefix_configs.count() == 1
        assert old_primary.prefix_configs.count() == 0


@pytest.mark.django_db
class TestHARoleChangeProtection:
    """Tests for HA role change protection."""

    def test_cannot_change_primary_role_with_configs(self, dhcp_server_factory, prefix_factory):
        """Test that changing from primary role with configs raises error."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship, PrefixDHCPConfig

        relationship = DHCPHARelationship.objects.create(
            name="role-protection-test",
            mode="hot-standby",
        )

        primary_server = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        # Create prefix config
        prefix = prefix_factory()
        PrefixDHCPConfig.objects.create(
            prefix=prefix,
            server=primary_server,
            valid_lifetime=3600,
            max_lifetime=7200,
        )

        # Try to change role from primary
        primary_server.ha_role = "standby"

        with pytest.raises(ValidationError):
            primary_server.full_clean()

    def test_can_change_primary_role_after_migration(self, dhcp_server_factory, prefix_factory):
        """Test that changing role is allowed after migrating configs."""
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship, PrefixDHCPConfig

        relationship = DHCPHARelationship.objects.create(
            name="migration-role-test",
            mode="hot-standby",
        )

        old_primary = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="primary",
            ha_url="http://192.168.1.1:8000/",
        )

        new_primary = dhcp_server_factory(
            ha_relationship=relationship,
            ha_role="standby",
            ha_url="http://192.168.1.2:8000/",
        )

        # Create prefix config
        prefix = prefix_factory()
        PrefixDHCPConfig.objects.create(
            prefix=prefix,
            server=old_primary,
            valid_lifetime=3600,
            max_lifetime=7200,
        )

        # Migrate configs first
        relationship.migrate_configs_to_new_primary(new_primary)

        # Now changing role should work
        old_primary.ha_role = "standby"
        old_primary.full_clean()  # Should not raise
        old_primary.save()

        assert old_primary.ha_role == "standby"
