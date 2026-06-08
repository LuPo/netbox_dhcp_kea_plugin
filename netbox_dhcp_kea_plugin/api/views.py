from django.core.exceptions import ValidationError as DjangoValidationError
from ipam.api.serializers import IPAddressSerializer
from ipam.filtersets import IPAddressFilterSet
from ipam.models import IPAddress, Prefix
from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework.views import APIView


class PlainTextRenderer(BaseRenderer):
    media_type = "text/plain"
    format = "text"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, str):
            return data.encode(self.charset or "utf-8")
        return data


from .. import filtersets
from ..models import (
    ClientClass,
    D2Daemon,
    DDNSDomain,
    DDNSPolicy,
    DHCPHARelationship,
    DHCPServer,
    Hook,
    HookGroup,
    OptionData,
    OptionDefinition,
    StaticReservation,
    StorkAgentGroup,
    StorkServer,
    Subnet,
    SubnetPool,
    TSIGKey,
    VendorOptionSpace,
)
from .serializers import (
    ClientClassSerializer,
    D2DaemonSerializer,
    DDNSDomainSerializer,
    DDNSPolicySerializer,
    DHCPHARelationshipSerializer,
    DHCPServerSerializer,
    HookGroupSerializer,
    HookSerializer,
    OptionDataSerializer,
    OptionDefinitionSerializer,
    StaticReservationProvisionSerializer,
    StaticReservationSerializer,
    StorkAgentGroupSerializer,
    StorkServerSerializer,
    SubnetPoolSerializer,
    SubnetSerializer,
    TSIGKeySerializer,
    VendorOptionSpaceSerializer,
)


class HookViewSet(NetBoxModelViewSet):
    queryset = Hook.objects.all()
    serializer_class = HookSerializer
    filterset_class = filtersets.HookFilterSet


class HookGroupViewSet(NetBoxModelViewSet):
    queryset = HookGroup.objects.prefetch_related("hooks", "servers")
    serializer_class = HookGroupSerializer
    filterset_class = filtersets.HookGroupFilterSet


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
    queryset = DHCPServer.objects.select_related("stork_agent_group")
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


class SubnetViewSet(NetBoxModelViewSet):
    queryset = Subnet.objects.select_related("prefix", "server", "client_class").prefetch_related(
        "option_data", "evaluate_additional_classes"
    )
    serializer_class = SubnetSerializer
    filterset_class = filtersets.SubnetFilterSet

    @action(detail=True, methods=["get"], url_path="pools")
    def pools(self, request, pk=None):
        """
        Return all SubnetPool configurations for this subnet.
        """
        subnet = self.get_object()
        pool_configs = (
            SubnetPool.objects.filter(subnet=subnet)
            .select_related("ip_range", "client_class")
            .prefetch_related("evaluate_additional_classes", "option_data")
        )
        serializer = SubnetPoolSerializer(pool_configs, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="relay-config")
    def relay_config(self, request, pk=None):
        """
        Return DHCP relay configuration for this prefix.

        Returns server info and relay target IPs (ip helper-address values)
        for configuring DHCP relay on Layer 3 devices.
        """
        config = self.get_object()
        return Response(config.get_relay_config())


class SubnetPoolViewSet(NetBoxModelViewSet):
    queryset = SubnetPool.objects.select_related("subnet", "ip_range", "client_class").prefetch_related(
        "evaluate_additional_classes", "option_data"
    )
    serializer_class = SubnetPoolSerializer
    filterset_class = filtersets.SubnetPoolFilterSet


