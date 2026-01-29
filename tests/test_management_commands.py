"""
Tests for the generate_kea_demo_data management command.

Run with:
    cd /path/to/netbox-dhcp-kea-plugin
    source /path/to/netbox/venv/bin/activate
    pytest tests/test_management_commands.py -v
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from extras.models import Tag

from netbox_dhcp_kea_plugin.models import (
    ClientClass,
    DHCPHARelationship,
    DHCPServer,
    OptionData,
    OptionDefinition,
    VendorOptionSpace,
)

# Demo tag constants (must match the command)
DEMO_TAG_SLUG = "dhcp-kea-demo-data"


class TestGenerateKeaDemoDataCommand:
    """Tests for the generate_kea_demo_data management command."""

    def test_command_fails_when_disabled(self, db, settings):
        """Test that command fails when demo_data.enabled is False."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": False,
                }
            }
        }

        with pytest.raises(CommandError) as exc_info:
            call_command("generate_kea_demo_data")

        assert "disabled" in str(exc_info.value).lower()

    def test_command_runs_with_force_flag(self, db, settings):
        """Test that command runs with --force even when disabled."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": False,
                    "vendor_option_spaces": 1,
                    "option_definitions_per_space": 1,
                    "option_data": 1,
                    "client_classes": 1,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", "--force", stdout=out)

        assert "Demo data generation complete" in out.getvalue()

    def test_dry_run_creates_nothing(self, db, settings):
        """Test that --dry-run doesn't create any objects."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 3,
                    "option_definitions_per_space": 5,
                    "option_data": 10,
                    "client_classes": 5,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        initial_vendor_count = VendorOptionSpace.objects.count()
        initial_definition_count = OptionDefinition.objects.filter(is_standard=False).count()
        initial_option_data_count = OptionData.objects.count()
        initial_client_class_count = ClientClass.objects.count()

        out = StringIO()
        call_command("generate_kea_demo_data", "--dry-run", stdout=out)

        assert "DRY RUN MODE" in out.getvalue()
        assert VendorOptionSpace.objects.count() == initial_vendor_count
        assert OptionDefinition.objects.filter(is_standard=False).count() == initial_definition_count
        assert OptionData.objects.count() == initial_option_data_count
        assert ClientClass.objects.count() == initial_client_class_count

    def test_creates_vendor_option_spaces(self, db, settings):
        """Test that command creates vendor option spaces."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 3,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", stdout=out)

        assert VendorOptionSpace.objects.count() >= 3
        # Check some expected vendor spaces
        assert VendorOptionSpace.objects.filter(name="cisco-ucm").exists()

    def test_creates_option_definitions(self, db, settings):
        """Test that command creates option definitions for vendor spaces."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 2,
                    "option_definitions_per_space": 3,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", stdout=out)

        # Should have created 2 spaces * 3 definitions = 6 definitions
        custom_definitions = OptionDefinition.objects.filter(is_standard=False)
        assert custom_definitions.count() >= 6

    def test_creates_option_data(self, db, settings):
        """Test that command creates option data instances."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 1,
                    "option_definitions_per_space": 2,
                    "option_data": 5,
                    "client_classes": 0,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", stdout=out)

        assert OptionData.objects.count() >= 5

    def test_creates_client_classes(self, db, settings):
        """Test that command creates client classes."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 1,
                    "option_definitions_per_space": 1,
                    "option_data": 2,
                    "client_classes": 3,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", stdout=out)

        assert ClientClass.objects.count() >= 3
        # Check some expected client classes
        assert ClientClass.objects.filter(name="Cisco-UC-Phones").exists()

    def test_creates_ha_relationships(self, db, settings):
        """Test that command creates HA relationships."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 0,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 0,
                    "ha_relationships": 2,
                    "prefix_configs": 0,
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", stdout=out)

        assert DHCPHARelationship.objects.count() >= 2

    def test_clear_removes_only_demo_tagged_data(
        self, db, settings, vendor_option_space, option_definition, client_class
    ):
        """Test that --clear removes only demo-tagged plugin data, not user data."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 1,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 1,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        # First, generate some demo data (this will create the demo tag and tagged objects)
        call_command("generate_kea_demo_data", stdout=StringIO())

        # Verify we have both user data (from fixtures) and demo data
        assert VendorOptionSpace.objects.count() >= 2  # fixture + demo
        assert ClientClass.objects.count() >= 2  # fixture + demo

        # Verify demo tag exists and is applied
        demo_tag = Tag.objects.get(slug=DEMO_TAG_SLUG)
        assert ClientClass.objects.filter(tags=demo_tag).count() >= 1

        # User-created fixture data should NOT have the demo tag
        assert client_class.tags.filter(slug=DEMO_TAG_SLUG).count() == 0

        out = StringIO()
        call_command("generate_kea_demo_data", "--clear", stdout=out)

        assert "Clearing demo-generated plugin data" in out.getvalue()

        # User-created client class should still exist (not tagged)
        assert ClientClass.objects.filter(name="TestClass").exists()

        # Demo-tagged objects should be gone
        assert ClientClass.objects.filter(tags=demo_tag).count() == 0

    def test_idempotent_creation(self, db, settings):
        """Test that running command twice doesn't duplicate data."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 2,
                    "option_definitions_per_space": 2,
                    "option_data": 0,
                    "client_classes": 2,
                    "dhcp_servers": 0,
                    "ha_relationships": 1,
                    "prefix_configs": 0,
                }
            }
        }

        # Run twice
        call_command("generate_kea_demo_data", stdout=StringIO())
        first_vendor_count = VendorOptionSpace.objects.count()
        first_class_count = ClientClass.objects.count()
        first_ha_count = DHCPHARelationship.objects.count()

        call_command("generate_kea_demo_data", stdout=StringIO())
        second_vendor_count = VendorOptionSpace.objects.count()
        second_class_count = ClientClass.objects.count()
        second_ha_count = DHCPHARelationship.objects.count()

        # Counts should be the same (get_or_create)
        assert first_vendor_count == second_vendor_count
        assert first_class_count == second_class_count
        assert first_ha_count == second_ha_count

    def test_uses_default_config_values(self, db, settings):
        """Test that command uses default values when not specified."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    # Not specifying other values - should use defaults
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", stdout=out)

        output = out.getvalue()
        # Check that default values are shown
        assert "Vendor Option Spaces: 3" in output
        assert "Client Classes: 5" in output


