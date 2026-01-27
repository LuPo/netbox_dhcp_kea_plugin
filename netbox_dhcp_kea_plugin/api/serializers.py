from dcim.api.serializers_.manufacturers import ManufacturerSerializer
from ipam.api.serializers import IPAddressSerializer, ServiceSerializer, ServiceTemplateSerializer
from ipam.models import Prefix
from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from rest_framework import serializers

from ..models import (
    ClientClass,
    DHCPHARelationship,
    DHCPServer,
    OptionData,
    OptionDefinition,
    PrefixDHCPConfig,
    VendorOptionSpace,
)


class NestedPrefixSerializer(WritableNestedSerializer):
    class Meta:
        model = Prefix
        fields = ["id", "url", "display", "prefix"]


class NestedDHCPServerSerializer(WritableNestedSerializer):
    class Meta:
        model = DHCPServer
        fields = ["id", "url", "display", "name"]


class NestedVendorOptionSpaceSerializer(WritableNestedSerializer):
    class Meta:
        model = VendorOptionSpace
        fields = ["id", "url", "display", "name", "enterprise_id"]


class NestedOptionDefinitionSerializer(WritableNestedSerializer):
    class Meta:
        model = OptionDefinition
        fields = ["id", "url", "display", "name", "code", "option_type"]


class VendorOptionSpaceSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dhcp_kea_plugin-api:vendoroptionspace-detail"
    )
    manufacturer = ManufacturerSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = VendorOptionSpace
        fields = (
            "id",
            "url",
            "display",
            "name",
            "enterprise_id",
            "manufacturer",
            "description",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


class OptionDefinitionSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dhcp_kea_plugin-api:optiondefinition-detail"
    )
    vendor_option_space = NestedVendorOptionSpaceSerializer(read_only=True)

    class Meta:
        model = OptionDefinition
        fields = (
            "id",
            "url",
            "display",
            "name",
            "code",
            "option_type",
            "option_space",
            "vendor_option_space",
            "is_array",
            "encapsulate",
            "record_types",
            "description",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


class OptionDataSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:optiondata-detail")
    definition = NestedOptionDefinitionSerializer(read_only=True)
    vendor_option_space = NestedVendorOptionSpaceSerializer(read_only=True)

    class Meta:
        model = OptionData
        fields = (
            "id",
            "url",
            "display",
            "distinctive_name",
            "definition",
            "option_space",
            "vendor_option_space",
            "delivery_type",
            "data",
            "always_send",
            "csv_format",
            "description",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


class DHCPServerSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:dhcpserver-detail")
    ip_address = IPAddressSerializer(nested=True, read_only=True)
    service_template = ServiceTemplateSerializer(nested=True, read_only=True)
    service = ServiceSerializer(nested=True, read_only=True)
    option_data = OptionDataSerializer(many=True, read_only=True)
    ha_relationship = serializers.SerializerMethodField()

    class Meta:
        model = DHCPServer
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "ip_address",
            "is_active",
            "service_template",
            "service",
            "option_data",
            "ha_relationship",
            "ha_role",
            "ha_url",
            "ha_auto_failover",
            "ha_basic_auth_user",
            "ha_basic_auth_password",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def get_ha_relationship(self, obj):
        if obj.ha_relationship:
            return {
                "id": obj.ha_relationship.id,
                "name": obj.ha_relationship.name,
                "mode": obj.ha_relationship.mode,
            }
        return None


class ClientClassSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:clientclass-detail")
    option_data = OptionDataSerializer(many=True, read_only=True)

    class Meta:
        model = ClientClass
        fields = (
            "id",
            "url",
            "display",
            "name",
            "test_expression",
            "description",
            "option_data",
            "next_server",
            "server_hostname",
            "boot_file_name",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


class PrefixDHCPConfigSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dhcp_kea_plugin-api:prefixdhcpconfig-detail"
    )
    prefix = NestedPrefixSerializer()
    server = NestedDHCPServerSerializer()
    option_data = OptionDataSerializer(many=True, read_only=True)
    client_classes = ClientClassSerializer(many=True, read_only=True)
    router_ip = serializers.SerializerMethodField()

    class Meta:
        model = PrefixDHCPConfig
        fields = (
            "id",
            "url",
            "display",
            "prefix",
            "server",
            "valid_lifetime",
            "max_lifetime",
            "routers_option_offset",
            "router_ip",
            "option_data",
            "client_classes",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def get_router_ip(self, obj):
        """Return the calculated router IP address."""
        return obj.get_router_ip()


class NestedDHCPHARelationshipSerializer(WritableNestedSerializer):
    class Meta:
        model = DHCPHARelationship
        fields = ["id", "url", "display", "name", "mode"]


class DHCPHARelationshipSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dhcp_kea_plugin-api:dhcpharelationship-detail"
    )
    servers = NestedDHCPServerSerializer(many=True, read_only=True)

    class Meta:
        model = DHCPHARelationship
        fields = (
            "id",
            "url",
            "display",
            "name",
            "mode",
            "heartbeat_delay",
            "max_response_delay",
            "max_ack_delay",
            "max_unacked_clients",
            "max_rejected_lease_updates",
            "enable_multi_threading",
            "http_dedicated_listener",
            "http_listener_threads",
            "http_client_threads",
            "description",
            "servers",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
