import json

from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.ui import layout
from netbox.ui.actions import AddObject
from netbox.ui.panels import ContextTablePanel, JSONPanel, ObjectsTablePanel, PluginContentPanel, TemplatePanel
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from . import filtersets, forms, models, tables
from .models import SubnetPool
from .ui import panels as ui_panels
from .ui.attrs import hinted


def _ddns_enabled(_instance=None):
    from netbox.plugins.utils import get_plugin_config

    return bool(get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"))


def _is_primary(server):
    return server.is_ha_primary()


# Hook Views
@register_model_view(models.Hook)
class HookView(generic.ObjectView):
    queryset = models.Hook.objects.prefetch_related("hook_groups")
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.HookPanel(),
            TagsPanel(),
        ],
        right_panels=[
            JSONPanel("parameters", title=_("Parameters")),
            CustomFieldsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                "netbox_dhcp_kea_plugin.HookGroup",
                title=_("Hook Groups"),
                filters={"hooks": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


@register_model_view(models.Hook, "list", path="", detail=False)
class HookListView(generic.ObjectListView):
    queryset = models.Hook.objects.annotate(hook_groups_count=Count("hook_groups"))
    table = tables.HookTable
    filterset = filtersets.HookFilterSet
    filterset_form = forms.HookFilterForm


@register_model_view(models.Hook, "add", detail=False)
@register_model_view(models.Hook, "edit")
class HookEditView(generic.ObjectEditView):
    queryset = models.Hook.objects.all()
    form = forms.HookForm


@register_model_view(models.Hook, "delete")
class HookDeleteView(generic.ObjectDeleteView):
    queryset = models.Hook.objects.all()


@register_model_view(models.Hook, "bulk_delete", path="delete", detail=False)
class HookBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Hook.objects.all()
    filterset = filtersets.HookFilterSet
    table = tables.HookTable


@register_model_view(models.Hook, "bulk_import", path="import", detail=False)
class HookImportView(generic.BulkImportView):
    queryset = models.Hook.objects.all()
    model_form = forms.HookImportForm


def get_hook_group_count(obj):
    """Get the number of hook groups for a hook."""
    return obj.hook_groups.count()


@register_model_view(models.Hook, name="hook_groups", path="hook-groups")
class HookHookGroupsView(generic.ObjectChildrenView):
    queryset = models.Hook.objects.all()
    child_model = models.HookGroup
    table = tables.HookGroupTable
    filterset = filtersets.HookGroupFilterSet
    filterset_form = forms.HookGroupFilterForm
    tab = ViewTab(
        label=_("Hook Groups"),
        badge=get_hook_group_count,
        permission="netbox_dhcp_kea_plugin.view_hook",
    )

    def get_children(self, request, parent):
        return parent.hook_groups.restrict(request.user, "view")


# HookGroup Views
@register_model_view(models.HookGroup)
class HookGroupView(generic.ObjectView):
    queryset = models.HookGroup.objects.prefetch_related("hooks", "servers", "d2_daemons")
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.HookGroupPanel(),
            TagsPanel(),
        ],
        right_panels=[
            CustomFieldsPanel(),
        ],
    )


@register_model_view(models.HookGroup, "list", path="", detail=False)
class HookGroupListView(generic.ObjectListView):
    queryset = models.HookGroup.objects.annotate(
        hooks_count=Count("hooks", distinct=True),
        servers_count=Count("servers", distinct=True),
    )
    table = tables.HookGroupTable
    filterset = filtersets.HookGroupFilterSet
    filterset_form = forms.HookGroupFilterForm


@register_model_view(models.HookGroup, "add", detail=False)
@register_model_view(models.HookGroup, "edit")
class HookGroupEditView(generic.ObjectEditView):
    queryset = models.HookGroup.objects.all()
    form = forms.HookGroupForm


@register_model_view(models.HookGroup, "delete")
class HookGroupDeleteView(generic.ObjectDeleteView):
    queryset = models.HookGroup.objects.all()


@register_model_view(models.HookGroup, "bulk_delete", path="delete", detail=False)
class HookGroupBulkDeleteView(generic.BulkDeleteView):
    queryset = models.HookGroup.objects.all()
    filterset = filtersets.HookGroupFilterSet
    table = tables.HookGroupTable


@register_model_view(models.HookGroup, "bulk_import", path="import", detail=False)
class HookGroupImportView(generic.BulkImportView):
    queryset = models.HookGroup.objects.all()
    model_form = forms.HookGroupImportForm


def get_hookgroup_hooks_count(obj):
    """Get the number of hooks in a hook group."""
    return obj.hooks.count()


@register_model_view(models.HookGroup, name="hooks", path="hooks")
class HookGroupHooksView(generic.ObjectChildrenView):
    queryset = models.HookGroup.objects.all()
    child_model = models.Hook
    table = tables.HookTable
    filterset = filtersets.HookFilterSet
    filterset_form = forms.HookFilterForm
    tab = ViewTab(
        label=_("Hooks"),
        badge=get_hookgroup_hooks_count,
        permission="netbox_dhcp_kea_plugin.view_hookgroup",
    )

    def get_children(self, request, parent):
        return parent.hooks.restrict(request.user, "view")


def get_hookgroup_servers_count(obj):
    """Get the number of servers in a hook group."""
    return obj.servers.count()


@register_model_view(models.HookGroup, name="servers", path="servers")
class HookGroupServersView(generic.ObjectChildrenView):
    queryset = models.HookGroup.objects.all()
    child_model = models.DHCPServer
    table = tables.DHCPServerTable
    filterset = filtersets.DHCPServerFilterSet
    filterset_form = forms.DHCPServerFilterForm
    tab = ViewTab(
        label=_("Servers"),
        badge=get_hookgroup_servers_count,
        permission="netbox_dhcp_kea_plugin.view_hookgroup",
    )

    def get_children(self, request, parent):
        return parent.servers.restrict(request.user, "view")


