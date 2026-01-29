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
                'prefix_configs': 5,
            }
        }
    }
"""

import random

from dcim.models import Manufacturer
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from extras.models import Tag
from ipam.models import IPAddress, Prefix, ServiceTemplate
from netbox.plugins.utils import get_plugin_config
from virtualization.models import Cluster, ClusterType, VirtualMachine, VMInterface

from netbox_dhcp_kea_plugin import DHCPKEAConfig
from netbox_dhcp_kea_plugin.models import (
    ClientClass,
    DHCPHARelationship,
    DHCPServer,
    OptionData,
    OptionDefinition,
    PrefixDHCPConfig,
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

        # First, delete PrefixDHCPConfigs that are tagged OR reference demo-tagged servers
        demo_servers = DHCPServer.objects.filter(tags=demo_tag)
        count = PrefixDHCPConfig.objects.filter(tags=demo_tag).count()
        count += PrefixDHCPConfig.objects.filter(server__in=demo_servers).exclude(tags=demo_tag).count()
        PrefixDHCPConfig.objects.filter(tags=demo_tag).delete()
        PrefixDHCPConfig.objects.filter(server__in=demo_servers).delete()
        self.stdout.write(f"  - Deleted {count} PrefixDHCPConfig objects")

        # Clear HA relationships from demo servers before deleting
        demo_servers.update(ha_relationship=None, ha_role="", ha_url="")

        count = DHCPServer.objects.filter(tags=demo_tag).count()
        DHCPServer.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} DHCPServer objects")

        count = DHCPHARelationship.objects.filter(tags=demo_tag).count()
        DHCPHARelationship.objects.filter(tags=demo_tag).delete()
        self.stdout.write(f"  - Deleted {count} DHCPHARelationship objects")

        count = ClientClass.objects.filter(tags=demo_tag).count()
        ClientClass.objects.filter(tags=demo_tag).delete()
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
        total = len(vendor_spaces) * per_space
        self.stdout.write(f"\nCreating {total} OptionDefinition objects...")

        option_templates = [
            {"name": "tftp-server", "code": 1, "option_type": "ipv4-address", "description": "TFTP server address"},
            {"name": "config-file", "code": 2, "option_type": "string", "description": "Configuration file path"},
            {"name": "firmware-path", "code": 3, "option_type": "string", "description": "Firmware file path"},
            {"name": "vlan-id", "code": 4, "option_type": "uint16", "description": "VLAN ID assignment"},
            {"name": "ntp-server", "code": 5, "option_type": "ipv4-address", "description": "NTP server address"},
            {"name": "syslog-server", "code": 6, "option_type": "ipv4-address", "description": "Syslog server"},
            {"name": "provisioning-url", "code": 7, "option_type": "string", "description": "Provisioning URL"},
            {"name": "controller-ip", "code": 8, "option_type": "ipv4-address", "description": "Controller IP"},
            {"name": "device-mode", "code": 9, "option_type": "uint8", "description": "Device operation mode"},
            {"name": "backup-server", "code": 10, "option_type": "ipv4-address", "description": "Backup server IP"},
        ]

        created_definitions = []
        for space in vendor_spaces:
            for template in option_templates[:per_space]:
                if dry_run:
                    self.stdout.write(f"  [DRY-RUN] Would create: {template['name']} in {space.name}")
                    continue

                definition, created = OptionDefinition.objects.get_or_create(
                    vendor_option_space=space,
                    code=template["code"],
                    defaults={
                        "name": template["name"],
                        "option_type": template["option_type"],
                        "description": f"{template['description']} for {space.name}",
                    },
                )
                if created:
                    self.tag_object(definition, demo_tag)
                created_definitions.append(definition)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {definition.name} (code {definition.code}) in {space.name}")

        return created_definitions

    def create_option_data(self, count, definitions, vendor_spaces, demo_tag, dry_run=False):
        """Create option data instances."""
        self.stdout.write(f"\nCreating {count} OptionData objects...")

        # Sample data values
        ip_addresses = ["192.168.1.10", "10.0.0.50", "172.16.0.100", "192.168.100.1"]
        paths = ["/tftpboot/config.cfg", "/firmware/latest.bin", "/provisioning/device.xml"]
        urls = ["http://prov.example.com/config", "https://firmware.example.com/update"]

        created_option_data = []
        delivery_types = ["standard", "option43", "vivso"]

        for i in range(count):
            if definitions:
                definition = random.choice(definitions)
                space = definition.vendor_option_space
            else:
                definition = None
                space = random.choice(vendor_spaces) if vendor_spaces else None

            # Generate appropriate data based on option type
            if definition:
                if definition.option_type == "ipv4-address":
                    data = random.choice(ip_addresses)
                elif definition.option_type in ("uint8", "uint16", "uint32"):
                    data = str(random.randint(1, 255))
                else:
                    data = random.choice(paths + urls)
                distinctive_name = f"demo-{definition.name}-{i + 1}"
            else:
                data = random.choice(ip_addresses + paths)
                distinctive_name = f"demo-option-data-{i + 1}"

            delivery_type = random.choice(delivery_types)
            # VIVSO requires enterprise_id
            if delivery_type == "vivso" and (not space or not space.enterprise_id):
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
                        "description": f"Demo option data {i + 1}",
                    },
                )
                if created:
                    self.tag_object(option_data, demo_tag)
                created_option_data.append(option_data)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {distinctive_name}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create {distinctive_name}: {e}"))

        return created_option_data

    def create_client_classes(self, count, option_data_list, demo_tag, dry_run=False):
        """Create client classes."""
        self.stdout.write(f"\nCreating {count} ClientClass objects...")

        class_templates = [
            {
                "name": "Cisco-UC-Phones",
                "test_expression": "option[60].text == 'Cisco UC Phone'",
                "description": "Cisco Unified Communications IP phones",
            },
            {
                "name": "Microsoft-Lync-Clients",
                "test_expression": "option[60].text == 'MS-UC-Client'",
                "description": "Microsoft Lync/Skype for Business clients",
            },
            {
                "name": "PXE-Boot-Clients",
                "test_expression": "option[60].text == 'PXEClient'",
                "description": "PXE boot clients for network installation",
                "next_server": "192.168.1.10",
                "boot_file_name": "pxelinux.0",
            },
            {
                "name": "Polycom-Phones",
                "test_expression": "option[60].text == 'Polycom'",
                "description": "Polycom VoIP phones",
            },
            {
                "name": "Yealink-Phones",
                "test_expression": "substring(option[60].text, 0, 7) == 'yealink'",
                "description": "Yealink IP phones",
            },
            {
                "name": "VOIP-Devices",
                "test_expression": "member('Cisco-UC-Phones') or member('Polycom-Phones') or member('Yealink-Phones')",
                "description": "All VoIP devices",
            },
            {
                "name": "Network-Printers",
                "test_expression": "option[60].text == 'HP Printer'",
                "description": "Network printers",
            },
            {
                "name": "Access-Points",
                "test_expression": "option[60].text == 'Aruba AP'",
                "description": "Wireless access points",
            },
        ]

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
                    },
                )

                # Add some option data to the class
                if created:
                    self.tag_object(client_class, demo_tag)
                    if option_data_list:
                        options_to_add = random.sample(
                            option_data_list, min(random.randint(1, 3), len(option_data_list))
                        )
                        client_class.option_data.set(options_to_add)

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

        created_servers = []
        for i, template in enumerate(server_templates[:count]):
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
                        "is_active": True,
                    },
                )

                # Store the intended role for later HA assignment (None means standalone/no HA)
                server._intended_ha_role = template["role"]

                # Add client classes to the server (via ClientClass.servers reverse relation)
                if created:
                    self.tag_object(server, demo_tag)
                    if client_classes:
                        classes_to_add = random.sample(client_classes, min(random.randint(1, 3), len(client_classes)))
                        for client_class in classes_to_add:
                            client_class.servers.add(server)

                created_servers.append(server)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {server.name} ({ip_address.address})")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create {template['name']}: {e}"))

        return created_servers

    def assign_servers_to_ha(self, servers, ha_relationships, dry_run=False):
        """Assign DHCP servers to HA relationships.

        Servers with _intended_ha_role=None are standalone and not assigned to HA.
        """
        if not servers or not ha_relationships:
            return

        self.stdout.write("\nAssigning DHCP servers to HA relationships...")

        # Filter out standalone servers (role=None)
        ha_servers = [s for s in servers if getattr(s, "_intended_ha_role", None) is not None]
        standalone_servers = [s for s in servers if getattr(s, "_intended_ha_role", None) is None]

        if standalone_servers:
            for server in standalone_servers:
                self.stdout.write(f"  Skipping {server.name} - standalone server (no HA)")

        # Assign first two HA servers to the first HA relationship
        ha_relationship = ha_relationships[0]
        for i, server in enumerate(ha_servers[:2]):
            if dry_run:
                role = getattr(server, "_intended_ha_role", "primary" if i == 0 else "standby")
                self.stdout.write(f"  [DRY-RUN] Would assign {server.name} to {ha_relationship.name} as {role}")
                continue

            try:
                # Store role before refresh_from_db (which would lose the dynamic attribute)
                role = getattr(server, "_intended_ha_role", "primary" if i == 0 else "standby")
                # Refresh server from DB to ensure ip_address is properly loaded
                server.refresh_from_db()
                server.ha_relationship = ha_relationship
                server.ha_role = role
                server.ha_url = f"http://{server.ip_address.address.ip}:8000/"
                server.save()
                self.stdout.write(f"  Assigned {server.name} to {ha_relationship.name} as {role}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to assign {server.name} to HA: {e}"))

    def create_prefix_configs(
        self, count, prefixes, servers, option_data_list, client_classes, demo_tag, dry_run=False
    ):
        """Create prefix DHCP configurations.

        Only assigns prefixes to primary servers (ha_role='primary' or not in HA).
        This mirrors the constraint enforced in the GUI where non-primary servers
        are automatically redirected to their primary.
        """
        self.stdout.write(f"\nCreating {count} PrefixDHCPConfig objects...")

        if not prefixes:
            self.stdout.write(self.style.WARNING("  Skipping prefix config creation - no suitable prefixes available"))
            return []

        if not servers:
            self.stdout.write(self.style.WARNING("  Skipping prefix config creation - no DHCP servers available"))
            return []

        # Filter to only primary servers (ha_role='primary' or not in HA relationship)
        primary_servers = [s for s in servers if s.is_ha_primary()]
        if not primary_servers:
            self.stdout.write(
                self.style.WARNING("  Skipping prefix config creation - no primary DHCP servers available")
            )
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

                config, created = PrefixDHCPConfig.objects.get_or_create(
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
                        config.client_classes.set(classes_to_add)

                created_configs.append(config)
                status = "Created" if created else "Already exists"
                self.stdout.write(f"  {status}: {prefix} -> {server.name}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Failed to create config for {prefix}: {e}"))

        return created_configs

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
        self.stdout.write(f"  - Prefix Configs: {config['prefix_configs']}")
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

        prefix_configs = self.create_prefix_configs(
            config["prefix_configs"],
            prerequisites["prefixes"],
            servers,
            option_data_list,
            client_classes,
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
            self.stdout.write(f"  - Prefix Configs: {len(prefix_configs)}")
