import json

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from . import filtersets, forms, models, tables
from .models import SubnetPool


# Hook Views
class HookView(generic.ObjectView):
    queryset = models.Hook.objects.prefetch_related("hook_groups")


class HookListView(generic.ObjectListView):
    queryset = models.Hook.objects.annotate(hook_groups_count=Count("hook_groups"))
    table = tables.HookTable
    filterset = filtersets.HookFilterSet
    filterset_form = forms.HookFilterForm


class HookEditView(generic.ObjectEditView):
    queryset = models.Hook.objects.all()
    form = forms.HookForm


class HookDeleteView(generic.ObjectDeleteView):
    queryset = models.Hook.objects.all()


class HookBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Hook.objects.all()
    filterset = filtersets.HookFilterSet
    table = tables.HookTable


class HookImportView(generic.BulkImportView):
    queryset = models.Hook.objects.all()
    model_form = forms.HookImportForm


def get_hook_group_count(obj):
    """Get the number of hook groups for a hook."""
    return obj.hook_groups.count()


@register_model_view(models.Hook, name="hook_groups", path="hook-groups")
class HookHookGroupsView(generic.ObjectView):
    queryset = models.Hook.objects.all()
    template_name = "netbox_dhcp_kea_plugin/hook_hookgroups.html"
    tab = ViewTab(
        label="Hook Groups",
        badge=get_hook_group_count,
        permission="netbox_dhcp_kea_plugin.view_hook",
    )

    def get(self, request, pk):
        hook = self.get_object(pk=pk)
        hook_groups = hook.hook_groups.all()

        return render(
            request,
            self.template_name,
            {
                "object": hook,
                "hook_groups": hook_groups,
                "tab": self.tab,
            },
        )


# HookGroup Views
class HookGroupView(generic.ObjectView):
    queryset = models.HookGroup.objects.prefetch_related("hooks", "servers")


class HookGroupListView(generic.ObjectListView):
    queryset = models.HookGroup.objects.annotate(
        hooks_count=Count("hooks", distinct=True),
        servers_count=Count("servers", distinct=True),
    )
    table = tables.HookGroupTable
    filterset = filtersets.HookGroupFilterSet
    filterset_form = forms.HookGroupFilterForm


class HookGroupEditView(generic.ObjectEditView):
    queryset = models.HookGroup.objects.all()
    form = forms.HookGroupForm


class HookGroupDeleteView(generic.ObjectDeleteView):
    queryset = models.HookGroup.objects.all()


class HookGroupBulkDeleteView(generic.BulkDeleteView):
    queryset = models.HookGroup.objects.all()
    filterset = filtersets.HookGroupFilterSet
    table = tables.HookGroupTable


class HookGroupImportView(generic.BulkImportView):
    queryset = models.HookGroup.objects.all()
    model_form = forms.HookGroupImportForm


def get_hookgroup_hooks_count(obj):
    """Get the number of hooks in a hook group."""
    return obj.hooks.count()


@register_model_view(models.HookGroup, name="hooks", path="hooks")
class HookGroupHooksView(generic.ObjectView):
    queryset = models.HookGroup.objects.all()
    template_name = "netbox_dhcp_kea_plugin/hookgroup_hooks.html"
    tab = ViewTab(
        label="Hooks",
        badge=get_hookgroup_hooks_count,
        permission="netbox_dhcp_kea_plugin.view_hookgroup",
    )

    def get(self, request, pk):
        hook_group = self.get_object(pk=pk)
        hooks = hook_group.hooks.all()

        return render(
            request,
            self.template_name,
            {
                "object": hook_group,
                "hooks": hooks,
                "tab": self.tab,
            },
        )


def get_hookgroup_servers_count(obj):
    """Get the number of servers in a hook group."""
    return obj.servers.count()


@register_model_view(models.HookGroup, name="servers", path="servers")
class HookGroupServersView(generic.ObjectView):
    queryset = models.HookGroup.objects.all()
    template_name = "netbox_dhcp_kea_plugin/hookgroup_servers.html"
    tab = ViewTab(
        label="Servers",
        badge=get_hookgroup_servers_count,
        permission="netbox_dhcp_kea_plugin.view_hookgroup",
    )

    def get(self, request, pk):
        hook_group = self.get_object(pk=pk)
        servers = hook_group.servers.all()

        return render(
            request,
            self.template_name,
            {
                "object": hook_group,
                "servers": servers,
                "tab": self.tab,
            },
        )


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
        }


