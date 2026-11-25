"""Object detail panels, one per model, in the style of NetBox's own ``<app>/ui/panels.py``."""

from django.utils.translation import gettext_lazy as _
from netbox.ui import attrs, panels


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