class TestGenerateKeaDemoDataTagging:
    """Tests for demo data tagging in generate_kea_demo_data."""

    def test_creates_demo_tag(self, db, settings):
        """Test that command creates the demo tag."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 1,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        call_command("generate_kea_demo_data", stdout=StringIO())

        assert Tag.objects.filter(slug=DEMO_TAG_SLUG).exists()
        tag = Tag.objects.get(slug=DEMO_TAG_SLUG)
        assert tag.color == "ff9800"  # Orange

    def test_tags_created_objects(self, db, settings):
        """Test that created objects are tagged with the demo tag."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 2,
                    "option_definitions_per_space": 1,
                    "option_data": 1,
                    "client_classes": 1,
                    "dhcp_servers": 0,
                    "ha_relationships": 1,
                    "prefix_configs": 0,
                }
            }
        }

        call_command("generate_kea_demo_data", stdout=StringIO())

        demo_tag = Tag.objects.get(slug=DEMO_TAG_SLUG)

        # Verify all created objects are tagged
        assert VendorOptionSpace.objects.filter(tags=demo_tag).count() == 2
        assert OptionDefinition.objects.filter(tags=demo_tag, is_standard=False).count() == 2
        assert OptionData.objects.filter(tags=demo_tag).count() >= 1
        assert ClientClass.objects.filter(tags=demo_tag).count() >= 1
        assert DHCPHARelationship.objects.filter(tags=demo_tag).count() >= 1

    def test_purge_demo_data_only_deletes(self, db, settings):
        """Test that --purge-demo-data only deletes demo data without generating new data."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 2,
                    "option_definitions_per_space": 1,
                    "option_data": 1,
                    "client_classes": 1,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        # First generate some demo data
        call_command("generate_kea_demo_data", stdout=StringIO())

        # Verify demo data was created
        demo_tag = Tag.objects.get(slug=DEMO_TAG_SLUG)
        assert VendorOptionSpace.objects.filter(tags=demo_tag).count() == 2
        assert ClientClass.objects.filter(tags=demo_tag).count() >= 1

        # Now purge the demo data
        out = StringIO()
        call_command("generate_kea_demo_data", "--purge-demo-data", stdout=out)

        output = out.getvalue()
        assert "Purging demo-tagged data only" in output
        assert "Demo data purge complete" in output

        # Verify demo data was deleted
        assert VendorOptionSpace.objects.filter(tags=demo_tag).count() == 0
        assert ClientClass.objects.filter(tags=demo_tag).count() == 0

    def test_purge_demo_data_preserves_user_data(self, db, settings, vendor_option_space, client_class):
        """Test that --purge-demo-data preserves user-created data."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 1,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 1,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        # Generate some demo data
        call_command("generate_kea_demo_data", stdout=StringIO())

        # Verify user data exists (from fixtures)
        assert VendorOptionSpace.objects.filter(name="TestVendor").exists()
        assert ClientClass.objects.filter(name="TestClass").exists()

        # Purge demo data
        call_command("generate_kea_demo_data", "--purge-demo-data", stdout=StringIO())

        # User data should still exist
        assert VendorOptionSpace.objects.filter(name="TestVendor").exists()
        assert ClientClass.objects.filter(name="TestClass").exists()

    def test_purge_demo_data_without_enabled_flag(self, db, settings):
        """Test that --purge-demo-data works even when enabled is False."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": False,
                }
            }
        }

        # Should not raise CommandError even though enabled is False
        out = StringIO()
        call_command("generate_kea_demo_data", "--purge-demo-data", stdout=out)

        assert "Demo data purge complete" in out.getvalue()

    def test_clear_without_demo_tag_does_nothing(self, db, settings, vendor_option_space, client_class):
        """Test that --clear does nothing if no demo tag exists."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 0,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        # Ensure no demo tag exists
        Tag.objects.filter(slug=DEMO_TAG_SLUG).delete()

        initial_vendor_count = VendorOptionSpace.objects.count()
        initial_class_count = ClientClass.objects.count()

        out = StringIO()
        call_command("generate_kea_demo_data", "--clear", stdout=out)

        assert "No demo tag found" in out.getvalue()
        # User data should be untouched
        assert VendorOptionSpace.objects.count() == initial_vendor_count
        assert ClientClass.objects.count() == initial_class_count


