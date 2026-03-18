"""
Management command to generate demo data for the NetBox DHCP KEA Plugin.

This command creates demo/test data for all plugin models based on the
PLUGINS_CONFIG settings in NetBox's configuration.py.

Usage:
    python manage.py generate_kea_demo_data

Configuration in configuration.py:
    PLUGINS_CONFIG = {
        'netbox_dhcp_kea_plugin': {
            'demo_data': {
                'enabled': True,  # Must be True or use --force
                'vendor_option_spaces': 3,
                'option_definitions_per_space': 5,
                'option_data': 10,
                'client_classes': 5,
                'dhcp_servers': 3,
                'ha_relationships': 1,
                'dhcp_subnets': 5,
            }
        }
    }
"""

import random

from dcim.models import Manufacturer
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from extras.models import Tag
from ipam.models import IPAddress, IPRange, Prefix, ServiceTemplate
from netbox.plugins.utils import get_plugin_config
from virtualization.models import Cluster, ClusterType, VirtualMachine, VMInterface

from netbox_dhcp_kea_plugin import DHCPKEAConfig
from netbox_dhcp_kea_plugin.models import (
    ClientClass,
    DHCPHARelationship,
    DHCPServer,
    Hook,
    HookGroup,
    OptionData,
    OptionDefinition,
    Subnet,
    SubnetPool,
    VendorOptionSpace,
)

# Tag name used to identify demo-generated data
DEMO_TAG_NAME = "dhcp-kea-demo-data"
DEMO_TAG_SLUG = "dhcp-kea-demo-data"


