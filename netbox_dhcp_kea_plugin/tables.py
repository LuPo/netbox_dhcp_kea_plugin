import django_tables2 as tables
from netbox.tables import BooleanColumn, ChoiceFieldColumn, NetBoxTable
from netbox.tables.columns import DateTimeColumn

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


class ViewEditActionsColumn(tables.TemplateColumn):
    """Custom actions column with view (eye) button and standard edit dropdown."""

    def __init__(self, *args, **kwargs):
        template_code = """
        <a href="{{ record.get_absolute_url }}" class="btn btn-sm btn-outline-primary" title="View">
            <i class="mdi mdi-eye"></i>
        </a>
        {% load helpers %}
        {% if perms.netbox_dhcp_kea_plugin.change_subnet %}
        <span class="dropdown">
            <a href="{% url 'plugins:netbox_dhcp_kea_plugin:subnet_edit' pk=record.pk %}" class="btn btn-sm btn-warning" title="Edit">
                <i class="mdi mdi-pencil"></i>
            </a>
            <button type="button" class="btn btn-warning btn-sm dropdown-toggle dropdown-toggle-split" data-bs-toggle="dropdown" aria-expanded="false">
                <span class="visually-hidden">Toggle Dropdown</span>
            </button>
            <ul class="dropdown-menu dropdown-menu-end">
                {% if perms.netbox_dhcp_kea_plugin.delete_subnet %}
                <li><a class="dropdown-item text-danger" href="{% url 'plugins:netbox_dhcp_kea_plugin:subnet_delete' pk=record.pk %}"><i class="mdi mdi-trash-can-outline"></i> Delete</a></li>
                {% endif %}
                <li><a class="dropdown-item" href="{% url 'plugins:netbox_dhcp_kea_plugin:subnet_changelog' pk=record.pk %}"><i class="mdi mdi-history"></i> Changelog</a></li>
            </ul>
        </span>
        {% endif %}
        """
        kwargs["template_code"] = template_code
        kwargs["verbose_name"] = ""
        kwargs["orderable"] = False
        super().__init__(*args, **kwargs)


class RawValueColumn(tables.Column):
    """Column that exports the raw database value for choice fields."""

    def __init__(self, field_name=None, *args, **kwargs):
        self.field_name = field_name
        super().__init__(*args, **kwargs)

    def render(self, record, value, column, bound_column):
        """For display, show the human-readable choice label."""
        field_name = self.field_name or bound_column.name
        display_method = getattr(record, f"get_{field_name}_display", None)
        if display_method:
            return display_method()
        return value

    def value(self, record, value):
        """For export, return the raw database value by accessing the attribute directly."""
        field_name = self.field_name or self.verbose_name
        # Access the raw attribute value from the record
        raw_value = getattr(record, field_name, value)
        return raw_value


class IsStandardColumn(BooleanColumn):
    """Display-only column for is_standard that is excluded from export."""

    def value(self, record, value):
        """Return empty string for export to effectively skip this column."""
        return ""  # Return empty string to exclude from export


def get_is_standard_attribute(record):
    """
    Get option standard state as string to attach to <tr/> DOM element.
    """
    if record.is_standard:
        return "standard"
    else:
        return "custom"


def get_has_vendor_attribute(record):
    """
    Get whether option has vendor option space to attach to <tr/> DOM element.
    """
    if record.vendor_option_space:
        return "vendor"
    else:
        return "standard-space"


class VendorOptionSpaceTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="name")
    enterprise_id = tables.Column(verbose_name="enterprise_id")
    manufacturer = tables.Column(linkify=True, verbose_name="Manufacturer")
    description = tables.Column(verbose_name="description")
    definitions_count = tables.Column(verbose_name="Definitions", accessor="option_definitions__count", orderable=False)

    class Meta(NetBoxTable.Meta):
        model = VendorOptionSpace
        fields = ("pk", "name", "enterprise_id", "manufacturer", "description", "definitions_count", "actions")
        default_columns = ("name", "enterprise_id", "manufacturer", "description")


class OptionDefinitionTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="name")
    id = tables.Column(verbose_name="id")
    code = tables.Column(verbose_name="code")
    option_type = RawValueColumn(field_name="option_type", verbose_name="option_type")
    option_space = RawValueColumn(field_name="option_space", verbose_name="option_space")
    vendor_option_space = tables.Column(
        linkify=True, verbose_name="vendor_option_space", accessor="vendor_option_space__name"
    )
    is_standard = BooleanColumn(verbose_name="is_standard")
    is_array = BooleanColumn(verbose_name="is_array")
    encapsulate = tables.Column(verbose_name="encapsulate")
    record_types = tables.Column(verbose_name="record_types")
    description = tables.Column(verbose_name="description")

    class Meta(NetBoxTable.Meta):
        model = OptionDefinition
        fields = (
            "pk",
            "name",
            "code",
            "option_type",
            "option_space",
            "vendor_option_space",
            "is_standard",
            "is_array",
            "encapsulate",
            "record_types",
            "description",
            "id",
            "actions",
        )
        default_columns = ("name", "code", "option_type", "vendor_option_space", "is_standard", "is_array")
        row_attrs = {
            "data-standard": get_is_standard_attribute,
            "data-vendor": get_has_vendor_attribute,
        }


class OptionDefinitionExportTable(NetBoxTable):
    """Export-specific table without is_standard column."""

    name = tables.Column(verbose_name="name")
    code = tables.Column(verbose_name="code")
    option_type = RawValueColumn(field_name="option_type", verbose_name="option_type")
    option_space = RawValueColumn(field_name="option_space", verbose_name="option_space")
    vendor_option_space = tables.Column(verbose_name="vendor_option_space", accessor="vendor_option_space__name")
    is_array = BooleanColumn(verbose_name="is_array")
    encapsulate = tables.Column(verbose_name="encapsulate")
    record_types = tables.Column(verbose_name="record_types")
    description = tables.Column(verbose_name="description")

    class Meta(NetBoxTable.Meta):
        model = OptionDefinition
        fields = (
            "name",
            "code",
            "option_type",
            "option_space",
            "vendor_option_space",
            "is_array",
            "encapsulate",
            "record_types",
            "description",
        )
        default_columns = ("name", "code", "option_type", "vendor_option_space", "is_array")
        exclude = ("id",)


class OptionDataTable(NetBoxTable):
    distinctive_name = tables.Column(linkify=True, verbose_name="Distinctive Name")
    id = tables.Column(verbose_name="id")
    definition = tables.Column(
        linkify=lambda record: record.definition.get_absolute_url() if record.definition else None,
        verbose_name="Definition",
        accessor="definition__name",
    )
    code = tables.Column(verbose_name="Code", accessor="definition__code")
    option_space = ChoiceFieldColumn(verbose_name="option_space")
    vendor_option_space = tables.Column(linkify=True, verbose_name="vendor_option_space")
    delivery_type = ChoiceFieldColumn(verbose_name="Delivery Type")
    ascii_data = tables.Column(
        verbose_name="Data (ASCII)",
        accessor="ascii_data",
        attrs={"td": {"class": "text-truncate", "style": "max-width: 200px;"}},
    )
    always_send = BooleanColumn(verbose_name="always_send")
    csv_format = BooleanColumn(verbose_name="csv_format")
    description = tables.Column(verbose_name="description")

    class Meta(NetBoxTable.Meta):
        model = OptionData
        fields = (
            "pk",
            "distinctive_name",
            "definition",
            "code",
            "option_space",
            "vendor_option_space",
            "delivery_type",
            "ascii_data",
            "always_send",
            "csv_format",
            "description",
            "id",
            "actions",
        )
        default_columns = (
            "distinctive_name",
            "definition",
            "code",
            "delivery_type",
            "vendor_option_space",
            "ascii_data",
        )


