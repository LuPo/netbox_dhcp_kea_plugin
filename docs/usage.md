---
title: Usage
description: Task-oriented walkthroughs — quick start, relay configuration, Kea config generation, Stork env files, demo data.
---

# Usage

## Quick start

1. **Create DHCP servers** — Navigate to *DHCP KEA → DHCP Servers* and add your Kea server instances.
2. **Configure HA** *(optional)* — Set up HA relationships, assign server roles, configure HA peer address / port / TLS, and optionally set the relationship's shared basic-auth credentials.
3. **Configure control sockets** *(optional)* — Enable HTTP and/or Unix control sockets on DHCP servers.
4. **Configure Stork** *(optional)* — Set up Stork servers and agent groups for monitoring.
5. **Define options** — Create option definitions for vendor-specific options, or use standard DHCP options.
6. **Create option data** — Define option values to apply to client classes or prefixes. See [Guides — Class-conditional option delivery](guides/class-conditional-option-delivery.md) for the right attachment scope.
7. **Set up client classes** — Configure client classification rules with Kea test expressions.
8. **Configure prefixes** — Link NetBox Prefixes to DHCP servers with pools and options.

## Relay configuration

When configuring DHCP relay on Layer 3 switches or routers, you need the DHCP server IP addresses to use as helper addresses. The plugin exposes this through three equivalent endpoints.

### Method 1 — query the Prefix API directly

The plugin extends NetBox's Prefix API with a `dhcp_config` field:

```bash
GET /api/ipam/prefixes/{id}/
```

```json
{
    "id": 123,
    "prefix": "10.0.100.0/24",
    "vrf": null,
    "dhcp_config": {
        "server": {
            "name": "kea-dhcp-primary"
        },
        "relay_targets": ["192.168.1.10", "192.168.1.11"]
    }
}
```

### Method 2 — lookup by prefix CIDR

```bash
# Global VRF
GET /api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=10.0.100.0/24

# Specific VRF
GET /api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=10.0.100.0/24&vrf=CustomerA
```

```json
{
    "prefix": "10.0.100.0/24",
    "dhcp_config": {
        "server": {
            "name": "kea-dhcp-primary"
        },
        "relay_targets": ["192.168.1.10", "192.168.1.11"]
    }
}
```

### Method 3 — from a Subnet

```bash
GET /api/plugins/netbox-dhcp-kea-plugin/subnets/{id}/relay-config/
```

### Using relay targets in network configs

The `relay_targets` array contains every DHCP server IP that should receive relayed requests. For HA configurations, this includes all servers in the relationship — configure them all as helpers so failover is transparent.

=== "Cisco IOS / IOS-XE"

    ```text
    interface Vlan100
      ip helper-address 192.168.1.10
      ip helper-address 192.168.1.11
    ```

=== "Juniper Junos"

    ```text
    set forwarding-options dhcp-relay server-group DHCP-SERVERS 192.168.1.10
    set forwarding-options dhcp-relay server-group DHCP-SERVERS 192.168.1.11
    set forwarding-options dhcp-relay group RELAYS active-server-group DHCP-SERVERS
    set forwarding-options dhcp-relay group RELAYS interface vlan.100
    ```

=== "Arista EOS"

    ```text
    interface Vlan100
      ip helper-address 192.168.1.10
      ip helper-address 192.168.1.11
    ```

## Kea configuration generation

Generate a Kea-compatible configuration for a DHCP server:

```bash
GET /api/plugins/netbox-dhcp-kea-plugin/dhcp-servers/{id}/kea-config/
```

The endpoint returns a complete `Dhcp4` dictionary including:

- Global options
- Client class definitions
- Subnet configurations with pools
- Host reservations (auto-discovered from NetBox IP assignments with MAC addresses)
- Control sockets (if configured)
- HA configuration (if applicable)
- DDNS keys (`dhcp-ddns` block + `ddns-*` overrides) when `enable_ddns` is on and the server has a `d2_daemon` and/or `ddns_policy` set

### HA fields on DHCPServer

When creating or updating DHCP servers via the API, HA peer connection details are split across discrete fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `ha_address` | string | `""` | IP address for HA communication (validated as IPv4 / IPv6). |
| `ha_port` | integer | `8080` | Port for HA communication. |
| `ha_tls` | boolean | `false` | Use TLS (HTTPS) for HA communication. |
| `ha_url` | string | *(read-only)* | Computed URL from address / port / TLS (e.g. `http://192.168.1.1:8080/`). |

`ha_url` is read-only in API responses — it's reconstructed from `ha_address`, `ha_port`, and `ha_tls`. The emitted Kea configuration uses this computed URL in `high-availability` peer entries, so downstream Kea configs require no changes when you flip TLS or move the port.

**Validation rules:**

- `ha_address` and `ctrl_socket_http_address` must be valid IP addresses when provided.
- `ha_port` must differ from `ctrl_socket_http_port` when the HTTP control socket is enabled.

### HA reverse proxy

