from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem
from netbox.plugins.utils import get_plugin_config

menu_name = get_plugin_config("netbox_dhcp_kea_plugin", "menu_name")
top_level_menu = get_plugin_config("netbox_dhcp_kea_plugin", "top_level_menu")

# Define menu items
vendoroptionspace_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:vendoroptionspace_list",
    link_text="Vendor Option Spaces",
    permissions=["netbox_dhcp_kea_plugin.view_vendoroptionspace"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:vendoroptionspace_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_vendoroptionspace"],
        ),
    ),
)

optiondefinition_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:optiondefinition_list",
    link_text="Option Definitions",
    permissions=["netbox_dhcp_kea_plugin.view_optiondefinition"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:optiondefinition_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_optiondefinition"],
        ),
    ),
)

optiondata_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:optiondata_list",
    link_text="Option Data",
    permissions=["netbox_dhcp_kea_plugin.view_optiondata"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:optiondata_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_optiondata"],
        ),
    ),
)

dhcpserver_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:dhcpserver_list",
    link_text="DHCP Servers",
    permissions=["netbox_dhcp_kea_plugin.view_dhcpserver"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:dhcpserver_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_dhcpserver"],
        ),
    ),
)

clientclass_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:clientclass_list",
    link_text="Client Classes",
    permissions=["netbox_dhcp_kea_plugin.view_clientclass"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:clientclass_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_clientclass"],
        ),
    ),
)

prefixdhcpconfig_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_list",
    link_text="DHCP Prefixes",
    permissions=["netbox_dhcp_kea_plugin.view_prefixdhcpconfig"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_prefixdhcpconfig"],
        ),
    ),
)

dhcpharelationship_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:dhcpharelationship_list",
    link_text="HA Relationships",
    permissions=["netbox_dhcp_kea_plugin.view_dhcpharelationship"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:dhcpharelationship_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_dhcpharelationship"],
        ),
    ),
)


if top_level_menu:
    menu = PluginMenu(
        label=menu_name,
        groups=(
            (
                "Server Configuration",
                (
                    dhcpserver_menu_item,
                    prefixdhcpconfig_menu_item,
                    clientclass_menu_item,
                ),
            ),
            (
                "High Availability",
                (dhcpharelationship_menu_item,),
            ),
            (
                "Option Definition",
                (
                    optiondefinition_menu_item,
                    optiondata_menu_item,
                    vendoroptionspace_menu_item,
                ),
            ),
        ),
        icon_class="mdi mdi-bird",
    )
else:
    menu_items = (
        dhcpserver_menu_item,
        prefixdhcpconfig_menu_item,
        clientclass_menu_item,
        dhcpharelationship_menu_item,
        optiondefinition_menu_item,
        optiondata_menu_item,
        vendoroptionspace_menu_item,
    )