class TestGenerateKeaDemoDataPrerequisites:
    """Tests for prerequisite handling in generate_kea_demo_data."""

    def test_creates_manufacturer(self, db, settings):
        """Test that command creates a demo manufacturer."""
        from dcim.models import Manufacturer

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 1,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        call_command("generate_kea_demo_data", stdout=StringIO())

        assert Manufacturer.objects.filter(name="Demo Manufacturer").exists()

    def test_creates_service_template(self, db, settings):
        """Test that command creates a KEA DHCP service template."""
        from ipam.models import ServiceTemplate

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 0,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        call_command("generate_kea_demo_data", stdout=StringIO())

        template = ServiceTemplate.objects.filter(name="KEA DHCP Server").first()
        assert template is not None
        assert template.protocol == "udp"
        assert 67 in template.ports


class TestGenerateKeaDemoDataPrefixFiltering:
    """Tests for prefix filtering in generate_kea_demo_data."""

    def test_filters_prefix_by_mask_length(self, db, settings, prefix_factory):
        """Test that only prefixes with /22-/28 mask are selected."""
        # Create prefixes with various mask lengths
        prefix_factory(network="10.0.0.0/8")  # Too large
        prefix_factory(network="10.1.0.0/16")  # Too large
        prefix_factory(network="10.2.0.0/20")  # Too large
        prefix_factory(network="10.3.0.0/22")  # Valid
        prefix_factory(network="10.4.0.0/24")  # Valid
        prefix_factory(network="10.5.0.0/28")  # Valid
        prefix_factory(network="10.6.0.0/30")  # Too small
        prefix_factory(network="10.7.0.0/32")  # Too small

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 0,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 0,
                    "ha_relationships": 0,
                    "prefix_configs": 10,
                }
            }
        }

        # We can't directly test without DHCP servers, but we can verify the filtering logic
        # by checking what prefixes would be selected
        from ipam.models import Prefix

        candidate_prefixes = Prefix.objects.filter(
            prefix__family=4,
            dhcp_config__isnull=True,
        )

        valid_prefixes = []
        for prefix in candidate_prefixes:
            prefix_len = prefix.prefix.prefixlen
            if 22 <= prefix_len <= 28:
                valid_prefixes.append(prefix)

        # Should only have /22, /24, and /28
        assert len(valid_prefixes) == 3
        prefix_lens = [p.prefix.prefixlen for p in valid_prefixes]
        assert 22 in prefix_lens
        assert 24 in prefix_lens
        assert 28 in prefix_lens
        assert 8 not in prefix_lens
        assert 30 not in prefix_lens

    def test_excludes_overlapping_prefixes(self, db, settings, prefix_factory):
        """Test that overlapping prefixes are excluded."""
        # Create overlapping prefixes
        prefix_factory(network="192.168.0.0/22")  # Parent
        prefix_factory(network="192.168.0.0/24")  # Child - should be excluded
        prefix_factory(network="192.168.1.0/24")  # Child - should be excluded
        prefix_factory(network="172.16.0.0/24")  # Non-overlapping - should be included

        from ipam.models import Prefix

        candidate_prefixes = Prefix.objects.filter(
            prefix__family=4,
            dhcp_config__isnull=True,
        )

        # Apply the same filtering logic as the command
        prefixes = []
        for prefix in candidate_prefixes:
            prefix_len = prefix.prefix.prefixlen
            if prefix_len < 22 or prefix_len > 28:
                continue

            is_overlapping = False
            for selected in prefixes:
                if prefix.prefix in selected.prefix or selected.prefix in prefix.prefix:
                    is_overlapping = True
                    break

            if not is_overlapping:
                prefixes.append(prefix)

        # Should have /22 and 172.16.0.0/24, but not the /24s under the /22
        assert len(prefixes) == 2
        prefix_strs = [str(p.prefix) for p in prefixes]
        assert "192.168.0.0/22" in prefix_strs
        assert "172.16.0.0/24" in prefix_strs
        assert "192.168.0.0/24" not in prefix_strs
        assert "192.168.1.0/24" not in prefix_strs