`ha_proxy_enabled` is a field on **`DHCPHARelationship`**, not on the individual servers. When it is on, every member's rendered peer list is all-loopback: its own entry binds `127.0.0.1:<ha_port>`, and each peer entry points at a local egress port the proxy forwards from. No `trust-anchor` / `cert-file` / `key-file` is ever emitted, because KEA speaks plain HTTP in both directions and the proxy owns TLS.

This is all-or-nothing by design. A relationship proxied on one member only fails in both directions: the unproxied peer dials plain HTTP at the other's proxy listener, while that proxy originates TLS to a KEA that speaks none. Making it a relationship field removes the possibility.

Each server keeps its own `ha_egress_base_port` (default `18080`) — one consecutive loopback port per peer, ordered by peer name — because which local ports are free is a per-host question. `ha_tls` must be off on a member whose relationship enables the proxy.

`DHCPServer.ha_proxy_enabled` is still readable in the API as a read-only field inherited from the relationship, alongside the computed `ha_proxy` plan that Ansible consumes.

### HA basic-auth fields on DHCPHARelationship

The HA channel's HTTP basic-auth credentials belong to the **relationship**, not to its members — Kea treats them as one shared secret for the cluster.

| Field | Type | Default | Description |
|---|---|---|---|
| `ha_basic_auth_user` | string | `""` | Username every member requires on its HA listener and presents to its peers. |
| `ha_basic_auth_password` | string | `""` | The paired password. |

Both values are written onto **every** peer entry in the emitted `high-availability` hook configuration, including the entry whose `name` matches `this-server-name`. That is deliberate, and it reflects how Kea reads the peer list:

- The entry matching `this-server-name` configures the member's **own listener** — the credentials there are what it *requires* from incoming connections.
- Every other entry configures a connection it *makes* — the credentials there are what it *presents* to that peer.

Writing the same pair everywhere therefore makes the channel authenticated symmetrically. Leaving both blank is valid and yields an unauthenticated HA channel; setting only one of the two is rejected.

!!! warning "Changing these changes every member at once"

    Because each member's listener requirement comes from the same field, editing the pair alters both sides of the channel. Fetch and deploy every member of the relationship **together** — a half-applied rollout leaves one server requiring credentials its partner is not yet sending, which surfaces as HTTP 401 on the HA channel and, after `max-response-delay`, a spurious `partner-down`.

!!! danger "The credentials appear in the rendered configuration"

    The password is part of the JSON returned by the `kea-config/` endpoint and written to the deployed config file. Suppress diff output when deploying it, and treat archived config copies as holding the secret.

## D2 daemon configuration generation

When DDNS is enabled, each `D2Daemon` exposes a per-instance endpoint that emits a complete `kea-dhcp-ddns.conf`:

```bash
GET /api/plugins/netbox_dhcp_kea_plugin/d2-daemons/{id}/kea-config/
```