# VendorOptionSpace Views
@register_model_view(models.VendorOptionSpace)
class VendorOptionSpaceView(generic.ObjectView):
    queryset = models.VendorOptionSpace.objects.annotate(definitions_count=Count("option_definitions"))
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.VendorOptionSpacePanel(),
            TagsPanel(),
        ],
        right_panels=[
            TemplatePanel(
                "netbox_dhcp_kea_plugin/panels/vendor_option43.html", title=_("KEA Option 43 Configuration")
            ),
            ui_panels.ConditionalTemplatePanel(
                "netbox_dhcp_kea_plugin/panels/vendor_vivso.html",
                condition=lambda space: space.enterprise_id,
                title=_("KEA VIVSO (Option 125) Configuration"),
            ),
            CustomFieldsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                "netbox_dhcp_kea_plugin.OptionDefinition",
                filters={"vendor_option_space_id": lambda ctx: ctx["object"].pk},
                actions=[
                    AddObject(
                        "netbox_dhcp_kea_plugin.OptionDefinition",
                        url_params={"vendor_option_space": lambda ctx: ctx["object"].pk},
                    ),
                ],
            ),
            ObjectsTablePanel(
                "netbox_dhcp_kea_plugin.OptionData",
                filters={"vendor_option_space": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


@register_model_view(models.VendorOptionSpace, "list", path="", detail=False)
class VendorOptionSpaceListView(generic.ObjectListView):
    queryset = models.VendorOptionSpace.objects.annotate(definitions_count=Count("option_definitions"))
    table = tables.VendorOptionSpaceTable
    filterset = filtersets.VendorOptionSpaceFilterSet
    filterset_form = forms.VendorOptionSpaceFilterForm


@register_model_view(models.VendorOptionSpace, "add", detail=False)
@register_model_view(models.VendorOptionSpace, "edit")
class VendorOptionSpaceEditView(generic.ObjectEditView):
    queryset = models.VendorOptionSpace.objects.all()
    form = forms.VendorOptionSpaceForm


@register_model_view(models.VendorOptionSpace, "delete")
class VendorOptionSpaceDeleteView(generic.ObjectDeleteView):
    queryset = models.VendorOptionSpace.objects.all()


@register_model_view(models.VendorOptionSpace, "bulk_delete", path="delete", detail=False)
class VendorOptionSpaceBulkDeleteView(generic.BulkDeleteView):
    queryset = models.VendorOptionSpace.objects.all()
    filterset = filtersets.VendorOptionSpaceFilterSet
    table = tables.VendorOptionSpaceTable


@register_model_view(models.VendorOptionSpace, "bulk_import", path="import", detail=False)
class VendorOptionSpaceImportView(generic.BulkImportView):
    queryset = models.VendorOptionSpace.objects.all()
    model_form = forms.VendorOptionSpaceImportForm


# OptionDefinition Views
@register_model_view(models.OptionDefinition)
class OptionDefinitionView(generic.ObjectView):
    queryset = models.OptionDefinition.objects.select_related("vendor_option_space")
    # Extends generic/object.html only to make standard options read-only.
    template_name = "netbox_dhcp_kea_plugin/optiondefinition.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.OptionDefinitionPanel(),
            TagsPanel(),
        ],
        right_panels=[
            ui_panels.KeaJSONPanel(
                lambda definition, _ctx: None if definition.is_standard else definition.to_kea_dict(),
                title=_("KEA Configuration"),
                intro=lambda definition: (
                    ""
                    if definition.is_standard
                    else _("This option definition generates the following KEA option-def entry:")
                ),
                empty_message=_(
                    "Standard DHCP options are built into KEA and need no option-def entry. Use this option "
                    "directly in option-data by name or code."
                ),
                element_id="optiondefinition-kea",
            ),
            CustomFieldsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                "netbox_dhcp_kea_plugin.OptionData",
                title=_("Option Data Using This Definition"),
                filters={"definition": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


@register_model_view(models.OptionDefinition, "list", path="", detail=False)
class OptionDefinitionListView(generic.ObjectListView):
    queryset = models.OptionDefinition.objects.select_related("vendor_option_space")
    table = tables.OptionDefinitionTable
    filterset = filtersets.OptionDefinitionFilterSet
    filterset_form = forms.OptionDefinitionFilterForm
    template_name = "netbox_dhcp_kea_plugin/optiondefinition_list.html"

    def get_table(self, data, request, bulk_actions=True):
        # Use export table (without is_standard) for exports
        if request.GET.get("export"):
            table = tables.OptionDefinitionExportTable(data, user=request.user)
            return table
        return super().get_table(data, request, bulk_actions)


@register_model_view(models.OptionDefinition, "add", detail=False)
@register_model_view(models.OptionDefinition, "edit")
class OptionDefinitionEditView(generic.ObjectEditView):
    queryset = models.OptionDefinition.objects.filter(is_standard=False)
    form = forms.OptionDefinitionForm

    def dispatch(self, request, *args, **kwargs):
        # Check if trying to edit a standard option
        if "pk" in kwargs:
            try:
                obj = models.OptionDefinition.objects.get(pk=kwargs["pk"])
                if obj.is_standard:
                    messages.error(request, "Standard DHCP options cannot be modified.")
                    return redirect(obj.get_absolute_url())
            except models.OptionDefinition.DoesNotExist:
                pass
        return super().dispatch(request, *args, **kwargs)


@register_model_view(models.OptionDefinition, "delete")
class OptionDefinitionDeleteView(generic.ObjectDeleteView):
    queryset = models.OptionDefinition.objects.filter(is_standard=False)

    def dispatch(self, request, *args, **kwargs):
        # Check if trying to delete a standard option
        if "pk" in kwargs:
            try:
                obj = models.OptionDefinition.objects.get(pk=kwargs["pk"])
                if obj.is_standard:
                    messages.error(request, "Standard DHCP options cannot be deleted.")
                    return redirect(obj.get_absolute_url())
            except models.OptionDefinition.DoesNotExist:
                pass
        return super().dispatch(request, *args, **kwargs)


@register_model_view(models.OptionDefinition, "bulk_delete", path="delete", detail=False)
class OptionDefinitionBulkDeleteView(generic.BulkDeleteView):
    queryset = models.OptionDefinition.objects.filter(is_standard=False)
    filterset = filtersets.OptionDefinitionFilterSet
    table = tables.OptionDefinitionTable


@register_model_view(models.OptionDefinition, "bulk_import", path="import", detail=False)
class OptionDefinitionImportView(generic.BulkImportView):
    queryset = models.OptionDefinition.objects.all()
    model_form = forms.OptionDefinitionImportForm


# OptionData Views
def _option_data_intro(option):
    if option.delivery_type == "option43":
        return _("Delivered via Option 43 (Vendor-Encapsulated-Options) in this KEA option-data entry:")
    if option.delivery_type == "vivso":
        return _("Delivered via Option 125 (VIVSO) in this KEA option-data entry:")
    return _("This option data generates the following KEA option-data entry:")


@register_model_view(models.OptionData)
class OptionDataView(generic.ObjectView):
    queryset = models.OptionData.objects.select_related("definition", "vendor_option_space")
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.OptionDataPanel(),
            ui_panels.OptionIPSourcesPanel(),
            TagsPanel(),
        ],
        right_panels=[
            ui_panels.KeaJSONPanel(
                lambda option, _ctx: option.to_kea_dict(),
                title=_("KEA Configuration"),
                intro=_option_data_intro,
                element_id="optiondata-kea",
            ),
            CustomFieldsPanel(),
        ],
    )


@register_model_view(models.OptionData, "list", path="", detail=False)
class OptionDataListView(generic.ObjectListView):
    queryset = models.OptionData.objects.select_related("definition", "vendor_option_space")
    table = tables.OptionDataTable
    filterset = filtersets.OptionDataFilterSet
    filterset_form = forms.OptionDataFilterForm

    def get_table(self, data, request, bulk_actions=True):
        # Use export table (with consistent naming) for exports
        if request.GET.get("export"):
            table = tables.OptionDataExportTable(data, user=request.user)
            return table
        return super().get_table(data, request, bulk_actions)


@register_model_view(models.OptionData, "add", detail=False)
@register_model_view(models.OptionData, "edit")
class OptionDataEditView(generic.ObjectEditView):
    queryset = models.OptionData.objects.all()
    form = forms.OptionDataForm


@register_model_view(models.OptionData, "delete")
class OptionDataDeleteView(generic.ObjectDeleteView):
    queryset = models.OptionData.objects.all()


@register_model_view(models.OptionData, "bulk_delete", path="delete", detail=False)
class OptionDataBulkDeleteView(generic.BulkDeleteView):
    queryset = models.OptionData.objects.all()
    filterset = filtersets.OptionDataFilterSet
    table = tables.OptionDataTable


@register_model_view(models.OptionData, "bulk_import", path="import", detail=False)
class OptionDataImportView(generic.BulkImportView):
    queryset = models.OptionData.objects.all()
    model_form = forms.OptionDataImportForm


@register_model_view(models.OptionData, name="client_classes", path="client-classes")
class OptionDataClientClassesView(generic.ObjectChildrenView):
    queryset = models.OptionData.objects.all()
    child_model = models.ClientClass
    table = tables.ClientClassTable
    filterset = filtersets.ClientClassFilterSet
    filterset_form = forms.ClientClassFilterForm
    tab = ViewTab(
        label=_("Client Classes"),
        badge=lambda option: option.client_classes.count(),
        permission="netbox_dhcp_kea_plugin.view_optiondata",
    )

    def get_children(self, request, parent):
        return parent.client_classes.restrict(request.user, "view")


# DHCPServer Views
def _pki_dns_integration_active():
    """True when PKI identities are expected to be bound to netbox_dns records."""
    from netbox.plugins.utils import get_plugin_config

    if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_netbox_dns"):
        return False
    try:
        import netbox_dns  # noqa: F401
    except ImportError:
        return False
    return True


@register_model_view(models.DHCPServer)
class DHCPServerView(generic.ObjectView):
    queryset = models.DHCPServer.objects.all()
    # Extends generic/object.html only to add the HA standby badge.
    template_name = "netbox_dhcp_kea_plugin/dhcpserver.html"
    layout = layout.Layout(
        layout.Row(layout.Column(ui_panels.ContextAlertsPanel("pki_identity_advisories"))),
        layout.Row(
            layout.Column(
                ui_panels.DHCPServerPanel(),
                ui_panels.DHCPServerProxyPanel(),
                ui_panels.DHCPServerReservationDefaultsPanel(),
                TemplatePanel("netbox_dhcp_kea_plugin/panels/server_summary.html", title=_("Configuration Summary")),
                TagsPanel(),
                PluginContentPanel("left_page"),
            ),
            layout.Column(
                # Client-class problems and the HA standby note; each card shows only when it applies.
                TemplatePanel("netbox_dhcp_kea_plugin/panels/server_class_warnings.html"),
                # A standby takes its subnets, classes and options from the primary.
                ui_panels.ConditionalPanel(ui_panels.DHCPServerLeasePanel(), _is_primary),
                ui_panels.ConditionalPanel(
                    ui_panels.DHCPServerDDNSPanel(),
                    lambda server: ui_panels.ddns_enabled() and server.is_ha_primary(),
                ),
                ui_panels.ConditionalPanel(
                    ObjectsTablePanel(
                        "netbox_dhcp_kea_plugin.OptionData",
                        title=_("Global Option Data"),
                        filters={"server_id": lambda ctx: ctx["object"].pk},
                    ),
                    _is_primary,
                ),
                ui_panels.ConditionalPanel(
                    TemplatePanel(
                        "netbox_dhcp_kea_plugin/panels/server_client_classes.html", title=_("Global Client Classes")
                    ),
                    _is_primary,
                ),
                CustomFieldsPanel(),
                PluginContentPanel("right_page"),
            ),
        ),
        layout.Row(layout.Column(PluginContentPanel("full_width_page"))),
    )

    def get_extra_context(self, request, instance):
        from netbox.plugins.utils import get_plugin_config

        # Get configuration summary counts
        kea_config = instance.to_kea_dict()
        dhcp4 = kea_config.get("Dhcp4", {})

        # Check for unused only_in_additional_list classes
        unused_classes = instance.get_unused_only_in_additional_list_classes()

        # Check for unconditional classes (empty test) that are globally evaluated
        unconditional_global_classes = instance.client_classes.filter(test_expression="", only_in_additional_list=False)

        # Check for unreachable subnet restrictions (only-in-additional-list class
        # used as subnet client-class — no higher scope can trigger evaluation)
        unreachable_subnets = instance.get_unreachable_subnet_restrictions()

        # Check for unreachable pool restrictions (only-in-additional-list class
        # used as pool client-class without being in the parent subnet's
        # evaluate-additional-classes)
        unreachable_pools = instance.get_unreachable_pool_restrictions()

        return {
            "subnet_count": len(dhcp4.get("subnet4", [])),
            "client_class_count": len(dhcp4.get("client-classes", [])),
            "global_option_count": len(dhcp4.get("option-data", [])),
            "option_def_count": len(dhcp4.get("option-def", [])),
            "hook_count": len(dhcp4.get("hooks-libraries", [])),
            "unused_only_in_additional_list_classes": unused_classes,
            "unconditional_global_classes": unconditional_global_classes,
            "unreachable_subnets": unreachable_subnets,
            "unreachable_pools": unreachable_pools,
            "enable_stork": get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork"),
            "enable_ddns": get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"),
            # Advisory only — a valid PKI name may be absent from NetBox's DNS
            # records, so this is shown rather than enforced at save time.
            "pki_identity_advisories": instance.pki_identity_advisories(),
            # Resolved once here rather than called from the template, which
            # would re-query for every reference.
            "pki_record": instance.pki_record(),
            # Whether the DNS integration is active. Only then is an unbound
            # name worth flagging — the form binds every name it sets, so an
            # unbound one arrived some other way (API, import, or before the
            # integration was switched on). Without the integration every name
            # is unbound and the marker would be noise on every server.
            "pki_dns_integration": _pki_dns_integration_active(),
        }


@register_model_view(models.DHCPServer, "list", path="", detail=False)
class DHCPServerListView(generic.ObjectListView):
    queryset = models.DHCPServer.objects.all()
    table = tables.DHCPServerTable
    filterset = filtersets.DHCPServerFilterSet
    filterset_form = forms.DHCPServerFilterForm


@register_model_view(models.DHCPServer, "add", detail=False)
@register_model_view(models.DHCPServer, "edit")
class DHCPServerEditView(generic.ObjectEditView):
    queryset = models.DHCPServer.objects.all()
    form = forms.DHCPServerForm

    def get(self, request, *args, **kwargs):
        """Show info message when editing non-primary HA server."""
        from django.contrib import messages

        response = super().get(request, *args, **kwargs)

        # If editing an existing non-primary HA server, inform the user
        if kwargs.get("pk"):
            obj = self.get_object()
            if obj.ha_relationship and not obj.is_ha_primary():
                primary_server = obj.ha_relationship.servers.filter(ha_role="primary").first()
                if primary_server:
                    messages.info(
                        request,
                        f"Note: '{obj.name}' is a {obj.get_ha_role_display()} server in HA. "
                        f"Option data and client classes are managed on the primary server '{primary_server.name}' "
                        f"and automatically shared with all HA peers.",
                    )

        return response

    def post(self, request, *args, **kwargs):
        """Handle form submission with HA redirect notification."""
        from django.contrib import messages

        response = super().post(request, *args, **kwargs)

        # Check if the form was valid and if client classes were redirected
        form = getattr(self, "_form", None)
        if form is None:
            # Try to get the form from the response context
            obj = self.get_object() if kwargs.get("pk") else None
            form = self.form(request.POST, instance=obj)
            if form.is_valid():
                form = form

        if hasattr(form, "_redirected_to_primary") and form._redirected_to_primary:
            original_name = getattr(form, "_original_server_name", "the selected server")
            if form.instance and form.instance.ha_relationship:
                primary_server = form.instance.ha_relationship.servers.filter(ha_role="primary").first()
                if primary_server:
                    messages.info(
                        request,
                        f"Note: '{original_name}' is not the primary in its HA relationship. "
                        f"Client classes have been assigned to the primary server '{primary_server.name}' instead. "
                        f"All HA peers will automatically use these client classes.",
                    )

        return response


@register_model_view(models.DHCPServer, "delete")
class DHCPServerDeleteView(generic.ObjectDeleteView):
    queryset = models.DHCPServer.objects.all()


@register_model_view(models.DHCPServer, "bulk_edit", path="edit", detail=False)
class DHCPServerBulkEditView(generic.BulkEditView):
    queryset = models.DHCPServer.objects.all()
    filterset = filtersets.DHCPServerFilterSet
    table = tables.DHCPServerTable
    form = forms.DHCPServerBulkEditForm


@register_model_view(models.DHCPServer, "bulk_delete", path="delete", detail=False)
class DHCPServerBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DHCPServer.objects.all()
    filterset = filtersets.DHCPServerFilterSet
    table = tables.DHCPServerTable


@register_model_view(models.DHCPServer, "bulk_import", path="import", detail=False)
class DHCPServerImportView(generic.BulkImportView):
    queryset = models.DHCPServer.objects.all()
    model_form = forms.DHCPServerImportForm


@register_model_view(models.DHCPServer, name="prefixes", path="prefixes")
class DHCPServerPrefixesView(generic.ObjectView):
    queryset = models.DHCPServer.objects.all()
    template_name = "netbox_dhcp_kea_plugin/dhcpserver_prefixes.html"
    tab = ViewTab(
        label="Subnets",
        badge=lambda obj: obj.subnet_items.count(),
        visible=lambda obj: obj.is_ha_primary(),
        permission="netbox_dhcp_kea_plugin.view_dhcpserver",
    )

    def get(self, request, pk):
        server = self.get_object(pk=pk)
        subnet_items = server.subnet_items.select_related("prefix").all()
        return render(
            request,
            self.template_name,
            {
                "object": server,
                "subnet_items": subnet_items,
                "tab": self.tab,
            },
        )


@register_model_view(models.DHCPServer, name="kea_config", path="kea-config")
class DHCPServerKeaConfigView(generic.ObjectView):
    queryset = models.DHCPServer.objects.all()
    template_name = "netbox_dhcp_kea_plugin/dhcpserver_kea_config.html"
    tab = ViewTab(
        label="KEA Configuration",
        permission="netbox_dhcp_kea_plugin.view_dhcpserver",
    )

    def get(self, request, pk):
        from django.http import HttpResponse

        server = self.get_object(pk=pk)
        kea_config = server.to_kea_dict()
        kea_config_json = json.dumps(kea_config, indent=4)

        # Handle export/download request
        if request.GET.get("export") == "kea-config":
            response = HttpResponse(kea_config_json, content_type="application/json")
            filename = f"{server.name}_kea-config.json"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return render(
            request,
            self.template_name,
            {
                "object": server,
                "tab": self.tab,
                "kea_config": kea_config,
                "kea_config_json": kea_config_json,
            },
        )


# ClientClass Views
@register_model_view(models.ClientClass)
class ClientClassView(generic.ObjectView):
    queryset = models.ClientClass.objects.prefetch_related("option_data")
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.ClientClassPanel(),
            TagsPanel(),
        ],
        right_panels=[
            ui_panels.ClientClassKeaPanel(),
            CustomFieldsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                "netbox_dhcp_kea_plugin.OptionData",
                filters={"client_class_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


@register_model_view(models.ClientClass, "list", path="", detail=False)
class ClientClassListView(generic.ObjectListView):
    queryset = models.ClientClass.objects.annotate(option_data_count=Count("option_data"))
    table = tables.ClientClassTable
    filterset = filtersets.ClientClassFilterSet
    filterset_form = forms.ClientClassFilterForm


@register_model_view(models.ClientClass, "add", detail=False)
@register_model_view(models.ClientClass, "edit")
class ClientClassEditView(generic.ObjectEditView):
    queryset = models.ClientClass.objects.all()
    form = forms.ClientClassForm

    def post(self, request, *args, **kwargs):
        """Handle form submission with HA redirect notification."""
        from django.contrib import messages

        # Store original state before save (if editing existing)
        was_enabled = False
        if kwargs.get("pk"):
            try:
                original = models.ClientClass.objects.get(pk=kwargs["pk"])
                was_enabled = original.only_in_additional_list
            except models.ClientClass.DoesNotExist:
                pass

        # Call parent to handle the form submission
        response = super().post(request, *args, **kwargs)

        # Try to get the form that was just processed
        form = getattr(self, "_form", None)

        if form is None:
            # Try to reconstruct the form to check flags
            obj = self.get_object() if kwargs.get("pk") else None
            form = self.form(request.POST, instance=obj)
            if form.is_valid():
                # Form was valid, check for redirect flags
                pass

        # Check if servers were redirected to primary - check both form AND request object
        redirected_to_primary = False
        redirected_names = []
        primary_names = []

        # Try to get flags from form first
        if form and hasattr(form, "_redirected_to_primary") and form._redirected_to_primary:
            redirected_to_primary = True
            redirected_names = getattr(form, "_redirected_server_names", [])
            primary_names = getattr(form, "_primary_server_names", [])

        # If not on form, try request object (more reliable)
        if not redirected_to_primary and hasattr(request, "_clientclass_redirected_to_primary"):
            redirected_to_primary = request._clientclass_redirected_to_primary
            redirected_names = getattr(request, "_clientclass_redirected_server_names", [])
            primary_names = getattr(request, "_clientclass_primary_server_names", [])

        if redirected_to_primary and redirected_names and primary_names:
            redirected_list = ", ".join([f"'{name}'" for name in redirected_names])
            primary_list = ", ".join([f"'{name}'" for name in primary_names])
            messages.info(
                request,
                f"Note: {redirected_list} {'is' if len(redirected_names) == 1 else 'are'} not primary in HA. "
                f"This client class has been assigned to the primary server(s) {primary_list} instead. "
                f"All HA peers will automatically use this client class.",
            )

        # Check if we need to show warning for only_in_additional_list (only if form saved successfully)
        if form and hasattr(form, "instance") and form.instance.pk:
            is_now_enabled = form.instance.only_in_additional_list
            if not was_enabled and is_now_enabled:
                prefix_count = form.instance.subnet_items.count()
                if prefix_count == 0:
                    messages.warning(
                        request,
                        f"Warning: '{form.instance.name}' now has 'Only in additional list' enabled but is not assigned to any "
                        f"prefixes. The class will be defined in the KEA configuration but never evaluated. "
                        f"No clients will match this class until you assign it to subnets via Prefix DHCP Config.",
                    )

        return response


@register_model_view(models.ClientClass, "delete")
class ClientClassDeleteView(generic.ObjectDeleteView):
    queryset = models.ClientClass.objects.all()


@register_model_view(models.ClientClass, "bulk_delete", path="delete", detail=False)
class ClientClassBulkDeleteView(generic.BulkDeleteView):
    queryset = models.ClientClass.objects.all()
    filterset = filtersets.ClientClassFilterSet
    table = tables.ClientClassTable


@register_model_view(models.ClientClass, "bulk_import", path="import", detail=False)
class ClientClassImportView(generic.BulkImportView):
    queryset = models.ClientClass.objects.all()
    model_form = forms.ClientClassImportForm


@register_model_view(models.ClientClass, name="servers", path="servers")
class ClientClassServersView(generic.ObjectChildrenView):
    queryset = models.ClientClass.objects.all()
    child_model = models.DHCPServer
    table = tables.DHCPServerTable
    filterset = filtersets.DHCPServerFilterSet
    filterset_form = forms.DHCPServerFilterForm
    tab = ViewTab(
        label=_("DHCP Servers"),
        badge=lambda obj: obj.servers.count(),
        permission="netbox_dhcp_kea_plugin.view_clientclass",
    )

    def get_children(self, request, parent):
        return parent.servers.restrict(request.user, "view")


def _get_subnet_count_for_class(obj):
    """Count subnets where the client class is used as restricting or evaluate-additional."""
    from .models import Subnet

    return Subnet.objects.filter(Q(client_class=obj) | Q(evaluate_additional_classes=obj)).distinct().count()


@register_model_view(models.ClientClass, name="prefixes", path="prefixes")
class ClientClassPrefixesView(generic.ObjectChildrenView):
    """Subnets that restrict to this class or evaluate it as an additional class."""

    queryset = models.ClientClass.objects.all()
    child_model = models.Subnet
    table = tables.SubnetTable
    filterset = filtersets.SubnetFilterSet
    filterset_form = forms.SubnetFilterForm
    tab = ViewTab(
        label=_("Subnets"),
        badge=lambda obj: _get_subnet_count_for_class(obj),
        visible=lambda obj: obj.only_in_additional_list,
        permission="netbox_dhcp_kea_plugin.view_clientclass",
    )

    def get_children(self, request, parent):
        return (
            models.Subnet.objects.restrict(request.user, "view")
            .filter(Q(client_class=parent) | Q(evaluate_additional_classes=parent))
            .distinct()
            .select_related("prefix", "server")
        )


# Subnet Views
@register_model_view(models.Subnet)
class SubnetView(generic.ObjectView):
    queryset = models.Subnet.objects.select_related("prefix", "server", "client_class").prefetch_related(
        "option_data", "evaluate_additional_classes"
    )
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.SubnetPanel(),
            ui_panels.SubnetReservationModePanel(),
            ui_panels.SubnetClientClassesPanel(),
            ui_panels.RedundantEvaluationClassesPanel(),
            TagsPanel(),
        ],
        right_panels=[
            ui_panels.KeaJSONPanel(
                lambda subnet, _ctx: subnet.to_kea_dict(),
                title=_("KEA Subnet Configuration"),
                element_id="subnet-kea",
            ),
            CustomFieldsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                "netbox_dhcp_kea_plugin.OptionData",
                filters={"subnet_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


@register_model_view(models.Subnet, "list", path="", detail=False)
class SubnetListView(generic.ObjectListView):
    queryset = models.Subnet.objects.select_related("prefix", "server").annotate(
        pool_count=Count("subnet_pools"),
    )
    table = tables.SubnetTable
    filterset = filtersets.SubnetFilterSet
    filterset_form = forms.SubnetFilterForm

    def get_table(self, data, request, bulk_actions=True):
        # Use export table for CSV/YAML exports
        if request.GET.get("export"):
            return tables.SubnetExportTable(data)
        return super().get_table(data, request, bulk_actions)


@register_model_view(models.Subnet, "add", detail=False)
@register_model_view(models.Subnet, "edit")
class SubnetEditView(generic.ObjectEditView):
    queryset = models.Subnet.objects.all()
    form = forms.SubnetForm

    def post(self, request, *args, **kwargs):
        """Handle form submission with HA redirect notification."""
        response = super().post(request, *args, **kwargs)

        # Check if the form was valid and if server was redirected
        form = getattr(self, "_form", None)
        if form is None:
            # Try to get the form from the response context
            obj = self.get_object() if kwargs.get("pk") else None
            form = self.form(request.POST, instance=obj)
            if form.is_valid():
                form = form

        if hasattr(form, "_redirected_to_primary") and form._redirected_to_primary:
            original_name = getattr(form, "_original_server_name", "the selected server")
            primary_name = form.cleaned_data.get("server")
            if primary_name:
                messages.info(
                    request,
                    f"Note: '{original_name}' is not the primary in its HA relationship. "
                    f"The prefix has been assigned to the primary server '{primary_name.name}' instead. "
                    f"All HA peers will automatically serve this prefix.",
                )

        return response


@register_model_view(models.Subnet, "delete")
class SubnetDeleteView(generic.ObjectDeleteView):
    queryset = models.Subnet.objects.all()


@register_model_view(models.Subnet, "bulk_delete", path="delete", detail=False)
class SubnetBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Subnet.objects.all()
    filterset = filtersets.SubnetFilterSet
    table = tables.SubnetTable


@register_model_view(models.Subnet, "bulk_import", path="import", detail=False)
class SubnetImportView(generic.BulkImportView):
    queryset = models.Subnet.objects.all()
    model_form = forms.SubnetImportForm


# DHCPHARelationship Views
@register_model_view(models.DHCPHARelationship)
class DHCPHARelationshipView(generic.ObjectView):
    queryset = models.DHCPHARelationship.objects.prefetch_related("servers")
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.HARelationshipPanel(),
            ui_panels.HATimingPanel(),
            ui_panels.HAProxyPanel(),
            ui_panels.HAAuthenticationPanel(),
            ui_panels.ConditionalPanel(ui_panels.HADDNSPanel(), ui_panels.ddns_enabled),
            TagsPanel(),
        ],
        right_panels=[
            ui_panels.HAMultiThreadingPanel(),
            ContextTablePanel(
                "servers_table",
                title=hinted(
                    _("HA Servers"),
                    _("To add an existing server, edit the server and set its HA Relationship field."),
                ),
                actions=[
                    AddObject(
                        "netbox_dhcp_kea_plugin.DHCPServer",
                        url_params={"ha_relationship": lambda ctx: ctx["object"].pk},
                    ),
                ],
            ),
            CustomFieldsPanel(),
        ],
    )

    def get_extra_context(self, request, instance):
        servers_table = tables.HAMemberTable(instance.servers.restrict(request.user, "view"), orderable=False)
        servers_table.configure(request)
        return {
            "servers_table": servers_table,
            # Why the badge says Invalid; empty when the configuration is fine.
            "configuration_errors": instance.configuration_errors(),
        }


@register_model_view(models.DHCPHARelationship, "list", path="", detail=False)
class DHCPHARelationshipListView(generic.ObjectListView):
    queryset = models.DHCPHARelationship.objects.annotate(servers_count=Count("servers"))
    table = tables.DHCPHARelationshipTable
    filterset = filtersets.DHCPHARelationshipFilterSet
    filterset_form = forms.DHCPHARelationshipFilterForm


@register_model_view(models.DHCPHARelationship, "add", detail=False)
@register_model_view(models.DHCPHARelationship, "edit")
class DHCPHARelationshipEditView(generic.ObjectEditView):
    queryset = models.DHCPHARelationship.objects.all()
    form = forms.DHCPHARelationshipForm


@register_model_view(models.DHCPHARelationship, "delete")
class DHCPHARelationshipDeleteView(generic.ObjectDeleteView):
    queryset = models.DHCPHARelationship.objects.all()


@register_model_view(models.DHCPHARelationship, "bulk_delete", path="delete", detail=False)
class DHCPHARelationshipBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DHCPHARelationship.objects.all()
    filterset = filtersets.DHCPHARelationshipFilterSet
    table = tables.DHCPHARelationshipTable


@register_model_view(models.DHCPHARelationship, "bulk_import", path="import", detail=False)
class DHCPHARelationshipImportView(generic.BulkImportView):
    queryset = models.DHCPHARelationship.objects.all()
    model_form = forms.DHCPHARelationshipImportForm


def get_reservation_count(obj):
    """Calculate the number of DHCP reservations for a Subnet."""
    return len(obj.get_reservations())


def get_pool_count(obj):
    """Calculate the number of configured SubnetPools for a Subnet."""
    return obj.subnet_pools.count()


@register_model_view(models.Subnet, name="pools", path="pools")
class SubnetPoolsView(generic.ObjectView):
    """The prefix's child IP ranges as pools, each with its optional pool settings."""

    queryset = models.Subnet.objects.select_related("prefix")
    template_name = "generic/object.html"
    tab = ViewTab(
        label=_("Pools"),
        badge=get_pool_count,
        permission="netbox_dhcp_kea_plugin.view_subnetpool",
    )
    layout = layout.Layout(
        layout.Row(layout.Column(TemplatePanel("netbox_dhcp_kea_plugin/panels/subnet_pools.html"))),
    )

    def get_extra_context(self, request, instance):
        subnet = instance
        pools = subnet.get_pools()

        # Get IP ranges and their SubnetPool configs
        ip_ranges = subnet.prefix.get_child_ranges().filter(mark_utilized=False)
        pool_configs = {
            sp.ip_range_id: sp
            for sp in SubnetPool.objects.filter(subnet=subnet, ip_range__in=ip_ranges)
            .select_related("client_class", "ip_range")
            .prefetch_related("evaluate_additional_classes", "option_data")
        }

        # Build enriched pool data for the template
        pool_data = []
        for ip_range in ip_ranges:
            start_ip = str(ip_range.start_address).split("/")[0]
            end_ip = str(ip_range.end_address).split("/")[0]
            subnet_pool = pool_configs.get(ip_range.pk)
            pool_data.append(
                {
                    "ip_range": ip_range,
                    "pool_range": f"{start_ip} - {end_ip}",
                    "subnet_pool": subnet_pool,
                    "client_class": subnet_pool.client_class if subnet_pool else None,
                    "additional_classes": list(subnet_pool.evaluate_additional_classes.all()) if subnet_pool else [],
                    "option_data": list(subnet_pool.option_data.all()) if subnet_pool else [],
                }
            )

        # Also include computed pools (from available IPs) that don't have IP ranges
        has_ip_ranges = ip_ranges.exists()

        return {
            "pool_data": pool_data,
            "pools": pools,
            "has_ip_ranges": has_ip_ranges,
            "pool_config_count": len(pool_configs),
        }


@register_model_view(models.Subnet, name="reservations", path="reservations")
class SubnetReservationsView(generic.ObjectView):
    """Reservations derived from devices and VMs, plus static ones, and their KEA entries."""

    queryset = models.Subnet.objects.select_related("prefix")
    template_name = "generic/object.html"
    tab = ViewTab(
        label=_("Reservations"),
        badge=get_reservation_count,
        permission="netbox_dhcp_kea_plugin.view_subnet",
    )
    layout = layout.Layout(
        layout.Row(
            layout.Column(
                TemplatePanel("netbox_dhcp_kea_plugin/panels/subnet_reservations.html", title=_("DHCP Reservations")),
                width=8,
            ),
            layout.Column(
                ui_panels.KeaJSONPanel(
                    lambda _subnet, ctx: ctx["kea_reservations"],
                    title=_("KEA Reservations Configuration"),
                    element_id="subnet-reservations-kea",
                ),
                width=4,
            ),
        ),
    )

    def get_extra_context(self, request, instance):
        reservations = instance.get_reservations()
        return {
            "reservations": reservations,
            "reservation_count": len(reservations),
            "skipped_count": sum(1 for _, meta in reservations if not meta["has_hw_address"]),
            "kea_reservations": instance.get_kea_reservations(),
        }


# SubnetPool Views
@register_model_view(models.SubnetPool)
class SubnetPoolView(generic.ObjectView):
    queryset = SubnetPool.objects.select_related("subnet", "ip_range", "client_class", "ddns_policy").prefetch_related(
        "evaluate_additional_classes", "option_data"
    )
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.SubnetPoolPanel(),
            ui_panels.RedundantEvaluationClassesPanel(),
            TagsPanel(),
        ],
        right_panels=[
            ui_panels.KeaJSONPanel(
                lambda pool, _ctx: pool.to_kea_dict(),
                title=_("KEA Pool Configuration"),
                element_id="subnetpool-kea",
            ),
            CustomFieldsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                "netbox_dhcp_kea_plugin.OptionData",
                title=_("Pool Option Data"),
                filters={"pool_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


@register_model_view(models.SubnetPool, "list", path="", detail=False)
class SubnetPoolListView(generic.ObjectListView):
    queryset = SubnetPool.objects.select_related("subnet", "ip_range", "client_class")
    table = tables.SubnetPoolTable
    filterset = filtersets.SubnetPoolFilterSet
    filterset_form = forms.SubnetPoolFilterForm


@register_model_view(models.SubnetPool, "add", detail=False)
@register_model_view(models.SubnetPool, "edit")
class SubnetPoolEditView(generic.ObjectEditView):
    queryset = SubnetPool.objects.all()
    form = forms.SubnetPoolForm


@register_model_view(models.SubnetPool, "delete")
class SubnetPoolDeleteView(generic.ObjectDeleteView):
    queryset = SubnetPool.objects.all()


@register_model_view(models.SubnetPool, "bulk_delete", path="delete", detail=False)
class SubnetPoolBulkDeleteView(generic.BulkDeleteView):
    queryset = SubnetPool.objects.all()
    filterset = filtersets.SubnetPoolFilterSet
    table = tables.SubnetPoolTable


@register_model_view(models.SubnetPool, "bulk_import", path="import", detail=False)
class SubnetPoolImportView(generic.BulkImportView):
    queryset = SubnetPool.objects.all()
    model_form = forms.SubnetPoolImportForm


# --- Static Reservation Views ---


@register_model_view(models.StaticReservation)
class StaticReservationView(generic.ObjectView):
    queryset = models.StaticReservation.objects.select_related("subnet", "ip_address", "mac_address")
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[
            ui_panels.StaticReservationPanel(),
            TagsPanel(),
        ],
        right_panels=[
            ui_panels.StaticReservationSourcePanel(),
            ui_panels.KeaJSONPanel(
                lambda reservation, _ctx: reservation.to_kea_dict(),
                title=_("Kea Reservation"),
                element_id="staticreservation-kea",
            ),
            CustomFieldsPanel(),
        ],
    )


@register_model_view(models.StaticReservation, "list", path="", detail=False)
class StaticReservationListView(generic.ObjectListView):
    queryset = models.StaticReservation.objects.select_related("subnet", "ip_address", "mac_address")
    table = tables.StaticReservationTable
    filterset = filtersets.StaticReservationFilterSet
    filterset_form = forms.StaticReservationFilterForm


@register_model_view(models.StaticReservation, "add", detail=False)
@register_model_view(models.StaticReservation, "edit")
class StaticReservationEditView(generic.ObjectEditView):
    queryset = models.StaticReservation.objects.all()
    form = forms.StaticReservationForm


@register_model_view(models.StaticReservation, "delete")
class StaticReservationDeleteView(generic.ObjectDeleteView):
    queryset = models.StaticReservation.objects.all()


@register_model_view(models.StaticReservation, "bulk_delete", path="delete", detail=False)
class StaticReservationBulkDeleteView(generic.BulkDeleteView):
    queryset = models.StaticReservation.objects.select_related("subnet", "ip_address", "mac_address")
    filterset = filtersets.StaticReservationFilterSet
    table = tables.StaticReservationTable


@register_model_view(models.StaticReservation, "bulk_import", path="import", detail=False)
class StaticReservationImportView(generic.BulkImportView):
    queryset = models.StaticReservation.objects.all()
    model_form = forms.StaticReservationImportForm


# --- Stork Server Views ---


@register_model_view(models.StorkServer)
class StorkServerView(generic.ObjectView):
    queryset = models.StorkServer.objects.prefetch_related("agent_groups")

    def get_extra_context(self, request, instance):
        return {
            # Dialling an address over TLS is unusual but not impossible, so
            # this is shown rather than enforced at save time.
            "tls_verification_warnings": instance.tls_verification_warnings(),
            "endpoint_record": instance.endpoint_record(),
        }


@register_model_view(models.StorkServer, "list", path="", detail=False)
class StorkServerListView(generic.ObjectListView):
    queryset = models.StorkServer.objects.annotate(
        agent_groups_count=Count("agent_groups", distinct=True),
    )
    table = tables.StorkServerTable
    filterset = filtersets.StorkServerFilterSet
    filterset_form = forms.StorkServerFilterForm


@register_model_view(models.StorkServer, "add", detail=False)
@register_model_view(models.StorkServer, "edit")
class StorkServerEditView(generic.ObjectEditView):
    queryset = models.StorkServer.objects.all()
    form = forms.StorkServerForm


@register_model_view(models.StorkServer, "delete")
class StorkServerDeleteView(generic.ObjectDeleteView):
    queryset = models.StorkServer.objects.all()


@register_model_view(models.StorkServer, "bulk_delete", path="delete", detail=False)
class StorkServerBulkDeleteView(generic.BulkDeleteView):
    queryset = models.StorkServer.objects.all()
    filterset = filtersets.StorkServerFilterSet
    table = tables.StorkServerTable


@register_model_view(models.StorkServer, "bulk_import", path="import", detail=False)
class StorkServerImportView(generic.BulkImportView):
    queryset = models.StorkServer.objects.all()
    model_form = forms.StorkServerImportForm


def get_storkserver_agent_groups_count(obj):
    """Get the number of agent groups for a Stork server."""
    return obj.agent_groups.count()


@register_model_view(models.StorkServer, name="agent_groups", path="agent-groups")
class StorkServerAgentGroupsView(generic.ObjectView):
    queryset = models.StorkServer.objects.all()
    template_name = "netbox_dhcp_kea_plugin/storkserver_agent_groups.html"
    tab = ViewTab(
        label="Agent Groups",
        badge=get_storkserver_agent_groups_count,
        permission="netbox_dhcp_kea_plugin.view_storkserver",
    )

    def get(self, request, pk):
        stork_server = self.get_object(pk=pk)
        agent_groups = stork_server.agent_groups.all()

        return render(
            request,
            self.template_name,
            {
                "object": stork_server,
                "agent_groups": agent_groups,
                "tab": self.tab,
            },
        )


@register_model_view(models.StorkServer, name="config", path="config")
class StorkServerConfigView(generic.ObjectView):
    queryset = models.StorkServer.objects.all()
    template_name = "netbox_dhcp_kea_plugin/storkserver_config.html"
    tab = ViewTab(
        label="Configuration",
        permission="netbox_dhcp_kea_plugin.view_storkserver",
    )

    def get(self, request, pk):
        from django.http import HttpResponse

        server = self.get_object(pk=pk)
        env_content = server.to_env_content()

        if request.GET.get("export") == "stork-server-config":
            response = HttpResponse(env_content, content_type="text/plain")
            filename = f"{server.name}_stork-server.env"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return render(
            request,
            self.template_name,
            {
                "object": server,
                "tab": self.tab,
                "env_content": env_content,
            },
        )


# --- Stork Agent Group Views ---


@register_model_view(models.StorkAgentGroup)
class StorkAgentGroupView(generic.ObjectView):
    queryset = models.StorkAgentGroup.objects.select_related("stork_server").prefetch_related("servers")


@register_model_view(models.StorkAgentGroup, "list", path="", detail=False)
class StorkAgentGroupListView(generic.ObjectListView):
    queryset = models.StorkAgentGroup.objects.annotate(
        servers_count=Count("servers", distinct=True),
    )
    table = tables.StorkAgentGroupTable
    filterset = filtersets.StorkAgentGroupFilterSet
    filterset_form = forms.StorkAgentGroupFilterForm


@register_model_view(models.StorkAgentGroup, "add", detail=False)
@register_model_view(models.StorkAgentGroup, "edit")
class StorkAgentGroupEditView(generic.ObjectEditView):
    queryset = models.StorkAgentGroup.objects.all()
    form = forms.StorkAgentGroupForm


@register_model_view(models.StorkAgentGroup, "delete")
class StorkAgentGroupDeleteView(generic.ObjectDeleteView):
    queryset = models.StorkAgentGroup.objects.all()


@register_model_view(models.StorkAgentGroup, "bulk_delete", path="delete", detail=False)
class StorkAgentGroupBulkDeleteView(generic.BulkDeleteView):
    queryset = models.StorkAgentGroup.objects.all()
    filterset = filtersets.StorkAgentGroupFilterSet
    table = tables.StorkAgentGroupTable


@register_model_view(models.StorkAgentGroup, "bulk_import", path="import", detail=False)
class StorkAgentGroupImportView(generic.BulkImportView):
    queryset = models.StorkAgentGroup.objects.all()
    model_form = forms.StorkAgentGroupImportForm


def get_storkagentgroup_servers_count(obj):
    """Get the number of servers in a Stork agent group."""
    return obj.servers.count()


@register_model_view(models.StorkAgentGroup, name="servers", path="servers")
class StorkAgentGroupServersView(generic.ObjectView):
    queryset = models.StorkAgentGroup.objects.all()
    template_name = "netbox_dhcp_kea_plugin/storkagentgroup_servers.html"
    tab = ViewTab(
        label="Servers",
        badge=get_storkagentgroup_servers_count,
        permission="netbox_dhcp_kea_plugin.view_storkagentgroup",
    )

    def get(self, request, pk):
        agent_group = self.get_object(pk=pk)
        servers = agent_group.servers.all()

        return render(
            request,
            self.template_name,
            {
                "object": agent_group,
                "servers": servers,
                "tab": self.tab,
            },
        )


@register_model_view(models.StorkAgentGroup, name="config", path="config")
class StorkAgentGroupConfigView(generic.ObjectView):
    queryset = models.StorkAgentGroup.objects.all()
    template_name = "netbox_dhcp_kea_plugin/storkagentgroup_config.html"
    tab = ViewTab(
        label="Configuration",
        permission="netbox_dhcp_kea_plugin.view_storkagentgroup",
    )

    def get(self, request, pk):
        from django.http import HttpResponse

        agent_group = self.get_object(pk=pk)

        # Download env file for a specific server: ?server=<id>
        server_id = request.GET.get("server")
        if server_id:
            try:
                server = agent_group.servers.select_related("ip_address").get(pk=int(server_id))
                env_content = agent_group.to_env_content(server=server)
                response = HttpResponse(env_content, content_type="text/plain")
                filename = f"{server.name}_stork-agent.env"
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response
            except (ValueError, models.DHCPServer.DoesNotExist):
                pass

        # Display generic template with placeholder
        env_content = agent_group.to_env_content()

        return render(
            request,
            self.template_name,
            {
                "object": agent_group,
                "tab": self.tab,
                "env_content": env_content,
            },
        )


# --- TSIGKey Views ---


@register_model_view(models.TSIGKey)
class TSIGKeyView(generic.ObjectView):
    queryset = models.TSIGKey.objects.all()

    def get_extra_context(self, request, instance):
        return {
            "can_view_secret": request.user.has_perm("netbox_dhcp_kea_plugin.view_secret_tsigkey"),
        }


@register_model_view(models.TSIGKey, "list", path="", detail=False)
class TSIGKeyListView(generic.ObjectListView):
    queryset = models.TSIGKey.objects.all()
    table = tables.TSIGKeyTable
    filterset = filtersets.TSIGKeyFilterSet
    filterset_form = forms.TSIGKeyFilterForm


@register_model_view(models.TSIGKey, "add", detail=False)
@register_model_view(models.TSIGKey, "edit")
class TSIGKeyEditView(generic.ObjectEditView):
    queryset = models.TSIGKey.objects.all()
    form = forms.TSIGKeyForm


@register_model_view(models.TSIGKey, "delete")
class TSIGKeyDeleteView(generic.ObjectDeleteView):
    queryset = models.TSIGKey.objects.all()


@register_model_view(models.TSIGKey, "bulk_delete", path="delete", detail=False)
class TSIGKeyBulkDeleteView(generic.BulkDeleteView):
    queryset = models.TSIGKey.objects.all()
    filterset = filtersets.TSIGKeyFilterSet
    table = tables.TSIGKeyTable


@register_model_view(models.TSIGKey, "bulk_import", path="import", detail=False)
class TSIGKeyImportView(generic.BulkImportView):
    queryset = models.TSIGKey.objects.all()
    model_form = forms.TSIGKeyImportForm


# --- D2Daemon Views ---


@register_model_view(models.D2Daemon)
class D2DaemonView(generic.ObjectView):
    queryset = models.D2Daemon.objects.select_related("ip_address").prefetch_related("hook_groups")

    def get_extra_context(self, request, instance):
        # Rows saved before a check existed are never re-validated.
        return {
            "configuration_errors": instance.configuration_errors(),
            "servers": instance.servers_using(),
        }


@register_model_view(models.D2Daemon, "list", path="", detail=False)
class D2DaemonListView(generic.ObjectListView):
    queryset = models.D2Daemon.objects.all()
    table = tables.D2DaemonTable
    filterset = filtersets.D2DaemonFilterSet
    filterset_form = forms.D2DaemonFilterForm


@register_model_view(models.D2Daemon, "add", detail=False)
@register_model_view(models.D2Daemon, "edit")
class D2DaemonEditView(generic.ObjectEditView):
    queryset = models.D2Daemon.objects.all()
    form = forms.D2DaemonForm


@register_model_view(models.D2Daemon, "delete")
class D2DaemonDeleteView(generic.ObjectDeleteView):
    queryset = models.D2Daemon.objects.all()


@register_model_view(models.D2Daemon, "bulk_delete", path="delete", detail=False)
class D2DaemonBulkDeleteView(generic.BulkDeleteView):
    queryset = models.D2Daemon.objects.all()
    filterset = filtersets.D2DaemonFilterSet
    table = tables.D2DaemonTable


@register_model_view(models.D2Daemon, "bulk_import", path="import", detail=False)
class D2DaemonImportView(generic.BulkImportView):
    queryset = models.D2Daemon.objects.all()
    model_form = forms.D2DaemonImportForm


def get_d2daemon_servers_count(obj):
    return obj.servers_using().count()


@register_model_view(models.D2Daemon, name="domains", path="domains")
class D2DaemonDomainsView(generic.ObjectView):
    """The domains each server using the daemon derives, and why."""

    queryset = models.D2Daemon.objects.all()
    template_name = "netbox_dhcp_kea_plugin/d2daemon_domains.html"
    tab = ViewTab(
        label="Servers & Domains",
        badge=get_d2daemon_servers_count,
        permission="netbox_dhcp_kea_plugin.view_d2daemon",
    )

    def get(self, request, pk):
        from .ddns import group_by_relationship

        daemon = self.get_object(pk=pk)
        derived_by_server = [(server, server.derived_ddns()) for server in daemon.servers_using()]
        return render(
            request,
            self.template_name,
            {"object": daemon, "groups": group_by_relationship(derived_by_server), "tab": self.tab},
        )


def _d2_config_context(request, render_config, contains_secrets, requires_substitution):
    """Render a D2 configuration for display, hiding secrets the user may not see.

    Viewing a configuration must not reveal what the TSIG key page itself
    withholds, so secrets NetBox holds are redacted without view_secret_tsigkey.
    """
    secrets_redacted = contains_secrets and not request.user.has_perm("netbox_dhcp_kea_plugin.view_secret_tsigkey")
    config = render_config(secrets_redacted)
    return {
        "requires_secret_substitution": requires_substitution,
        "secrets_redacted": secrets_redacted,
        "config_json": json.dumps(config, indent=2) if config is not None else None,
    }


@register_model_view(models.D2Daemon, name="config", path="config")
class D2DaemonConfigView(generic.ObjectView):
    queryset = models.D2Daemon.objects.all()
    template_name = "netbox_dhcp_kea_plugin/d2daemon_config.html"
    tab = ViewTab(
        label="Configuration",
        permission="netbox_dhcp_kea_plugin.view_d2daemon",
    )

    def get(self, request, pk):
        daemon = self.get_object(pk=pk)
        context = {"object": daemon, "tab": self.tab, "servers": daemon.servers_using()}
        if not daemon.is_local:
            domains, _errors = daemon.derived_domains()
            context.update(
                _d2_config_context(
                    request,
                    lambda redact: daemon.render(domains, redact_secrets=redact),
                    daemon.contains_secrets(domains),
                    daemon.requires_secret_substitution(domains),
                )
            )
        return render(request, self.template_name, context)


@register_model_view(models.DHCPServer, name="d2config", path="d2-config")
class DHCPServerD2ConfigView(generic.ObjectView):
    """This host's derived D2 domains and its kea-dhcp-ddns configuration."""

    queryset = models.DHCPServer.objects.select_related("ha_relationship", "d2_daemon")
    template_name = "netbox_dhcp_kea_plugin/dhcpserver_d2config.html"
    tab = ViewTab(
        label="D2 Configuration",
        visible=_ddns_enabled,
        permission="netbox_dhcp_kea_plugin.view_dhcpserver",
        weight=1600,
    )

    def get(self, request, pk):
        # Routed with every server view, so refuse it here when DDNS is off.
        if not _ddns_enabled():
            raise Http404
        server = self.get_object(pk=pk)
        derived = server.derived_ddns()
        context = {
            "object": server,
            "tab": self.tab,
            "daemon": server.effective_d2_daemon,
            "runs_local_d2": server.runs_local_d2(),
            "derived": derived,
        }
        if server.runs_local_d2():
            context.update(
                _d2_config_context(
                    request,
                    lambda redact: server.d2_kea_dict(redact_secrets=redact, derived=derived),
                    server.d2_contains_secrets(derived),
                    server.d2_requires_secret_substitution(derived),
                )
            )
        return render(request, self.template_name, context)


# --- DDNSDomain Views ---


@register_model_view(models.DDNSDomain)
class DDNSDomainView(generic.ObjectView):
    queryset = models.DDNSDomain.objects.select_related(
        "dhcp_server", "ha_relationship", "zone", "tsig_key"
    ).prefetch_related("zone__nameservers")

    def get_extra_context(self, request, instance):
        # What each nameserver renders as, with the override (if any) that shapes it.
        return {"nameserver_entries": instance.nameserver_entries()}


@register_model_view(models.DDNSDomain, "list", path="", detail=False)
class DDNSDomainListView(generic.ObjectListView):
    queryset = models.DDNSDomain.objects.all()
    table = tables.DDNSDomainTable
    filterset = filtersets.DDNSDomainFilterSet
    filterset_form = forms.DDNSDomainFilterForm


@register_model_view(models.DDNSDomain, "add", detail=False)
@register_model_view(models.DDNSDomain, "edit")
class DDNSDomainEditView(generic.ObjectEditView):
    queryset = models.DDNSDomain.objects.all()
    form = forms.DDNSDomainForm


@register_model_view(models.DDNSDomain, "delete")
class DDNSDomainDeleteView(generic.ObjectDeleteView):
    queryset = models.DDNSDomain.objects.all()


@register_model_view(models.DDNSDomain, "bulk_edit", path="edit", detail=False)
class DDNSDomainBulkEditView(generic.BulkEditView):
    queryset = models.DDNSDomain.objects.all()
    filterset = filtersets.DDNSDomainFilterSet
    table = tables.DDNSDomainTable
    form = forms.DDNSDomainBulkEditForm


@register_model_view(models.DDNSDomain, "bulk_delete", path="delete", detail=False)
class DDNSDomainBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DDNSDomain.objects.all()
    filterset = filtersets.DDNSDomainFilterSet
    table = tables.DDNSDomainTable


@register_model_view(models.DDNSDomain, "bulk_import", path="import", detail=False)
class DDNSDomainImportView(generic.BulkImportView):
    queryset = models.DDNSDomain.objects.all()
    model_form = forms.DDNSDomainImportForm


# --- DDNSServerOverride Views ---


@register_model_view(models.DDNSServerOverride)
class DDNSServerOverrideView(generic.ObjectView):
    queryset = models.DDNSServerOverride.objects.select_related("ddns_domain", "ddns_domain__zone", "tsig_key")


@register_model_view(models.DDNSServerOverride, "list", path="", detail=False)
class DDNSServerOverrideListView(generic.ObjectListView):
    queryset = models.DDNSServerOverride.objects.select_related("ddns_domain", "tsig_key")
    table = tables.DDNSServerOverrideTable
    filterset = filtersets.DDNSServerOverrideFilterSet
    filterset_form = forms.DDNSServerOverrideFilterForm


@register_model_view(models.DDNSServerOverride, "add", detail=False)
@register_model_view(models.DDNSServerOverride, "edit")
class DDNSServerOverrideEditView(generic.ObjectEditView):
    queryset = models.DDNSServerOverride.objects.all()
    form = forms.DDNSServerOverrideForm


@register_model_view(models.DDNSServerOverride, "delete")
class DDNSServerOverrideDeleteView(generic.ObjectDeleteView):
    queryset = models.DDNSServerOverride.objects.all()


@register_model_view(models.DDNSServerOverride, "bulk_delete", path="delete", detail=False)
class DDNSServerOverrideBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DDNSServerOverride.objects.all()
    filterset = filtersets.DDNSServerOverrideFilterSet
    table = tables.DDNSServerOverrideTable


# --- DDNSPolicy Views ---


@register_model_view(models.DDNSPolicy)
class DDNSPolicyView(generic.ObjectView):
    queryset = models.DDNSPolicy.objects.prefetch_related("servers", "subnets", "pools")


@register_model_view(models.DDNSPolicy, "list", path="", detail=False)
class DDNSPolicyListView(generic.ObjectListView):
    queryset = models.DDNSPolicy.objects.annotate(
        servers_count=Count("servers", distinct=True),
        subnets_count=Count("subnets", distinct=True),
        pools_count=Count("pools", distinct=True),
    )
    table = tables.DDNSPolicyTable
    filterset = filtersets.DDNSPolicyFilterSet
    filterset_form = forms.DDNSPolicyFilterForm


@register_model_view(models.DDNSPolicy, "add", detail=False)
@register_model_view(models.DDNSPolicy, "edit")
class DDNSPolicyEditView(generic.ObjectEditView):
    queryset = models.DDNSPolicy.objects.all()
    form = forms.DDNSPolicyForm


@register_model_view(models.DDNSPolicy, "delete")
class DDNSPolicyDeleteView(generic.ObjectDeleteView):
    queryset = models.DDNSPolicy.objects.all()


@register_model_view(models.DDNSPolicy, "bulk_delete", path="delete", detail=False)
class DDNSPolicyBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DDNSPolicy.objects.all()
    filterset = filtersets.DDNSPolicyFilterSet
    table = tables.DDNSPolicyTable


@register_model_view(models.DDNSPolicy, "bulk_import", path="import", detail=False)
class DDNSPolicyImportView(generic.BulkImportView):
    queryset = models.DDNSPolicy.objects.all()
    model_form = forms.DDNSPolicyImportForm


def get_ddnspolicy_servers_count(obj):
    return obj.servers.count()


def get_ddnspolicy_subnets_count(obj):
    return obj.subnets.count()


def get_ddnspolicy_pools_count(obj):
    return obj.pools.count()


@register_model_view(models.DDNSPolicy, name="servers", path="servers")
class DDNSPolicyServersView(generic.ObjectView):
    queryset = models.DDNSPolicy.objects.all()
    template_name = "netbox_dhcp_kea_plugin/ddnspolicy_servers.html"
    tab = ViewTab(
        label="Servers",
        badge=get_ddnspolicy_servers_count,
        permission="netbox_dhcp_kea_plugin.view_ddnspolicy",
    )

    def get(self, request, pk):
        policy = self.get_object(pk=pk)
        return render(
            request,
            self.template_name,
            {"object": policy, "servers": policy.servers.all(), "tab": self.tab},
        )


@register_model_view(models.DDNSPolicy, name="subnets", path="subnets")
class DDNSPolicySubnetsView(generic.ObjectView):
    queryset = models.DDNSPolicy.objects.all()
    template_name = "netbox_dhcp_kea_plugin/ddnspolicy_subnets.html"
    tab = ViewTab(
        label="Subnets",
        badge=get_ddnspolicy_subnets_count,
        permission="netbox_dhcp_kea_plugin.view_ddnspolicy",
    )

    def get(self, request, pk):
        policy = self.get_object(pk=pk)
        return render(
            request,
            self.template_name,
            {"object": policy, "subnets": policy.subnets.all(), "tab": self.tab},
        )


@register_model_view(models.DDNSPolicy, name="pools", path="pools")
class DDNSPolicyPoolsView(generic.ObjectView):
    queryset = models.DDNSPolicy.objects.all()
    template_name = "netbox_dhcp_kea_plugin/ddnspolicy_pools.html"
    tab = ViewTab(
        label="Pools",
        badge=get_ddnspolicy_pools_count,
        permission="netbox_dhcp_kea_plugin.view_ddnspolicy",
    )

    def get(self, request, pk):
        policy = self.get_object(pk=pk)
        pools = policy.pools.select_related("subnet", "subnet__prefix", "ip_range")
        return render(
            request,
            self.template_name,
            {"object": policy, "pools": pools, "tab": self.tab},
        )
