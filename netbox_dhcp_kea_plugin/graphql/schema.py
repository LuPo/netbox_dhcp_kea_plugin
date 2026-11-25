"""GraphQL query roots for the DHCP-KEA plugin.

One Query class per exposed model; each provides a single-object and a `_list`
field. NetBox merges these into the global schema (see ``graphql/__init__.py``).
"""

import strawberry
import strawberry_django

from .types import (
    ClientClassType,
    D2DaemonType,
    DDNSDomainType,
    DDNSPolicyType,
    DDNSServerOverrideType,
    DHCPServerType,
    StaticReservationType,
    SubnetPoolType,
    SubnetType,
    TSIGKeyType,
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


@strawberry.type(name="Query")
class NetBoxDHCPKeaStaticReservationQuery:
    netbox_dhcp_kea_static_reservation: StaticReservationType = strawberry_django.field()
    netbox_dhcp_kea_static_reservation_list: list[StaticReservationType] = (
        strawberry_django.field()
    )


# --- DDNS (registered only when enable_ddns is on; see graphql/__init__.py) ---


@strawberry.type(name="Query")
class NetBoxDHCPKeaTSIGKeyQuery:
    netbox_dhcp_kea_tsig_key: TSIGKeyType = strawberry_django.field()
    netbox_dhcp_kea_tsig_key_list: list[TSIGKeyType] = strawberry_django.field()


@strawberry.type(name="Query")
class NetBoxDHCPKeaD2DaemonQuery:
    netbox_dhcp_kea_d2_daemon: D2DaemonType = strawberry_django.field()
    netbox_dhcp_kea_d2_daemon_list: list[D2DaemonType] = strawberry_django.field()


@strawberry.type(name="Query")
class NetBoxDHCPKeaDDNSDomainQuery:
    netbox_dhcp_kea_ddns_domain: DDNSDomainType = strawberry_django.field()
    netbox_dhcp_kea_ddns_domain_list: list[DDNSDomainType] = strawberry_django.field()


@strawberry.type(name="Query")
class NetBoxDHCPKeaDDNSServerOverrideQuery:
    netbox_dhcp_kea_ddns_server_override: DDNSServerOverrideType = strawberry_django.field()
    netbox_dhcp_kea_ddns_server_override_list: list[DDNSServerOverrideType] = strawberry_django.field()


@strawberry.type(name="Query")
class NetBoxDHCPKeaDDNSPolicyQuery:
    netbox_dhcp_kea_ddns_policy: DDNSPolicyType = strawberry_django.field()
    netbox_dhcp_kea_ddns_policy_list: list[DDNSPolicyType] = strawberry_django.field()