class OptionDataExportTable(NetBoxTable):
    """Export-specific table for OptionData with consistent naming."""

    distinctive_name = tables.Column(verbose_name="distinctive_name")
    definition = tables.Column(verbose_name="definition", accessor="definition__name")
    option_space = RawValueColumn(field_name="option_space", verbose_name="option_space")
    vendor_option_space = tables.Column(verbose_name="vendor_option_space", accessor="vendor_option_space__name")
    delivery_type = RawValueColumn(field_name="delivery_type", verbose_name="delivery_type")
    data = tables.Column(verbose_name="data")
    always_send = BooleanColumn(verbose_name="always_send")
    csv_format = BooleanColumn(verbose_name="csv_format")
    description = tables.Column(verbose_name="description")

    class Meta(NetBoxTable.Meta):
        model = OptionData
        fields = (
            "distinctive_name",
            "definition",
            "option_space",
            "vendor_option_space",
            "delivery_type",
            "data",
            "always_send",
            "csv_format",
            "description",
        )
        default_columns = ("distinctive_name", "definition", "delivery_type", "vendor_option_space", "data")
        exclude = ("id",)


class DHCPServerTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="name")
    description = tables.Column(verbose_name="description")
    ip_address = tables.Column(linkify=True, verbose_name="ip_address")
    status = ChoiceFieldColumn(verbose_name="status")
    service_template = tables.Column(linkify=True, verbose_name="service_template", accessor="service_template__pk")
    service = tables.Column(linkify=True, verbose_name="Application Service")
    ha_relationship = tables.Column(linkify=True, verbose_name="HA Relationship")
    ha_role = RawValueColumn(field_name="ha_role", verbose_name="HA Role")
    ha_address = tables.Column(verbose_name="HA Address")
    ha_port = tables.Column(verbose_name="HA Port")
    ha_tls = BooleanColumn(verbose_name="HA TLS")
    ha_auto_failover = BooleanColumn(verbose_name="HA Auto Failover")
    ctrl_socket_type = ChoiceFieldColumn(verbose_name="Control Socket")
    reservations_global = BooleanColumn(verbose_name="Reservations Global")
    reservations_in_subnet = BooleanColumn(verbose_name="Reservations In-Subnet")
    reservations_out_of_pool = BooleanColumn(verbose_name="Reservations Out-of-Pool")

    class Meta(NetBoxTable.Meta):
        model = DHCPServer
        fields = (
            "pk",
            "name",
            "description",
            "ip_address",
            "status",
            "service_template",
            "service",
            "ha_relationship",
            "ha_role",
            "ha_address",
            "ha_port",
            "ha_tls",
            "ha_auto_failover",
            "ctrl_socket_type",
            "reservations_global",
            "reservations_in_subnet",
            "reservations_out_of_pool",
            "actions",
        )
        default_columns = ("name", "description", "ip_address", "status", "ha_relationship", "ha_role")


class ClientClassTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="name")
    id = tables.Column(verbose_name="id")
    test_expression = tables.Column(verbose_name="test_expression")
    only_in_additional_list = BooleanColumn(verbose_name="Only in Additional List")
    next_server = tables.Column(verbose_name="next_server")
    server_hostname = tables.Column(verbose_name="server_hostname")
    boot_file_name = tables.Column(verbose_name="boot_file_name")
    option_data_count = tables.Column(verbose_name="option_data_count", accessor="option_data__count", orderable=False)
    description = tables.Column(verbose_name="description")

    class Meta(NetBoxTable.Meta):
        model = ClientClass
        fields = (
            "pk",
            "name",
            "test_expression",
            "only_in_additional_list",
            "next_server",
            "server_hostname",
            "boot_file_name",
            "description",
            "option_data_count",
            "id",
            "actions",
        )
        default_columns = ("name", "test_expression", "only_in_additional_list", "description")


