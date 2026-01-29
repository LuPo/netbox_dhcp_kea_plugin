import json

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from . import filtersets, forms, models, tables


# VendorOptionSpace Views
class VendorOptionSpaceView(generic.ObjectView):
    queryset = models.VendorOptionSpace.objects.annotate(definitions_count=Count("option_definitions"))


class VendorOptionSpaceListView(generic.ObjectListView):
    queryset = models.VendorOptionSpace.objects.annotate(definitions_count=Count("option_definitions"))
    table = tables.VendorOptionSpaceTable
    filterset = filtersets.VendorOptionSpaceFilterSet
    filterset_form = forms.VendorOptionSpaceFilterForm


class VendorOptionSpaceEditView(generic.ObjectEditView):
    queryset = models.VendorOptionSpace.objects.all()
    form = forms.VendorOptionSpaceForm


class VendorOptionSpaceDeleteView(generic.ObjectDeleteView):
    queryset = models.VendorOptionSpace.objects.all()


class VendorOptionSpaceBulkDeleteView(generic.BulkDeleteView):
    queryset = models.VendorOptionSpace.objects.all()
    filterset = filtersets.VendorOptionSpaceFilterSet
    table = tables.VendorOptionSpaceTable


class VendorOptionSpaceImportView(generic.BulkImportView):
    queryset = models.VendorOptionSpace.objects.all()
    model_form = forms.VendorOptionSpaceImportForm


# OptionDefinition Views
class OptionDefinitionView(generic.ObjectView):
    queryset = models.OptionDefinition.objects.select_related("vendor_option_space")


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


class OptionDefinitionBulkDeleteView(generic.BulkDeleteView):
    queryset = models.OptionDefinition.objects.filter(is_standard=False)
    filterset = filtersets.OptionDefinitionFilterSet
    table = tables.OptionDefinitionTable


class OptionDefinitionImportView(generic.BulkImportView):
    queryset = models.OptionDefinition.objects.all()
    model_form = forms.OptionDefinitionImportForm


# OptionData Views
class OptionDataView(generic.ObjectView):
    queryset = models.OptionData.objects.select_related("definition", "vendor_option_space")


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


class OptionDataEditView(generic.ObjectEditView):
    queryset = models.OptionData.objects.all()
    form = forms.OptionDataForm


class OptionDataDeleteView(generic.ObjectDeleteView):
    queryset = models.OptionData.objects.all()


class OptionDataBulkDeleteView(generic.BulkDeleteView):
    queryset = models.OptionData.objects.all()
    filterset = filtersets.OptionDataFilterSet
    table = tables.OptionDataTable


class OptionDataImportView(generic.BulkImportView):
    queryset = models.OptionData.objects.all()
    model_form = forms.OptionDataImportForm


@register_model_view(models.OptionData, name="client_classes", path="client-classes")
class OptionDataClientClassesView(generic.ObjectView):
    queryset = models.OptionData.objects.prefetch_related("client_classes")
    template_name = "netbox_dhcp_kea_plugin/optiondata_clientclasses.html"
    tab = ViewTab(
        label="Client Classes",
        badge=lambda obj: obj.client_classes.count(),
        permission="netbox_dhcp_kea_plugin.view_optiondata",
    )

    def get(self, request, pk):
        option_data = self.get_object(pk=pk)
        return render(
            request,
            self.template_name,
            {
                "object": option_data,
                "tab": self.tab,
            },
        )


# DHCPServer Views
class DHCPServerView(generic.ObjectView):
    queryset = models.DHCPServer.objects.all()

    def get_extra_context(self, request, instance):
        # Get configuration summary counts
        kea_config = instance.to_kea_dict()
        dhcp4 = kea_config.get("Dhcp4", {})
        return {
            "subnet_count": len(dhcp4.get("subnet4", [])),
            "client_class_count": len(dhcp4.get("client-classes", [])),
            "global_option_count": len(dhcp4.get("option-data", [])),
            "option_def_count": len(dhcp4.get("option-def", [])),
        }


class DHCPServerListView(generic.ObjectListView):
    queryset = models.DHCPServer.objects.all()
    table = tables.DHCPServerTable
    filterset = filtersets.DHCPServerFilterSet
    filterset_form = forms.DHCPServerFilterForm


class DHCPServerEditView(generic.ObjectEditView):
    queryset = models.DHCPServer.objects.all()
    form = forms.DHCPServerForm


class DHCPServerDeleteView(generic.ObjectDeleteView):
    queryset = models.DHCPServer.objects.all()


class DHCPServerBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DHCPServer.objects.all()
    filterset = filtersets.DHCPServerFilterSet
    table = tables.DHCPServerTable


class DHCPServerImportView(generic.BulkImportView):
    queryset = models.DHCPServer.objects.all()
    model_form = forms.DHCPServerImportForm


