from dcim.api.serializers_.manufacturers import ManufacturerSerializer
from ipam.api.serializers import IPAddressSerializer, IPRangeSerializer, ServiceSerializer, ServiceTemplateSerializer
from ipam.models import Prefix
from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from netbox.plugins.utils import get_plugin_config
from rest_framework import serializers

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
    OptionDataIPSource,
    OptionDefinition,
    StorkAgentGroup,
    StorkServer,
    Subnet,
    SubnetPool,
    TSIGKey,
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


class NestedHookSerializer(WritableNestedSerializer):
    class Meta:
        model = Hook
        fields = ["id", "url", "display", "name", "library_name"]


class NestedHookGroupSerializer(WritableNestedSerializer):
    class Meta:
        model = HookGroup
        fields = ["id", "url", "display", "name"]


class NestedSubnetSerializer(WritableNestedSerializer):
    class Meta:
        model = Subnet
        fields = ["id", "url", "display"]


class NestedClientClassSerializer(WritableNestedSerializer):
    class Meta:
        model = ClientClass
        fields = ["id", "url", "display", "name"]


class NestedStorkAgentGroupSerializer(WritableNestedSerializer):
    class Meta:
        model = StorkAgentGroup
        fields = ["id", "url", "display", "name", "operating_mode"]


class HookSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:hook-detail")

    class Meta:
        model = Hook
        fields = (
            "id",
            "url",
            "display",
            "name",
            "library_name",
            "description",
            "is_standard",
            "allowed_processes",
            "parameters",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


class HookGroupSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:hookgroup-detail")
    hooks = NestedHookSerializer(many=True, read_only=True)
    servers = NestedDHCPServerSerializer(many=True, read_only=True)

    class Meta:
        model = HookGroup
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "library_path",
            "hooks",
            "servers",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


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


class OptionDataIPSourceSerializer(serializers.ModelSerializer):
    resolved_ip = serializers.SerializerMethodField()

    class Meta:
        model = OptionDataIPSource
        fields = (
            "id",
            "content_type",
            "object_id",
            "ordinal",
            "resolved_ip",
        )

    def get_resolved_ip(self, obj):
        return OptionData._resolve_ip(obj.ip_source)


class OptionDataSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:optiondata-detail")
    definition = NestedOptionDefinitionSerializer(read_only=True)
    vendor_option_space = NestedVendorOptionSpaceSerializer(read_only=True)
    ip_sources = OptionDataIPSourceSerializer(many=True, read_only=True)
    data = serializers.SerializerMethodField()

    def get_data(self, obj):
        """Return resolved data from to_kea_dict() for record/IP-source options."""
        return obj.to_kea_dict().get("data", obj.data)

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
            "ip_sources",
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
    ha_url = serializers.SerializerMethodField()
    stork_agent_group = NestedStorkAgentGroupSerializer(read_only=True)
    d2_daemon = serializers.SerializerMethodField()
    effective_d2_daemon = serializers.SerializerMethodField()
    ddns_policy = serializers.SerializerMethodField()

    class Meta:
        model = DHCPServer
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "ip_address",
            "status",
            "service_template",
            "service",
            "option_data",
            "reservations_global",
            "reservations_in_subnet",
            "reservations_out_of_pool",
            "ha_relationship",
            "ha_role",
            "ha_address",
            "ha_port",
            "ha_tls",
            "ha_url",
            "ha_auto_failover",
            "ha_basic_auth_user",
            "ha_basic_auth_password",
            "stork_agent_group",
            "d2_daemon",
            "effective_d2_daemon",
            "ddns_enable_updates",
            "ddns_sender_ip",
            "ddns_sender_port",
            "ddns_policy",
            "ctrl_socket_type",
            "ctrl_socket_http_address",
            "ctrl_socket_http_port",
            "ctrl_socket_unix_path",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork"):
            self.fields.pop("stork_agent_group", None)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
            for f in (
                "d2_daemon",
                "effective_d2_daemon",
                "ddns_enable_updates",
                "ddns_sender_ip",
                "ddns_sender_port",
                "ddns_policy",
            ):
                self.fields.pop(f, None)

    def _daemon_dict(self, daemon):
        if daemon is None:
            return None
        return {"id": daemon.id, "name": daemon.name}

    def get_d2_daemon(self, obj):
        return self._daemon_dict(obj.d2_daemon)

    def get_effective_d2_daemon(self, obj):
        daemon = obj.effective_d2_daemon
        if daemon is None:
            return None
        result = self._daemon_dict(daemon)
        result["inherited_from_ha_relationship"] = bool(
            obj.ha_relationship_id and obj.ha_relationship.d2_daemon_id == daemon.id
        )
        return result

    def get_ddns_policy(self, obj):
        if obj.ddns_policy is None:
            return None
        return {"id": obj.ddns_policy.id, "name": obj.ddns_policy.name}

    def get_ha_url(self, obj):
        return obj.ha_url

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
    ddns_policy = serializers.SerializerMethodField()

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
            "only_in_additional_list",
            "next_server",
            "server_hostname",
            "boot_file_name",
            "ddns_policy",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
            self.fields.pop("ddns_policy", None)

    def get_ddns_policy(self, obj):
        if obj.ddns_policy is None:
            return None
        return {"id": obj.ddns_policy.id, "name": obj.ddns_policy.name}


class SubnetSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:subnet-detail")
    prefix = NestedPrefixSerializer()
    server = NestedDHCPServerSerializer()
    option_data = OptionDataSerializer(many=True, read_only=True)
    client_class = NestedClientClassSerializer(read_only=True)
    evaluate_additional_classes = NestedClientClassSerializer(many=True, read_only=True)
    router_ip = serializers.SerializerMethodField()
    ddns_policy = serializers.SerializerMethodField()

    class Meta:
        model = Subnet
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
            "client_class",
            "evaluate_additional_classes",
            "reservations_global",
            "reservations_in_subnet",
            "reservations_out_of_pool",
            "reservations_only",
            "ddns_policy",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
            self.fields.pop("ddns_policy", None)

    def get_router_ip(self, obj):
        """Return the calculated router IP address."""
        return obj.get_router_ip()

    def get_ddns_policy(self, obj):
        if obj.ddns_policy is None:
            return None
        return {"id": obj.ddns_policy.id, "name": obj.ddns_policy.name}


class SubnetPoolSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:subnetpool-detail")
    subnet = NestedSubnetSerializer()
    ip_range = IPRangeSerializer(nested=True, read_only=True)
    client_class = NestedClientClassSerializer(read_only=True)
    evaluate_additional_classes = NestedClientClassSerializer(many=True, read_only=True)
    option_data = OptionDataSerializer(many=True, read_only=True)

    class Meta:
        model = SubnetPool
        fields = (
            "id",
            "url",
            "display",
            "subnet",
            "ip_range",
            "client_class",
            "evaluate_additional_classes",
            "option_data",
            "description",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


class NestedDHCPHARelationshipSerializer(WritableNestedSerializer):
    class Meta:
        model = DHCPHARelationship
        fields = ["id", "url", "display", "name", "mode"]


class DHCPHARelationshipSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dhcp_kea_plugin-api:dhcpharelationship-detail"
    )
    servers = NestedDHCPServerSerializer(many=True, read_only=True)
    d2_daemon = serializers.SerializerMethodField()

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
            "d2_daemon",
            "ddns_enable_updates",
            "ddns_policy",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
            for f in ("d2_daemon", "ddns_enable_updates", "ddns_policy"):
                self.fields.pop(f, None)

    def get_d2_daemon(self, obj):
        if obj.d2_daemon is None:
            return None
        return {"id": obj.d2_daemon.id, "name": obj.d2_daemon.name}


class NestedStorkServerSerializer(WritableNestedSerializer):
    class Meta:
        model = StorkServer
        fields = ["id", "url", "display", "name"]


class StorkServerSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:storkserver-detail")
    ip_address = IPAddressSerializer(nested=True, read_only=True)
    agent_groups = serializers.SerializerMethodField()

    class Meta:
        model = StorkServer
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "ip_address",
            "status",
            "rest_port",
            "rest_base_url",
            "use_tls",
            "db_host",
            "db_port",
            "db_name",
            "db_user",
            "db_ssl_mode",
            "enable_metrics",
            "grafana_url",
            "default_agent_registration",
            "stork_version",
            "log_level",
            "agent_groups",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def get_agent_groups(self, obj):
        return [{"id": g.id, "name": g.name, "operating_mode": g.operating_mode} for g in obj.agent_groups.all()]


class StorkAgentGroupSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dhcp_kea_plugin-api:storkagentgroup-detail"
    )
    stork_server = NestedStorkServerSerializer(read_only=True)
    servers = serializers.SerializerMethodField()

    class Meta:
        model = StorkAgentGroup
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "stork_server",
            "operating_mode",
            "agent_port",
            "prometheus_exporter_address",
            "prometheus_exporter_port",
            "prometheus_per_subnet_stats",
            "skip_tls_cert_verification",
            "log_level",
            "servers",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def get_servers(self, obj):
        servers = obj.servers.all()
        return NestedDHCPServerSerializer(servers, many=True, context=self.context).data


