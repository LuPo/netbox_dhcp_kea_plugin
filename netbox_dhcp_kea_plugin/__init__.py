"""Top-level package for NetBox DHCP-KEA Plugin."""

__author__ = """Łukasz Polański"""
__email__ = "wookasz@gmail.com"
__version__ = "0.2.0"


from netbox.plugins import PluginConfig


class DHCPKEAConfig(PluginConfig):
    name = "netbox_dhcp_kea_plugin"
    verbose_name = "NetBox DHCP-KEA Plugin"
    description = "NetBox plugin for KEA DHCP configuration"
    version = "version"
    base_url = "netbox_dhcp_kea_plugin"
    default_settings = {
        "top_level_menu": True,
        "menu_name": "DHCP KEA",
    }


config = DHCPKEAConfig
