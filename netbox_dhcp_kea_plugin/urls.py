from django.urls import path
from netbox.plugins.utils import get_plugin_config
from netbox.views.generic import ObjectChangeLogView

from . import models, views

_urlpatterns = [
    # Hook URLs
    path("hooks/", views.HookListView.as_view(), name="hook_list"),
    path("hooks/add/", views.HookEditView.as_view(), name="hook_add"),
    path("hooks/import/", views.HookImportView.as_view(), name="hook_bulk_import"),
    path("hooks/delete/", views.HookBulkDeleteView.as_view(), name="hook_bulk_delete"),
    path("hooks/<int:pk>/", views.HookView.as_view(), name="hook"),
    path("hooks/<int:pk>/edit/", views.HookEditView.as_view(), name="hook_edit"),
    path("hooks/<int:pk>/delete/", views.HookDeleteView.as_view(), name="hook_delete"),
    path(
        "hooks/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="hook_changelog",
        kwargs={"model": models.Hook},
    ),
    path(
        "hooks/<int:pk>/hook-groups/",
        views.HookHookGroupsView.as_view(),
        name="hook_hook_groups",
    ),
    # HookGroup URLs
    path("hook-groups/", views.HookGroupListView.as_view(), name="hookgroup_list"),
    path("hook-groups/add/", views.HookGroupEditView.as_view(), name="hookgroup_add"),
    path("hook-groups/import/", views.HookGroupImportView.as_view(), name="hookgroup_bulk_import"),
    path("hook-groups/delete/", views.HookGroupBulkDeleteView.as_view(), name="hookgroup_bulk_delete"),
    path("hook-groups/<int:pk>/", views.HookGroupView.as_view(), name="hookgroup"),
    path("hook-groups/<int:pk>/edit/", views.HookGroupEditView.as_view(), name="hookgroup_edit"),
    path("hook-groups/<int:pk>/delete/", views.HookGroupDeleteView.as_view(), name="hookgroup_delete"),
    path(
        "hook-groups/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="hookgroup_changelog",
        kwargs={"model": models.HookGroup},
    ),
    path(
        "hook-groups/<int:pk>/hooks/",
        views.HookGroupHooksView.as_view(),
        name="hookgroup_hooks",
    ),
    path(
        "hook-groups/<int:pk>/servers/",
        views.HookGroupServersView.as_view(),
        name="hookgroup_servers",
    ),
    # VendorOptionSpace
    path("vendor-option-spaces/", views.VendorOptionSpaceListView.as_view(), name="vendoroptionspace_list"),
    path("vendor-option-spaces/add/", views.VendorOptionSpaceEditView.as_view(), name="vendoroptionspace_add"),
    path(
        "vendor-option-spaces/import/",
        views.VendorOptionSpaceImportView.as_view(),
        name="vendoroptionspace_bulk_import",
    ),
    path(
        "vendor-option-spaces/delete/",
        views.VendorOptionSpaceBulkDeleteView.as_view(),
        name="vendoroptionspace_bulk_delete",
    ),
    path("vendor-option-spaces/<int:pk>/", views.VendorOptionSpaceView.as_view(), name="vendoroptionspace"),
    path(
        "vendor-option-spaces/<int:pk>/edit/", views.VendorOptionSpaceEditView.as_view(), name="vendoroptionspace_edit"
    ),
    path(
        "vendor-option-spaces/<int:pk>/delete/",
        views.VendorOptionSpaceDeleteView.as_view(),
        name="vendoroptionspace_delete",
    ),
    path(
        "vendor-option-spaces/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="vendoroptionspace_changelog",
        kwargs={"model": models.VendorOptionSpace},
    ),
    # OptionDefinition
    path("option-definitions/", views.OptionDefinitionListView.as_view(), name="optiondefinition_list"),
    path("option-definitions/add/", views.OptionDefinitionEditView.as_view(), name="optiondefinition_add"),
    path("option-definitions/import/", views.OptionDefinitionImportView.as_view(), name="optiondefinition_bulk_import"),
    path(
        "option-definitions/delete/",
        views.OptionDefinitionBulkDeleteView.as_view(),
        name="optiondefinition_bulk_delete",
    ),
    path("option-definitions/<int:pk>/", views.OptionDefinitionView.as_view(), name="optiondefinition"),
    path("option-definitions/<int:pk>/edit/", views.OptionDefinitionEditView.as_view(), name="optiondefinition_edit"),
    path(
        "option-definitions/<int:pk>/delete/",
        views.OptionDefinitionDeleteView.as_view(),
        name="optiondefinition_delete",
    ),
    path(
        "option-definitions/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="optiondefinition_changelog",
        kwargs={"model": models.OptionDefinition},
    ),
    # OptionData
    path("option-data/", views.OptionDataListView.as_view(), name="optiondata_list"),
    path("option-data/add/", views.OptionDataEditView.as_view(), name="optiondata_add"),
    path("option-data/import/", views.OptionDataImportView.as_view(), name="optiondata_bulk_import"),
    path("option-data/delete/", views.OptionDataBulkDeleteView.as_view(), name="optiondata_bulk_delete"),
    path("option-data/<int:pk>/", views.OptionDataView.as_view(), name="optiondata"),
    path("option-data/<int:pk>/edit/", views.OptionDataEditView.as_view(), name="optiondata_edit"),
    path("option-data/<int:pk>/delete/", views.OptionDataDeleteView.as_view(), name="optiondata_delete"),
    path(
        "option-data/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="optiondata_changelog",
        kwargs={"model": models.OptionData},
    ),
    path(
        "option-data/<int:pk>/client-classes/",
        views.OptionDataClientClassesView.as_view(),
        name="optiondata_client_classes",
    ),
    # DHCPServer
    path("dhcp-servers/", views.DHCPServerListView.as_view(), name="dhcpserver_list"),
    path("dhcp-servers/add/", views.DHCPServerEditView.as_view(), name="dhcpserver_add"),
    path("dhcp-servers/import/", views.DHCPServerImportView.as_view(), name="dhcpserver_bulk_import"),
    path("dhcp-servers/delete/", views.DHCPServerBulkDeleteView.as_view(), name="dhcpserver_bulk_delete"),
    path("dhcp-servers/<int:pk>/", views.DHCPServerView.as_view(), name="dhcpserver"),
    path("dhcp-servers/<int:pk>/edit/", views.DHCPServerEditView.as_view(), name="dhcpserver_edit"),
    path("dhcp-servers/<int:pk>/delete/", views.DHCPServerDeleteView.as_view(), name="dhcpserver_delete"),
    path(
        "dhcp-servers/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="dhcpserver_changelog",
        kwargs={"model": models.DHCPServer},
    ),
    path(
        "dhcp-servers/<int:pk>/prefixes/",
        views.DHCPServerPrefixesView.as_view(),
        name="dhcpserver_prefixes",
    ),
    path(
        "dhcp-servers/<int:pk>/kea-config/",
        views.DHCPServerKeaConfigView.as_view(),
        name="dhcpserver_kea_config",
    ),
    # ClientClass
    path("client-classes/", views.ClientClassListView.as_view(), name="clientclass_list"),
    path("client-classes/add/", views.ClientClassEditView.as_view(), name="clientclass_add"),
    path("client-classes/import/", views.ClientClassImportView.as_view(), name="clientclass_bulk_import"),
    path("client-classes/delete/", views.ClientClassBulkDeleteView.as_view(), name="clientclass_bulk_delete"),
    path("client-classes/<int:pk>/", views.ClientClassView.as_view(), name="clientclass"),
    path("client-classes/<int:pk>/edit/", views.ClientClassEditView.as_view(), name="clientclass_edit"),
    path("client-classes/<int:pk>/delete/", views.ClientClassDeleteView.as_view(), name="clientclass_delete"),
    path(
        "client-classes/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="clientclass_changelog",
        kwargs={"model": models.ClientClass},
    ),
    path(
        "client-classes/<int:pk>/servers/",
        views.ClientClassServersView.as_view(),
        name="clientclass_servers",
    ),
    path(
        "client-classes/<int:pk>/prefixes/",
        views.ClientClassPrefixesView.as_view(),
        name="clientclass_prefixes",
    ),
    # Subnet
    path("subnets/", views.SubnetListView.as_view(), name="subnet_list"),
    path("subnets/add/", views.SubnetEditView.as_view(), name="subnet_add"),
    path("subnets/import/", views.SubnetImportView.as_view(), name="subnet_bulk_import"),
    path("subnets/delete/", views.SubnetBulkDeleteView.as_view(), name="subnet_bulk_delete"),
    path("subnets/<int:pk>/", views.SubnetView.as_view(), name="subnet"),
    path("subnets/<int:pk>/edit/", views.SubnetEditView.as_view(), name="subnet_edit"),
    path("subnets/<int:pk>/delete/", views.SubnetDeleteView.as_view(), name="subnet_delete"),
    path(
        "subnets/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="subnet_changelog",
        kwargs={"model": models.Subnet},
    ),
    path(
        "subnets/<int:pk>/reservations/",
        views.SubnetReservationsView.as_view(),
        name="subnet_reservations",
    ),
    path(
        "subnets/<int:pk>/pools/",
        views.SubnetPoolsView.as_view(),
        name="subnet_pools",
    ),
    # SubnetPool
    path("subnet-pools/", views.SubnetPoolListView.as_view(), name="subnetpool_list"),
    path("subnet-pools/add/", views.SubnetPoolEditView.as_view(), name="subnetpool_add"),
    path("subnet-pools/import/", views.SubnetPoolImportView.as_view(), name="subnetpool_bulk_import"),
    path("subnet-pools/delete/", views.SubnetPoolBulkDeleteView.as_view(), name="subnetpool_bulk_delete"),
    path("subnet-pools/<int:pk>/", views.SubnetPoolView.as_view(), name="subnetpool"),
    path("subnet-pools/<int:pk>/edit/", views.SubnetPoolEditView.as_view(), name="subnetpool_edit"),
    path("subnet-pools/<int:pk>/delete/", views.SubnetPoolDeleteView.as_view(), name="subnetpool_delete"),
    path(
        "subnet-pools/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="subnetpool_changelog",
        kwargs={"model": models.SubnetPool},
    ),
    # StaticReservation
    path("static-reservations/", views.StaticReservationListView.as_view(), name="staticreservation_list"),
    path("static-reservations/add/", views.StaticReservationEditView.as_view(), name="staticreservation_add"),
    path(
        "static-reservations/import/",
        views.StaticReservationImportView.as_view(),
        name="staticreservation_bulk_import",
    ),
    path(
        "static-reservations/delete/",
        views.StaticReservationBulkDeleteView.as_view(),
        name="staticreservation_bulk_delete",
    ),
    path("static-reservations/<int:pk>/", views.StaticReservationView.as_view(), name="staticreservation"),
    path(
        "static-reservations/<int:pk>/edit/",
        views.StaticReservationEditView.as_view(),
        name="staticreservation_edit",
    ),
    path(
        "static-reservations/<int:pk>/delete/",
        views.StaticReservationDeleteView.as_view(),
        name="staticreservation_delete",
    ),
    path(
        "static-reservations/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="staticreservation_changelog",
        kwargs={"model": models.StaticReservation},
    ),
    # DHCPHARelationship
    path("ha-relationships/", views.DHCPHARelationshipListView.as_view(), name="dhcpharelationship_list"),
    path("ha-relationships/add/", views.DHCPHARelationshipEditView.as_view(), name="dhcpharelationship_add"),
    path(
        "ha-relationships/import/", views.DHCPHARelationshipImportView.as_view(), name="dhcpharelationship_bulk_import"
    ),
    path(
        "ha-relationships/delete/",
        views.DHCPHARelationshipBulkDeleteView.as_view(),
        name="dhcpharelationship_bulk_delete",
    ),
    path("ha-relationships/<int:pk>/", views.DHCPHARelationshipView.as_view(), name="dhcpharelationship"),
    path("ha-relationships/<int:pk>/edit/", views.DHCPHARelationshipEditView.as_view(), name="dhcpharelationship_edit"),
    path(
        "ha-relationships/<int:pk>/delete/",
        views.DHCPHARelationshipDeleteView.as_view(),
        name="dhcpharelationship_delete",
    ),
    path(
        "ha-relationships/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="dhcpharelationship_changelog",
        kwargs={"model": models.DHCPHARelationship},
    ),
]