# --- DDNS Serializers ---


class NestedTSIGKeySerializer(WritableNestedSerializer):
    class Meta:
        model = TSIGKey
        fields = ["id", "url", "display", "name", "algorithm"]


class NestedD2DaemonSerializer(WritableNestedSerializer):
    class Meta:
        model = D2Daemon
        fields = ["id", "url", "display", "name", "port"]


class NestedDDNSPolicySerializer(WritableNestedSerializer):
    class Meta:
        model = DDNSPolicy
        fields = ["id", "url", "display", "name"]


class TSIGKeySerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:tsigkey-detail")

    class Meta:
        model = TSIGKey
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "algorithm",
            "digest_bits",
            "secret_backend",
            "secret_plaintext",
            "secret_ref",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request") if self.context else None
        if request is None or not request.user.has_perm("netbox_dhcp_kea_plugin.view_secret_tsigkey"):
            self.fields.pop("secret_plaintext", None)


class D2DaemonSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:d2daemon-detail")
    ip_address = IPAddressSerializer(nested=True, read_only=True)
    domains_count = serializers.SerializerMethodField()

    class Meta:
        model = D2Daemon
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "listener_mode",
            "ip_address",
            "port",
            "control_socket_path",
            "ncr_protocol",
            "ncr_format",
            "domains_count",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def get_domains_count(self, obj):
        return obj.domains.count()


class DDNSDomainSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:ddnsdomain-detail")
    d2_daemon = NestedD2DaemonSerializer(read_only=True)
    tsig_key = NestedTSIGKeySerializer(read_only=True)
    zone = serializers.SerializerMethodField()
    is_reverse = serializers.BooleanField(read_only=True)

    class Meta:
        model = DDNSDomain
        fields = (
            "id",
            "url",
            "display",
            "d2_daemon",
            "zone",
            "tsig_key",
            "is_reverse",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def get_zone(self, obj):
        if obj.zone_id is None:
            return None
        return {"id": obj.zone_id, "name": obj.zone.name}


class DDNSPolicySerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_dhcp_kea_plugin-api:ddnspolicy-detail")

    class Meta:
        model = DDNSPolicy
        fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "ddns_send_updates",
            "ddns_override_no_update",
            "ddns_override_client_update",
            "ddns_replace_client_name",
            "ddns_generated_prefix",
            "ddns_qualifying_suffix",
            "hostname_char_set",
            "hostname_char_replacement",
            "ddns_update_on_renew",
            "ddns_conflict_resolution_mode",
            "ddns_ttl_percent",
            "ddns_ttl",
            "ddns_ttl_min",
            "ddns_ttl_max",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
