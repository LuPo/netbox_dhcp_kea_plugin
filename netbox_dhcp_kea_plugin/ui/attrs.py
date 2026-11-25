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
