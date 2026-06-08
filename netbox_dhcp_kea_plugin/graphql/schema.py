"""GraphQL query roots for the DHCP-KEA plugin.

One Query class per exposed model; each provides a single-object and a `_list`
field. NetBox merges these into the global schema (see ``graphql/__init__.py``).
"""

import strawberry
import strawberry_django

from .types import (
    ClientClassType,
    DHCPServerType,
    SubnetPoolType,
    SubnetType,
)


@strawberry.type(name="Query")
class NetBoxDHCPKeaDHCPServerQuery:
    netbox_dhcp_kea_dhcp_server: DHCPServerType = strawberry_django.field()
    netbox_dhcp_kea_dhcp_server_list: list[DHCPServerType] = strawberry_django.field()


@strawberry.type(name="Query")
class NetBoxDHCPKeaSubnetQuery:
    netbox_dhcp_kea_subnet: SubnetType = strawberry_django.field()
    netbox_dhcp_kea_subnet_list: list[SubnetType] = strawberry_django.field()


@strawberry.type(name="Query")
class NetBoxDHCPKeaSubnetPoolQuery:
    netbox_dhcp_kea_subnet_pool: SubnetPoolType = strawberry_django.field()
    netbox_dhcp_kea_subnet_pool_list: list[SubnetPoolType] = strawberry_django.field()


@strawberry.type(name="Query")
class NetBoxDHCPKeaClientClassQuery:
    netbox_dhcp_kea_client_class: ClientClassType = strawberry_django.field()
    netbox_dhcp_kea_client_class_list: list[ClientClassType] = strawberry_django.field()
