"""Object detail panels, one per model, in the style of NetBox's own ``<app>/ui/panels.py``."""

from django.utils.translation import gettext_lazy as _
from netbox.ui import attrs, panels
from netbox.ui.actions import CopyContent

from netbox_dhcp_kea_plugin.ui.attrs import InheritedBooleanAttr, JSONAttr, SecondsAttr, hinted


class ConditionalTemplatePanel(panels.TemplatePanel):
    """A template panel shown only when ``condition(object)`` is true."""

    def __init__(self, template_name, condition, **kwargs):
        super().__init__(template_name, **kwargs)
        self.condition = condition

    def should_render(self, context):
        return bool(self.condition(context.get("object")))


class KeaJSONPanel(panels.ObjectPanel):
    """Kea JSON computed from the object, with a copy button.

    Parameters:
        data (callable): ``data(object, context)`` returning the JSON-able value, or None
        intro (str | callable): text shown above the JSON; a callable gets the object
        empty_message (str): shown instead when ``data`` returns None
        element_id (str): DOM id of the JSON block, for the copy button
    """

    template_name = "netbox_dhcp_kea_plugin/panels/kea_json.html"

    def __init__(self, data, intro=None, empty_message="", element_id="kea-json", **kwargs):
        super().__init__(**kwargs)
        self.data = data
        self.intro = intro
        self.empty_message = empty_message
        self.element_id = element_id
        self.actions.append(CopyContent(element_id))

    def get_context(self, context):
        ctx = super().get_context(context)
        obj = ctx["object"]
        intro = self.intro(obj) if callable(self.intro) else self.intro
        return {
            **ctx,
            "data": self.data(obj, context),
            "intro": intro,
            "empty_message": self.empty_message,
            "element_id": self.element_id,
        }


class HookPanel(panels.ObjectAttributesPanel):
    title = _("Hook Library")

    name = attrs.TextAttr("name")
    library_name = attrs.TextAttr("library_name", style="font-monospace")
    description = attrs.TextAttr("description")
    is_standard = attrs.BooleanAttr("is_standard", label=_("Standard hook"))
    allowed_processes = attrs.ArrayAttr("allowed_processes")


class HookGroupPanel(panels.ObjectAttributesPanel):
    title = _("Hook Group")

    name = attrs.TextAttr("name")
    description = attrs.TextAttr("description")
    library_path = attrs.TextAttr("library_path", style="font-monospace")
    d2_daemons = attrs.RelatedObjectListAttr("d2_daemons", linkify=True, label=_("D2 daemons"))


class VendorOptionSpacePanel(panels.ObjectAttributesPanel):
    title = _("Vendor Option Space")

    name = attrs.TextAttr("name")
    enterprise_id = attrs.NumericAttr("enterprise_id", label=_("Enterprise ID"))
    manufacturer = attrs.RelatedObjectAttr("manufacturer", linkify=True)
    description = attrs.TextAttr("description")


class OptionDefinitionPanel(panels.ObjectAttributesPanel):
    title = _("Option Definition")

    name = attrs.TextAttr("name")
    code = attrs.NumericAttr("code")
    option_type = attrs.ChoiceAttr("option_type", label=_("Type"))
    option_space = attrs.ChoiceAttr("option_space")
    vendor_option_space = attrs.RelatedObjectAttr("vendor_option_space", linkify=True)
    is_array = attrs.BooleanAttr("is_array", label=_("Array"))
    is_standard = attrs.BooleanAttr("is_standard", label=_("Standard option (RFC)"))
    encapsulate = attrs.TextAttr("encapsulate", label=_("Encapsulates"))
    record_types = attrs.TextAttr("record_types", style="font-monospace")
    description = attrs.TextAttr("description")