@register_model_view(models.DHCPServer, name="prefixes", path="prefixes")
class DHCPServerPrefixesView(generic.ObjectView):
    queryset = models.DHCPServer.objects.all()
    template_name = "netbox_dhcp_kea_plugin/dhcpserver_prefixes.html"
    tab = ViewTab(
        label="Assigned Prefixes",
        badge=lambda obj: obj.prefix_configs.count(),
        visible=lambda obj: obj.is_ha_primary(),
        permission="netbox_dhcp_kea_plugin.view_dhcpserver",
    )

    def get(self, request, pk):
        server = self.get_object(pk=pk)
        prefix_configs = server.prefix_configs.select_related("prefix").all()
        return render(
            request,
            self.template_name,
            {
                "object": server,
                "prefix_configs": prefix_configs,
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
class ClientClassView(generic.ObjectView):
    queryset = models.ClientClass.objects.prefetch_related("option_data")

    def get_extra_context(self, request, instance):
        return {
            "kea_config_hex": instance.to_kea_json(ascii_format=False, indent=4),
            "kea_config_ascii": instance.to_kea_json(ascii_format=True, indent=4),
        }


class ClientClassListView(generic.ObjectListView):
    queryset = models.ClientClass.objects.annotate(option_data_count=Count("option_data"))
    table = tables.ClientClassTable
    filterset = filtersets.ClientClassFilterSet
    filterset_form = forms.ClientClassFilterForm


class ClientClassEditView(generic.ObjectEditView):
    queryset = models.ClientClass.objects.all()
    form = forms.ClientClassForm


class ClientClassDeleteView(generic.ObjectDeleteView):
    queryset = models.ClientClass.objects.all()


class ClientClassBulkDeleteView(generic.BulkDeleteView):
    queryset = models.ClientClass.objects.all()
    filterset = filtersets.ClientClassFilterSet
    table = tables.ClientClassTable


class ClientClassImportView(generic.BulkImportView):
    queryset = models.ClientClass.objects.all()
    model_form = forms.ClientClassImportForm


@register_model_view(models.ClientClass, name="servers", path="servers")
class ClientClassServersView(generic.ObjectView):
    queryset = models.ClientClass.objects.prefetch_related("servers")
    template_name = "netbox_dhcp_kea_plugin/clientclass_servers.html"
    tab = ViewTab(
        label="DHCP Servers",
        badge=lambda obj: obj.servers.count(),
        permission="netbox_dhcp_kea_plugin.view_clientclass",
    )

    def get(self, request, pk):
        client_class = self.get_object(pk=pk)
        return render(
            request,
            self.template_name,
            {
                "object": client_class,
                "tab": self.tab,
            },
        )


# PrefixDHCPConfig Views
class PrefixDHCPConfigView(generic.ObjectView):
    queryset = models.PrefixDHCPConfig.objects.select_related("prefix", "server").prefetch_related(
        "option_data", "client_classes"
    )

    def get_extra_context(self, request, instance):
        import json

        return {
            "kea_config": json.dumps(instance.to_kea_dict(), indent=2),
        }


class PrefixDHCPConfigListView(generic.ObjectListView):
    queryset = models.PrefixDHCPConfig.objects.select_related("prefix", "server")
    table = tables.PrefixDHCPConfigTable
    filterset = filtersets.PrefixDHCPConfigFilterSet
    filterset_form = forms.PrefixDHCPConfigFilterForm

    def get_table(self, data, request, bulk_actions=True):
        # Use export table for CSV/YAML exports
        if request.GET.get("export"):
            return tables.PrefixDHCPConfigExportTable(data)
        return super().get_table(data, request, bulk_actions)


class PrefixDHCPConfigEditView(generic.ObjectEditView):
    queryset = models.PrefixDHCPConfig.objects.all()
    form = forms.PrefixDHCPConfigForm

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


class PrefixDHCPConfigDeleteView(generic.ObjectDeleteView):
    queryset = models.PrefixDHCPConfig.objects.all()


class PrefixDHCPConfigBulkDeleteView(generic.BulkDeleteView):
    queryset = models.PrefixDHCPConfig.objects.all()
    filterset = filtersets.PrefixDHCPConfigFilterSet
    table = tables.PrefixDHCPConfigTable


class PrefixDHCPConfigImportView(generic.BulkImportView):
    queryset = models.PrefixDHCPConfig.objects.all()
    model_form = forms.PrefixDHCPConfigImportForm


# DHCPHARelationship Views
class DHCPHARelationshipView(generic.ObjectView):
    queryset = models.DHCPHARelationship.objects.prefetch_related("servers")


class DHCPHARelationshipListView(generic.ObjectListView):
    queryset = models.DHCPHARelationship.objects.annotate(servers_count=Count("servers"))
    table = tables.DHCPHARelationshipTable
    filterset = filtersets.DHCPHARelationshipFilterSet
    filterset_form = forms.DHCPHARelationshipFilterForm


class DHCPHARelationshipEditView(generic.ObjectEditView):
    queryset = models.DHCPHARelationship.objects.all()
    form = forms.DHCPHARelationshipForm


class DHCPHARelationshipDeleteView(generic.ObjectDeleteView):
    queryset = models.DHCPHARelationship.objects.all()


class DHCPHARelationshipBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DHCPHARelationship.objects.all()
    filterset = filtersets.DHCPHARelationshipFilterSet
    table = tables.DHCPHARelationshipTable


class DHCPHARelationshipImportView(generic.BulkImportView):
    queryset = models.DHCPHARelationship.objects.all()
    model_form = forms.DHCPHARelationshipImportForm


def get_reservation_count(obj):
    """Calculate the number of DHCP reservations for a PrefixDHCPConfig."""
    return len(obj.get_reservations())


@register_model_view(models.PrefixDHCPConfig, name="reservations", path="reservations")
class PrefixDHCPConfigReservationsView(generic.ObjectView):
    queryset = models.PrefixDHCPConfig.objects.select_related("prefix")
    template_name = "netbox_dhcp_kea_plugin/prefixdhcpconfig_reservations.html"
    tab = ViewTab(
        label="Reservations",
        badge=get_reservation_count,
        permission="netbox_dhcp_kea_plugin.view_prefixdhcpconfig",
    )

    def get(self, request, pk):
        config = self.get_object(pk=pk)
        reservations = config.get_reservations()

        return render(
            request,
            self.template_name,
            {
                "object": config,
                "reservations": reservations,
                "reservation_count": len(reservations),
                "kea_reservations": config.get_kea_reservations(),
                "tab": self.tab,
            },
        )
