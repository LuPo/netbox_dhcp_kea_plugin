from django.urls import include, path
from netbox.plugins.utils import get_plugin_config
from utilities.urls import get_model_urls

from . import views  # noqa: F401 — importing registers every view with register_model_view

APP_LABEL = "netbox_dhcp_kea_plugin"


def _model_urls(prefix, model_name):
    """The list-level and object-level routes NetBox registered for one model."""
    return [
        path(f"{prefix}/", include(get_model_urls(APP_LABEL, model_name, detail=False))),
        path(f"{prefix}/<int:pk>/", include(get_model_urls(APP_LABEL, model_name))),
    ]


urlpatterns = [
    *_model_urls("hooks", "hook"),
    *_model_urls("hook-groups", "hookgroup"),
    *_model_urls("vendor-option-spaces", "vendoroptionspace"),
    *_model_urls("option-definitions", "optiondefinition"),
    *_model_urls("option-data", "optiondata"),
    *_model_urls("dhcp-servers", "dhcpserver"),
    *_model_urls("client-classes", "clientclass"),
    *_model_urls("subnets", "subnet"),
    *_model_urls("subnet-pools", "subnetpool"),
    *_model_urls("static-reservations", "staticreservation"),
    *_model_urls("ha-relationships", "dhcpharelationship"),
]

if get_plugin_config(APP_LABEL, "enable_stork"):
    urlpatterns += [
        *_model_urls("stork-servers", "storkserver"),
        *_model_urls("stork-agent-groups", "storkagentgroup"),
    ]

if get_plugin_config(APP_LABEL, "enable_ddns"):
    urlpatterns += [
        *_model_urls("tsig-keys", "tsigkey"),
        *_model_urls("d2-daemons", "d2daemon"),
        *_model_urls("ddns-domains", "ddnsdomain"),
        *_model_urls("ddns-policies", "ddnspolicy"),
        *_model_urls("ddns-server-overrides", "ddnsserveroverride"),
    ]
