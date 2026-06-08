---
title: GraphQL API
description: Query the plugin's DHCP objects and traverse to native NetBox objects through NetBox's GraphQL endpoint.
---

# GraphQL API

The plugin registers types in NetBox's GraphQL schema, so you can query DHCP objects and
traverse to the related native NetBox objects (prefixes, IP addresses, IP ranges, services) in a
single request. This is convenient for provisioning and automation tools that need, for example,
to find the Kea subnets for a given prefix role and read their server and pools at once.

## Endpoint and authentication

- **Endpoint:** `POST /graphql/`
- **Auth:** a DRF **API token** (`Authorization: Token <token>`) or an authenticated session.
- **Field naming:** NetBox runs strawberry with `auto_camel_case=False`, so all field and query
  names are **snake_case** exactly as shown below.

## Query roots

Each exposed model provides a single-object lookup and a `_list` field (the list field accepts
`filters`, `pagination`, and `ordering`):

| Query root | Returns |
|---|---|
| `netbox_dhcp_kea_dhcp_server` / `_list` | DHCP servers |
| `netbox_dhcp_kea_subnet` / `_list` | Subnets |
| `netbox_dhcp_kea_subnet_pool` / `_list` | Subnet pools |
| `netbox_dhcp_kea_client_class` / `_list` | Client classes |

!!! note "Scope"
    This first iteration covers the four core models above — the ones needed to discover and
    inspect DHCP subnets. Additional types (host reservations, DDNS, Stork, option data) will be
    added incrementally using the same pattern.

## Types and traversals

Each type exposes its own scalar fields plus typed relations you can traverse — both to other
plugin types and to **native NetBox types**:

| Type | Native traversals | Plugin traversals |
|---|---|---|
| `DHCPServerType` | `ip_address` → IPAM IP address, `service` → IPAM service | `subnet_items` → subnets |
| `SubnetType` | `prefix` → IPAM prefix (→ `role`, `scope`) | `server`, `client_class`, `subnet_pools` |
| `SubnetPoolType` | `ip_range` → IPAM IP range | `subnet`, `client_class` |
| `ClientClassType` | — | `servers` |

### Filtering

List fields accept a `filters` argument. Plugin filters include relation filters into native
NetBox filters — most usefully `SubnetFilter.prefix`, which lets you filter subnets by their
prefix's **role** and **scope/site**:

```graphql
query {
  netbox_dhcp_kea_subnet_list(
    filters: { prefix: { role: { name: { exact: "WiFi End Users" } } } }
  ) {
    prefix { prefix }
  }
}
```

## Worked example

Find the Kea subnets whose prefix role is "End Users", and read each one's prefix, owning server
(with its IP), and dynamic pools — in one request:

```graphql
query {
  netbox_dhcp_kea_subnet_list(
    filters: { prefix: { role: { name: { exact: "End Users" } } } }
  ) {
    prefix {
      prefix
      role { name }
      scope_type
    }
    server {
      name
      ip_address { address }
    }
    subnet_pools {
      ip_range { start_address end_address }
    }
  }
}
```

Example call with a token:

```bash
curl -s https://netbox.example.com/graphql/ \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ netbox_dhcp_kea_subnet_list { prefix { prefix role { name } } server { name } } }"}'
```

!!! tip "REST is still available"
    The same objects remain available through the [REST API](usage.md#rest-api-endpoints). Use
    GraphQL when you want to fetch related objects in one round-trip; use REST for simple CRUD or
    the config-generation endpoints.
