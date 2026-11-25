from netbox.plugins.utils import get_plugin_config

from .schema import (
    NetBoxDHCPKeaClientClassQuery,
    NetBoxDHCPKeaD2DaemonQuery,
    NetBoxDHCPKeaDDNSDomainQuery,
    NetBoxDHCPKeaDDNSPolicyQuery,
    NetBoxDHCPKeaDDNSServerOverrideQuery,
    NetBoxDHCPKeaDHCPServerQuery,
    NetBoxDHCPKeaStaticReservationQuery,
    NetBoxDHCPKeaSubnetPoolQuery,
    NetBoxDHCPKeaSubnetQuery,
    NetBoxDHCPKeaTSIGKeyQuery,
)

# NetBox auto-discovers this `schema` list via the default
# graphql_schema='graphql.schema' plugin resource path.
schema = [
    NetBoxDHCPKeaDHCPServerQuery,
    NetBoxDHCPKeaSubnetQuery,
    NetBoxDHCPKeaSubnetPoolQuery,
    NetBoxDHCPKeaClientClassQuery,
    NetBoxDHCPKeaStaticReservationQuery,
]

# Like the REST routes, the DDNS roots exist only with DDNS enabled; their
# types traverse into netbox-dns, which enable_ddns requires.
if get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
    schema += [
        NetBoxDHCPKeaTSIGKeyQuery,
        NetBoxDHCPKeaD2DaemonQuery,
        NetBoxDHCPKeaDDNSDomainQuery,
        NetBoxDHCPKeaDDNSServerOverrideQuery,
        NetBoxDHCPKeaDDNSPolicyQuery,
    ]