class DHCPServerListView(generic.ObjectListView):
    queryset = models.DHCPServer.objects.all()
    table = tables.DHCPServerTable
    filterset = filtersets.DHCPServerFilterSet
    filterset_form = forms.DHCPServerFilterForm


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


def _get_subnet_count_for_class(obj):
    """Count subnets where the client class is used as restricting or evaluate-additional."""
    from .models import Subnet

    return Subnet.objects.filter(Q(client_class=obj) | Q(evaluate_additional_classes=obj)).distinct().count()


@register_model_view(models.ClientClass, name="prefixes", path="prefixes")
class ClientClassPrefixesView(generic.ObjectView):
    queryset = models.ClientClass.objects.prefetch_related(
        "subnet_restrictions__prefix",
        "subnet_restrictions__server",
        "subnet_evaluations__prefix",
        "subnet_evaluations__server",
    )
    template_name = "netbox_dhcp_kea_plugin/clientclass_prefixes.html"
    tab = ViewTab(
        label="Subnets",
        badge=lambda obj: _get_subnet_count_for_class(obj),
        visible=lambda obj: obj.only_in_additional_list,
        permission="netbox_dhcp_kea_plugin.view_clientclass",
    )

    def get(self, request, pk):
        client_class = self.get_object(pk=pk)
        # Subnets where this class is the restricting client_class
        restricting_subnets = client_class.subnet_restrictions.select_related("prefix", "server").all()
        # Subnets where this class is in evaluate_additional_classes
        evaluation_subnets = client_class.subnet_evaluations.select_related("prefix", "server").all()
        # Combine and deduplicate
        all_subnet_ids = set(restricting_subnets.values_list("pk", flat=True)) | set(
            evaluation_subnets.values_list("pk", flat=True)
        )
        subnet_items = models.Subnet.objects.filter(pk__in=all_subnet_ids).select_related("prefix", "server")

        return render(
            request,
            self.template_name,
            {
                "object": client_class,
                "subnet_items": subnet_items,
                "tab": self.tab,
            },
        )


# Subnet Views
class SubnetView(generic.ObjectView):
    queryset = models.Subnet.objects.select_related("prefix", "server", "client_class").prefetch_related(
        "option_data", "evaluate_additional_classes"
    )

    def get_extra_context(self, request, instance):
        import json

        # Find evaluate_additional_classes entries that don't have only_in_additional_list set.
        # These classes are already evaluated globally by KEA, so listing them in
        # evaluate-additional-classes is redundant.
        redundant_eval_classes = list(instance.evaluate_additional_classes.filter(only_in_additional_list=False))

        return {
            "kea_config": json.dumps(instance.to_kea_dict(), indent=2),
            "pool_count": instance.subnet_pools.count(),
            "redundant_eval_classes": redundant_eval_classes,
        }


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


class SubnetDeleteView(generic.ObjectDeleteView):
    queryset = models.Subnet.objects.all()


class SubnetBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Subnet.objects.all()
    filterset = filtersets.SubnetFilterSet
    table = tables.SubnetTable


class SubnetImportView(generic.BulkImportView):
    queryset = models.Subnet.objects.all()
    model_form = forms.SubnetImportForm


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
    """Calculate the number of DHCP reservations for a Subnet."""
    return len(obj.get_reservations())


def get_pool_count(obj):
    """Calculate the number of configured SubnetPools for a Subnet."""
    return obj.subnet_pools.count()


@register_model_view(models.Subnet, name="pools", path="pools")
class SubnetPoolsView(generic.ObjectView):
    queryset = models.Subnet.objects.select_related("prefix")
    template_name = "netbox_dhcp_kea_plugin/subnet_pools.html"
    tab = ViewTab(
        label="Pools",
        badge=get_pool_count,
        permission="netbox_dhcp_kea_plugin.view_subnetpool",
    )

    def get(self, request, pk):
        subnet = self.get_object(pk=pk)
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

        return render(
            request,
            self.template_name,
            {
                "object": subnet,
                "pool_data": pool_data,
                "pools": pools,
                "has_ip_ranges": has_ip_ranges,
                "pool_config_count": len(pool_configs),
                "tab": self.tab,
            },
        )