urlpatterns = _urlpatterns

if get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork"):
    urlpatterns += [
        # StorkServer URLs
        path("stork-servers/", views.StorkServerListView.as_view(), name="storkserver_list"),
        path("stork-servers/add/", views.StorkServerEditView.as_view(), name="storkserver_add"),
        path("stork-servers/import/", views.StorkServerImportView.as_view(), name="storkserver_bulk_import"),
        path("stork-servers/delete/", views.StorkServerBulkDeleteView.as_view(), name="storkserver_bulk_delete"),
        path("stork-servers/<int:pk>/", views.StorkServerView.as_view(), name="storkserver"),
        path("stork-servers/<int:pk>/edit/", views.StorkServerEditView.as_view(), name="storkserver_edit"),
        path("stork-servers/<int:pk>/delete/", views.StorkServerDeleteView.as_view(), name="storkserver_delete"),
        path(
            "stork-servers/<int:pk>/changelog/",
            ObjectChangeLogView.as_view(),
            name="storkserver_changelog",
            kwargs={"model": models.StorkServer},
        ),
        path(
            "stork-servers/<int:pk>/agent-groups/",
            views.StorkServerAgentGroupsView.as_view(),
            name="storkserver_agent_groups",
        ),
        path(
            "stork-servers/<int:pk>/config/",
            views.StorkServerConfigView.as_view(),
            name="storkserver_config",
        ),
        # StorkAgentGroup URLs
        path("stork-agent-groups/", views.StorkAgentGroupListView.as_view(), name="storkagentgroup_list"),
        path("stork-agent-groups/add/", views.StorkAgentGroupEditView.as_view(), name="storkagentgroup_add"),
        path(
            "stork-agent-groups/import/", views.StorkAgentGroupImportView.as_view(), name="storkagentgroup_bulk_import"
        ),
        path(
            "stork-agent-groups/delete/",
            views.StorkAgentGroupBulkDeleteView.as_view(),
            name="storkagentgroup_bulk_delete",
        ),
        path("stork-agent-groups/<int:pk>/", views.StorkAgentGroupView.as_view(), name="storkagentgroup"),
        path("stork-agent-groups/<int:pk>/edit/", views.StorkAgentGroupEditView.as_view(), name="storkagentgroup_edit"),
        path(
            "stork-agent-groups/<int:pk>/delete/",
            views.StorkAgentGroupDeleteView.as_view(),
            name="storkagentgroup_delete",
        ),
        path(
            "stork-agent-groups/<int:pk>/changelog/",
            ObjectChangeLogView.as_view(),
            name="storkagentgroup_changelog",
            kwargs={"model": models.StorkAgentGroup},
        ),
        path(
            "stork-agent-groups/<int:pk>/servers/",
            views.StorkAgentGroupServersView.as_view(),
            name="storkagentgroup_servers",
        ),
        path(
            "stork-agent-groups/<int:pk>/config/",
            views.StorkAgentGroupConfigView.as_view(),
            name="storkagentgroup_config",
        ),
    ]

