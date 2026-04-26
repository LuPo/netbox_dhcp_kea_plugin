from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem
from netbox.plugins.utils import get_plugin_config

menu_name = get_plugin_config("netbox_dhcp_kea_plugin", "menu_name")
top_level_menu = get_plugin_config("netbox_dhcp_kea_plugin", "top_level_menu")
enable_stork = get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork")
enable_ddns = get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns")

# Define menu items
hook_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:hook_list",
    link_text="Hooks",
    permissions=["netbox_dhcp_kea_plugin.view_hook"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:hook_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_hook"],
        ),
    ),
)

hookgroup_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:hookgroup_list",
    link_text="Hook Groups",
    permissions=["netbox_dhcp_kea_plugin.view_hookgroup"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:hookgroup_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_hookgroup"],
        ),
    ),
)

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

subnet_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:subnet_list",
    link_text="Subnets",
    permissions=["netbox_dhcp_kea_plugin.view_subnet"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:subnet_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_subnet"],
        ),
    ),
)

subnet_pools_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:subnetpool_list",
    link_text="Subnet Pools",
    permissions=["netbox_dhcp_kea_plugin.view_subnetpool"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:subnetpool_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_subnetpool"],
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

storkserver_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:storkserver_list",
    link_text="Stork Servers",
    permissions=["netbox_dhcp_kea_plugin.view_storkserver"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:storkserver_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_storkserver"],
        ),
    ),
)

storkagentgroup_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:storkagentgroup_list",
    link_text="Stork Agent Groups",
    permissions=["netbox_dhcp_kea_plugin.view_storkagentgroup"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:storkagentgroup_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_storkagentgroup"],
        ),
    ),
)

# --- DDNS Menu Items ---

tsigkey_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:tsigkey_list",
    link_text="TSIG Keys",
    permissions=["netbox_dhcp_kea_plugin.view_tsigkey"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:tsigkey_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_tsigkey"],
        ),
    ),
)

d2daemon_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:d2daemon_list",
    link_text="D2 Daemons",
    permissions=["netbox_dhcp_kea_plugin.view_d2daemon"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:d2daemon_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_d2daemon"],
        ),
    ),
)

ddnsdomain_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:ddnsdomain_list",
    link_text="DDNS Domains",
    permissions=["netbox_dhcp_kea_plugin.view_ddnsdomain"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:ddnsdomain_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_ddnsdomain"],
        ),
    ),
)

ddnspolicy_menu_item = PluginMenuItem(
    link="plugins:netbox_dhcp_kea_plugin:ddnspolicy_list",
    link_text="DDNS Policies",
    permissions=["netbox_dhcp_kea_plugin.view_ddnspolicy"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_dhcp_kea_plugin:ddnspolicy_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            permissions=["netbox_dhcp_kea_plugin.add_ddnspolicy"],
        ),
    ),
)


# Build menu groups, conditionally including Stork
_menu_groups = [
    (
        "Servers",
        (
            dhcpserver_menu_item,
            dhcpharelationship_menu_item,
            hook_menu_item,
            hookgroup_menu_item,
        ),
    ),
    (
        "DHCP Configuration",
        (
            subnet_menu_item,
            subnet_pools_menu_item,
            clientclass_menu_item,
        ),
    ),
    (
        "Options",
        (
            optiondefinition_menu_item,
            optiondata_menu_item,
            vendoroptionspace_menu_item,
        ),
    ),
]

if enable_stork:
    _menu_groups.append(
        (
            "Stork Monitoring",
            (
                storkserver_menu_item,
                storkagentgroup_menu_item,
            ),
        ),
    )

if enable_ddns:
    _menu_groups.append(
        (
            "DDNS",
            (
                tsigkey_menu_item,
                d2daemon_menu_item,
                ddnsdomain_menu_item,
                ddnspolicy_menu_item,
            ),
        ),
    )

if top_level_menu:
    menu = PluginMenu(
        label=menu_name,
        groups=tuple(_menu_groups),
        icon_class="mdi mdi-bird",
    )
else:
    _flat_items = [
        dhcpserver_menu_item,
        dhcpharelationship_menu_item,
        hook_menu_item,
        hookgroup_menu_item,
        subnet_menu_item,
        subnet_pools_menu_item,
        clientclass_menu_item,
        optiondefinition_menu_item,
        optiondata_menu_item,
        vendoroptionspace_menu_item,
    ]
    if enable_stork:
        _flat_items.extend([storkserver_menu_item, storkagentgroup_menu_item])
    if enable_ddns:
        _flat_items.extend(
            [
                tsigkey_menu_item,
                d2daemon_menu_item,
                ddnsdomain_menu_item,
                ddnspolicy_menu_item,
            ]
        )
    menu_items = tuple(_flat_items)