@register_model_view(models.Subnet, name="reservations", path="reservations")
class SubnetReservationsView(generic.ObjectView):
    queryset = models.Subnet.objects.select_related("prefix")
    template_name = "netbox_dhcp_kea_plugin/subnet_reservations.html"
    tab = ViewTab(
        label="Reservations",
        badge=get_reservation_count,
        permission="netbox_dhcp_kea_plugin.view_subnet",
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


# SubnetPool Views
class SubnetPoolView(generic.ObjectView):
    queryset = SubnetPool.objects.select_related("subnet", "ip_range", "client_class").prefetch_related(
        "evaluate_additional_classes", "option_data"
    )

    def get_extra_context(self, request, instance):
        # Find evaluate_additional_classes entries that don't have only_in_additional_list set.
        # These classes are already evaluated globally by KEA, so listing them in
        # evaluate-additional-classes is redundant.
        redundant_eval_classes = list(instance.evaluate_additional_classes.filter(only_in_additional_list=False))

        return {
            "kea_pool_config": json.dumps(instance.to_kea_dict(), indent=2),
            "redundant_eval_classes": redundant_eval_classes,
        }


class SubnetPoolListView(generic.ObjectListView):
    queryset = SubnetPool.objects.select_related("subnet", "ip_range", "client_class")
    table = tables.SubnetPoolTable
    filterset = filtersets.SubnetPoolFilterSet
    filterset_form = forms.SubnetPoolFilterForm


class SubnetPoolEditView(generic.ObjectEditView):
    queryset = SubnetPool.objects.all()
    form = forms.SubnetPoolForm


class SubnetPoolDeleteView(generic.ObjectDeleteView):
    queryset = SubnetPool.objects.all()


class SubnetPoolBulkDeleteView(generic.BulkDeleteView):
    queryset = SubnetPool.objects.all()
    filterset = filtersets.SubnetPoolFilterSet
    table = tables.SubnetPoolTable


class SubnetPoolImportView(generic.BulkImportView):
    queryset = SubnetPool.objects.all()
    model_form = forms.SubnetPoolImportForm


# --- Stork Server Views ---


class StorkServerView(generic.ObjectView):
    queryset = models.StorkServer.objects.prefetch_related("agent_groups")


class StorkServerListView(generic.ObjectListView):
    queryset = models.StorkServer.objects.annotate(
        agent_groups_count=Count("agent_groups", distinct=True),
    )
    table = tables.StorkServerTable
    filterset = filtersets.StorkServerFilterSet
    filterset_form = forms.StorkServerFilterForm


class StorkServerEditView(generic.ObjectEditView):
    queryset = models.StorkServer.objects.all()
    form = forms.StorkServerForm


class StorkServerDeleteView(generic.ObjectDeleteView):
    queryset = models.StorkServer.objects.all()


class StorkServerBulkDeleteView(generic.BulkDeleteView):
    queryset = models.StorkServer.objects.all()
    filterset = filtersets.StorkServerFilterSet
    table = tables.StorkServerTable


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
        config = server.to_config_dict()
        config_json = json.dumps(config, indent=4)

        if request.GET.get("export") == "stork-server-config":
            response = HttpResponse(config_json, content_type="application/json")
            filename = f"{server.name}_stork-server-config.json"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        return render(
            request,
            self.template_name,
            {
                "object": server,
                "tab": self.tab,
                "config": config,
                "config_json": config_json,
            },
        )


# --- Stork Agent Group Views ---


class StorkAgentGroupView(generic.ObjectView):
    queryset = models.StorkAgentGroup.objects.select_related("stork_server").prefetch_related("servers")


class StorkAgentGroupListView(generic.ObjectListView):
    queryset = models.StorkAgentGroup.objects.annotate(
        servers_count=Count("servers", distinct=True),
    )
    table = tables.StorkAgentGroupTable
    filterset = filtersets.StorkAgentGroupFilterSet
    filterset_form = forms.StorkAgentGroupFilterForm


class StorkAgentGroupEditView(generic.ObjectEditView):
    queryset = models.StorkAgentGroup.objects.all()
    form = forms.StorkAgentGroupForm


class StorkAgentGroupDeleteView(generic.ObjectDeleteView):
    queryset = models.StorkAgentGroup.objects.all()


class StorkAgentGroupBulkDeleteView(generic.BulkDeleteView):
    queryset = models.StorkAgentGroup.objects.all()
    filterset = filtersets.StorkAgentGroupFilterSet
    table = tables.StorkAgentGroupTable


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
