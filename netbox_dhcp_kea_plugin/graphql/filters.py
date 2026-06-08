"""GraphQL filters for the DHCP-KEA plugin models.

Base ``NetBoxModelFilter`` (the plugin's models are ``NetBoxModel`` subclasses).
Explicit relation-filter fields are declared (lazily) for the cross-type
traversals callers need — notably ``SubnetFilter.prefix`` so subnets can be
filtered by ``prefix.role.name`` and scope/site.
"""

from typing import TYPE_CHECKING, Annotated

import strawberry
import strawberry_django
from netbox.graphql.filters import NetBoxModelFilter

from netbox_dhcp_kea_plugin.models import (
    ClientClass,
    DHCPServer,
    Subnet,
    SubnetPool,
)

if TYPE_CHECKING:
    from ipam.graphql.filters import (
        IPAddressFilter,
        IPRangeFilter,
        PrefixFilter,
    )

__all__ = (
    "ClientClassFilter",
    "DHCPServerFilter",
    "SubnetFilter",
    "SubnetPoolFilter",
)


@strawberry_django.filter_type(ClientClass, lookups=True)
class ClientClassFilter(NetBoxModelFilter):
    pass


@strawberry_django.filter_type(DHCPServer, lookups=True)
class DHCPServerFilter(NetBoxModelFilter):
    ip_address: (
        Annotated["IPAddressFilter", strawberry.lazy("ipam.graphql.filters")] | None
    ) = strawberry_django.filter_field()


@strawberry_django.filter_type(Subnet, lookups=True)
class SubnetFilter(NetBoxModelFilter):
    prefix: (
        Annotated["PrefixFilter", strawberry.lazy("ipam.graphql.filters")] | None
    ) = strawberry_django.filter_field()
    server: (
        Annotated[
            "DHCPServerFilter",
            strawberry.lazy("netbox_dhcp_kea_plugin.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
    client_class: (
        Annotated[
            "ClientClassFilter",
            strawberry.lazy("netbox_dhcp_kea_plugin.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()


@strawberry_django.filter_type(SubnetPool, lookups=True)
class SubnetPoolFilter(NetBoxModelFilter):
    subnet: (
        Annotated[
            "SubnetFilter",
            strawberry.lazy("netbox_dhcp_kea_plugin.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
    ip_range: (
        Annotated["IPRangeFilter", strawberry.lazy("ipam.graphql.filters")] | None
    ) = strawberry_django.filter_field()
    client_class: (
        Annotated[
            "ClientClassFilter",
            strawberry.lazy("netbox_dhcp_kea_plugin.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
