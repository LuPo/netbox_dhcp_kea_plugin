import django_filters
from dcim.choices import DeviceStatusChoices
from dcim.models import Manufacturer
from django.db.models import Q
from netbox.filtersets import NetBoxModelFilterSet
from netbox.plugins.utils import get_plugin_config

from .models import (
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


class DHCPServerFilterSet(NetBoxModelFilterSet):
    status = django_filters.MultipleChoiceFilter(choices=DeviceStatusChoices, label="Status")
    ha_relationship = django_filters.ModelChoiceFilter(
        queryset=DHCPHARelationship.objects.all(), label="HA Relationship"
    )
    ha_role = django_filters.ChoiceFilter(choices=DHCPServer.HA_ROLE_CHOICES, label="HA Role")
    ha_auto_failover = django_filters.BooleanFilter(label="HA Auto Failover")
    reservations_global = django_filters.BooleanFilter(label="Reservations Global")
    reservations_in_subnet = django_filters.BooleanFilter(label="Reservations In-Subnet")
    reservations_out_of_pool = django_filters.BooleanFilter(label="Reservations Out-of-Pool")
    ctrl_socket_type = django_filters.ChoiceFilter(
        choices=DHCPServer.CTRL_SOCKET_TYPE_CHOICES, label="Control Socket Type"
    )
    stork_agent_group = django_filters.ModelChoiceFilter(
        queryset=StorkAgentGroup.objects.all(), label="Stork Agent Group"
    )
    d2_daemon = django_filters.ModelChoiceFilter(queryset=D2Daemon.objects.all(), label="D2 Daemon")
    ddns_policy = django_filters.ModelChoiceFilter(queryset=DDNSPolicy.objects.all(), label="DDNS Policy")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork"):
            if "stork_agent_group" in self.filters:
                del self.filters["stork_agent_group"]
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
            for fname in ("d2_daemon", "ddns_policy"):
                if fname in self.filters:
                    del self.filters[fname]

    class Meta:
        model = DHCPServer
        fields = [
            "id",
            "name",
            "status",
            "ha_relationship",
            "ha_role",
            "ha_auto_failover",
            "stork_agent_group",
            "ctrl_socket_type",
            "d2_daemon",
            "ddns_policy",
        ]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


class VendorOptionSpaceFilterSet(NetBoxModelFilterSet):
    manufacturer = django_filters.ModelChoiceFilter(queryset=Manufacturer.objects.all(), label="Manufacturer")

    class Meta:
        model = VendorOptionSpace
        fields = ["id", "name", "enterprise_id", "manufacturer"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(manufacturer__name__icontains=value) | Q(description__icontains=value)
        )


class OptionDefinitionFilterSet(NetBoxModelFilterSet):
    is_standard = django_filters.BooleanFilter(
        label="Standard Option", help_text="Filter by standard (RFC-defined) or custom options"
    )
    vendor_option_space = django_filters.ModelChoiceFilter(
        queryset=VendorOptionSpace.objects.all(), label="Vendor Option Space", null_label="-- Standard (dhcp4/dhcp6) --"
    )
    vendor_option_space_id = django_filters.CharFilter(
        method="filter_vendor_option_space_id", label="Vendor Option Space (ID)"
    )
    option_space = django_filters.ChoiceFilter(
        choices=OptionDefinition.OPTION_SPACE_CHOICES, label="Option Space", method="filter_option_space"
    )
    option_type = django_filters.ChoiceFilter(choices=OptionDefinition.OPTION_TYPE_CHOICES, label="Option Type")

    class Meta:
        model = OptionDefinition
        fields = [
            "id",
            "name",
            "code",
            "option_type",
            "option_space",
            "vendor_option_space",
            "vendor_option_space_id",
            "is_standard",
            "is_array",
        ]

    def filter_vendor_option_space_id(self, queryset, name, value):
        """Filter by vendor_option_space_id. If value is 'null', empty, or 0, show non-vendor definitions."""
        if value is None or value == "" or value == "null" or value == "0":
            return queryset.filter(vendor_option_space__isnull=True)
        return queryset.filter(vendor_option_space_id=int(value))

    def filter_option_space(self, queryset, name, value):
        """Filter by option_space, but skip when a vendor option space is selected."""
        if not value:
            return queryset
        # If vendor_option_space_id is set, vendor definitions have their own space — skip this filter
        vos = self.data.get("vendor_option_space_id", "")
        if vos and vos not in ("", "null", "0"):
            return queryset
        return queryset.filter(option_space=value)

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


class OptionDataFilterSet(NetBoxModelFilterSet):
    definition = django_filters.ModelChoiceFilter(queryset=OptionDefinition.objects.all(), label="Option Definition")
    vendor_option_space = django_filters.ModelChoiceFilter(
        queryset=VendorOptionSpace.objects.all(), label="Vendor Option Space"
    )
    delivery_type = django_filters.ChoiceFilter(choices=OptionData.DELIVERY_TYPE_CHOICES, label="Delivery Type")
    always_send = django_filters.BooleanFilter(label="Always Send")

    class Meta:
        model = OptionData
        fields = [
            "id",
            "distinctive_name",
            "definition",
            "vendor_option_space",
            "delivery_type",
            "always_send",
            "csv_format",
        ]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(distinctive_name__icontains=value) | Q(description__icontains=value) | Q(data__icontains=value)
        )