class OptionDataPanel(panels.ObjectAttributesPanel):
    title = _("Option Data")

    distinctive_name = attrs.TextAttr("distinctive_name")
    definition = attrs.RelatedObjectAttr("definition", linkify=True)
    vendor_option_space = attrs.RelatedObjectAttr("vendor_option_space", linkify=True)
    delivery_type = attrs.ChoiceAttr("delivery_type")
    data = attrs.TextAttr("data", style="font-monospace")
    ascii_data = attrs.TextAttr("ascii_data", label=_("ASCII data"))
    always_send = attrs.BooleanAttr("always_send")
    csv_format = attrs.BooleanAttr("csv_format", label=_("CSV format"))
    description = attrs.TextAttr("description")


class OptionIPSourcesPanel(panels.ObjectPanel):
    """The IP sources an option's data is resolved from, when it has any."""

    template_name = "netbox_dhcp_kea_plugin/panels/option_ip_sources.html"
    title = _("IP Sources")

    def get_context(self, context):
        from netbox_dhcp_kea_plugin.models import OptionData

        ctx = super().get_context(context)
        sources = list(ctx["object"].ip_sources.order_by("ordinal"))
        for source in sources:
            source.resolved_ip = OptionData._resolve_ip(source.ip_source)
        return {**ctx, "ip_sources": sources}

    def should_render(self, context):
        return bool(context["ip_sources"])


class ClientClassPanel(panels.ObjectAttributesPanel):
    title = _("Client Class")

    name = attrs.TextAttr("name")
    test_expression = attrs.TextAttr("test_expression", style="font-monospace")
    template_test = attrs.BooleanAttr(
        "template_test",
        label=hinted(
            _("Template class"),
            _(
                "Rendered as template-test. KEA spawns a subclass named SPAWN_<class>_<value> per distinct "
                "result, so one class definition yields one class per client."
            ),
        ),
    )
    valid_lifetime = SecondsAttr("valid_lifetime")
    renew_timer = SecondsAttr("renew_timer", label=_("Renew timer (T1)"))
    rebind_timer = SecondsAttr("rebind_timer", label=_("Rebind timer (T2)"))
    user_context = JSONAttr(
        "user_context",
        label=hinted(
            _("User context"),
            _(
                "Passed through to KEA as user-context. Hook libraries read their configuration from "
                "here — libdhcp_limits.so takes its limits from it."
            ),
        ),
    )
    only_in_additional_list = attrs.BooleanAttr("only_in_additional_list")
    description = attrs.TextAttr("description")
    next_server = attrs.TextAttr("next_server")
    server_hostname = attrs.TextAttr("server_hostname")
    boot_file_name = attrs.TextAttr("boot_file_name")


class ClientClassKeaPanel(panels.ObjectPanel):
    """The class's KEA entry, switchable between hex and ASCII option data."""

    template_name = "netbox_dhcp_kea_plugin/panels/client_class_kea.html"
    title = _("KEA Configuration Preview")

    def get_context(self, context):
        ctx = super().get_context(context)
        client_class = ctx["object"]
        return {
            **ctx,
            "kea_config_hex": client_class.to_kea_json(ascii_format=False, indent=4),
            "kea_config_ascii": client_class.to_kea_json(ascii_format=True, indent=4),
        }


class SubnetPanel(panels.ObjectAttributesPanel):
    title = _("Prefix DHCP Configuration")

    prefix = attrs.RelatedObjectAttr("prefix", linkify=True)
    vrf = attrs.RelatedObjectAttr("prefix.vrf", linkify=True, label=_("VRF"))
    server = attrs.RelatedObjectAttr("server", linkify=True)
    valid_lifetime = SecondsAttr("valid_lifetime")
    max_lifetime = SecondsAttr("max_lifetime")
    renew_timer = SecondsAttr("renew_timer", label=_("Renew timer (T1)"))
    rebind_timer = SecondsAttr("rebind_timer", label=_("Rebind timer (T2)"))
    user_context = JSONAttr(
        "user_context",
        label=hinted(
            _("User context"),
            _(
                "Passed through to KEA as user-context. Hook libraries read their configuration from "
                "here — libdhcp_limits.so takes per-subnet limits from it."
            ),
        ),
    )
    routers_option_offset = attrs.TemplatedAttr(
        "routers_option_offset",
        template_name="netbox_dhcp_kea_plugin/attrs/router_offset.html",
        label=_("Router option offset"),
    )
    ddns_policy = attrs.RelatedObjectAttr("ddns_policy", linkify=True, label=_("DDNS policy"))


