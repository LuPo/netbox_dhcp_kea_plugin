from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

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


class DHCPHARelationshipViewSet(NetBoxModelViewSet):
    queryset = DHCPHARelationship.objects.prefetch_related("servers")
    serializer_class = DHCPHARelationshipSerializer
    filterset_class = filtersets.DHCPHARelationshipFilterSet