class StaticReservationViewSet(NetBoxModelViewSet):
    queryset = StaticReservation.objects.select_related("subnet", "ip_address", "mac_address")
    serializer_class = StaticReservationSerializer
    filterset_class = filtersets.StaticReservationFilterSet

    @action(detail=False, methods=["post"], url_path="provision")
    def provision(self, request):
        """Allocate the next out-of-pool address in a subnet and reserve it for a
        MAC, atomically.

        POST body: ``subnet`` (id), ``mac_address`` (string), and optional
        ``hostname`` / ``dns_name`` / ``source`` / ``external_id`` /
        ``description``. The address is chosen under a per-prefix lock so
        concurrent callers never collide. Pass ``external_id`` to make the call
        idempotent (a retry returns the existing reservation with ``200`` rather
        than allocating again).

        Returns the created reservation (``201``), or the existing one when
        ``external_id`` already exists (``200``).
        """
        in_serializer = StaticReservationProvisionSerializer(data=request.data)
        in_serializer.is_valid(raise_exception=True)
        data = in_serializer.validated_data

        try:
            reservation, created = data["subnet"].allocate_reservation(
                data["mac_address"],
                hostname=data.get("hostname", ""),
                dns_name=data.get("dns_name", ""),
                source=data.get("source", ""),
                external_id=data.get("external_id") or None,
                description=data.get("description", ""),
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
            return Response({"errors": detail}, status=status.HTTP_400_BAD_REQUEST)

        out = StaticReservationSerializer(reservation, context={"request": request})
        return Response(
            out.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SubnetIPChoicesView(ListAPIView):
    """IP addresses contained in a Kea subnet's prefix, for the static-reservation
    IP picker. Filter with ``?subnet_id=<id>``; standard search (``q``) and
    pagination are honoured via the native IPAddress filterset.
    """

    # NetBox TokenPermissions inspects .queryset to resolve the model.
    queryset = IPAddress.objects.none()
    serializer_class = IPAddressSerializer

    def get_serializer(self, *args, **kwargs):
        kwargs.setdefault("nested", True)  # brief form for the picker
        return super().get_serializer(*args, **kwargs)

    def get_queryset(self):
        subnet_id = self.request.query_params.get("subnet_id")
        if not subnet_id:
            return IPAddress.objects.none()
        subnet = Subnet.objects.select_related("prefix").filter(pk=subnet_id).first()
        if subnet is None:
            return IPAddress.objects.none()
        base = IPAddress.objects.filter(
            address__net_host_contained=str(subnet.prefix.prefix),
            vrf=subnet.prefix.vrf,
        )
        return IPAddressFilterSet(self.request.GET, queryset=base).qs


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

    # NetBox applies TokenPermissions to every API view and inspects
    # ``.queryset`` to resolve the model for permission checks. Without it,
    # token-authenticated requests raise AssertionError before reaching get().
    queryset = Prefix.objects.all()

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
        except Subnet.DoesNotExist:
            return Response(
                {
                    "prefix": prefix_str,
                    "dhcp_config": None,
                }
            )

        return Response(
            {
                "prefix": prefix_str,
                "dhcp_config": dhcp_config.get_relay_config(),
            }
        )


class DHCPHARelationshipViewSet(NetBoxModelViewSet):
    queryset = DHCPHARelationship.objects.prefetch_related("servers")
    serializer_class = DHCPHARelationshipSerializer
    filterset_class = filtersets.DHCPHARelationshipFilterSet


class StorkServerViewSet(NetBoxModelViewSet):
    queryset = StorkServer.objects.prefetch_related("agent_groups")
    serializer_class = StorkServerSerializer
    filterset_class = filtersets.StorkServerFilterSet

    @action(detail=True, methods=["get"], url_path="config", renderer_classes=[PlainTextRenderer])
    def config(self, request, pk=None):
        """
        Return the Stork Server environment file.

        Returns plain-text content suitable for /etc/stork/server.env.
        """
        server = self.get_object()
        return Response(server.to_env_content())


class StorkAgentGroupViewSet(NetBoxModelViewSet):
    queryset = StorkAgentGroup.objects.select_related("stork_server").prefetch_related("servers")
    serializer_class = StorkAgentGroupSerializer
    filterset_class = filtersets.StorkAgentGroupFilterSet

    @action(detail=True, methods=["get"], url_path="config", renderer_classes=[PlainTextRenderer])
    def config(self, request, pk=None):
        """
        Return the Stork Agent environment file for this agent group.

        By default returns a generic template with a placeholder for
        STORK_AGENT_HOST.  Pass ``?server=<id>`` to generate an env file
        with the concrete IP address of a specific DHCP server.

        Returns plain-text content suitable for /etc/stork/agent.env.
        """
        agent_group = self.get_object()
        server = None
        server_id = request.query_params.get("server")
        if server_id:
            try:
                server = agent_group.servers.get(pk=int(server_id))
            except (ValueError, DHCPServer.DoesNotExist):
                return Response(
                    f"Server {server_id} is not assigned to this agent group.",
                    status=status.HTTP_404_NOT_FOUND,
                )

        env_content = agent_group.to_env_content(server=server)
        return Response(env_content)


# ----- DDNS ViewSets -----


class TSIGKeyViewSet(NetBoxModelViewSet):
    queryset = TSIGKey.objects.all()
    serializer_class = TSIGKeySerializer
    filterset_class = filtersets.TSIGKeyFilterSet


class D2DaemonViewSet(NetBoxModelViewSet):
    queryset = D2Daemon.objects.select_related("ip_address").prefetch_related("domains")
    serializer_class = D2DaemonSerializer
    filterset_class = filtersets.D2DaemonFilterSet

    @action(detail=True, methods=["get"], url_path="kea-config")
    def kea_config(self, request, pk=None):
        """
        Return the complete kea-dhcp-ddns configuration for this D2 daemon.
        """
        daemon = self.get_object()
        return Response(daemon.to_kea_dict())


class DDNSDomainViewSet(NetBoxModelViewSet):
    queryset = DDNSDomain.objects.select_related("d2_daemon", "tsig_key", "zone")
    serializer_class = DDNSDomainSerializer
    filterset_class = filtersets.DDNSDomainFilterSet


class DDNSPolicyViewSet(NetBoxModelViewSet):
    queryset = DDNSPolicy.objects.prefetch_related("servers", "subnets", "client_classes")
    serializer_class = DDNSPolicySerializer
    filterset_class = filtersets.DDNSPolicyFilterSet
