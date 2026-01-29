"""Top-level package for NetBox DHCP-KEA Plugin."""

__author__ = """Łukasz Polański"""
__email__ = "wookasz@gmail.com"
__version__ = "0.2.0"


from netbox.plugins import PluginConfig
from rest_framework import serializers


class DHCPKEAConfig(PluginConfig):
    name = "netbox_dhcp_kea_plugin"
    verbose_name = "NetBox DHCP-KEA Plugin"
    description = "NetBox plugin for KEA DHCP configuration"
    version = "version"
    base_url = "netbox_dhcp_kea_plugin"
    default_settings = {
        "top_level_menu": True,
        "menu_name": "DHCP KEA",
        "demo_data": {
            "enabled": False,
            "vendor_option_spaces": 3,
            "option_definitions_per_space": 5,
            "option_data": 10,
            "client_classes": 5,
            "dhcp_servers": 3,
            "ha_relationships": 1,
            "prefix_configs": 5,
        },
    }

    def ready(self):
        """Extend Prefix API serializer with DHCP config and relay targets."""
        super().ready()

        from ipam.api.serializers import PrefixSerializer

        from .models import PrefixDHCPConfig

        def get_dhcp_config(self, obj):
            """Return DHCP config with server info and relay targets."""
            try:
                config = obj.dhcp_config
            except PrefixDHCPConfig.DoesNotExist:
                return None

            if not config or not config.server:
                return None

            server = config.server

            # Build relay targets list
            relay_targets = []
            if server.ha_relationship:
                for s in server.ha_relationship.servers.all():
                    if s.ip_address:
                        relay_targets.append(str(s.ip_address.address.ip))
            elif server.ip_address:
                relay_targets.append(str(server.ip_address.address.ip))

            return {
                "server": {
                    "name": server.name,
                    "url": server.ha_url
                    or (f"http://{server.ip_address.address.ip}:8000/" if server.ip_address else None),
                },
                "relay_targets": relay_targets,
            }

        # Create the SerializerMethodField
        dhcp_config_field = serializers.SerializerMethodField()

        # Add to _declared_fields (this is what DRF actually uses)
        PrefixSerializer._declared_fields["dhcp_config"] = dhcp_config_field

        # Add the method to the class
        PrefixSerializer.get_dhcp_config = get_dhcp_config

        # Add dhcp_config to the fields list
        if hasattr(PrefixSerializer.Meta, "fields") and isinstance(PrefixSerializer.Meta.fields, list):
            if "dhcp_config" not in PrefixSerializer.Meta.fields:
                PrefixSerializer.Meta.fields.append("dhcp_config")


config = DHCPKEAConfig
