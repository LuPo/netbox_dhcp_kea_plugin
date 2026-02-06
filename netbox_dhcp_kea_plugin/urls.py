from django.urls import path
from netbox.views.generic import ObjectChangeLogView

from . import models, views

urlpatterns = (
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
)
