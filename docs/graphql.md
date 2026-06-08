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
| `SubnetType` | `prefix` → IPAM prefix (→ `role`, `scope`) | `server`, `client_class`, **`pools`** (all emitted pools — see [Computed fields](#computed-fields)), `subnet_pools` (configured pools only) |
| `SubnetPoolType` | `ip_range` → IPAM IP range | `subnet`, `client_class` |
| `ClientClassType` | — | `servers` |

!!! warning "Use `pools`, not `subnet_pools`, to list a subnet's pools"
    These are **two different fields** and the difference matters:

    - **`pools`** *(computed)* — **every** pool the subnet emits, configured or not, each with a
      `configured` flag. **This is the one you almost always want.**
    - **`subnet_pools`** *(raw relation)* — only the **`SubnetPool` config objects**, which exist
      solely when an operator has *configured* a pool (to attach a client class, extra classes, or
      option data to an IP Range). It is **sparse**: a subnet with a plain dynamic pool and no such
      config returns `[]` — so it will **not** show that pool.

### Computed fields

`SubnetType` exposes two computed fields beyond the stored columns:

- **`available_out_of_pool_count: Int`** — how many addresses can still be allocated for a
  **static reservation** on the subnet. It starts from the prefix's available IPs (NetBox already
  excludes assigned IPs and the network/broadcast), then applies the subnet's **effective
  `reservations-out-of-pool`** policy (which inherits from the DHCP server when not set on the
  subnet):
    - the dynamic pool does **not** constrain reservations — `reservations_only` (there is no
      pool) or `reservations-out-of-pool = False` (in-pool reservations are allowed; Kea resolves
      any overlap at runtime) → **every** available address counts, including when no IP Range is
      defined;
    - `reservations-out-of-pool = True` (reservations must stay out of pool) → the subnet's
      dynamic pool ranges are subtracted; with no IP Range the pool spans the available space, so
      the count is `0`.

  This lets the caller show, per subnet, how many addresses can still be reserved — without
  fetching the address list.

- **`pools: [SubnetPoolEntry!]`** — every DHCP pool the subnet emits, in one list, whether or not
  it has a `SubnetPool` config. Each entry has:
    - `pool_range: String` — the emitted `"start - end"` range;
    - `configured: Boolean` — `true` when a `SubnetPool` config is attached to the backing IP
      Range, `false` for a bare IP-Range pool or a computed pool;
    - `ip_range: IPRange` — the backing IPAM IP Range (`null` for computed pools that have no IP
      Range);
    - `config: SubnetPool` — the attached config when `configured` (else `null`).

  Pools come from the subnet's `mark_utilized=False` child IP Ranges; when none are defined, the
  computed pool(s) from the available/usable space are returned instead (always `configured:
  false`). A `reservations_only` subnet emits no pools.

### Filtering

List fields accept a `filters` argument. Plugin filters include relation filters into native
NetBox filters — most usefully `SubnetFilter.prefix`, which lets you filter subnets by their
prefix's **role** and **scope/site**:

```graphql
query {
  netbox_dhcp_kea_subnet_list(
    filters: { prefix: { role: { name: { exact: "Workstations" } } } }
  ) {
    prefix { prefix }
  }
}
```

## Worked example

Find the Kea subnets whose prefix role is `Workstations` **and** whose prefix is scoped to a
**Site**, and read — in one request — each one's prefix and site, owning server, dynamic pools,
and how many addresses are free for a static reservation:

```graphql
query {
  netbox_dhcp_kea_subnet_list(
    filters: {
      prefix: {
        role: { name: { exact: "Workstations" } }
        scope_type: { app_label: { exact: "dcim" }, model: { exact: "site" } }
      }
    }
  ) {
    prefix {
      prefix
      role { name }
      scope {
        ... on SiteType { name slug }
      }
    }
    server {
      name
      ip_address { address }
    }
    pools {
      pool_range
      configured
      ip_range { start_address end_address }
      config { id }
    }
    available_out_of_pool_count
  }
}
```

`prefix.scope_type` is a **content-type** filter, so `{ model: { exact: "site" } }` restricts the
result to Site-scoped prefixes — which is why each `scope` below resolves to a `SiteType` and is
read with the `... on SiteType` fragment alone. In general `scope` is a **union**: a prefix may
instead be scoped to a Location, Region, or Site Group, or be unscoped (`null`). To handle those,
drop the `scope_type` filter and query each variant with `__typename`, then dispatch in the client
(e.g. `scope.name` for a `SiteType`, `scope.site.name` for a `LocationType`). Response:

```json
{
  "data": {
    "netbox_dhcp_kea_subnet_list": [
      {
        "prefix": {
          "prefix": "192.0.2.0/24",
          "role": { "name": "Workstations" },
          "scope": { "name": "Headquarters", "slug": "hq" }
        },
        "server": { "name": "dhcp-1", "ip_address": { "address": "192.0.2.10/24" } },
        "pools": [
          {
            "pool_range": "192.0.2.50 - 192.0.2.200",
            "configured": true,
            "ip_range": { "start_address": "192.0.2.50/24", "end_address": "192.0.2.200/24" },
            "config": { "id": "42" }
          }
        ],
        "available_out_of_pool_count": 103
      },
      {
        "prefix": {
          "prefix": "198.51.100.0/24",
          "role": { "name": "Workstations" },
          "scope": { "name": "Branch Office", "slug": "branch" }
        },
        "server": { "name": "dhcp-2", "ip_address": { "address": "192.0.2.11/24" } },
        "pools": [
          {
            "pool_range": "198.51.100.200 - 198.51.100.250",
            "configured": false,
            "ip_range": { "start_address": "198.51.100.200/24", "end_address": "198.51.100.250/24" },
            "config": null
          }
        ],
        "available_out_of_pool_count": 203
      }
    ]
  }
}
```

`pools` lists every pool each subnet emits with a `configured` flag: subnet 1's pool has a
`SubnetPool` config attached (`configured: true`, `config` populated), while subnet 2's is a bare
IP-Range pool (`configured: false`, `config: null`). Use `subnet_pools` instead if you only want
the configured ones.

The `available_out_of_pool_count` values above assume the default **`reservations-out-of-pool =
True`**, under which it reflects only out-of-pool space: subnet 1 has a 151-address pool
(`254 − 151 = 103`) and subnet 2 a 51-address pool (`254 − 51 = 203`). With
`reservations-out-of-pool = False` (in-pool reservations allowed) each would instead report every
available address. See [Computed fields](#computed-fields).

Example call with a token (one inline fragment on the scope union):

```bash
curl -s https://netbox.example.com/graphql/ \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ netbox_dhcp_kea_subnet_list { prefix { prefix scope { ... on SiteType { name } } } available_out_of_pool_count } }"}'
```

!!! tip "REST is still available"
    The same objects remain available through the [REST API](usage.md#rest-api-endpoints). Use
    GraphQL when you want to fetch related objects in one round-trip; use REST for simple CRUD or
    the config-generation endpoints.
