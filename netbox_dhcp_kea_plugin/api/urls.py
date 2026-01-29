from django.urls import path
from netbox.api.routers import NetBoxRouter

from . import views

app_name = "netbox_dhcp_kea_plugin"

router = NetBoxRouter()
router.register("vendor-option-spaces", views.VendorOptionSpaceViewSet)
router.register("option-definitions", views.OptionDefinitionViewSet)
router.register("option-data", views.OptionDataViewSet)
router.register("dhcp-servers", views.DHCPServerViewSet)
router.register("client-classes", views.ClientClassViewSet)
router.register("prefix-dhcp-configs", views.PrefixDHCPConfigViewSet)
router.register("ha-relationships", views.DHCPHARelationshipViewSet)

urlpatterns = router.urls + [
    # Lookup DHCP relay config by prefix
    # GET /api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=10.0.0.0/24
    path("relay-config/", views.PrefixRelayConfigView.as_view(), name="relay-config"),
]