The output includes the listener block (`ip-address` resolved from `listener_mode` — `127.0.0.1` for local, the IPAM-pinned IP for remote), the control socket, the TSIG key ring (deduplicated across this daemon's domains), and the forward / reverse `ddns-domains` arrays partitioned by zone name.

## Stork configuration

When Stork integration is enabled ([`enable_stork: True`](configuration.md#core-settings)), the plugin can generate environment files for ISC Stork server and agent deployment.

### Stork server env file

```bash
GET /api/plugins/netbox-dhcp-kea-plugin/stork-servers/{id}/config/
```

Returns plain text (`text/plain`) with environment variables suitable for `/etc/stork/server.env` — database connection, REST API, and metrics settings.

### Stork agent env file

```bash
# Generic template with placeholder for STORK_AGENT_HOST
GET /api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/{id}/config/

# Resolved for a specific DHCP server (placeholder replaced with that server's IP)
GET /api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/{id}/config/?server={dhcp_server_id}
```

Returns plain text for `/etc/stork/agent.env` — server connection, Prometheus exporter, and logging settings.

### Ansible integration

The config endpoints respond with `text/plain`, so Ansible's `ansible.builtin.uri` module consumes them directly:

```yaml
- name: Fetch Stork agent env file
  ansible.builtin.uri:
    url: "https://netbox.example.com/api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/1/config/?server=5"
    headers:
      Accept: "text/plain"
      Authorization: "Token {{ netbox_token }}"
    return_content: yes
  register: stork_agent_env

- name: Write agent env file
  ansible.builtin.copy:
    content: "{{ stork_agent_env.content }}"
    dest: /etc/stork/agent.env
```

## Static reservation provisioning

When an automation tool knows a client's **MAC** and the **subnet** it belongs to, but wants NetBox
to choose the address, post to the provisioning endpoint. NetBox allocates the next available
out-of-pool address, creates the `IPAddress`, and writes the reservation — atomically, under a
per-prefix lock (see [Features — Allocate-and-reserve provisioning](features.md#allocate-and-reserve-provisioning)).

```bash
curl -s https://netbox.example.com/api/plugins/netbox-dhcp-kea-plugin/static-reservations/provision/ \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "subnet": 12,
        "mac_address": "00:53:00:11:22:33",
        "hostname": "printer-lobby",
        "source": "nac",
        "external_id": "nac-rec-4567"
      }'
```

Request fields:

| Field | Required | Description |
|---|---|---|
| `subnet` | yes | Plugin `Subnet` id to allocate within |
| `mac_address` | yes | Client MAC, as a string (a standalone MAC record is created) |
| `hostname` | no | Reservation hostname (defaults to the IP's DNS name) |
| `dns_name` | no | DNS name to set on the newly created IP address |
| `source` | no | Origin tag stored on the reservation (e.g. `nac`) |
| `external_id` | no | Identifier in the originating system — **makes the call idempotent** |
| `description` | no | Free-form description |

Responses:

- **`201 Created`** — a new reservation; the body is the full reservation, including the allocated
  `ip_address`.
- **`200 OK`** — an `external_id` that already exists; the body is the **existing** reservation,
  unchanged (safe to retry).
- **`400 Bad Request`** — no out-of-pool capacity, the MAC is already reserved in that subnet, or
  the payload is invalid. The body is `{"errors": …}`.

```json
{
  "id": 87,
  "url": "https://netbox.example.com/api/plugins/netbox-dhcp-kea-plugin/static-reservations/87/",
  "display": "192.0.2.2/24 → 00:53:00:11:22:33",
  "subnet": { "id": 12, "prefix": "192.0.2.0/24" },
  "ip_address": { "id": 904, "address": "192.0.2.2/24" },
  "mac_address": { "id": 511, "mac_address": "00:53:00:11:22:33" },
  "hostname": "printer-lobby",
  "source": "nac",
  "external_id": "nac-rec-4567"
}
```

!!! tip "Reading back capacity and reservations"
    Use the [GraphQL API](graphql.md) to read a subnet's `available_out_of_pool_count` *before*
    provisioning, and its `static_reservations` afterwards — both in one round-trip.

## REST API endpoints

| Endpoint | Description |
|---|---|
| `/api/plugins/netbox-dhcp-kea-plugin/dhcp-servers/` | DHCP server management |
| `/api/plugins/netbox-dhcp-kea-plugin/dhcp-servers/{id}/kea-config/` | Generate Kea config for a DHCP server |
| `/api/plugins/netbox-dhcp-kea-plugin/vendor-option-spaces/` | Vendor option spaces |
| `/api/plugins/netbox-dhcp-kea-plugin/option-definitions/` | Option definitions |
| `/api/plugins/netbox-dhcp-kea-plugin/option-data/` | Option data / values |
| `/api/plugins/netbox-dhcp-kea-plugin/client-classes/` | Client classifications |
| `/api/plugins/netbox-dhcp-kea-plugin/subnets/` | Subnet configurations |
| `/api/plugins/netbox-dhcp-kea-plugin/subnets/{id}/relay-config/` | Relay config for a subnet |
| `/api/plugins/netbox-dhcp-kea-plugin/subnet-pools/` | Subnet-pool configurations |
| `/api/plugins/netbox-dhcp-kea-plugin/static-reservations/` | Explicit host reservations (CRUD) |
| `/api/plugins/netbox-dhcp-kea-plugin/static-reservations/provision/` | Allocate the next out-of-pool address and reserve it for a MAC |
| `/api/plugins/netbox-dhcp-kea-plugin/ha-relationships/` | HA relationships |
| `/api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=…` | Lookup relay config by prefix |
| `/api/plugins/netbox-dhcp-kea-plugin/stork-servers/` | Stork server management *(if `enable_stork`)* |
| `/api/plugins/netbox-dhcp-kea-plugin/stork-servers/{id}/config/` | Stork server env file *(if `enable_stork`)* |
| `/api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/` | Stork agent group management *(if `enable_stork`)* |
| `/api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/{id}/config/` | Stork agent env file *(if `enable_stork`)* |
| `/api/plugins/netbox_dhcp_kea_plugin/d2-daemons/` | D2 daemon management *(if `enable_ddns`)* |
| `/api/plugins/netbox_dhcp_kea_plugin/d2-daemons/{id}/kea-config/` | Generate `kea-dhcp-ddns.conf` for a D2 daemon *(if `enable_ddns`)* |
| `/api/plugins/netbox_dhcp_kea_plugin/tsig-keys/` | TSIG keys *(if `enable_ddns`)* |
| `/api/plugins/netbox_dhcp_kea_plugin/ddns-domains/` | DDNS domains *(if `enable_ddns`)* |
| `/api/plugins/netbox_dhcp_kea_plugin/ddns-policies/` | DDNS policies *(if `enable_ddns`)* |

!!! note
    Stork API endpoints are only available when `enable_stork: True` in plugin settings; DDNS API endpoints only when `enable_ddns: True`.

## Demo data

The plugin ships a management command to generate demo data for testing:

```bash
# Generate demo data
python manage.py generate_kea_demo_data --force

# Clear and regenerate
python manage.py generate_kea_demo_data --clear --force

# Preview without creating
python manage.py generate_kea_demo_data --dry-run

# Remove all demo data
python manage.py generate_kea_demo_data --purge-demo-data
```

Quantities are configured through `PLUGINS_CONFIG['demo_data']` — see [Configuration — Demo data](configuration.md#demo-data).