class SubnetTable(NetBoxTable):
    prefix = tables.Column(linkify=True)
    id = tables.Column(verbose_name="id")
    server = tables.Column(linkify=True)
    valid_lifetime = tables.Column(verbose_name="Valid Lifetime")
    max_lifetime = tables.Column(verbose_name="Max Lifetime")
    pool_count = tables.Column(verbose_name="Pools", accessor="pool_count", orderable=True)
    option_data_count = tables.Column(verbose_name="Options", accessor="option_data__count", orderable=False)
    actions = tables.TemplateColumn(
        template_code="""
            <div class="text-end text-nowrap">
            <a href="{{ record.get_absolute_url }}" class="btn btn-sm btn-outline-primary" title="View"><i class="mdi mdi-eye"></i></a>
            {% load helpers %}
            {% if perms.netbox_dhcp_kea_plugin.change_subnet %}
            <span class="btn-group">
                <a href="{% url 'plugins:netbox_dhcp_kea_plugin:subnet_edit' pk=record.pk %}" class="btn btn-sm btn-warning" title="Edit"><i class="mdi mdi-pencil"></i></a>
                <button type="button" class="btn btn-warning btn-sm dropdown-toggle dropdown-toggle-split" data-bs-toggle="dropdown" aria-expanded="false"><span class="visually-hidden">Toggle Dropdown</span></button>
                <ul class="dropdown-menu dropdown-menu-end">
                    {% if perms.netbox_dhcp_kea_plugin.delete_subnet %}<li><a class="dropdown-item text-danger" href="{% url 'plugins:netbox_dhcp_kea_plugin:subnet_delete' pk=record.pk %}"><i class="mdi mdi-trash-can-outline"></i> Delete</a></li>{% endif %}
                    <li><a class="dropdown-item" href="{% url 'plugins:netbox_dhcp_kea_plugin:subnet_changelog' pk=record.pk %}"><i class="mdi mdi-history"></i> Changelog</a></li>
                </ul>
            </span>
            {% endif %}
            </div>
        """,
        verbose_name="",
        orderable=False,
    )

    reservations_global = tables.BooleanColumn(verbose_name="Res. Global")
    reservations_in_subnet = tables.BooleanColumn(verbose_name="Res. In-Subnet")
    reservations_out_of_pool = tables.BooleanColumn(verbose_name="Res. Out-of-Pool")
    reservations_only = tables.BooleanColumn(verbose_name="Res. Only")

    class Meta(NetBoxTable.Meta):
        model = Subnet
        fields = (
            "pk",
            "prefix",
            "server",
            "valid_lifetime",
            "max_lifetime",
            "pool_count",
            "option_data_count",
            "reservations_global",
            "reservations_in_subnet",
            "reservations_out_of_pool",
            "reservations_only",
            "id",
            "actions",
        )
        default_columns = (
            "prefix",
            "server",
            "valid_lifetime",
            "max_lifetime",
            "pool_count",
            "option_data_count",
            "actions",
        )


class SubnetExportTable(NetBoxTable):
    """Export-specific table for Subnet with VRF for prefix identification."""

    prefix = tables.Column(accessor="prefix__prefix", verbose_name="prefix")
    vrf = tables.Column(accessor="prefix__vrf__name", verbose_name="vrf")
    server = tables.Column(accessor="server__name", verbose_name="server")
    valid_lifetime = tables.Column(verbose_name="valid_lifetime")
    max_lifetime = tables.Column(verbose_name="max_lifetime")
    routers_option_offset = tables.Column(verbose_name="routers_option_offset")

    class Meta(NetBoxTable.Meta):
        model = Subnet
        fields = ("prefix", "vrf", "server", "valid_lifetime", "max_lifetime", "routers_option_offset")
        default_columns = ("prefix", "vrf", "server", "valid_lifetime", "max_lifetime", "routers_option_offset")
        exclude = ("id",)


