import django_filters
from django.db.models import Q
from netbox.filtersets import NetBoxModelFilterSet

from .models import (
    ClientClass,
    DHCPHARelationship,
    DHCPServer,
    Hook,
    HookGroup,
    OptionData,
    OptionDefinition,
    Subnet,
    SubnetPool,
    VendorOptionSpace,
)


class DHCPServerFilterSet(NetBoxModelFilterSet):
    ha_relationship = django_filters.ModelChoiceFilter(
        queryset=DHCPHARelationship.objects.all(), label="HA Relationship"
    )
    ha_role = django_filters.ChoiceFilter(choices=DHCPServer.HA_ROLE_CHOICES, label="HA Role")

    class Meta:
        model = DHCPServer
        fields = ["id", "name", "status", "ha_relationship", "ha_role", "ha_auto_failover"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


class VendorOptionSpaceFilterSet(NetBoxModelFilterSet):
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
    option_space = django_filters.ChoiceFilter(choices=OptionDefinition.OPTION_SPACE_CHOICES, label="Option Space")
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

    class Meta:
        model = Subnet
        fields = ["id", "prefix", "server", "client_class"]

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


class DHCPHARelationshipFilterSet(NetBoxModelFilterSet):
    mode = django_filters.ChoiceFilter(choices=DHCPHARelationship.HA_MODE_CHOICES, label="HA Mode")

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
    hooks = django_filters.ModelChoiceFilter(
        queryset=Hook.objects.all(),
        label="Hook",
    )
    servers = django_filters.ModelChoiceFilter(
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