if get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
    urlpatterns += [
        # TSIGKey URLs
        path("tsig-keys/", views.TSIGKeyListView.as_view(), name="tsigkey_list"),
        path("tsig-keys/add/", views.TSIGKeyEditView.as_view(), name="tsigkey_add"),
        path("tsig-keys/import/", views.TSIGKeyImportView.as_view(), name="tsigkey_bulk_import"),
        path("tsig-keys/delete/", views.TSIGKeyBulkDeleteView.as_view(), name="tsigkey_bulk_delete"),
        path("tsig-keys/<int:pk>/", views.TSIGKeyView.as_view(), name="tsigkey"),
        path("tsig-keys/<int:pk>/edit/", views.TSIGKeyEditView.as_view(), name="tsigkey_edit"),
        path("tsig-keys/<int:pk>/delete/", views.TSIGKeyDeleteView.as_view(), name="tsigkey_delete"),
        path(
            "tsig-keys/<int:pk>/changelog/",
            ObjectChangeLogView.as_view(),
            name="tsigkey_changelog",
            kwargs={"model": models.TSIGKey},
        ),
        # D2Daemon URLs
        path("d2-daemons/", views.D2DaemonListView.as_view(), name="d2daemon_list"),
        path("d2-daemons/add/", views.D2DaemonEditView.as_view(), name="d2daemon_add"),
        path("d2-daemons/import/", views.D2DaemonImportView.as_view(), name="d2daemon_bulk_import"),
        path("d2-daemons/delete/", views.D2DaemonBulkDeleteView.as_view(), name="d2daemon_bulk_delete"),
        path("d2-daemons/<int:pk>/", views.D2DaemonView.as_view(), name="d2daemon"),
        path("d2-daemons/<int:pk>/edit/", views.D2DaemonEditView.as_view(), name="d2daemon_edit"),
        path("d2-daemons/<int:pk>/delete/", views.D2DaemonDeleteView.as_view(), name="d2daemon_delete"),
        path(
            "d2-daemons/<int:pk>/changelog/",
            ObjectChangeLogView.as_view(),
            name="d2daemon_changelog",
            kwargs={"model": models.D2Daemon},
        ),
        path(
            "d2-daemons/<int:pk>/domains/",
            views.D2DaemonDomainsView.as_view(),
            name="d2daemon_domains",
        ),
        path(
            "d2-daemons/<int:pk>/config/",
            views.D2DaemonConfigView.as_view(),
            name="d2daemon_config",
        ),
        # DDNSDomain URLs
        path("ddns-domains/", views.DDNSDomainListView.as_view(), name="ddnsdomain_list"),
        path("ddns-domains/add/", views.DDNSDomainEditView.as_view(), name="ddnsdomain_add"),
        path("ddns-domains/import/", views.DDNSDomainImportView.as_view(), name="ddnsdomain_bulk_import"),
        path("ddns-domains/edit/", views.DDNSDomainBulkEditView.as_view(), name="ddnsdomain_bulk_edit"),
        path("ddns-domains/delete/", views.DDNSDomainBulkDeleteView.as_view(), name="ddnsdomain_bulk_delete"),
        path("ddns-domains/<int:pk>/", views.DDNSDomainView.as_view(), name="ddnsdomain"),
        path("ddns-domains/<int:pk>/edit/", views.DDNSDomainEditView.as_view(), name="ddnsdomain_edit"),
        path("ddns-domains/<int:pk>/delete/", views.DDNSDomainDeleteView.as_view(), name="ddnsdomain_delete"),
        path(
            "ddns-domains/<int:pk>/changelog/",
            ObjectChangeLogView.as_view(),
            name="ddnsdomain_changelog",
            kwargs={"model": models.DDNSDomain},
        ),
        # DDNSPolicy URLs
        path("ddns-policies/", views.DDNSPolicyListView.as_view(), name="ddnspolicy_list"),
        path("ddns-policies/add/", views.DDNSPolicyEditView.as_view(), name="ddnspolicy_add"),
        path("ddns-policies/import/", views.DDNSPolicyImportView.as_view(), name="ddnspolicy_bulk_import"),
        path("ddns-policies/delete/", views.DDNSPolicyBulkDeleteView.as_view(), name="ddnspolicy_bulk_delete"),
        path("ddns-policies/<int:pk>/", views.DDNSPolicyView.as_view(), name="ddnspolicy"),
        path("ddns-policies/<int:pk>/edit/", views.DDNSPolicyEditView.as_view(), name="ddnspolicy_edit"),
        path("ddns-policies/<int:pk>/delete/", views.DDNSPolicyDeleteView.as_view(), name="ddnspolicy_delete"),
        path(
            "ddns-policies/<int:pk>/changelog/",
            ObjectChangeLogView.as_view(),
            name="ddnspolicy_changelog",
            kwargs={"model": models.DDNSPolicy},
        ),
        path(
            "ddns-policies/<int:pk>/servers/",
            views.DDNSPolicyServersView.as_view(),
            name="ddnspolicy_servers",
        ),
        path(
            "ddns-policies/<int:pk>/subnets/",
            views.DDNSPolicySubnetsView.as_view(),
            name="ddnspolicy_subnets",
        ),
        path(
            "ddns-policies/<int:pk>/client-classes/",
            views.DDNSPolicyClientClassesView.as_view(),
            name="ddnspolicy_clientclasses",
        ),
    ]
