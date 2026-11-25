"""GraphQL object types for the DHCP-KEA plugin.

Base ``NetBoxObjectType`` (the models are ``NetBoxModel`` subclasses). Scalar
fields are listed explicitly via ``fields=[...]`` rather than ``"__all__"`` so
the schema does not pull in related plugin models that have no GraphQL type yet
(option data, HA relationships, Stork, …). Cross-type relations are declared as
lazy ``Annotated[...]`` attributes pointing only at built plugin types, native
NetBox types (IPAM Prefix / IPAddress / IPRange / Service) or netbox-dns types.

The TSIG key type has no secret field, by design: GraphQL has no per-field
permission like the REST serializer's ``view_secret_tsigkey`` check.
"""

from typing import Annotated

import strawberry
import strawberry_django
from netbox.graphql.types import NetBoxObjectType

from netbox_dhcp_kea_plugin.models import (
    ClientClass,
    D2Daemon,
    DDNSDomain,
    DDNSPolicy,
    DDNSServerOverride,
    DHCPServer,
    StaticReservation,
    Subnet,
    SubnetPool,
    TSIGKey,
)

from .filters import (
    ClientClassFilter,
    D2DaemonFilter,
    DDNSDomainFilter,
    DDNSPolicyFilter,
    DDNSServerOverrideFilter,
    DHCPServerFilter,
    StaticReservationFilter,
    SubnetFilter,
    SubnetPoolFilter,
    TSIGKeyFilter,
)

__all__ = (
    "ClientClassType",
    "D2DaemonType",
    "DDNSDomainType",
    "DDNSPolicyType",
    "DDNSServerOverrideType",
    "DHCPServerType",
    "StaticReservationType",
    "SubnetType",
    "SubnetPoolType",
    "SubnetPoolEntryType",
    "TSIGKeyType",
)


