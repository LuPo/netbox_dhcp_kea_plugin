from ipam.models import Prefix
from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import filtersets
from ..models import (
    ClientClass,
    DHCPHARelationship,
    DHCPServer,
    OptionData,
    OptionDefinition,
    PrefixDHCPConfig,
    VendorOptionSpace,
)
from .serializers import (
    ClientClassSerializer,
    DHCPHARelationshipSerializer,
    DHCPServerSerializer,
    OptionDataSerializer,
    OptionDefinitionSerializer,
    PrefixDHCPConfigSerializer,
    VendorOptionSpaceSerializer,
)


class VendorOptionSpaceViewSet(NetBoxModelViewSet):
    queryset = VendorOptionSpace.objects.all()
    serializer_class = VendorOptionSpaceSerializer
    filterset_class = filtersets.VendorOptionSpaceFilterSet


class OptionDefinitionViewSet(NetBoxModelViewSet):
    queryset = OptionDefinition.objects.select_related("vendor_option_space")
    serializer_class = OptionDefinitionSerializer
    filterset_class = filtersets.OptionDefinitionFilterSet

    def get_queryset(self):
        queryset = super().get_queryset()
        # If vendor_option_space_id is not in the request params at all,
        # default to showing only non-vendor (standard/custom) definitions
        # This enables proper filtering for DynamicModelChoiceField when no vendor space is selected
        if (
            "vendor_option_space_id" not in self.request.query_params
            and "vendor_option_space" not in self.request.query_params
        ):
            queryset = queryset.filter(vendor_option_space__isnull=True)
        return queryset


class OptionDataViewSet(NetBoxModelViewSet):
    queryset = OptionData.objects.select_related("definition", "vendor_option_space")
    serializer_class = OptionDataSerializer
    filterset_class = filtersets.OptionDataFilterSet


class DHCPServerViewSet(NetBoxModelViewSet):
    queryset = DHCPServer.objects.all()
    serializer_class = DHCPServerSerializer
    filterset_class = filtersets.DHCPServerFilterSet

    @action(detail=True, methods=["get"], url_path="kea-config")
    def kea_config(self, request, pk=None):
        """
        Return the complete KEA DHCP configuration for this server.

        This endpoint generates a full Dhcp4 configuration dictionary
        including all option definitions, client classes, and subnets
        associated with this DHCP server.
        """
        server = self.get_object()
        return Response(server.to_kea_dict())


class ClientClassViewSet(NetBoxModelViewSet):
    queryset = ClientClass.objects.prefetch_related("option_data")
    serializer_class = ClientClassSerializer
    filterset_class = filtersets.ClientClassFilterSet


class PrefixDHCPConfigViewSet(NetBoxModelViewSet):
    queryset = PrefixDHCPConfig.objects.select_related("prefix", "server").prefetch_related(
        "option_data", "client_classes"
    )
    serializer_class = PrefixDHCPConfigSerializer
    filterset_class = filtersets.PrefixDHCPConfigFilterSet

    @action(detail=True, methods=["get"], url_path="relay-config")
    def relay_config(self, request, pk=None):
        """
        Return DHCP relay configuration for this prefix.

        Returns server info and relay target IPs (ip helper-address values)
        for configuring DHCP relay on Layer 3 devices.
        """
        config = self.get_object()
        server = config.server

        # Build relay targets list
        relay_targets = []
        if server.ha_relationship:
            # HA: return all server IPs in the relationship
            for s in server.ha_relationship.servers.all():
                if s.ip_address:
                    relay_targets.append(str(s.ip_address.address.ip))
        elif server.ip_address:
            # Standalone: just this server's IP
            relay_targets.append(str(server.ip_address.address.ip))

        return Response(
            {
                "server": {
                    "name": server.name,
                    "url": server.ha_url
                    or (f"http://{server.ip_address.address.ip}:8000/" if server.ip_address else None),
                },
                "relay_targets": relay_targets,
            }
        )


class PrefixRelayConfigView(APIView):
    """
    Lookup DHCP relay configuration by prefix.

    GET /api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=10.0.0.0/24
    GET /api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=10.0.0.0/24&vrf=CustomerA

    Query Parameters:
        prefix (required): The prefix in CIDR notation (e.g., 10.0.0.0/24)
        vrf (optional): VRF name. If omitted, searches in global routing table.

    Returns relay target IPs for configuring DHCP relay (ip helper-address).
    """

    def get(self, request):
        prefix_str = request.query_params.get("prefix")
        vrf_name = request.query_params.get("vrf")

        if not prefix_str:
            return Response(
                {"error": "prefix query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build query filters
        filters = {"prefix": prefix_str}
        if vrf_name:
            filters["vrf__name"] = vrf_name
        else:
            filters["vrf__isnull"] = True  # Global VRF

        # Find the prefix
        try:
            prefix = Prefix.objects.get(**filters)
        except Prefix.DoesNotExist:
            vrf_display = vrf_name or "global"
            return Response(
                {"error": f"Prefix {prefix_str} not found in VRF {vrf_display}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Prefix.MultipleObjectsReturned:
            return Response(
                {"error": f"Multiple prefixes found for {prefix_str}. Please specify vrf parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if DHCP config exists
        try:
            dhcp_config = prefix.dhcp_config
        except PrefixDHCPConfig.DoesNotExist:
            return Response(
                {
                    "prefix": prefix_str,
                    "dhcp_config": None,
                }
            )

        server = dhcp_config.server

        # Build relay targets list
        relay_targets = []
        if server.ha_relationship:
            for s in server.ha_relationship.servers.all():
                if s.ip_address:
                    relay_targets.append(str(s.ip_address.address.ip))
        elif server.ip_address:
            relay_targets.append(str(server.ip_address.address.ip))

        return Response(
            {
                "prefix": prefix_str,
                "dhcp_config": {
                    "server": {
                        "name": server.name,
                        "url": server.ha_url
                        or (f"http://{server.ip_address.address.ip}:8000/" if server.ip_address else None),
                    },
                    "relay_targets": relay_targets,
                },
            }
        )


class DHCPHARelationshipViewSet(NetBoxModelViewSet):
    queryset = DHCPHARelationship.objects.prefetch_related("servers")
    serializer_class = DHCPHARelationshipSerializer
    filterset_class = filtersets.DHCPHARelationshipFilterSet