class SubnetPoolTable(NetBoxTable):
    subnet = tables.Column(linkify=True)
    ip_range = tables.Column(verbose_name="IP Range", linkify=True)
    client_class = tables.Column(verbose_name="Client Class", linkify=True)
    additional_classes_count = tables.Column(
        verbose_name="Additional Classes",
        accessor="evaluate_additional_classes__count",
        orderable=False,
    )
    option_data_count = tables.Column(
        verbose_name="Options",
        accessor="option_data__count",
        orderable=False,
    )
    description = tables.Column(verbose_name="Description")
    actions = tables.TemplateColumn(
        template_code="""
            <div class="text-end text-nowrap">
            <a href="{{ record.get_absolute_url }}" class="btn btn-sm btn-outline-primary" title="View"><i class="mdi mdi-eye"></i></a>
            {% load helpers %}
            {% if perms.netbox_dhcp_kea_plugin.change_subnetpool %}
            <span class="btn-group">
                <a href="{% url 'plugins:netbox_dhcp_kea_plugin:subnetpool_edit' pk=record.pk %}" class="btn btn-sm btn-warning" title="Edit"><i class="mdi mdi-pencil"></i></a>
                <button type="button" class="btn btn-warning btn-sm dropdown-toggle dropdown-toggle-split" data-bs-toggle="dropdown" aria-expanded="false"><span class="visually-hidden">Toggle Dropdown</span></button>
                <ul class="dropdown-menu dropdown-menu-end">
                    {% if perms.netbox_dhcp_kea_plugin.delete_subnetpool %}<li><a class="dropdown-item text-danger" href="{% url 'plugins:netbox_dhcp_kea_plugin:subnetpool_delete' pk=record.pk %}"><i class="mdi mdi-trash-can-outline"></i> Delete</a></li>{% endif %}
                    <li><a class="dropdown-item" href="{% url 'plugins:netbox_dhcp_kea_plugin:subnetpool_changelog' pk=record.pk %}"><i class="mdi mdi-history"></i> Changelog</a></li>
                </ul>
            </span>
            {% endif %}
            </div>
        """,
        verbose_name="",
        orderable=False,
    )

    class Meta(NetBoxTable.Meta):
        model = SubnetPool
        fields = (
            "pk",
            "subnet",
            "ip_range",
            "client_class",
            "additional_classes_count",
            "option_data_count",
            "description",
            "actions",
        )
        default_columns = (
            "subnet",
            "ip_range",
            "client_class",
            "additional_classes_count",
            "option_data_count",
            "actions",
        )


class StaticReservationTable(NetBoxTable):
    ip_address = tables.Column(verbose_name="IP Address", linkify=True)
    mac_address = tables.Column(verbose_name="MAC Address", linkify=True)
    subnet = tables.Column(linkify=True)
    hostname = tables.Column()
    source = tables.Column()
    external_id = tables.Column(verbose_name="External ID")
    last_synced = DateTimeColumn(verbose_name="Last Synced")
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = StaticReservation
        fields = (
            "pk",
            "ip_address",
            "mac_address",
            "subnet",
            "hostname",
            "source",
            "external_id",
            "last_synced",
            "description",
            "actions",
        )
        default_columns = (
            "ip_address",
            "mac_address",
            "subnet",
            "hostname",
            "source",
            "last_synced",
            "actions",
        )


class DHCPHARelationshipTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="name")
    mode = RawValueColumn(field_name="mode", verbose_name="mode")
    heartbeat_delay = tables.Column(verbose_name="heartbeat_delay")
    max_response_delay = tables.Column(verbose_name="max_response_delay")
    max_ack_delay = tables.Column(verbose_name="max_ack_delay")
    max_unacked_clients = tables.Column(verbose_name="max_unacked_clients")
    max_rejected_lease_updates = tables.Column(verbose_name="max_rejected_lease_updates")
    enable_multi_threading = BooleanColumn(verbose_name="enable_multi_threading")
    http_dedicated_listener = BooleanColumn(verbose_name="http_dedicated_listener")
    http_listener_threads = tables.Column(verbose_name="http_listener_threads")
    http_client_threads = tables.Column(verbose_name="http_client_threads")
    description = tables.Column(verbose_name="description")
    servers_count = tables.Column(verbose_name="servers", accessor="servers__count", orderable=False)
    ha_basic_auth_user = tables.Column(verbose_name="basic_auth_user")
    # Whether the channel is authenticated, never the secret itself.
    ha_basic_auth = BooleanColumn(
        verbose_name="basic_auth",
        accessor="ha_basic_auth_user",
        orderable=False,
        # Without this, a blank user is an "empty value" and django-tables2 shows a
        # placeholder instead of calling render() — an unauthenticated relationship
        # would read as unknown rather than as off.
        empty_values=(),
    )

    class Meta(NetBoxTable.Meta):
        model = DHCPHARelationship
        fields = (
            "pk",
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
            "ha_basic_auth",
            "ha_basic_auth_user",
            "description",
            "servers_count",
            "actions",
        )
        default_columns = ("name", "mode", "servers_count", "enable_multi_threading", "description")
        exclude = ("id",)


class HookTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="Name")
    library_name = tables.Column(verbose_name="Library Name")
    is_standard = BooleanColumn(verbose_name="Standard")
    allowed_processes = tables.Column(verbose_name="Allowed Processes")
    description = tables.Column(verbose_name="Description")
    hook_groups_count = tables.Column(
        verbose_name="Hook Groups",
        accessor="hook_groups__count",
        orderable=False,
        linkify=False,
    )

    class Meta(NetBoxTable.Meta):
        model = Hook
        fields = (
            "pk",
            "name",
            "library_name",
            "is_standard",
            "allowed_processes",
            "description",
            "hook_groups_count",
            "actions",
        )
        default_columns = ("name", "library_name", "is_standard", "allowed_processes", "hook_groups_count")
        exclude = ("id",)

    def render_allowed_processes(self, value):
        """Render allowed_processes as comma-separated list."""
        if value:
            # Map process codes to display names
            process_map = dict(Hook.PROCESS_CHOICES)
            return ", ".join(process_map.get(p, p) for p in value)
        return "—"


class HookGroupTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="Name")
    library_path = tables.Column(verbose_name="Library Path")
    description = tables.Column(verbose_name="Description")
    hooks_count = tables.Column(
        verbose_name="Hooks",
        accessor="hooks__count",
        orderable=False,
        linkify=False,
    )
    servers_count = tables.Column(
        verbose_name="Servers",
        accessor="servers__count",
        orderable=False,
        linkify=False,
    )

    class Meta(NetBoxTable.Meta):
        model = HookGroup
        fields = (
            "pk",
            "name",
            "library_path",
            "description",
            "hooks_count",
            "servers_count",
            "actions",
        )
        default_columns = ("name", "library_path", "hooks_count", "servers_count", "description")
        exclude = ("id",)


class StorkServerTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="Name")
    status = tables.Column(verbose_name="Status")
    ip_address = tables.Column(linkify=True, verbose_name="IP Address")
    rest_port = tables.Column(verbose_name="REST Port")
    use_tls = BooleanColumn(verbose_name="TLS")
    enable_metrics = BooleanColumn(verbose_name="Metrics")
    stork_version = tables.Column(verbose_name="Version")
    description = tables.Column(verbose_name="Description")
    agent_groups_count = tables.Column(
        verbose_name="Agent Groups",
        accessor="agent_groups__count",
        orderable=False,
        linkify=False,
    )

    class Meta(NetBoxTable.Meta):
        model = StorkServer
        fields = (
            "pk",
            "name",
            "status",
            "ip_address",
            "rest_port",
            "use_tls",
            "enable_metrics",
            "stork_version",
            "description",
            "agent_groups_count",
            "actions",
        )
        default_columns = (
            "name",
            "status",
            "ip_address",
            "rest_port",
            "use_tls",
            "stork_version",
            "agent_groups_count",
        )
        exclude = ("id",)


class StorkAgentGroupTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="Name")
    stork_server = tables.Column(linkify=True, verbose_name="Stork Server")
    operating_mode = tables.Column(verbose_name="Mode")
    agent_port = tables.Column(verbose_name="Agent Port")
    prometheus_exporter_port = tables.Column(verbose_name="Exporter Port")
    description = tables.Column(verbose_name="Description")
    servers_count = tables.Column(
        verbose_name="Servers",
        accessor="servers__count",
        orderable=False,
        linkify=False,
    )

    class Meta(NetBoxTable.Meta):
        model = StorkAgentGroup
        fields = (
            "pk",
            "name",
            "stork_server",
            "operating_mode",
            "agent_port",
            "prometheus_exporter_port",
            "description",
            "servers_count",
            "actions",
        )
        default_columns = (
            "name",
            "stork_server",
            "operating_mode",
            "agent_port",
            "prometheus_exporter_port",
            "servers_count",
        )
        exclude = ("id",)


