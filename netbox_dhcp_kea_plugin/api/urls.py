from django.urls import path
from netbox.api.routers import NetBoxRouter

from . import views

app_name = "netbox_dhcp_kea_plugin"

router = NetBoxRouter()
router.register("hooks", views.HookViewSet)
router.register("hook-groups", views.HookGroupViewSet)
router.register("vendor-option-spaces", views.VendorOptionSpaceViewSet)
router.register("option-definitions", views.OptionDefinitionViewSet)
router.register("option-data", views.OptionDataViewSet)
router.register("dhcp-servers", views.DHCPServerViewSet)
router.register("client-classes", views.ClientClassViewSet)
router.register("subnets", views.SubnetViewSet)
router.register("subnet-pools", views.SubnetPoolViewSet)
router.register("ha-relationships", views.DHCPHARelationshipViewSet)
router.register("stork-servers", views.StorkServerViewSet)
router.register("stork-agent-groups", views.StorkAgentGroupViewSet)

urlpatterns = router.urls + [
    # Lookup DHCP relay config by prefix
    # GET /api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=10.0.0.0/24
    path("relay-config/", views.PrefixRelayConfigView.as_view(), name="relay-config"),
]
