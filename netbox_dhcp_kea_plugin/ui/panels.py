"""Object detail panels, one per model, in the style of NetBox's own ``<app>/ui/panels.py``."""

from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from netbox.ui import attrs, panels
from netbox.ui.actions import CopyContent, PanelAction

from netbox_dhcp_kea_plugin.ui.attrs import (
    InheritedBooleanAttr,
    InheritedFromHAAttr,
    JSONAttr,
    PKIFQDNAttr,
    SecondsAttr,
    SecretSetAttr,
    ValidityAttr,
    hinted,
)


class ConditionalTemplatePanel(panels.TemplatePanel):
    """A template panel shown only when ``condition(object)`` is true."""

    def __init__(self, template_name, condition, **kwargs):
        super().__init__(template_name, **kwargs)
        self.condition = condition

    def should_render(self, context):
        return bool(self.condition(context.get("object")))


def ddns_enabled(_obj=None):
    """Read per request, so a changed setting shows without a restart."""
    from netbox.plugins.utils import get_plugin_config

    return bool(get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"))


def stork_enabled(_obj=None):
    from netbox.plugins.utils import get_plugin_config

    return bool(get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork"))


# Words kept upper-case in labels derived from field names.
_ACRONYMS = {"ha", "ip", "kea", "ddns", "d2", "pki", "fqdn", "http", "id", "ascii", "csv", "url", "vrf", "tsig", "ncr"}


class AttributesPanel(panels.ObjectAttributesPanel):
    """The plugin's attribute panel: Title Case labels, and rows that can hide.

    ``hide_when`` maps an attribute name to ``callable(object)``; the row is
    left out when it returns true, e.g. a port that only matters once a proxy
    is on.
    """

    hide_when = {}

    @staticmethod
    def _name_to_label(name):
        words = name.split("_")
        return " ".join(word.upper() if word in _ACRONYMS else word.capitalize() for word in words)

    def get_context(self, context):
        ctx = super().get_context(context)
        obj = ctx["object"]
        hidden = {
            str(self._attrs[name].label or self._name_to_label(name))
            for name, condition in self.hide_when.items()
            if name in self._attrs and condition(obj)
        }
        if hidden:
            ctx["attrs"] = [attr for attr in ctx["attrs"] if str(attr["label"]) not in hidden]
        return ctx


class KeaJSONPanel(panels.ObjectPanel):
    """Kea JSON computed from the object, with a copy button.

    Parameters:
        data (callable): ``data(object, context)`` returning the JSON-able value, or None
        intro (str | callable): text shown above the JSON; a callable gets the object
        empty_message (str): shown instead when ``data`` returns None
        element_id (str): DOM id of the JSON block, for the copy button
    """

    template_name = "netbox_dhcp_kea_plugin/panels/kea_json.html"

    def __init__(
        self, data, intro=None, empty_message="", element_id="kea-json", title_icons=None, condition=None, **kwargs
    ):
        super().__init__(**kwargs)
        self.data = data
        self.intro = intro
        self.empty_message = empty_message
        self.element_id = element_id
        # ``title_icons(context)`` returns HTML placed after the title, e.g. tooltip icons.
        self.title_icons = title_icons
        # ``condition(object, context)``: render only when true.
        self.condition = condition
        self.actions.append(CopyContent(element_id))

    def get_context(self, context):
        ctx = super().get_context(context)
        obj = ctx["object"]
        intro = self.intro(obj) if callable(self.intro) else self.intro
        title = ctx["title"]
        if self.title_icons is not None:
            title = format_html("{} {}", title, self.title_icons(context))
        return {
            **ctx,
            "title": title,
            "show": self.condition is None or self.condition(obj, context),
            "data": self.data(obj, context),
            "intro": intro,
            "empty_message": self.empty_message,
            "element_id": self.element_id,
        }

    def should_render(self, context):
        return context["show"]


class ExportAction(PanelAction):
    """A Download button for the view's ``?export=<name>`` response."""

    template_name = "ui/actions/link.html"

    def __init__(self, export_name, **kwargs):
        kwargs.setdefault("label", _("Download"))
        kwargs.setdefault("button_icon", "download")
        super().__init__(**kwargs)
        self.export_name = export_name

    def get_context(self, context):
        return {**super().get_context(context), "url": f"?export={self.export_name}"}


class HookPanel(AttributesPanel):
    title = _("Hook Library")

    name = attrs.TextAttr("name")
    library_name = attrs.TextAttr("library_name", style="font-monospace")
    description = attrs.TextAttr("description")
    is_standard = attrs.BooleanAttr("is_standard", label=_("Standard Hook"))
    allowed_processes = attrs.ArrayAttr("allowed_processes")


class HookGroupPanel(AttributesPanel):
    title = _("Hook Group")
    hide_when = {"d2_daemons": lambda obj: not ddns_enabled()}


    name = attrs.TextAttr("name")
    description = attrs.TextAttr("description")
    library_path = attrs.TextAttr("library_path", style="font-monospace")
    d2_daemons = attrs.RelatedObjectListAttr("d2_daemons", linkify=True, label=_("D2 Daemons"))


class VendorOptionSpacePanel(AttributesPanel):
    title = _("Vendor Option Space")

    name = attrs.TextAttr("name")
    enterprise_id = attrs.NumericAttr("enterprise_id", label=_("Enterprise ID"))
    manufacturer = attrs.RelatedObjectAttr("manufacturer", linkify=True)
    description = attrs.TextAttr("description")


class OptionDefinitionPanel(AttributesPanel):
    title = _("Option Definition")
    hide_when = {
        "encapsulate": lambda definition: not definition.encapsulate,
        "record_types": lambda definition: not definition.record_types,
    }


    name = attrs.TextAttr("name")
    code = attrs.NumericAttr("code")
    option_type = attrs.ChoiceAttr("option_type", label=_("Type"))
    option_space = attrs.ChoiceAttr("option_space")
    vendor_option_space = attrs.RelatedObjectAttr("vendor_option_space", linkify=True)
    is_array = attrs.BooleanAttr("is_array", label=_("Array"))
    is_standard = attrs.BooleanAttr("is_standard", label=_("Standard Option (RFC)"))
    encapsulate = attrs.TextAttr("encapsulate", label=_("Encapsulates"))
    record_types = attrs.TextAttr("record_types", style="font-monospace")
    description = attrs.TextAttr("description")


class OptionDataPanel(AttributesPanel):
    title = _("Option Data")
    # The ASCII rendering only means something for hex (non-CSV) data.
    hide_when = {"ascii_data": lambda option: option.csv_format}


    distinctive_name = attrs.TextAttr("distinctive_name")
    definition = attrs.RelatedObjectAttr("definition", linkify=True)
    vendor_option_space = attrs.RelatedObjectAttr("vendor_option_space", linkify=True)
    delivery_type = attrs.ChoiceAttr("delivery_type")
    data = attrs.TextAttr("data", style="font-monospace")
    ascii_data = attrs.TextAttr("ascii_data", label=_("ASCII Data"))
    always_send = attrs.BooleanAttr("always_send")
    csv_format = attrs.BooleanAttr("csv_format", label=_("CSV Format"))
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


class ClientClassPanel(AttributesPanel):
    title = _("Client Class")
    hide_when = {
        "next_server": lambda cc: not cc.next_server,
        "server_hostname": lambda cc: not cc.server_hostname,
        "boot_file_name": lambda cc: not cc.boot_file_name,
    }


    name = attrs.TextAttr("name")
    test_expression = attrs.TextAttr("test_expression", style="font-monospace")
    template_test = attrs.BooleanAttr(
        "template_test",
        label=hinted(
            _("Template Class"),
            _(
                "Rendered as template-test. KEA spawns a subclass named SPAWN_<class>_<value> per distinct "
                "result, so one class definition yields one class per client."
            ),
        ),
    )
    valid_lifetime = SecondsAttr("valid_lifetime")
    renew_timer = SecondsAttr("renew_timer", label=_("Renew Timer (T1)"))
    rebind_timer = SecondsAttr("rebind_timer", label=_("Rebind Timer (T2)"))
    user_context = JSONAttr(
        "user_context",
        label=hinted(
            _("User Context"),
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


class SubnetPanel(AttributesPanel):
    title = _("Prefix DHCP Configuration")
    hide_when = {"ddns_policy": lambda obj: not ddns_enabled()}


    prefix = attrs.RelatedObjectAttr("prefix", linkify=True)
    vrf = attrs.RelatedObjectAttr("prefix.vrf", linkify=True, label=_("VRF"))
    server = attrs.RelatedObjectAttr("server", linkify=True)
    valid_lifetime = SecondsAttr("valid_lifetime")
    max_lifetime = SecondsAttr("max_lifetime")
    renew_timer = SecondsAttr("renew_timer", label=_("Renew Timer (T1)"))
    rebind_timer = SecondsAttr("rebind_timer", label=_("Rebind Timer (T2)"))
    user_context = JSONAttr(
        "user_context",
        label=hinted(
            _("User Context"),
            _(
                "Passed through to KEA as user-context. Hook libraries read their configuration from "
                "here — libdhcp_limits.so takes per-subnet limits from it."
            ),
        ),
    )
    routers_option_offset = attrs.TemplatedAttr(
        "routers_option_offset",
        template_name="netbox_dhcp_kea_plugin/attrs/router_offset.html",
        label=_("Router Option Offset"),
    )
    ddns_policy = attrs.RelatedObjectAttr("ddns_policy", linkify=True, label=_("DDNS Policy"))


class SubnetReservationModePanel(AttributesPanel):
    title = _("Reservation Mode")

    reservations_global = InheritedBooleanAttr("reservations_global", "effective_reservations_global")
    reservations_in_subnet = InheritedBooleanAttr(
        "reservations_in_subnet", "effective_reservations_in_subnet", label=_("Reservations In-Subnet")
    )
    reservations_out_of_pool = InheritedBooleanAttr(
        "reservations_out_of_pool", "effective_reservations_out_of_pool", label=_("Reservations Out-of-Pool")
    )
    reservations_only = attrs.BooleanAttr(
        "reservations_only",
        label=hinted(_("Reservations Only"), _("No dynamic pools — only reserved hosts get addresses.")),
    )


class SubnetClientClassesPanel(AttributesPanel):
    title = _("Client Classes")

    client_class = attrs.RelatedObjectAttr(
        "client_class",
        linkify=True,
        label=hinted(_("Restricting Class"), _("Only clients matching this class can use this subnet.")),
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


class SubnetPoolPanel(AttributesPanel):
    title = _("Subnet Pool Configuration")
    hide_when = {"ddns_policy": lambda obj: not ddns_enabled()}


    subnet = attrs.RelatedObjectAttr("subnet", linkify=True)
    ip_range = attrs.RelatedObjectAttr("ip_range", linkify=True, label=_("IP Range"))
    pool_range = attrs.TextAttr("pool_range", style="font-monospace")
    client_class = attrs.RelatedObjectAttr(
        "client_class",
        linkify=True,
        label=hinted(_("Client Class"), _("Restricts which clients can use this pool.")),
    )
    evaluate_additional_classes = attrs.RelatedObjectListAttr(
        "evaluate_additional_classes",
        linkify=True,
        label=hinted(
            _("Evaluate Additional Classes"),
            _("Evaluated additionally for clients in this pool (KEA evaluate-additional-classes)."),
        ),
    )
    ddns_policy = attrs.RelatedObjectAttr("ddns_policy", linkify=True, label=_("DDNS Policy"))
    description = attrs.TextAttr("description")


class StaticReservationPanel(AttributesPanel):
    title = _("Static Reservation")

    subnet = attrs.RelatedObjectAttr("subnet", linkify=True)
    ip_address = attrs.RelatedObjectAttr("ip_address", linkify=True, label=_("IP Address"))
    mac_address = attrs.RelatedObjectAttr("mac_address", linkify=True, label=_("MAC Address"))
    hostname = attrs.TextAttr("hostname")
    description = attrs.TextAttr("description")


class StaticReservationSourcePanel(AttributesPanel):
    title = _("Source")

    source = attrs.TextAttr("source")
    external_id = attrs.TextAttr("external_id", label=_("External ID"))
    last_synced = attrs.DateTimeAttr("last_synced")


class HARelationshipPanel(AttributesPanel):
    title = _("HA Relationship")

    name = attrs.TextAttr("name")
    mode = attrs.ChoiceAttr("mode")
    description = attrs.TextAttr("description")
    valid = ValidityAttr(label=_("Valid Configuration"))


class HATimingPanel(AttributesPanel):
    title = _("Timing Parameters")

    heartbeat_delay = attrs.TextAttr("heartbeat_delay", format_string="{} ms")
    max_response_delay = attrs.TextAttr("max_response_delay", format_string="{} ms")
    max_ack_delay = attrs.TextAttr("max_ack_delay", format_string="{} ms", label=_("Max ACK Delay"))
    max_unacked_clients = attrs.NumericAttr("max_unacked_clients")
    max_rejected_lease_updates = attrs.NumericAttr("max_rejected_lease_updates")


class HAProxyPanel(AttributesPanel):
    title = _("Reverse Proxy")

    ha_proxy_enabled = attrs.BooleanAttr(
        "ha_proxy_enabled",
        label=hinted(
            _("HA Reverse Proxy"),
            _(
                "All or nothing for the relationship: every member routes HA traffic through its own local "
                "proxy, and KEA speaks plain HTTP over loopback in both directions."
            ),
        ),
    )


class HAAuthenticationPanel(AttributesPanel):
    title = hinted(
        _("HA Authentication"),
        _(
            "Shared by every member: each one's HA listener requires these credentials and presents them "
            "to its peers."
        ),
    )

    ha_basic_auth_user = attrs.TextAttr("ha_basic_auth_user", label=_("Basic Auth User"))
    ha_basic_auth_password = SecretSetAttr("ha_basic_auth_password", label=_("Basic Auth Password"))


class HADDNSPanel(AttributesPanel):
    title = _("DDNS")

    d2_daemon = attrs.RelatedObjectAttr("d2_daemon", linkify=True, label=_("D2 Daemon"))
    ddns_enable_updates = attrs.BooleanAttr("ddns_enable_updates", label=_("Updates Enabled"))
    ddns_policy = attrs.RelatedObjectAttr("ddns_policy", linkify=True, label=_("DDNS Policy"))


class HAMultiThreadingPanel(AttributesPanel):
    title = _("Multi-Threading Settings")

    enable_multi_threading = attrs.BooleanAttr("enable_multi_threading")
    http_dedicated_listener = attrs.BooleanAttr("http_dedicated_listener", label=_("HTTP Dedicated Listener"))
    http_listener_threads = attrs.NumericAttr("http_listener_threads", label=_("HTTP Listener Threads"))
    http_client_threads = attrs.NumericAttr("http_client_threads", label=_("HTTP Client Threads"))


class ConditionalPanel(panels.Panel):
    """Render ``panel`` only when ``condition(object)`` is true."""

    def __init__(self, panel, condition):
        super().__init__()
        self.panel = panel
        self.condition = condition

    def render(self, context):
        if not self.condition(context.get("object")):
            return ""
        return self.panel.render(context)


class ContextAlertsPanel(panels.Panel):
    """Bootstrap alerts for the strings in a context list, if there are any."""

    template_name = "netbox_dhcp_kea_plugin/panels/alerts.html"

    def __init__(self, context_key, level="warning"):
        super().__init__()
        self.context_key = context_key
        self.level = level

    def get_context(self, context):
        return {**super().get_context(context), "alerts": context.get(self.context_key), "level": self.level}

    def should_render(self, context):
        return bool(context["alerts"])


def _ha_owns_ddns(server):
    return bool(server.ha_relationship_id and server.ha_relationship.d2_daemon_id)


class DHCPServerPanel(AttributesPanel):
    title = _("DHCP Server")
    hide_when = {
        "stork_agent_group": lambda server: not stork_enabled(),
        "stork_server": lambda server: not stork_enabled(),
        "ha_url": lambda server: not server.ha_relationship_id,
        "ha_auto_failover": lambda server: not server.ha_relationship_id,
        "http_socket": lambda server: not server.ctrl_socket_http_enabled,
        "ctrl_socket_unix_path": lambda server: not server.ctrl_socket_unix_enabled,
    }


    name = attrs.TextAttr("name")
    description = attrs.TextAttr("description")
    ip_address = attrs.TemplatedAttr(
        "ip_address", template_name="netbox_dhcp_kea_plugin/attrs/server_ip.html", label=_("IP Address")
    )
    status = attrs.ChoiceAttr("status")
    service = attrs.TemplatedAttr(
        "pk", template_name="netbox_dhcp_kea_plugin/attrs/server_service.html", label=_("Application Service")
    )
    ha_relationship = attrs.RelatedObjectAttr("ha_relationship", linkify=True, label=_("HA Relationship"))
    ha_role = attrs.ChoiceAttr("ha_role", label=_("HA Role"))
    ha_url = attrs.TextAttr("ha_url", label=_("HA URL"))
    ha_auto_failover = attrs.BooleanAttr("ha_auto_failover", label=_("HA Auto Failover"))
    pki_fqdn = PKIFQDNAttr("pki_fqdn", dns_integration=lambda: _pki_dns_integration(), label=_("PKI FQDN"))
    hook_groups = attrs.RelatedObjectListAttr("hook_groups", linkify=True)
    stork_agent_group = attrs.RelatedObjectAttr("stork_agent_group", linkify=True)
    stork_server = attrs.TemplatedAttr(
        "stork_agent_group.stork_server", template_name="netbox_dhcp_kea_plugin/attrs/stork_server.html"
    )
    ctrl_socket_type = attrs.ChoiceAttr("ctrl_socket_type", label=_("Control Socket"))
    http_socket = attrs.TemplatedAttr(
        "pk", template_name="netbox_dhcp_kea_plugin/attrs/http_socket.html", label=_("HTTP Socket")
    )
    ctrl_socket_unix_path = attrs.TextAttr("ctrl_socket_unix_path", label=_("Unix Socket"))


def _pki_dns_integration():
    from netbox_dhcp_kea_plugin.views import _pki_dns_integration_active

    return _pki_dns_integration_active()


class DHCPServerProxyPanel(AttributesPanel):
    # The egress port only matters once the proxy is on.
    hide_when = {
        "ha_egress_base_port": lambda server: not server.ha_proxy_enabled,
        "stork_proxy_enabled": lambda server: not stork_enabled(),
    }

    title = hinted(
        _("Reverse Proxy"),
        _(
            "Each of these moves one listener to loopback so a local proxy can bind the public address on its "
            "port. They are independent: a host may front its HA channel without fronting its control API."
        ),
    )

    ha_proxy_enabled = attrs.TemplatedAttr(
        "ha_proxy_enabled",
        template_name="netbox_dhcp_kea_plugin/attrs/ha_proxy.html",
        label=hinted(
            _("HA Reverse Proxy"),
            _("Owned by the HA relationship, not this server — it is all or nothing for the cluster."),
        ),
    )
    ha_egress_base_port = attrs.NumericAttr("ha_egress_base_port", label=_("HA Egress Base Port"))
    ctrl_socket_proxy_enabled = attrs.BooleanAttr("ctrl_socket_proxy_enabled", label=_("Control Socket Proxy"))
    stork_proxy_enabled = attrs.BooleanAttr(
        "stork_proxy_enabled",
        label=hinted(
            _("Stork Exporter Proxy"),
            _(
                "The Prometheus exporter binds 127.0.0.1 instead of the agent group's address, leaving the "
                "public address on that port free for the proxy."
            ),
        ),
    )


class DHCPServerReservationDefaultsPanel(AttributesPanel):
    title = _("Reservation Mode Defaults")

    reservations_global = attrs.BooleanAttr("reservations_global")
    reservations_in_subnet = attrs.BooleanAttr("reservations_in_subnet", label=_("Reservations In-Subnet"))
    reservations_out_of_pool = attrs.BooleanAttr("reservations_out_of_pool", label=_("Reservations Out-of-Pool"))


class DHCPServerLeasePanel(AttributesPanel):
    title = _("Lease Handling")

    valid_lifetime = SecondsAttr("valid_lifetime")
    max_valid_lifetime = SecondsAttr("max_valid_lifetime")
    renew_timer = SecondsAttr(
        "renew_timer", label=_("Renew Timer (T1)"), inherited_label=_("Not sent (client chooses)")
    )
    rebind_timer = SecondsAttr(
        "rebind_timer", label=_("Rebind Timer (T2)"), inherited_label=_("Not sent (client chooses)")
    )
    decline_probation_period = SecondsAttr(
        "decline_probation_period",
        inherited_label=_("86400 seconds (KEA default)"),
        label=hinted(
            _("Decline Probation Period"),
            _(
                "How long an address stays unavailable after a client DECLINEs it. Global only — KEA has no "
                "per-subnet form of this setting."
            ),
        ),
    )


class DHCPServerDDNSPanel(AttributesPanel):
    title = _("DDNS")

    effective_d2_daemon = InheritedFromHAAttr(
        "effective_d2_daemon", inherited=_ha_owns_ddns, label=_("D2 Daemon")
    )
    ddns_enable_updates = InheritedFromHAAttr(
        "ddns_enable_updates", inherited=_ha_owns_ddns, is_boolean=True, label=_("Updates Enabled")
    )
    effective_ddns_policy = InheritedFromHAAttr(
        "effective_ddns_policy",
        inherited=lambda server: bool(server.ha_relationship_id and server.ha_relationship.ddns_policy_id),
        label=_("DDNS Policy"),
    )
    sender = attrs.TemplatedAttr("pk", template_name="netbox_dhcp_kea_plugin/attrs/ddns_sender.html")


def d2_config_title_icons(context):
    """Info icons after a D2 config's title: a template awaiting substitution, hidden secrets."""
    icons = []
    if context.get("requires_secret_substitution"):
        icons.append(
            format_html(
                '<i class="mdi mdi-information-outline text-muted ms-1" data-bs-toggle="tooltip" '
                'data-bs-placement="right" title="{}"></i>',
                _(
                    "This configuration is a template: at least one TSIG key uses the vault backend, so its "
                    "secret is rendered as a reference, not the secret itself. Substitute it on the target "
                    "before deploying, then validate the result. KEA reads each TSIG secret as base64 and "
                    "will not load the reference."
                ),
            )
        )
    if context.get("secrets_redacted"):
        icons.append(
            format_html(
                '<i class="mdi mdi-lock text-info ms-1" data-bs-toggle="tooltip" data-bs-placement="right" '
                'title="{}"></i>',
                _(
                    "TSIG secrets are hidden: revealing them requires the view_secret_tsigkey permission, so "
                    "this copy cannot be deployed as shown."
                ),
            )
        )
    return format_html("{}", mark_safe("".join(str(icon) for icon in icons)))


def kea_config_panel(element_id, title=_("kea-dhcp-ddns.conf"), **kwargs):
    """A D2 configuration rendered by the view as ``d2_config``, with its info icons."""
    return KeaJSONPanel(
        lambda _obj, ctx: ctx.get("d2_config"),
        title=title,
        element_id=element_id,
        title_icons=d2_config_title_icons,
        **kwargs,
    )