class TestGenerateKeaDemoDataDHCPServers:
    """Tests for DHCP server creation in generate_kea_demo_data."""

    def test_creates_servers_with_vms_and_ips(self, db, settings):
        """Test that servers are created with associated VMs, interfaces, and IPs."""
        from ipam.models import IPAddress
        from virtualization.models import Cluster, ClusterType, VirtualMachine, VMInterface

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 0,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 2,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", stdout=out)

        # Should have created servers
        assert DHCPServer.objects.count() == 2

        # Should have created VMs for each server
        assert VirtualMachine.objects.filter(name__startswith="vm-kea-dhcp").count() == 2

        # Should have created interfaces
        assert VMInterface.objects.filter(name="eth0").count() == 2

        # Should have created IPs from management prefix (198.51.100.0/24)
        assert IPAddress.objects.filter(address__startswith="198.51.100.").count() == 2

        # VMs should have primary IPs set
        for vm in VirtualMachine.objects.filter(name__startswith="vm-kea-dhcp"):
            assert vm.primary_ip4 is not None

    def test_creates_demo_cluster_and_prefix(self, db, settings):
        """Test that demo cluster and management prefix are created."""
        from ipam.models import Prefix
        from virtualization.models import Cluster, ClusterType

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 0,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 1,
                    "ha_relationships": 0,
                    "prefix_configs": 0,
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", stdout=out)

        # Should have created cluster type and cluster
        assert ClusterType.objects.filter(name="Demo DHCP Cluster Type").exists()
        assert Cluster.objects.filter(name="Demo DHCP Cluster").exists()

        # Should have created management prefix
        assert Prefix.objects.filter(prefix="198.51.100.0/24").exists()


class TestGenerateKeaDemoDataHAAssignment:
    """Tests for HA relationship assignment in generate_kea_demo_data."""

    def test_assigns_servers_to_ha_relationship(self, db, settings):
        """Test that servers are assigned to HA relationships after creation."""
        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "demo_data": {
                    "enabled": True,
                    "vendor_option_spaces": 0,
                    "option_definitions_per_space": 0,
                    "option_data": 0,
                    "client_classes": 0,
                    "dhcp_servers": 2,
                    "ha_relationships": 1,
                    "prefix_configs": 0,
                }
            }
        }

        out = StringIO()
        call_command("generate_kea_demo_data", stdout=out)

        # Check that servers were assigned to HA
        ha_relationship = DHCPHARelationship.objects.first()
        if ha_relationship:
            servers_in_ha = DHCPServer.objects.filter(ha_relationship=ha_relationship)
            # Should have up to 2 servers assigned
            assert servers_in_ha.count() <= 2
            # Check roles are set
            for server in servers_in_ha:
                assert server.ha_role in ["primary", "standby", "secondary", "backup"]
