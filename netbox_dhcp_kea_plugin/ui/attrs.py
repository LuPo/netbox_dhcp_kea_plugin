"""Attribute types the plugin's panels need beyond NetBox's own."""

from django.utils.html import format_html
from django.utils.safestring import mark_safe
from netbox.ui import attrs


def hinted(label, hint):
    """A label followed by an info icon whose tooltip explains it."""
    return format_html(
        '{}&nbsp;<i class="mdi mdi-information-outline text-primary" data-bs-toggle="tooltip" '
        'data-bs-placement="top" title="{}"></i>',
        label,
        hint,
    )


class SecondsAttr(attrs.TextAttr):
    """A duration in seconds; blank means the value is inherited from an outer scope."""

    placeholder = mark_safe('<span class="text-muted">Inherited</span>')

    def __init__(self, *args, inherited_label=None, **kwargs):
        kwargs.setdefault("format_string", "{} seconds")
        super().__init__(*args, **kwargs)
        if inherited_label is not None:
            self.placeholder = format_html('<span class="text-muted">{}</span>', inherited_label)


class JSONAttr(attrs.ObjectAttribute):
    """A JSON value shown pretty-printed, e.g. user-context."""

    template_name = "netbox_dhcp_kea_plugin/attrs/json.html"

    def render(self, obj, context):
        value = self.get_value(obj)
        if value in (None, "", {}, []):
            return self.placeholder
        return super().render(obj, context)


class InheritedBooleanAttr(attrs.ObjectAttribute):
    """A nullable boolean; None inherits, so the effective value is shown beside it."""

    template_name = "netbox_dhcp_kea_plugin/attrs/inherited_boolean.html"

    def __init__(self, accessor, effective_accessor, **kwargs):
        super().__init__(accessor, **kwargs)
        self.effective_accessor = effective_accessor

    def render(self, obj, context):
        from django.template.loader import render_to_string
        from utilities.data import resolve_attr_path

        return render_to_string(
            self.template_name,
            {"value": self.get_value(obj), "effective": resolve_attr_path(obj, self.effective_accessor)},
        )


class ValidityAttr(attrs.ObjectAttribute):
    """Valid/Invalid from the object's ``configuration_errors()``, with the reasons as a tooltip."""

    template_name = "netbox_dhcp_kea_plugin/attrs/validity.html"

    def __init__(self, label=None):
        super().__init__("configuration_errors", label=label)

    def render(self, obj, context):
        from django.template.loader import render_to_string

        return render_to_string(self.template_name, {"errors": obj.configuration_errors()})


class SecretSetAttr(attrs.ObjectAttribute):
    """Whether a secret is set, never the secret itself."""

    template_name = "netbox_dhcp_kea_plugin/attrs/secret_set.html"


class InheritedFromHAAttr(attrs.ObjectAttribute):
    """A value that an HA relationship may override, flagged when it does.

    Parameters:
        inherited (callable): ``inherited(obj)`` is true when the value comes from the relationship
        is_boolean (bool): render a check mark instead of a link
    """

    template_name = "netbox_dhcp_kea_plugin/attrs/inherited_from_ha.html"

    def __init__(self, accessor, inherited, is_boolean=False, **kwargs):
        super().__init__(accessor, **kwargs)
        self.inherited = inherited
        self.is_boolean = is_boolean

    def render(self, obj, context):
        from django.template.loader import render_to_string

        return render_to_string(
            self.template_name,
            {"value": self.get_value(obj), "inherited": self.inherited(obj), "is_boolean": self.is_boolean},
        )


class PKIFQDNAttr(attrs.ObjectAttribute):
    """The PKI name, linked to its DNS record; flagged when it should be bound and is not."""

    template_name = "netbox_dhcp_kea_plugin/attrs/pki_fqdn.html"

    def __init__(self, accessor, dns_integration, **kwargs):
        super().__init__(accessor, **kwargs)
        self.dns_integration = dns_integration

    def get_context(self, obj, attr, value, context):
        return {"record": obj.pki_record(), "dns_integration": self.dns_integration()}


class MethodListAttr(attrs.RelatedObjectListAttr):
    """Related objects returned by calling a method of the object, e.g. ``servers_using()``."""

    def get_value(self, obj):
        method = getattr(obj, self.accessor, None)
        return method() if callable(method) else None


class DefaultedAttr(attrs.TextAttr):
    """A value with a stated default shown when it is blank, e.g. "500 ms (KEA default)"."""

    def __init__(self, *args, default_label, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = format_html('<span class="text-muted">{}</span>', default_label)