class ClientClassFilterSet(NetBoxModelFilterSet):
    only_in_additional_list = django_filters.BooleanFilter(
        field_name="only_in_additional_list", label="Only in Additional List"
    )
    server_id = django_filters.ModelChoiceFilter(
        field_name="servers",
        queryset=DHCPServer.objects.all(),
        label="Server",
    )

    class Meta:
        model = ClientClass
        fields = ["id", "name", "only_in_additional_list", "server_id"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value) | Q(test_expression__icontains=value)
        )


class SubnetFilterSet(NetBoxModelFilterSet):
    server = django_filters.ModelChoiceFilter(queryset=DHCPServer.objects.all(), label="DHCP Server")
    client_class = django_filters.ModelChoiceFilter(queryset=ClientClass.objects.all(), label="Client Class")
    reservations_global = django_filters.BooleanFilter(label="Reservations Global")
    reservations_in_subnet = django_filters.BooleanFilter(label="Reservations In-Subnet")
    reservations_out_of_pool = django_filters.BooleanFilter(label="Reservations Out-of-Pool")
    reservations_only = django_filters.BooleanFilter(label="Reservations Only")

    class Meta:
        model = Subnet
        fields = [
            "id",
            "prefix",
            "server",
            "client_class",
            "reservations_global",
            "reservations_in_subnet",
            "reservations_out_of_pool",
            "reservations_only",
        ]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(prefix__prefix__icontains=value))


class SubnetPoolFilterSet(NetBoxModelFilterSet):
    subnet = django_filters.ModelChoiceFilter(queryset=Subnet.objects.all(), label="Subnet")
    client_class = django_filters.ModelChoiceFilter(queryset=ClientClass.objects.all(), label="Client Class")

    class Meta:
        model = SubnetPool
        fields = ["id", "subnet", "ip_range", "client_class"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(description__icontains=value) | Q(subnet__prefix__prefix__icontains=value))


class StaticReservationFilterSet(NetBoxModelFilterSet):
    subnet = django_filters.ModelChoiceFilter(queryset=Subnet.objects.all(), label="Subnet")
    source = django_filters.CharFilter(label="Source")
    external_id = django_filters.CharFilter(label="External ID")

    class Meta:
        model = StaticReservation
        fields = ["id", "subnet", "ip_address", "mac_address", "source", "external_id"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(hostname__icontains=value)
            | Q(description__icontains=value)
            | Q(external_id__icontains=value)
            | Q(mac_address__mac_address__icontains=value)
        )


