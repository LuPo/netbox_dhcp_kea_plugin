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

if TYPE_CHECKING:
    from dcim.graphql.filters import MACAddressFilter
    from ipam.graphql.filters import (
        IPAddressFilter,
        IPRangeFilter,
        PrefixFilter,
    )

__all__ = (
    "ClientClassFilter",
    "D2DaemonFilter",
    "DDNSDomainFilter",
    "DDNSPolicyFilter",
    "DDNSServerOverrideFilter",
    "DHCPServerFilter",
    "StaticReservationFilter",
    "SubnetFilter",
    "SubnetPoolFilter",
    "TSIGKeyFilter",
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


@strawberry_django.filter_type(StaticReservation, lookups=True)
class StaticReservationFilter(NetBoxModelFilter):
    subnet: (
        Annotated[
            "SubnetFilter",
            strawberry.lazy("netbox_dhcp_kea_plugin.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
    ip_address: (
        Annotated["IPAddressFilter", strawberry.lazy("ipam.graphql.filters")] | None
    ) = strawberry_django.filter_field()
    mac_address: (
        Annotated["MACAddressFilter", strawberry.lazy("dcim.graphql.filters")] | None
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


# --- DDNS ---


@strawberry_django.filter_type(TSIGKey, lookups=True)
class TSIGKeyFilter(NetBoxModelFilter):
    pass


@strawberry_django.filter_type(D2Daemon, lookups=True)
class D2DaemonFilter(NetBoxModelFilter):
    pass


@strawberry_django.filter_type(DDNSDomain, lookups=True)
class DDNSDomainFilter(NetBoxModelFilter):
    dhcp_server: (
        Annotated[
            "DHCPServerFilter",
            strawberry.lazy("netbox_dhcp_kea_plugin.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
    tsig_key: (
        Annotated[
            "TSIGKeyFilter",
            strawberry.lazy("netbox_dhcp_kea_plugin.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()


@strawberry_django.filter_type(DDNSServerOverride, lookups=True)
class DDNSServerOverrideFilter(NetBoxModelFilter):
    ddns_domain: (
        Annotated[
            "DDNSDomainFilter",
            strawberry.lazy("netbox_dhcp_kea_plugin.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()


@strawberry_django.filter_type(DDNSPolicy, lookups=True)
class DDNSPolicyFilter(NetBoxModelFilter):
    pass