class Command(BaseCommand):
    help = "Generate demo data for the NetBox DHCP KEA Plugin"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Generate demo data even if 'enabled' is False in config",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing demo-tagged plugin data before generating new data",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating anything",
        )
        parser.add_argument(
            "--purge-demo-data",
            action="store_true",
            help="Only delete demo-tagged data without generating new data",
        )

    def get_config(self):
        """Get demo data configuration.

        NetBox's get_plugin_config() doesn't deep-merge nested dicts, so we need
        to manually merge user's demo_data settings with our defaults from PluginConfig.
        """
        # Get defaults from PluginConfig.default_settings
        defaults = DHCPKEAConfig.default_settings.get("demo_data", {})

        # Get user config (may be partial or None)
        user_config = get_plugin_config("netbox_dhcp_kea_plugin", "demo_data")

        if user_config is None:
            return defaults

        # Merge user config over defaults
        return {**defaults, **user_config}

    def get_or_create_demo_tag(self):
        """Get or create the demo data tag."""
        tag, created = Tag.objects.get_or_create(
            slug=DEMO_TAG_SLUG,
            defaults={
                "name": DEMO_TAG_NAME,
                "description": "Auto-generated demo data for DHCP KEA plugin. Safe to delete.",
                "color": "ff9800",  # Orange color to indicate demo/test data
            },
        )
        if created:
            self.stdout.write(f"  Created demo tag: {tag.name}")
        return tag

    def tag_object(self, obj, tag):
        """Add the demo tag to an object."""
        if hasattr(obj, "tags"):
            obj.tags.add(tag)

    def clear_existing_data(self):
        """Clear only demo-generated plugin data (tagged with demo tag)."""
        self.stdout.write("Clearing demo-generated plugin data...")

        try:
            demo_tag = Tag.objects.get(slug=DEMO_TAG_SLUG)
        except Tag.DoesNotExist:
            self.stdout.write(self.style.WARNING("  No demo tag found - nothing to clear."))
            return

        # Delete in order to respect foreign key constraints

        # Delete demo SubnetPools
        demo_subnets = Subnet.objects.filter(tags=demo_tag)
        count = SubnetPool.objects.filter(tags=demo_tag).count()
        count += SubnetPool.objects.filter(subnet__in=demo_subnets).exclude(tags=demo_tag).count()
        SubnetPool.objects.filter(tags=demo_tag).delete()
        SubnetPool.objects.filter(subnet__in=demo_subnets).delete()
        self.stdout.write(f"  - Deleted {count} SubnetPool objects")

        # Delete demo IP Ranges
        count = IPRange.objects.filter(tags=demo_tag).count()
        IPRange.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} IPRange objects")

        # Delete demo HookGroups (clear M2M relations first)
        demo_hook_groups = HookGroup.objects.filter(tags=demo_tag)
        count = demo_hook_groups.count()
        for hg in list(demo_hook_groups):
            hg.hooks.clear()
            hg.servers.clear()
            hg.delete()
        self.stdout.write(f"  - Deleted {count} HookGroup objects")

        # First, delete Subnets that are tagged OR reference demo-tagged servers
        demo_servers = DHCPServer.objects.filter(tags=demo_tag)
        count = Subnet.objects.filter(tags=demo_tag).count()
        count += Subnet.objects.filter(server__in=demo_servers).exclude(tags=demo_tag).count()
        Subnet.objects.filter(tags=demo_tag).delete()
        Subnet.objects.filter(server__in=demo_servers).delete()
        self.stdout.write(f"  - Deleted {count} Subnet objects")

        # Clear HA relationships from demo servers before deleting
        demo_servers.update(ha_relationship=None, ha_role="", ha_address="", ha_port=8080, ha_tls=False)

        count = DHCPServer.objects.filter(tags=demo_tag).count()
        DHCPServer.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} DHCPServer objects")

        count = DHCPHARelationship.objects.filter(tags=demo_tag).count()
        DHCPHARelationship.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} DHCPHARelationship objects")

        # Clear M2M relations on ClientClass before deleting
        demo_client_classes = ClientClass.objects.filter(tags=demo_tag)
        count = demo_client_classes.count()
        for cc in list(demo_client_classes):  # Convert to list to avoid queryset caching issues
            cc.option_data.clear()
            cc.servers.clear()
            cc.delete()  # Delete each one individually
        self.stdout.write(f"  - Deleted {count} ClientClass objects")

        count = OptionData.objects.filter(tags=demo_tag).count()
        OptionData.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} OptionData objects")

        count = OptionDefinition.objects.filter(tags=demo_tag, is_standard=False).count()
        OptionDefinition.objects.filter(tags=demo_tag, is_standard=False).delete()
        self.stdout.write(f"  - Deleted {count} custom OptionDefinition objects")

        count = VendorOptionSpace.objects.filter(tags=demo_tag).count()
        VendorOptionSpace.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} VendorOptionSpace objects")

        # Delete demo IP addresses (must be before VMs/interfaces)
        count = IPAddress.objects.filter(tags=demo_tag).count()
        IPAddress.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} IPAddress objects")

        # Delete demo VM interfaces
        count = VMInterface.objects.filter(tags=demo_tag).count()
        VMInterface.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} VMInterface objects")

        # Delete demo VMs
        count = VirtualMachine.objects.filter(tags=demo_tag).count()
        VirtualMachine.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} VirtualMachine objects")

        # Delete demo prefixes (server management network)
        count = Prefix.objects.filter(tags=demo_tag).count()
        Prefix.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} Prefix objects")

        # Delete demo clusters
        count = Cluster.objects.filter(tags=demo_tag).count()
        Cluster.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} Cluster objects")

        # Delete demo cluster types
        count = ClusterType.objects.filter(tags=demo_tag).count()
        ClusterType.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} ClusterType objects")

        self.stdout.write(self.style.SUCCESS("Demo-generated data cleared."))

    def get_or_create_prerequisites(self):
        """Ensure required NetBox objects exist for demo data."""
        prerequisites = {}

        # Get or create the demo tag first (needed for tagging prerequisites)
        demo_tag = self.get_or_create_demo_tag()
        prerequisites["demo_tag"] = demo_tag

        # Get or create a manufacturer for vendor option spaces
        manufacturer, created = Manufacturer.objects.get_or_create(
            name="Demo Manufacturer",
            defaults={"slug": "demo-manufacturer"},
        )
        prerequisites["manufacturer"] = manufacturer
        if created:
            self.stdout.write(f"  Created Manufacturer: {manufacturer.name}")

        # Get or create a cluster type for demo VMs
        cluster_type, created = ClusterType.objects.get_or_create(
            name="Demo DHCP Cluster Type",
            defaults={"slug": "demo-dhcp-cluster-type"},
        )
        if created:
            self.tag_object(cluster_type, demo_tag)
            self.stdout.write(f"  Created ClusterType: {cluster_type.name}")
        prerequisites["cluster_type"] = cluster_type

        # Get or create a cluster for demo VMs
        cluster, created = Cluster.objects.get_or_create(
            name="Demo DHCP Cluster",
            defaults={
                "type": cluster_type,
            },
        )
        if created:
            self.tag_object(cluster, demo_tag)
            self.stdout.write(f"  Created Cluster: {cluster.name}")
        prerequisites["cluster"] = cluster

        # Create a management prefix for DHCP server IPs (from IPv4 documentation space 198.51.100.0/24)
        mgmt_prefix, created = Prefix.objects.get_or_create(
            prefix="198.51.100.0/24",
            defaults={
                "description": "Demo DHCP Server Management Network (TEST-NET-2)",
            },
        )
        if created:
            self.tag_object(mgmt_prefix, demo_tag)
            self.stdout.write(f"  Created management Prefix: {mgmt_prefix.prefix}")
        prerequisites["mgmt_prefix"] = mgmt_prefix

        # Get available prefixes (IPv4 only for DHCPv4, /22 to /28 range)
        candidate_prefixes = Prefix.objects.filter(
            prefix__family=4,  # IPv4 only
            dhcp_config__isnull=True,  # Not already configured
        )

        # Filter to /22-/28 range and exclude overlapping prefixes
        prefixes = []
        for prefix in candidate_prefixes:
            prefix_len = prefix.prefix.prefixlen
            # Only include prefixes between /22 and /28
            if prefix_len < 22 or prefix_len > 28:
                continue

            # Check if this prefix overlaps with any already selected prefix
            is_overlapping = False
            for selected in prefixes:
                # Check if one contains the other
                if prefix.prefix in selected.prefix or selected.prefix in prefix.prefix:
                    is_overlapping = True
                    break

            if not is_overlapping:
                prefixes.append(prefix)

            # Stop if we have enough
            if len(prefixes) >= 20:
                break

        prerequisites["prefixes"] = prefixes

        if not prefixes:
            self.stdout.write(
                self.style.WARNING("  No available IPv4 prefixes found for DHCP configuration (/22-/28 range).")
            )

        # Get or create a service template for DHCP
        service_template, created = ServiceTemplate.objects.get_or_create(
            name="KEA DHCP Server",
            defaults={
                "protocol": "udp",
                "ports": [67],
                "description": "KEA DHCP Server service template for demo data",
            },
        )
        prerequisites["service_template"] = service_template
        if created:
            self.stdout.write(f"  Created ServiceTemplate: {service_template.name}")

        return prerequisites

    def create_vendor_option_spaces(self, count, manufacturer, demo_tag, dry_run=False):
        """Create vendor option spaces."""
        self.stdout.write(f"\nCreating {count} VendorOptionSpace objects...")

        vendor_data = [
            {"name": "hp-printers", "enterprise_id": 11, "description": "HP Printer options (Option 43 and VIVSO)"},
            {"name": "cisco-ucm", "enterprise_id": 9, "description": "Cisco Unified Communications Manager"},
            {"name": "microsoft-uc", "enterprise_id": 311, "description": "Microsoft Unified Communications"},
            {"name": "fortinet-fortigate", "enterprise_id": 12356, "description": "Fortinet FortiGate options"},
            {"name": "aruba-iap", "enterprise_id": 14823, "description": "Aruba Instant AP options"},
            {"name": "polycom-phones", "enterprise_id": 13885, "description": "Polycom VoIP phone options"},
            {"name": "yealink-phones", "enterprise_id": 52378, "description": "Yealink phone provisioning"},
            {"name": "ubiquiti-unifi", "enterprise_id": 41112, "description": "Ubiquiti UniFi options"},
            {"name": "hp-procurve", "enterprise_id": 11, "description": "HP ProCurve switch options"},
        ]

        created_spaces = []
        for data in vendor_data[:count]:
            if dry_run:
                self.stdout.write(f"  [DRY-RUN] Would create: {data['name']}")
                continue

            space, created = VendorOptionSpace.objects.get_or_create(
                name=data["name"],
                defaults={
                    "enterprise_id": data["enterprise_id"],
                    "manufacturer": manufacturer,
                    "description": data["description"],
                },
            )
            if created:
                self.tag_object(space, demo_tag)
            created_spaces.append(space)
            status = "Created" if created else "Already exists"
            self.stdout.write(f"  {status}: {space.name}")

        return created_spaces

    def create_option_definitions(self, vendor_spaces, per_space, demo_tag, dry_run=False):
        """Create option definitions for each vendor space."""
        self.stdout.write("\nCreating OptionDefinition objects...")

        # Vendor-specific option definitions
        vendor_option_definitions = {
            "microsoft-uc": [
                {
                    "name": "UCIdentifier",
                    "code": 1,
                    "option_type": "string",
                    "description": "UC client identifier (e.g., MS-UC-Client)",
                },
                {
                    "name": "URLScheme",
                    "code": 2,
                    "option_type": "string",
                    "description": "URL scheme (typically https)",
                },
                {
                    "name": "WebServerFqdn",
                    "code": 3,
                    "option_type": "string",
                    "description": "FQDN of the Lync/SfB Front End pool",
                },
                {
                    "name": "WebServerPort",
                    "code": 4,
                    "option_type": "uint16",
                    "description": "Web server port (standard 443)",
                },
                {
                    "name": "CertProvRelPath",
                    "code": 5,
                    "option_type": "string",
                    "description": "Relative path to the certificate service",
                },
            ],
            "cisco-ucm": [
                {
                    "name": "tftp-server",
                    "code": 1,
                    "option_type": "ipv4-address",
                    "description": "TFTP server address for phone configuration",
                },
                {
                    "name": "call-manager",
                    "code": 2,
                    "option_type": "ipv4-address",
                    "description": "Cisco Unified Communications Manager address",
                },
                {"name": "firmware-path", "code": 3, "option_type": "string", "description": "Firmware file path"},
                {"name": "vlan-id", "code": 4, "option_type": "uint16", "description": "Voice VLAN ID assignment"},
                {"name": "locale", "code": 5, "option_type": "string", "description": "Phone locale setting"},
            ],
            "fortinet-fortigate": [
                {
                    "name": "fortigate-ip",
                    "code": 1,
                    "option_type": "ipv4-address",
                    "description": "FortiGate management IP",
                },
                {
                    "name": "fortimanager-ip",
                    "code": 2,
                    "option_type": "ipv4-address",
                    "description": "FortiManager IP address",
                },
                {"name": "config-url", "code": 3, "option_type": "string", "description": "Configuration file URL"},
                {"name": "firmware-url", "code": 4, "option_type": "string", "description": "Firmware download URL"},
                {
                    "name": "registration-key",
                    "code": 5,
                    "option_type": "string",
                    "description": "Device registration key",
                },
            ],
            "aruba-iap": [
                {
                    "name": "aruba-controller",
                    "code": 1,
                    "option_type": "ipv4-address",
                    "description": "Aruba controller IP address",
                },
                {
                    "name": "aruba-master",
                    "code": 2,
                    "option_type": "ipv4-address",
                    "description": "Aruba master controller IP",
                },
                {"name": "ap-name", "code": 3, "option_type": "string", "description": "Access point name template"},
                {"name": "ap-group", "code": 4, "option_type": "string", "description": "AP group assignment"},
                {"name": "organization", "code": 5, "option_type": "string", "description": "Organization identifier"},
            ],
            "polycom-phones": [
                {
                    "name": "provisioning-server",
                    "code": 1,
                    "option_type": "ipv4-address",
                    "description": "Polycom provisioning server IP",
                },
                {"name": "config-path", "code": 2, "option_type": "string", "description": "Configuration file path"},
                {
                    "name": "app-server",
                    "code": 3,
                    "option_type": "ipv4-address",
                    "description": "Application server address",
                },
                {
                    "name": "log-server",
                    "code": 4,
                    "option_type": "ipv4-address",
                    "description": "Syslog server for phone logs",
                },
                {"name": "vlan-id", "code": 5, "option_type": "uint16", "description": "Voice VLAN ID"},
            ],
            "yealink-phones": [
                {
                    "name": "autoprov-server",
                    "code": 1,
                    "option_type": "string",
                    "description": "Auto-provisioning server URL",
                },
                {
                    "name": "config-server",
                    "code": 2,
                    "option_type": "ipv4-address",
                    "description": "Configuration server IP",
                },
                {
                    "name": "firmware-server",
                    "code": 3,
                    "option_type": "ipv4-address",
                    "description": "Firmware server IP",
                },
                {
                    "name": "ntp-server",
                    "code": 4,
                    "option_type": "ipv4-address",
                    "description": "NTP server for phone time sync",
                },
                {
                    "name": "syslog-server",
                    "code": 5,
                    "option_type": "ipv4-address",
                    "description": "Syslog server address",
                },
            ],
            "ubiquiti-unifi": [
                {
                    "name": "unifi-controller",
                    "code": 1,
                    "option_type": "ipv4-address",
                    "description": "UniFi controller IP address",
                },
                {"name": "inform-url", "code": 2, "option_type": "string", "description": "UniFi inform URL"},
                {
                    "name": "ssh-keys",
                    "code": 3,
                    "option_type": "string",
                    "description": "SSH public keys for device access",
                },
                {"name": "site-name", "code": 4, "option_type": "string", "description": "UniFi site name"},
                {"name": "firmware-url", "code": 5, "option_type": "string", "description": "Custom firmware URL"},
            ],
            "hp-procurve": [
                {
                    "name": "tftp-server",
                    "code": 1,
                    "option_type": "ipv4-address",
                    "description": "TFTP server for switch configs",
                },
                {"name": "config-file", "code": 2, "option_type": "string", "description": "Configuration file name"},
                {"name": "image-file", "code": 3, "option_type": "string", "description": "Software image file name"},
                {
                    "name": "manager-ip",
                    "code": 4,
                    "option_type": "ipv4-address",
                    "description": "Management station IP",
                },
                {
                    "name": "snmp-server",
                    "code": 5,
                    "option_type": "ipv4-address",
                    "description": "SNMP trap destination",
                },
            ],
            "hp-printers": [
                {
                    "name": "printer-name",
                    "code": 1,
                    "option_type": "string",
                    "description": "Printer device name",
                },
                {
                    "name": "print-server",
                    "code": 2,
                    "option_type": "ipv4-address",
                    "description": "Print server IP address",
                },
                {
                    "name": "config-url",
                    "code": 3,
                    "option_type": "string",
                    "description": "Configuration URL for printer",
                },
                {
                    "name": "firmware-url",
                    "code": 4,
                    "option_type": "string",
                    "description": "Firmware update URL",
                },
                {
                    "name": "snmp-community",
                    "code": 5,
                    "option_type": "string",
                    "description": "SNMP community string",
                },
            ],
        }

        created_definitions = []
        for space in vendor_spaces:
            # Get vendor-specific definitions or fall back to empty list
            definitions = vendor_option_definitions.get(space.name, [])

            for template in definitions[:per_space]:
                if dry_run:
                    self.stdout.write(f"  [DRY-RUN] Would create: {template['name']} in {space.name}")
                    continue

                definition, created = OptionDefinition.objects.get_or_create(
                    vendor_option_space=space,
                    code=template["code"],
                    defaults={
                        "name": template["name"],
                        "option_type": template["option_type"],
                        "description": template["description"],
                    },
                )
                if created:
                    self.tag_object(definition, demo_tag)
                created_definitions.append(definition)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {definition.name} (code {definition.code}) in {space.name}")

        return created_definitions

    def create_option_data(self, count, definitions, vendor_spaces, demo_tag, dry_run=False):
        """Create option data instances - one per definition with realistic values."""
        self.stdout.write("\nCreating OptionData objects...")

        # Standard (builtin) DHCP options with realistic values
        standard_option_values = [
            {
                "distinctive_name": "demo-log-servers",
                "definition_name": "log-servers",
                "data": "192.168.1.50",
                "description": "Syslog server for network devices",
            },
            {
                "distinctive_name": "demo-domain-name",
                "definition_name": "domain-name",
                "data": "example.com",
                "description": "Default domain name",
            },
            {
                "distinctive_name": "demo-domain-name-servers",
                "definition_name": "domain-name-servers",
                "data": "192.168.1.10,192.168.1.11",
                "description": "DNS servers",
            },
            {
                "distinctive_name": "demo-ntp-servers",
                "definition_name": "ntp-servers",
                "data": "192.168.1.1",
                "description": "NTP server for time synchronization",
            },
            {
                "distinctive_name": "demo-tftp-server-name",
                "definition_name": "tftp-server-name",
                "data": "tftp.example.com",
                "description": "TFTP server hostname",
            },
        ]

        # Vendor-specific realistic data values for each option definition
        vendor_option_values = {
            "microsoft-uc": {
                "UCIdentifier": "MS-UC-Client",
                "URLScheme": "https",
                "WebServerFqdn": "lyncpool.contoso.com",
                "WebServerPort": "443",
                "CertProvRelPath": "/CertProv/CertProvisioningService.svc",
            },
            "cisco-ucm": {
                "tftp-server": "10.1.1.10",
                "call-manager": "10.1.1.20",
                "firmware-path": "/firmware/sip78xx.12-5-1SR3-1.loads",
                "vlan-id": "100",
                "locale": "en_US",
            },
            "fortinet-fortigate": {
                "fortigate-ip": "192.168.1.1",
                "fortimanager-ip": "192.168.1.5",
                "config-url": "https://fmg.example.com/config",
                "firmware-url": "https://fmg.example.com/firmware/fortigate.bin",
                "registration-key": "FGT-REG-KEY-2024",
            },
            "aruba-iap": {
                "aruba-controller": "10.10.10.1",
                "aruba-master": "10.10.10.2",
                "ap-name": "AP-%m",
                "ap-group": "default",
                "organization": "Example-Corp",
            },
            "polycom-phones": {
                "provisioning-server": "172.16.1.100",
                "config-path": "/polycom/config/",
                "app-server": "172.16.1.101",
                "log-server": "172.16.1.50",
                "vlan-id": "200",
            },
            "yealink-phones": {
                "autoprov-server": "http://prov.example.com/yealink/",
                "config-server": "192.168.10.100",
                "firmware-server": "192.168.10.101",
                "ntp-server": "192.168.10.1",
                "syslog-server": "192.168.10.50",
            },
            "ubiquiti-unifi": {
                "unifi-controller": "192.168.1.10",
                "inform-url": "http://192.168.1.10:8080/inform",
                "ssh-keys": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...",
                "site-name": "default",
                "firmware-url": "https://dl.ui.com/unifi/firmware/",
            },
            "hp-procurve": {
                "tftp-server": "10.0.0.100",
                "config-file": "procurve-config.cfg",
                "image-file": "K_16_10_0011.swi",
                "manager-ip": "10.0.0.50",
                "snmp-server": "10.0.0.51",
            },
            "hp-printers": {
                "printer-name": "HP-LaserJet-Office",
                "print-server": "192.168.100.10",
                "config-url": "http://printserver.example.com/config",
                "firmware-url": "http://printserver.example.com/firmware",
                "snmp-community": "public",
            },
        }

        created_option_data = []

        # Create one OptionData per definition
        for definition in definitions:
            space = definition.vendor_option_space
            if not space:
                continue

            # Get the realistic value for this definition
            space_values = vendor_option_values.get(space.name, {})
            data = space_values.get(definition.name)

            if not data:
                # Fallback if no specific value defined
                if definition.option_type == "ipv4-address":
                    data = "192.168.1.1"
                elif definition.option_type in ("uint8", "uint16", "uint32"):
                    data = "1"
                else:
                    data = "default-value"

            distinctive_name = f"demo-{space.name}-{definition.name}"

            # Use option43 for vendor options (most common delivery type)
            delivery_type = "option43"

            if dry_run:
                self.stdout.write(f"  [DRY-RUN] Would create: {distinctive_name}")
                continue

            try:
                option_data, created = OptionData.objects.get_or_create(
                    distinctive_name=distinctive_name,
                    defaults={
                        "definition": definition,
                        "vendor_option_space": space,
                        "delivery_type": delivery_type,
                        "data": data,
                        "description": f"{definition.description}",
                    },
                )
                if created:
                    self.tag_object(option_data, demo_tag)
                created_option_data.append(option_data)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {distinctive_name} = {data}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create {distinctive_name}: {e}"))

            # For hp-printers, also create VIVSO variant
            if space.name == "hp-printers":
                distinctive_name_vivso = f"demo-{space.name}-{definition.name}-vivso"
                if not dry_run:
                    try:
                        option_data_vivso, created = OptionData.objects.get_or_create(
                            distinctive_name=distinctive_name_vivso,
                            defaults={
                                "definition": definition,
                                "vendor_option_space": space,
                                "delivery_type": "vivso",
                                "data": data,
                                "description": f"{definition.description} (VIVSO)",
                            },
                        )
                        if created:
                            self.tag_object(option_data_vivso, demo_tag)
                        created_option_data.append(option_data_vivso)
                        status = "Created" if created else "Already exists"
                        self.stdout.write(f"  {status}: {distinctive_name_vivso} = {data} (VIVSO)")
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"  Failed to create {distinctive_name_vivso}: {e}"))

        # Create standard (builtin) option data
        self.stdout.write("\n  Creating standard DHCP option data...")
        for std_opt in standard_option_values:
            if dry_run:
                self.stdout.write(f"  [DRY-RUN] Would create: {std_opt['distinctive_name']}")
                continue

            try:
                # Find the standard option definition
                std_definition = OptionDefinition.objects.filter(
                    name=std_opt["definition_name"],
                    is_standard=True,
                ).first()

                if not std_definition:
                    self.stdout.write(
                        self.style.WARNING(f"  Standard option '{std_opt['definition_name']}' not found, skipping")
                    )
                    continue

                option_data, created = OptionData.objects.get_or_create(
                    distinctive_name=std_opt["distinctive_name"],
                    defaults={
                        "definition": std_definition,
                        "vendor_option_space": None,
                        "delivery_type": "standard",
                        "data": std_opt["data"],
                        "description": std_opt["description"],
                    },
                )
                if created:
                    self.tag_object(option_data, demo_tag)
                created_option_data.append(option_data)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {std_opt['distinctive_name']} = {std_opt['data']}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create {std_opt['distinctive_name']}: {e}"))

        return created_option_data

    def create_client_classes(self, count, option_data_list, demo_tag, dry_run=False):
        """Create client classes with consistent vendor option space assignments."""
        self.stdout.write(f"\nCreating {count} ClientClass objects...")

        # Map client classes to their corresponding vendor option spaces
        # Each class gets its vendor-specific options plus some standard options
        class_templates = [
            {
                "name": "HP-Printers-Option43",
                "test_expression": "substring(option[60].text, 0, 2) == 'HP'",
                "description": "HP printers using Option 43 (vendor-encapsulated-options)",
                "vendor_space": "hp-printers",
                "delivery_type": "option43",
                "standard_options": ["demo-log-servers", "demo-ntp-servers"],
                "only_in_additional_list": False,
            },
            {
                "name": "HP-Printers-VIVSO",
                "test_expression": "substring(option[60].text, 0, 2) == 'HP'",
                "description": "HP printers using Option 125 VIVSO (Vendor-Identifying Vendor-Specific Options)",
                "vendor_space": "hp-printers",
                "delivery_type": "vivso",
                "standard_options": ["demo-domain-name"],
                "only_in_additional_list": True,
            },
            {
                "name": "Cisco-UC-Phones",
                "test_expression": "option[60].text == 'Cisco UC Phone'",
                "description": "Cisco Unified Communications IP phones",
                "vendor_space": "cisco-ucm",
                "standard_options": ["demo-log-servers", "demo-domain-name", "demo-ntp-servers"],
            },
            {
                "name": "Microsoft-Lync-Clients",
                "test_expression": "option[60].text == 'MS-UC-Client'",
                "description": "Microsoft Lync/Skype for Business clients",
                "vendor_space": "microsoft-uc",
                "standard_options": ["demo-domain-name", "demo-domain-name-servers"],
            },
            {
                "name": "PXE-Boot-Clients",
                "test_expression": "option[60].text == 'PXEClient'",
                "description": "PXE boot clients for network installation",
                "next_server": "192.168.1.10",
                "boot_file_name": "pxelinux.0",
                "vendor_space": None,
                "standard_options": ["demo-tftp-server-name", "demo-domain-name"],
            },
            {
                "name": "Polycom-Phones",
                "test_expression": "option[60].text == 'Polycom'",
                "description": "Polycom VoIP phones",
                "vendor_space": "polycom-phones",
                "standard_options": ["demo-log-servers", "demo-ntp-servers", "demo-domain-name"],
            },
            {
                "name": "Yealink-Phones",
                "test_expression": "substring(option[60].text, 0, 7) == 'yealink'",
                "description": "Yealink IP phones",
                "vendor_space": "yealink-phones",
                "standard_options": ["demo-log-servers", "demo-ntp-servers"],
            },
            {
                "name": "Aruba-Access-Points",
                "test_expression": "option[60].text == 'ArubaAP'",
                "description": "Aruba wireless access points",
                "vendor_space": "aruba-iap",
                "standard_options": ["demo-log-servers", "demo-domain-name-servers"],
            },
            {
                "name": "Fortinet-Devices",
                "test_expression": "option[60].text == 'FortiGate'",
                "description": "Fortinet FortiGate devices",
                "vendor_space": "fortinet-fortigate",
                "standard_options": ["demo-ntp-servers", "demo-domain-name"],
            },
            {
                "name": "UniFi-Devices",
                "test_expression": "option[60].text == 'ubnt'",
                "description": "Ubiquiti UniFi devices",
                "vendor_space": "ubiquiti-unifi",
                "standard_options": ["demo-log-servers"],
            },
        ]

        # Build a lookup dict for option data by distinctive_name
        option_data_by_name = {opt.distinctive_name: opt for opt in option_data_list}

        created_classes = []
        for template in class_templates[:count]:
            if dry_run:
                self.stdout.write(f"  [DRY-RUN] Would create: {template['name']}")
                continue

            try:
                client_class, created = ClientClass.objects.get_or_create(
                    name=template["name"],
                    defaults={
                        "test_expression": template["test_expression"],
                        "description": template["description"],
                        "next_server": template.get("next_server"),
                        "server_hostname": template.get("server_hostname", ""),
                        "boot_file_name": template.get("boot_file_name", ""),
                        "only_in_additional_list": template.get("only_in_additional_list", False),
                    },
                )

                # Add option data to the class
                if created:
                    self.tag_object(client_class, demo_tag)

                    options_to_add = []

                    # Add vendor-specific options (all options from that vendor space)
                    vendor_space_name = template.get("vendor_space")
                    delivery_type = template.get("delivery_type")
                    if vendor_space_name:
                        vendor_options = [
                            opt
                            for opt in option_data_list
                            if opt.vendor_option_space
                            and opt.vendor_option_space.name == vendor_space_name
                            and (delivery_type is None or opt.delivery_type == delivery_type)
                        ]
                        options_to_add.extend(vendor_options)

                    # Add standard options specified in the template
                    for std_opt_name in template.get("standard_options", []):
                        if std_opt_name in option_data_by_name:
                            options_to_add.append(option_data_by_name[std_opt_name])

                    if options_to_add:
                        client_class.option_data.set(options_to_add)
                        self.stdout.write(f"    Added {len(options_to_add)} option data entries")

                created_classes.append(client_class)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {client_class.name}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create {template['name']}: {e}"))

        return created_classes

    def create_ha_relationships(self, count, demo_tag, dry_run=False):
        """Create HA relationships."""
        self.stdout.write(f"\nCreating {count} DHCPHARelationship objects...")

        ha_templates = [
            {
                "name": "Primary-DC-HA",
                "mode": "hot-standby",
                "description": "Primary datacenter HA cluster",
            },
            {
                "name": "Load-Balanced-Cluster",
                "mode": "load-balancing",
                "description": "Load balanced DHCP cluster",
            },
            {
                "name": "DR-Passive-Backup",
                "mode": "passive-backup",
                "description": "Disaster recovery passive backup",
            },
        ]

        created_relationships = []
        for template in ha_templates[:count]:
            if dry_run:
                self.stdout.write(f"  [DRY-RUN] Would create: {template['name']}")
                continue

            try:
                relationship, created = DHCPHARelationship.objects.get_or_create(
                    name=template["name"],
                    defaults={
                        "mode": template["mode"],
                        "description": template["description"],
                    },
                )
                if created:
                    self.tag_object(relationship, demo_tag)
                created_relationships.append(relationship)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {relationship.name}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create {template['name']}: {e}"))

        return created_relationships

    def create_dhcp_servers(
        self, count, cluster, mgmt_prefix, service_template, client_classes, demo_tag, dry_run=False
    ):
        """Create DHCP servers with associated VMs, interfaces, and IPs.

        For each server, creates:
        - A VirtualMachine in the demo cluster
        - A VMInterface on the VM
        - An IPAddress from the management prefix (192.0.2.0/24)
        - The DHCPServer linked to the IP
        """
        self.stdout.write(f"\nCreating {count} DHCPServer objects with VMs...")

        server_templates = [
            {"name": "kea-dhcp-primary", "role": "primary", "description": "Primary DHCP server", "ip_offset": 1},
            {"name": "kea-dhcp-secondary", "role": "standby", "description": "Standby DHCP server", "ip_offset": 2},
            {
                "name": "kea-dhcp-standalone",
                "role": None,
                "description": "Standalone DHCP server (no HA)",
                "ip_offset": 3,
            },
            {
                "name": "kea-dhcp-dc2-primary",
                "role": "primary",
                "description": "DC2 Primary DHCP server",
                "ip_offset": 4,
            },
            {
                "name": "kea-dhcp-dc2-secondary",
                "role": "secondary",
                "description": "DC2 Secondary server",
                "ip_offset": 5,
            },
        ]

        created_servers = []  # List of (server, role) tuples
        for template in server_templates[:count]:
            if dry_run:
                self.stdout.write(
                    f"  [DRY-RUN] Would create: {template['name']} with VM and IP 198.51.100.{template['ip_offset']}"
                )
                continue

            try:
                # Calculate IP address from management prefix (198.51.100.0/24 - TEST-NET-2)
                ip_address_str = f"198.51.100.{template['ip_offset']}/24"

                # Create or get the VirtualMachine
                vm, vm_created = VirtualMachine.objects.get_or_create(
                    name=f"vm-{template['name']}",
                    defaults={
                        "cluster": cluster,
                        "status": "active",
                        "description": f"Demo VM for {template['description']}",
                    },
                )
                if vm_created:
                    self.tag_object(vm, demo_tag)
                    self.stdout.write(f"    Created VM: {vm.name}")

                # Create or get the VMInterface
                interface, iface_created = VMInterface.objects.get_or_create(
                    virtual_machine=vm,
                    name="eth0",
                    defaults={
                        "enabled": True,
                        "description": "Management interface",
                    },
                )
                if iface_created:
                    self.tag_object(interface, demo_tag)
                    self.stdout.write(f"    Created Interface: {interface.name}")

                # Create or get the IPAddress and assign to interface
                ip_address, ip_created = IPAddress.objects.get_or_create(
                    address=ip_address_str,
                    defaults={
                        "description": f"Management IP for {template['name']}",
                        "assigned_object_type": ContentType.objects.get_for_model(VMInterface),
                        "assigned_object_id": interface.pk,
                    },
                )
                if ip_created:
                    self.tag_object(ip_address, demo_tag)
                    self.stdout.write(f"    Created IP: {ip_address.address}")
                elif ip_address.assigned_object_id != interface.pk:
                    # Update assignment if IP exists but not assigned to this interface
                    ip_address.assigned_object_type = ContentType.objects.get_for_model(VMInterface)
                    ip_address.assigned_object_id = interface.pk
                    ip_address.save()

                # Set as primary IP for the VM
                if vm.primary_ip4 != ip_address:
                    vm.primary_ip4 = ip_address
                    vm.save()
                    self.stdout.write(f"    Set primary IP for {vm.name}: {ip_address.address}")

                # Create the DHCP Server
                server, created = DHCPServer.objects.get_or_create(
                    name=template["name"],
                    defaults={
                        "ip_address": ip_address,
                        "service_template": service_template,
                        "description": template["description"],
                        "status": "active",
                    },
                )

                # Add client classes to the server (via ClientClass.servers reverse relation)
                if created:
                    self.tag_object(server, demo_tag)
                    if client_classes:
                        classes_to_add = random.sample(client_classes, min(random.randint(1, 3), len(client_classes)))
                        for client_class in classes_to_add:
                            client_class.servers.add(server)

                # Store server with its intended role (None means standalone/no HA)
                created_servers.append((server, template["role"]))
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {server.name} ({ip_address.address})")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create {template['name']}: {e}"))

        return created_servers

    def create_hook_groups(self, servers, demo_tag, dry_run=False):
        """Create demo HookGroups with standard hooks and assign to servers.

        Creates sample hook groups that demonstrate common KEA hook configurations:
        - A "Basic DHCP4 Hooks" group with essential hooks for DHCPv4
        - A "HA Hooks" group for High Availability setups
        """
        self.stdout.write("\nCreating HookGroup objects...")

        # Define hook group configurations
        hook_group_configs = [
            {
                "name": "Basic DHCP4 Hooks",
                "description": "Essential hooks for DHCPv4 operations including lease commands and statistics",
                "library_path": "/usr/lib64/kea/hooks",
                "hook_names": ["Lease Commands", "Statistics Commands", "High Availability"],
            },
            {
                "name": "Extended DHCP4 Hooks",
                "description": "Additional hooks for advanced DHCPv4 features",
                "library_path": "/usr/lib64/kea/hooks",
                "hook_names": ["Host Commands", "Subnet Commands", "Config Backend Commands"],
            },
        ]

        created_groups = []
        for config in hook_group_configs:
            if dry_run:
                self.stdout.write(f"  [DRY-RUN] Would create HookGroup: {config['name']}")
                continue

            try:
                hook_group, created = HookGroup.objects.get_or_create(
                    name=config["name"],
                    defaults={
                        "description": config["description"],
                        "library_path": config["library_path"],
                    },
                )

                if created:
                    self.tag_object(hook_group, demo_tag)

                    # Add standard hooks to the group
                    for hook_name in config["hook_names"]:
                        try:
                            hook = Hook.objects.get(name=hook_name)
                            hook_group.hooks.add(hook)
                            self.stdout.write(f"    Added hook '{hook_name}' to '{config['name']}'")
                        except Hook.DoesNotExist:
                            self.stdout.write(self.style.WARNING(f"    Hook '{hook_name}' not found - skipping"))

                    self.stdout.write(f"  Created: {hook_group.name}")
                else:
                    self.stdout.write(f"  Already exists: {hook_group.name}")

                created_groups.append(hook_group)

            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create {config['name']}: {e}"))

        # Assign first hook group to the first server (if any)
        if created_groups and servers and not dry_run:
            first_group = created_groups[0]
            # servers is a list of (server, role) tuples
            first_server = servers[0][0] if isinstance(servers[0], tuple) else servers[0]
            first_group.servers.add(first_server)
            self.stdout.write(f"  Assigned '{first_group.name}' to server '{first_server.name}'")

            # If we have a second group and more servers, assign it to another server
            if len(created_groups) > 1 and len(servers) > 1:
                second_group = created_groups[1]
                second_server = servers[1][0] if isinstance(servers[1], tuple) else servers[1]
                second_group.servers.add(second_server)
                self.stdout.write(f"  Assigned '{second_group.name}' to server '{second_server.name}'")

        return created_groups

    def assign_servers_to_ha(self, servers_with_roles, ha_relationships, dry_run=False):
        """Assign DHCP servers to HA relationships.

        Args:
            servers_with_roles: List of (server, role) tuples. Role=None means standalone.
            ha_relationships: List of HA relationships to assign servers to.
            dry_run: If True, only print what would be done.
        """
        if not servers_with_roles or not ha_relationships:
            return

        self.stdout.write("\nAssigning DHCP servers to HA relationships...")

        # Filter out standalone servers (role=None)
        ha_servers = [(s, r) for s, r in servers_with_roles if r is not None]
        standalone_servers = [(s, r) for s, r in servers_with_roles if r is None]

        if standalone_servers:
            for server, _ in standalone_servers:
                self.stdout.write(f"  Skipping {server.name} - standalone server (no HA)")

        # Assign first two HA servers to the first HA relationship
        ha_relationship = ha_relationships[0]
        for server, role in ha_servers[:2]:
            if dry_run:
                self.stdout.write(f"  [DRY-RUN] Would assign {server.name} to {ha_relationship.name} as {role}")
                continue

            try:
                # Refresh server from DB to ensure ip_address is properly loaded
                server.refresh_from_db()
                server.ha_relationship = ha_relationship
                server.ha_role = role
                server.ha_address = str(server.ip_address.address.ip)
                server.ha_port = 8080
                server.ha_tls = False
                server.save()
                self.stdout.write(f"  Assigned {server.name} to {ha_relationship.name} as {role}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to assign {server.name} to HA: {e}"))

    def create_dhcp_subnets(
        self, count, prefixes, servers_with_roles, option_data_list, client_classes, demo_tag, dry_run=False
    ):
        """Create prefix DHCP configurations.

        Only assigns prefixes to primary servers (ha_role='primary' or not in HA).
        This mirrors the constraint enforced in the GUI where non-primary servers
        are automatically redirected to their primary.

        Args:
            servers_with_roles: List of (server, role) tuples from create_dhcp_servers.
        """
        self.stdout.write(f"\nCreating {count} Subnet objects...")

        if not prefixes:
            self.stdout.write(self.style.WARNING("  Skipping DHCP Subnet creation - no suitable prefixes available"))
            return []

        if not servers_with_roles:
            self.stdout.write(self.style.WARNING("  Skipping DHCP Subnet creation - no DHCP servers available"))
            return []

        # Extract just the servers from tuples
        servers = [s for s, _ in servers_with_roles]

        # Filter to only primary servers (ha_role='primary' or not in HA relationship)
        primary_servers = [s for s in servers if s.is_ha_primary()]
        if not primary_servers:
            self.stdout.write(self.style.WARNING("  Skipping DHCP Subnet creation - no primary DHCP servers available"))
            return []

        self.stdout.write(
            f"  Using {len(primary_servers)} primary server(s): {', '.join(s.name for s in primary_servers)}"
        )

        created_configs = []
        for i, prefix in enumerate(prefixes[:count]):
            if dry_run:
                self.stdout.write(f"  [DRY-RUN] Would create config for: {prefix}")
                continue

            try:
                server = primary_servers[i % len(primary_servers)]

                config, created = Subnet.objects.get_or_create(
                    prefix=prefix,
                    defaults={
                        "server": server,
                        "valid_lifetime": random.choice([3600, 7200, 14400]),
                        "max_lifetime": random.choice([7200, 14400, 28800]),
                        "routers_option_offset": 1,
                    },
                )

                # Add option data and client classes
                if created:
                    self.tag_object(config, demo_tag)
                    if option_data_list:
                        options_to_add = random.sample(
                            option_data_list, min(random.randint(0, 2), len(option_data_list))
                        )
                        config.option_data.set(options_to_add)
                    if client_classes:
                        classes_to_add = random.sample(client_classes, min(random.randint(0, 2), len(client_classes)))
                        config.evaluate_additional_classes.set(classes_to_add)

                created_configs.append(config)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {prefix} -> {server.name}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create config for {prefix}: {e}"))

        return created_configs

    def create_subnet_pools(self, dhcp_subnets, client_classes, option_data_list, demo_tag, dry_run=False):
        """Create IP Ranges and SubnetPool configurations for demo subnets.

        For each subnet, creates 2-3 IP Ranges within the prefix and optionally
        configures them with restricting client classes, evaluate-additional-classes,
        and pool-specific option data.

        Demonstrates correct KEA semantics:
        - Normal classes (only_in_additional_list=False) can be used as pool
          restrictions directly since they are globally evaluated.
        - only_in_additional_list classes can be used as pool restrictions ONLY
          when the parent subnet lists them in evaluate_additional_classes
          (which triggers their evaluation before pool selection).
        """
        self.stdout.write("\nCreating IP Ranges and SubnetPool configurations...")

        if not dhcp_subnets:
            self.stdout.write(self.style.WARNING("  Skipping SubnetPool creation - no subnets available"))
            return []

        import netaddr

        # Separate client classes by type for correct assignment
        normal_classes = [cc for cc in client_classes if not cc.only_in_additional_list]
        only_additional_classes = [cc for cc in client_classes if cc.only_in_additional_list]

        created_pools = []
        for subnet in dhcp_subnets:
            prefix_network = subnet.prefix.prefix
            if isinstance(prefix_network, str):
                prefix_network = netaddr.IPNetwork(prefix_network)

            # Skip if prefix is too small for multiple pools
            if prefix_network.size < 32:
                self.stdout.write(f"  Skipping {subnet}: prefix too small for demo pools")
                continue

            # Check if this prefix already has child IP ranges
            existing_ranges = subnet.prefix.get_child_ranges().count()
            if existing_ranges > 0:
                self.stdout.write(f"  Skipping {subnet}: already has {existing_ranges} IP range(s)")
                continue

            if dry_run:
                self.stdout.write(f"  [DRY-RUN] Would create IP ranges and pools for: {subnet}")
                continue

            try:
                # Calculate pool boundaries within the prefix, leaving room for
                # the router (.1) and some headroom at the top
                network_addr = int(prefix_network.network)
                broadcast_addr = int(prefix_network.broadcast)
                usable_start = network_addr + 10  # Skip .0-.9 (network, router, static)
                usable_end = broadcast_addr - 5  # Leave .251-.255 (broadcast, reserved)
                usable_size = usable_end - usable_start

                if usable_size < 30:
                    self.stdout.write(f"  Skipping {subnet}: not enough usable space for demo pools")
                    continue

                # Split usable space into 2-3 pools with gaps between them
                pool_count = 2 if usable_size < 100 else 3
                pool_size = usable_size // (pool_count + 1)  # +1 for gaps
                gap_size = max(5, pool_size // 4)

                ip_ranges = []
                current_start = usable_start
                for p_idx in range(pool_count):
                    pool_end = min(current_start + pool_size - 1, usable_end)
                    if pool_end <= current_start:
                        break

                    start_ip = netaddr.IPAddress(current_start)
                    end_ip = netaddr.IPAddress(pool_end)
                    prefix_len = prefix_network.prefixlen

                    ip_range, range_created = IPRange.objects.get_or_create(
                        start_address=netaddr.IPNetwork(f"{start_ip}/{prefix_len}"),
                        end_address=netaddr.IPNetwork(f"{end_ip}/{prefix_len}"),
                        defaults={
                            "description": f"Demo pool {p_idx + 1} for {subnet.prefix}",
                        },
                    )
                    if range_created:
                        self.tag_object(ip_range, demo_tag)
                    ip_ranges.append(ip_range)
                    self.stdout.write(f"    Created IP Range: {str(start_ip)} - {str(end_ip)}")

                    current_start = pool_end + gap_size + 1

                if not ip_ranges:
                    continue

                # --- Pool configuration scenarios ---
                # We demonstrate several patterns across the pools:
                #
                # Pool 0 (first pool): Restricted by a normal class (globally
                #   evaluated, so no special subnet config needed).
                #
                # Pool 1 (second pool): Restricted by an only_in_additional_list
                #   class — requires the parent subnet to list the class in
                #   evaluate_additional_classes so KEA evaluates it before pool
                #   selection. Also gets pool-level option data.
                #
                # Pool 2 (third pool, if exists): No restriction, but has
                #   evaluate_additional_classes at pool level to trigger extra
                #   class evaluation for clients in this pool.

                for p_idx, ip_range in enumerate(ip_ranges):
                    pool_kwargs = {
                        "subnet": subnet,
                        "ip_range": ip_range,
                    }
                    pool_eval_classes = []
                    pool_description = ""

                    if p_idx == 0 and normal_classes:
                        # Scenario 1: Normal class as pool restriction
                        restricting_class = random.choice(normal_classes)
                        pool_kwargs["client_class"] = restricting_class
                        pool_description = f"Restricted to '{restricting_class.name}' (globally evaluated class)"
                        self.stdout.write(
                            f"    Pool {p_idx + 1}: restricted by normal class '{restricting_class.name}'"
                        )

                    elif p_idx == 1 and only_additional_classes:
                        # Scenario 2: only_in_additional_list class as pool restriction
                        # Must add to subnet's evaluate_additional_classes first!
                        restricting_class = random.choice(only_additional_classes)
                        pool_kwargs["client_class"] = restricting_class

                        # Ensure the parent subnet evaluates this class
                        subnet.evaluate_additional_classes.add(restricting_class)
                        self.stdout.write(
                            f"    Pool {p_idx + 1}: restricted by only-in-additional "
                            f"class '{restricting_class.name}' "
                            f"(added to subnet evaluate-additional-classes)"
                        )
                        pool_description = (
                            f"Restricted to '{restricting_class.name}' "
                            f"(only-in-additional-list — subnet triggers evaluation)"
                        )

                        # Also add pool-level option data
                        if option_data_list:
                            pool_opts = random.sample(
                                option_data_list,
                                min(random.randint(1, 2), len(option_data_list)),
                            )

                    elif p_idx == 2:
                        # Scenario 3: No restriction, but pool-level evaluate-additional
                        if only_additional_classes:
                            pool_eval_classes = random.sample(
                                only_additional_classes,
                                min(1, len(only_additional_classes)),
                            )
                            class_names = ", ".join(c.name for c in pool_eval_classes)
                            self.stdout.write(
                                f"    Pool {p_idx + 1}: no restriction, evaluate-additional classes: [{class_names}]"
                            )
                            pool_description = f"Open pool with additional class evaluation: {class_names}"
                        else:
                            pool_description = "Open pool (no restrictions)"
                            self.stdout.write(f"    Pool {p_idx + 1}: open (no restrictions)")
                    else:
                        pool_description = "Open pool (no restrictions)"
                        self.stdout.write(f"    Pool {p_idx + 1}: open (no restrictions)")

                    pool_kwargs["description"] = pool_description

                    subnet_pool, pool_created = SubnetPool.objects.get_or_create(
                        subnet=subnet,
                        ip_range=ip_range,
                        defaults={k: v for k, v in pool_kwargs.items() if k not in ("subnet", "ip_range")},
                    )

                    if pool_created:
                        self.tag_object(subnet_pool, demo_tag)

                        # Set evaluate_additional_classes M2M
                        if pool_eval_classes:
                            subnet_pool.evaluate_additional_classes.set(pool_eval_classes)

                        # Set pool-level option data for scenario 2
                        if p_idx == 1 and option_data_list:
                            pool_opts = random.sample(
                                option_data_list,
                                min(random.randint(1, 2), len(option_data_list)),
                            )
                            subnet_pool.option_data.set(pool_opts)
                            self.stdout.write(f"      Added {len(pool_opts)} pool-level option data entries")

                    created_pools.append(subnet_pool)

                self.stdout.write(f"  Configured {len(ip_ranges)} pool(s) for {subnet}")

            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create pools for {subnet}: {e}"))

        return created_pools

    def handle(self, *args, **options):
        config = self.get_config()
        force = options["force"]
        clear = options["clear"]
        dry_run = options["dry_run"]
        purge_demo_data = options["purge_demo_data"]

        self.stdout.write(self.style.MIGRATE_HEADING("NetBox DHCP KEA Plugin - Demo Data Generator"))
        self.stdout.write("")

        # Handle --purge-demo-data: only delete, don't generate
        if purge_demo_data:
            self.stdout.write("Purging demo-tagged data only (no generation)...\n")
            self.clear_existing_data()
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Demo data purge complete!"))
            return

        # Check if enabled
        if not config["enabled"] and not force:
            raise CommandError(
                "Demo data generation is disabled in PLUGINS_CONFIG. "
                "Set 'enabled': True in the 'demo_data' config or use --force."
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made\n"))

        # Show configuration
        self.stdout.write("Configuration:")
        self.stdout.write(f"  - Vendor Option Spaces: {config['vendor_option_spaces']}")
        self.stdout.write(f"  - Option Definitions per Space: {config['option_definitions_per_space']}")
        self.stdout.write(f"  - Option Data: {config['option_data']}")
        self.stdout.write(f"  - Client Classes: {config['client_classes']}")
        self.stdout.write(f"  - DHCP Servers: {config['dhcp_servers']}")
        self.stdout.write(f"  - HA Relationships: {config['ha_relationships']}")
        self.stdout.write(f"  - DHCP Subnets: {config['dhcp_subnets']}")
        self.stdout.write("")

        # Clear existing data if requested
        if clear and not dry_run:
            self.clear_existing_data()

        # Check prerequisites
        self.stdout.write("Checking prerequisites...")
        prerequisites = self.get_or_create_prerequisites()

        # Get demo tag from prerequisites (already created there)
        demo_tag = prerequisites.get("demo_tag") if not dry_run else None

        # Create data in dependency order
        vendor_spaces = self.create_vendor_option_spaces(
            config["vendor_option_spaces"],
            prerequisites["manufacturer"],
            demo_tag,
            dry_run=dry_run,
        )

        definitions = self.create_option_definitions(
            vendor_spaces,
            config["option_definitions_per_space"],
            demo_tag,
            dry_run=dry_run,
        )

        option_data_list = self.create_option_data(
            config["option_data"],
            definitions,
            vendor_spaces,
            demo_tag,
            dry_run=dry_run,
        )

        client_classes = self.create_client_classes(
            config["client_classes"],
            option_data_list,
            demo_tag,
            dry_run=dry_run,
        )

        servers = self.create_dhcp_servers(
            config["dhcp_servers"],
            prerequisites["cluster"],
            prerequisites["mgmt_prefix"],
            prerequisites["service_template"],
            client_classes,
            demo_tag,
            dry_run=dry_run,
        )

        ha_relationships = self.create_ha_relationships(
            config["ha_relationships"],
            demo_tag,
            dry_run=dry_run,
        )

        # Assign servers to HA relationships
        self.assign_servers_to_ha(servers, ha_relationships, dry_run=dry_run)

        dhcp_subnets = self.create_dhcp_subnets(
            config["dhcp_subnets"],
            prerequisites["prefixes"],
            servers,
            option_data_list,
            client_classes,
            demo_tag,
            dry_run=dry_run,
        )

        # Create subnet pools with IP ranges and client class restrictions
        subnet_pools = self.create_subnet_pools(
            dhcp_subnets,
            client_classes,
            option_data_list,
            demo_tag,
            dry_run=dry_run,
        )

        # Create hook groups and assign to servers
        hook_groups = self.create_hook_groups(
            servers,
            demo_tag,
            dry_run=dry_run,
        )

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo data generation complete!"))
        if not dry_run:
            self.stdout.write("")
            self.stdout.write("Summary:")
            self.stdout.write(f"  - Vendor Option Spaces: {len(vendor_spaces)}")
            self.stdout.write(f"  - Option Definitions: {len(definitions)}")
            self.stdout.write(f"  - Option Data: {len(option_data_list)}")
            self.stdout.write(f"  - Client Classes: {len(client_classes)}")
            self.stdout.write(f"  - DHCP Servers: {len(servers)}")
            self.stdout.write(f"  - HA Relationships: {len(ha_relationships)}")
            self.stdout.write(f"  - DHCP Subnets: {len(dhcp_subnets)}")
            self.stdout.write(f"  - Subnet Pools: {len(subnet_pools)}")
            self.stdout.write(f"  - Hook Groups: {len(hook_groups)}")