# --- DDNS Tables ---


class TSIGKeyTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="Name")
    algorithm = tables.Column(verbose_name="Algorithm")
    digest_bits = tables.Column(verbose_name="Digest Bits")
    secret_backend = tables.Column(verbose_name="Secret Backend")
    description = tables.Column(verbose_name="Description")

    class Meta(NetBoxTable.Meta):
        model = TSIGKey
        fields = (
            "pk",
            "name",
            "algorithm",
            "digest_bits",
            "secret_backend",
            "description",
            "actions",
        )
        default_columns = (
            "name",
            "algorithm",
            "secret_backend",
            "description",
        )
        exclude = ("id",)


class D2DaemonTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="Name")
    listener_mode = tables.Column(verbose_name="Mode")
    ip_address = tables.Column(linkify=True, verbose_name="Listener IP")
    port = tables.Column(verbose_name="Port")
    ncr_protocol = tables.Column(verbose_name="NCR Protocol")
    ncr_format = tables.Column(verbose_name="NCR Format")
    domains_count = tables.Column(
        verbose_name="Domains",
        accessor="domains__count",
        orderable=False,
        linkify=False,
    )
    description = tables.Column(verbose_name="Description")

    class Meta(NetBoxTable.Meta):
        model = D2Daemon
        fields = (
            "pk",
            "name",
            "listener_mode",
            "ip_address",
            "port",
            "ncr_protocol",
            "ncr_format",
            "domains_count",
            "description",
            "actions",
        )
        default_columns = (
            "name",
            "listener_mode",
            "ip_address",
            "port",
            "ncr_protocol",
            "domains_count",
        )
        exclude = ("id",)


class DDNSDomainTable(NetBoxTable):
    d2_daemon = tables.Column(linkify=True, verbose_name="D2 Daemon")
    zone = tables.Column(linkify=True, verbose_name="Zone")
    tsig_key = tables.Column(linkify=True, verbose_name="TSIG Key")
    is_reverse = BooleanColumn(verbose_name="Reverse")

    class Meta(NetBoxTable.Meta):
        model = DDNSDomain
        fields = (
            "pk",
            "d2_daemon",
            "zone",
            "tsig_key",
            "is_reverse",
            "actions",
        )
        default_columns = (
            "d2_daemon",
            "zone",
            "tsig_key",
            "is_reverse",
        )
        exclude = ("id",)


class DDNSPolicyTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name="Name")
    ddns_send_updates = BooleanColumn(verbose_name="Send Updates")
    ddns_qualifying_suffix = tables.Column(verbose_name="Qualifying Suffix")
    ddns_conflict_resolution_mode = tables.Column(verbose_name="Conflict Mode")
    servers_count = tables.Column(
        verbose_name="Servers",
        accessor="servers__count",
        orderable=False,
        linkify=False,
    )
    subnets_count = tables.Column(
        verbose_name="Subnets",
        accessor="subnets__count",
        orderable=False,
        linkify=False,
    )
    client_classes_count = tables.Column(
        verbose_name="Client Classes",
        accessor="client_classes__count",
        orderable=False,
        linkify=False,
    )
    description = tables.Column(verbose_name="Description")

    class Meta(NetBoxTable.Meta):
        model = DDNSPolicy
        fields = (
            "pk",
            "name",
            "ddns_send_updates",
            "ddns_qualifying_suffix",
            "ddns_conflict_resolution_mode",
            "servers_count",
            "subnets_count",
            "client_classes_count",
            "description",
            "actions",
        )
        default_columns = (
            "name",
            "ddns_send_updates",
            "ddns_qualifying_suffix",
            "servers_count",
            "subnets_count",
            "client_classes_count",
        )
        exclude = ("id",)