@strawberry.type
class SubnetPoolEntryType:
    """One DHCP pool on a subnet — both explicitly-configured pools and bare /
    computed ones, distinguished by `configured`."""

    pool_range: str
    configured: bool
    ip_range: (
        Annotated["IPRangeType", strawberry.lazy("ipam.graphql.types")] | None
    ) = None
    config: (
        Annotated["SubnetPoolType", strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types")]
        | None
    ) = None


@strawberry_django.type(
    DHCPServer,
    fields=[
        "id",
        "name",
        "description",
        "status",
        "reservations_global",
        "reservations_in_subnet",
        "reservations_out_of_pool",
        "ha_role",
        "ha_address",
        "ha_port",
        "ha_tls",
    ],
    filters=DHCPServerFilter,
    pagination=True,
)
class DHCPServerType(NetBoxObjectType):
    name: str
    ip_address: Annotated["IPAddressType", strawberry.lazy("ipam.graphql.types")]
    service: (
        Annotated["ServiceType", strawberry.lazy("ipam.graphql.types")] | None
    )
    subnet_items: list[
        Annotated["SubnetType", strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types")]
    ]


@strawberry_django.type(
    ClientClass,
    fields=[
        "id",
        "name",
        "test_expression",
        "description",
        "only_in_additional_list",
        "next_server",
        "server_hostname",
        "boot_file_name",
    ],
    filters=ClientClassFilter,
    pagination=True,
)
class ClientClassType(NetBoxObjectType):
    name: str
    servers: list[
        Annotated[
            "DHCPServerType", strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types")
        ]
    ]


@strawberry_django.type(
    Subnet,
    fields=[
        "id",
        "valid_lifetime",
        "max_lifetime",
        "routers_option_offset",
        "reservations_global",
        "reservations_in_subnet",
        "reservations_out_of_pool",
        "reservations_only",
    ],
    filters=SubnetFilter,
    pagination=True,
)
class SubnetType(NetBoxObjectType):
    prefix: Annotated["PrefixType", strawberry.lazy("ipam.graphql.types")]
    server: Annotated[
        "DHCPServerType", strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types")
    ]
    client_class: (
        Annotated[
            "ClientClassType", strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types")
        ]
        | None
    )
    subnet_pools: list[
        Annotated[
            "SubnetPoolType", strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types")
        ]
    ]
    static_reservations: list[
        Annotated[
            "StaticReservationType",
            strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types"),
        ]
    ]

    @strawberry_django.field(
        description=(
            "Number of out-of-pool addresses available for a static reservation "
            "(available IPs minus the dynamic pool ranges)."
        )
    )
    def available_out_of_pool_count(self) -> int:
        return self.get_out_of_pool_available_ips().size

    @strawberry_django.field(
        description=(
            "All DHCP pools the subnet emits — both explicitly-configured pools "
            "(with their backing IP Range and config) and bare/computed pools — "
            "each flagged with `configured`."
        )
    )
    def pools(self) -> list[SubnetPoolEntryType]:
        return [
            SubnetPoolEntryType(
                pool_range=entry.pool_range,
                configured=entry.configured,
                ip_range=entry.ip_range,
                config=entry.subnet_pool,
            )
            for entry in self.get_pool_entries()
        ]


@strawberry_django.type(
    SubnetPool,
    fields=[
        "id",
        "description",
    ],
    filters=SubnetPoolFilter,
    pagination=True,
)
class SubnetPoolType(NetBoxObjectType):
    subnet: Annotated[
        "SubnetType", strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types")
    ]
    ip_range: Annotated["IPRangeType", strawberry.lazy("ipam.graphql.types")]
    client_class: (
        Annotated[
            "ClientClassType", strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types")
        ]
        | None
    )


@strawberry_django.type(
    StaticReservation,
    fields=[
        "id",
        "hostname",
        "description",
        "source",
        "external_id",
        "last_synced",
    ],
    filters=StaticReservationFilter,
    pagination=True,
)
class StaticReservationType(NetBoxObjectType):
    subnet: Annotated[
        "SubnetType", strawberry.lazy("netbox_dhcp_kea_plugin.graphql.types")
    ]
    ip_address: Annotated["IPAddressType", strawberry.lazy("ipam.graphql.types")]
    mac_address: Annotated["MACAddressType", strawberry.lazy("dcim.graphql.types")]


# --- DDNS ---

_PLUGIN_TYPES = "netbox_dhcp_kea_plugin.graphql.types"


@strawberry_django.type(
    TSIGKey,
    # No secret_plaintext: see the module docstring.
    fields=["id", "name", "description", "algorithm", "digest_bits", "secret_backend", "secret_ref"],
    filters=TSIGKeyFilter,
    pagination=True,
)
class TSIGKeyType(NetBoxObjectType):
    name: str


@strawberry_django.type(
    D2Daemon,
    fields=[
        "id",
        "name",
        "description",
        "listener_mode",
        "port",
        "dns_server_timeout",
        "control_socket_path",
        "ncr_protocol",
        "ncr_format",
    ],
    filters=D2DaemonFilter,
    pagination=True,
)
class D2DaemonType(NetBoxObjectType):
    name: str
    ip_address: Annotated["IPAddressType", strawberry.lazy("ipam.graphql.types")] | None

    @strawberry_django.field(description="DHCP servers using this daemon; their subnets decide its domains.")
    def servers(self) -> list[Annotated["DHCPServerType", strawberry.lazy(_PLUGIN_TYPES)]]:
        return list(self.servers_using())

    @strawberry_django.field(description="Whether kea-config is a template awaiting secret substitution.")
    def requires_secret_substitution(self) -> bool:
        return self.requires_secret_substitution()


@strawberry_django.type(
    DDNSDomain,
    fields=["id", "always_include", "user_context"],
    filters=DDNSDomainFilter,
    pagination=True,
)
class DDNSDomainType(NetBoxObjectType):
    dhcp_server: Annotated["DHCPServerType", strawberry.lazy(_PLUGIN_TYPES)] | None
    zone: Annotated["NetBoxDNSZoneType", strawberry.lazy("netbox_dns.graphql.types")]
    tsig_key: Annotated["TSIGKeyType", strawberry.lazy(_PLUGIN_TYPES)] | None
    server_overrides: list[Annotated["DDNSServerOverrideType", strawberry.lazy(_PLUGIN_TYPES)]]

    @strawberry_django.field(description="Whether the zone is a reverse (in-addr.arpa / ip6.arpa) zone.")
    def is_reverse(self) -> bool:
        return self.is_reverse

    @strawberry_django.field(description="global, ha_relationship or server.")
    def scope(self) -> str:
        return self.scope

    @strawberry_django.field(description="ID of the HA relationship this entry is limited to, if any.")
    def ha_relationship_id(self) -> int | None:
        return self.ha_relationship_id


@strawberry_django.type(
    DDNSServerOverride,
    fields=["id", "port", "description"],
    filters=DDNSServerOverrideFilter,
    pagination=True,
)
class DDNSServerOverrideType(NetBoxObjectType):
    ddns_domain: Annotated["DDNSDomainType", strawberry.lazy(_PLUGIN_TYPES)]
    nameserver: Annotated["NetBoxDNSNameServerType", strawberry.lazy("netbox_dns.graphql.types")]
    tsig_key: Annotated["TSIGKeyType", strawberry.lazy(_PLUGIN_TYPES)] | None


@strawberry_django.type(
    DDNSPolicy,
    fields=[
        "id",
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
    ],
    filters=DDNSPolicyFilter,
    pagination=True,
)
class DDNSPolicyType(NetBoxObjectType):
    name: str
    servers: list[Annotated["DHCPServerType", strawberry.lazy(_PLUGIN_TYPES)]]
    subnets: list[Annotated["SubnetType", strawberry.lazy(_PLUGIN_TYPES)]]
    pools: list[Annotated["SubnetPoolType", strawberry.lazy(_PLUGIN_TYPES)]]
