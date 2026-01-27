from ipam.models import Prefix
from netbox.plugins import PluginTemplateExtension

from .models import PrefixDHCPConfig


class PrefixDHCPInfo(PluginTemplateExtension):
    """
    Inject DHCP configuration information into the Prefix detail view
    """

    model = "ipam.prefix"

    def right_page(self):
        """
        Display DHCP configuration in the right column of the Prefix detail page
        """
        obj = self.context.get("object")

        # Ensure we're working with a Prefix instance
        if not isinstance(obj, Prefix):
            return ""

        try:
            dhcp_config = (
                PrefixDHCPConfig.objects.select_related("server")
                .prefetch_related("option_data", "client_classes")
                .get(prefix=obj)
            )

            return self.render(
                "netbox_dhcp_kea_plugin/inc/prefix_dhcp_panel.html",
                extra_context={
                    "dhcp_config": dhcp_config,
                },
            )
        except PrefixDHCPConfig.DoesNotExist:
            return ""


template_extensions = [PrefixDHCPInfo]