class SubnetReservationModePanel(panels.ObjectAttributesPanel):
    title = _("Reservation Mode")

    reservations_global = InheritedBooleanAttr("reservations_global", "effective_reservations_global")
    reservations_in_subnet = InheritedBooleanAttr(
        "reservations_in_subnet", "effective_reservations_in_subnet", label=_("Reservations in-subnet")
    )
    reservations_out_of_pool = InheritedBooleanAttr(
        "reservations_out_of_pool", "effective_reservations_out_of_pool", label=_("Reservations out-of-pool")
    )
    reservations_only = attrs.BooleanAttr(
        "reservations_only",
        label=hinted(_("Reservations only"), _("No dynamic pools — only reserved hosts get addresses.")),
    )


class SubnetClientClassesPanel(panels.ObjectAttributesPanel):
    title = _("Client Classes")

    client_class = attrs.RelatedObjectAttr(
        "client_class",
        linkify=True,
        label=hinted(_("Restricting class"), _("Only clients matching this class can use this subnet.")),
    )
    evaluate_additional_classes = attrs.RelatedObjectListAttr("evaluate_additional_classes", linkify=True)


class RedundantEvaluationClassesPanel(panels.ObjectPanel):
    """Additional classes KEA evaluates globally anyway, when there are any."""

    template_name = "netbox_dhcp_kea_plugin/panels/redundant_eval_classes.html"
    title = _("Redundant Evaluate-Additional-Classes")

    def get_context(self, context):
        ctx = super().get_context(context)
        redundant = list(ctx["object"].evaluate_additional_classes.filter(only_in_additional_list=False))
        return {**ctx, "redundant_eval_classes": redundant}

    def should_render(self, context):
        return bool(context["redundant_eval_classes"])


class SubnetPoolPanel(panels.ObjectAttributesPanel):
    title = _("Subnet Pool Configuration")

    subnet = attrs.RelatedObjectAttr("subnet", linkify=True)
    ip_range = attrs.RelatedObjectAttr("ip_range", linkify=True, label=_("IP range"))
    pool_range = attrs.TextAttr("pool_range", style="font-monospace")
    client_class = attrs.RelatedObjectAttr(
        "client_class",
        linkify=True,
        label=hinted(_("Client class"), _("Restricts which clients can use this pool.")),
    )
    evaluate_additional_classes = attrs.RelatedObjectListAttr(
        "evaluate_additional_classes",
        linkify=True,
        label=hinted(
            _("Evaluate additional classes"),
            _("Evaluated additionally for clients in this pool (KEA evaluate-additional-classes)."),
        ),
    )
    ddns_policy = attrs.RelatedObjectAttr("ddns_policy", linkify=True, label=_("DDNS policy"))
    description = attrs.TextAttr("description")


class StaticReservationPanel(panels.ObjectAttributesPanel):
    title = _("Static Reservation")

    subnet = attrs.RelatedObjectAttr("subnet", linkify=True)
    ip_address = attrs.RelatedObjectAttr("ip_address", linkify=True, label=_("IP address"))
    mac_address = attrs.RelatedObjectAttr("mac_address", linkify=True, label=_("MAC address"))
    hostname = attrs.TextAttr("hostname")
    description = attrs.TextAttr("description")


class StaticReservationSourcePanel(panels.ObjectAttributesPanel):
    title = _("Source")

    source = attrs.TextAttr("source")
    external_id = attrs.TextAttr("external_id", label=_("External ID"))
    last_synced = attrs.DateTimeAttr("last_synced")
