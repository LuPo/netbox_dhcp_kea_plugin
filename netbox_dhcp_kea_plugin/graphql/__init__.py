from .schema import (
    NetBoxDHCPKeaClientClassQuery,
    NetBoxDHCPKeaDHCPServerQuery,
    NetBoxDHCPKeaSubnetPoolQuery,
    NetBoxDHCPKeaSubnetQuery,
)

# NetBox auto-discovers this `schema` list via the default
# graphql_schema='graphql.schema' plugin resource path.
schema = [
    NetBoxDHCPKeaDHCPServerQuery,
    NetBoxDHCPKeaSubnetQuery,
    NetBoxDHCPKeaSubnetPoolQuery,
    NetBoxDHCPKeaClientClassQuery,
]
