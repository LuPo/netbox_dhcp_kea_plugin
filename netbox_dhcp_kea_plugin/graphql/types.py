"""GraphQL object types for the DHCP-KEA plugin.

Base ``NetBoxObjectType`` (the models are ``NetBoxModel`` subclasses). Scalar
fields are listed explicitly via ``fields=[...]`` rather than ``"__all__"`` so
the schema does not pull in related plugin models that have no GraphQL type yet
(option data, HA relationships, DDNS policies, …). Cross-type relations are
declared as lazy ``Annotated[...]`` attributes pointing only at the four built
types or at native NetBox types (IPAM Prefix / IPAddress / IPRange / Service).
"""

from typing import Annotated

import strawberry
import strawberry_django
from netbox.graphql.types import NetBoxObjectType

from netbox_dhcp_kea_plugin.models import (
    ClientClass,
    DHCPServer,
    Subnet,
    SubnetPool,
)

from .filters import (
    ClientClassFilter,
    DHCPServerFilter,
    SubnetFilter,
    SubnetPoolFilter,
)

__all__ = (
    "ClientClassType",
    "DHCPServerType",
    "SubnetType",
    "SubnetPoolType",
)


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

    @strawberry_django.field(
        description=(
            "Number of out-of-pool addresses available for a static reservation "
            "(available IPs minus the dynamic pool ranges)."
        )
    )
    def available_out_of_pool_count(self) -> int:
        return self.get_out_of_pool_available_ips().size


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
