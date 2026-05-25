---
title: Usage
description: Task-oriented walkthroughs — quick start, relay configuration, Kea config generation, Stork env files, demo data.
---

# Usage

## Quick start

1. **Create DHCP servers** — Navigate to *DHCP KEA → DHCP Servers* and add your Kea server instances.
2. **Configure HA** *(optional)* — Set up HA relationships, assign server roles, and configure HA peer address / port / TLS.
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