class DHCPHARelationshipFilterSet(NetBoxModelFilterSet):
    mode = django_filters.ChoiceFilter(choices=DHCPHARelationship.HA_MODE_CHOICES, label="HA Mode")
    enable_multi_threading = django_filters.BooleanFilter(label="Enable Multi-Threading")

    class Meta:
        model = DHCPHARelationship
        fields = ["id", "name", "mode", "enable_multi_threading"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


class HookFilterSet(NetBoxModelFilterSet):
    is_standard = django_filters.BooleanFilter(label="Standard Hook")
    allowed_processes = django_filters.CharFilter(
        method="filter_allowed_processes",
        label="Allowed Process",
    )

    class Meta:
        model = Hook
        fields = ["id", "name", "library_name", "is_standard"]

    def filter_allowed_processes(self, queryset, name, value):
        """Filter hooks that support a specific process."""
        if value:
            return queryset.filter(allowed_processes__contains=[value])
        return queryset

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(library_name__icontains=value) | Q(description__icontains=value)
        )


class HookGroupFilterSet(NetBoxModelFilterSet):
    hooks = django_filters.ModelMultipleChoiceFilter(
        queryset=Hook.objects.all(),
        label="Hook",
    )
    servers = django_filters.ModelMultipleChoiceFilter(
        queryset=DHCPServer.objects.all(),
        label="DHCP Server",
    )

    class Meta:
        model = HookGroup
        fields = ["id", "name", "library_path"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


class StorkServerFilterSet(NetBoxModelFilterSet):
    use_tls = django_filters.BooleanFilter(label="TLS Enabled")
    enable_metrics = django_filters.BooleanFilter(label="Metrics Enabled")

    class Meta:
        model = StorkServer
        fields = ["id", "name", "status", "use_tls", "enable_metrics", "db_ssl_mode"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value) | Q(stork_version__icontains=value)
        )


class StorkAgentGroupFilterSet(NetBoxModelFilterSet):
    stork_server = django_filters.ModelChoiceFilter(
        queryset=StorkServer.objects.all(),
        label="Stork Server",
    )
    operating_mode = django_filters.ChoiceFilter(
        choices=StorkAgentGroup.OPERATING_MODE_CHOICES,
        label="Operating Mode",
    )
    server = django_filters.ModelChoiceFilter(
        field_name="servers",
        queryset=DHCPServer.objects.all(),
        label="DHCP Server",
    )

    class Meta:
        model = StorkAgentGroup
        fields = ["id", "name", "stork_server", "operating_mode", "server"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


# --- DDNS FilterSets ---


class TSIGKeyFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = TSIGKey
        fields = ["id", "name", "algorithm", "secret_backend"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


class D2DaemonFilterSet(NetBoxModelFilterSet):
    ncr_protocol = django_filters.ChoiceFilter(choices=[("UDP", "UDP"), ("TCP", "TCP")])

    class Meta:
        model = D2Daemon
        fields = ["id", "name", "ip_address", "port", "ncr_protocol", "ncr_format"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


class DDNSDomainFilterSet(NetBoxModelFilterSet):
    d2_daemon = django_filters.ModelChoiceFilter(queryset=D2Daemon.objects.all())
    tsig_key = django_filters.ModelChoiceFilter(queryset=TSIGKey.objects.all())

    class Meta:
        model = DDNSDomain
        fields = ["id", "d2_daemon", "zone", "tsig_key"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(d2_daemon__name__icontains=value))


class DDNSPolicyFilterSet(NetBoxModelFilterSet):
    server = django_filters.ModelChoiceFilter(
        field_name="servers",
        queryset=DHCPServer.objects.all(),
        label="DHCP Server",
    )
    subnet = django_filters.ModelChoiceFilter(
        field_name="subnets",
        queryset=Subnet.objects.all(),
    )
    client_class = django_filters.ModelChoiceFilter(
        field_name="client_classes",
        queryset=ClientClass.objects.all(),
    )

    class Meta:
        model = DDNSPolicy
        fields = [
            "id",
            "name",
            "ddns_send_updates",
            "ddns_conflict_resolution_mode",
            "server",
            "subnet",
            "client_class",
        ]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))
