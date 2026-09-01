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

#### The `ha_proxy` plan

`ha_proxy` is a read-only field on the `DHCPServer` serializer. It is the contract the deployment builds Envoy's configuration from — both the Kea configuration and the proxy configuration derive from it, so the two cannot disagree. When the relationship does not enable the proxy it is exactly `{"enabled": false}`.

```json
{
  "enabled": true,
  "public_address": "10.0.0.1",
  "public_port": 8080,
  "internal_address": "127.0.0.1",
  "internal_port": 8080,
  "ctrl_port": 8000,
  "peers": [
    {
      "name": "kea-b",
      "egress_port": 18080,
      "upstream_address": "10.0.0.2",
      "upstream_port": 8080,
      "fqdn": "kea-b.pki.example.net",
      "sni": "kea-b.pki.example.net"
    }
  ]
}
```

| Key | Meaning |
|---|---|
| `enabled` | Whether this host runs the proxy. Inherited from the relationship; the whole dict is `{"enabled": false}` when off. |
| `public_address` / `public_port` | Where Envoy binds for inbound HA traffic — the member's own `ha_address` / `ha_port`. |
| `internal_address` / `internal_port` | Where Kea's own HA listener binds. Always loopback, on the same port. |
| `ctrl_port` | The HTTP control-socket port to publish, or `null` when the control-socket proxy is off. |
| `exporter_port` | The Stork agent's Prometheus exporter port to publish, or `null` when `stork_proxy_enabled` is off. The exporter itself moves to `127.0.0.1` so the proxy can bind the public address on that port. |
| `peers[].name` | The peer `DHCPServer`'s name. |
| `peers[].egress_port` | Loopback port Kea dials to reach that peer; base port plus an index over peers **ordered by name**, so it does not move when a server is added. |
| `peers[].upstream_address` / `upstream_port` | The peer's public endpoint, for reference. Envoy dials `fqdn`. |
| `peers[].fqdn` | The peer's PKI identity — the egress cluster address, and the exact SAN to accept. |
| `peers[].sni` | The TLS SNI to send. Identical to `fqdn`; it is **never** an address. |

`peers` lists only the *other* members of this server's relationship, which is what scopes a cluster: an Envoy built from this plan accepts exactly those names and no others.

### PKI identity (`pki_fqdn`)

When the reverse proxy is enabled, each Envoy verifies its peers by pinning the **exact** subject alternative name it will accept. `pki_fqdn` on `DHCPServer` is that name, and the same string is used three ways: the egress cluster address Envoy dials, the TLS SNI it sends, and the SAN matcher it accepts. It must therefore match the certificate byte for byte.

| Field | Type | Default | Description |
|---|---|---|---|
| `pki_fqdn` | string | `""` | The host's DNS name in the internal PKI — certificate CN, pinned SAN, and TLS SNI. |

It is published per peer in the `ha_proxy` plan as `peers[].fqdn` (and as `peers[].sni`), which is what the deployment builds Envoy's configuration from.

**It must be a DNS name, never an address.** TLS SNI cannot carry an IP address at all ([RFC 6066](https://www.rfc-editor.org/rfc/rfc6066)), so a certificate can never match one; `clean()` rejects a `pki_fqdn` that parses as IPv4 or IPv6. A server in a relationship with the proxy enabled must have one, and saving without it fails rather than rendering a configuration that cannot complete a handshake.

**Normalisation.** The value is stored lower-case with any trailing dot stripped, on every path in — the form, the API, an import. A DNS record's absolute `kea-a01.example.net.` and a typed `Kea-A01.Example.NET` therefore produce one pin, not two that differ by a dot or by case.

**Bound to a DNS record, when the DNS plugin is present.** With [netbox-plugin-dns](https://github.com/peteeckel/netbox-plugin-dns) installed and `enable_netbox_dns` on, the server form shows a **PKI DNS record** picker (unmanaged `A` / `AAAA` / `CNAME` records) *instead of* the text field, and the chosen record is recorded in `pki_record_id`. That binding is enforced:

| Action | Result |
|---|---|
| Delete a bound DNS record | **Refused** — the error names the servers using it. A certificate pinned to a name nothing serves would fail, and PKI onboarding refuses names that do not resolve. |
| Delete the DHCP server | The bound record is deleted with it, unless another server is bound to the same one. |
| Rename the bound record | `pki_fqdn` is re-derived, so the published pin cannot drift from the certificate. |

The binding is a soft reference rather than a database foreign key, because a real FK would make netbox-plugin-dns mandatory for every installation. The integrity above is supplied by signals that are only connected when the DNS plugin is importable.

!!! tip "Without netbox-plugin-dns"

    The plugin stays fully usable: the form shows `pki_fqdn` as a plain text field and the stored string is authoritative. Nothing is bound, so nothing is protected or cascaded — a typed name is just a name.

!!! note "Restricting to your issuable zones"

    The optional `pki_allowed_zone_suffixes` plugin setting lists the zones your CA will issue certificates for. It is **empty by default**, which turns the restriction off entirely. Once you set it:

    - The **record picker only offers records in those zones**, so you cannot pick a name that would then be refused. If no zone matches, the picker is empty rather than full of unusable choices.
    - A `pki_fqdn` outside them is **rejected at save time**, with an error naming the zones and pointing at the setting. That covers the API, imports and scripts, which have no picker.

    Adding a zone to your CA means adding it here too.

The server detail page shows the **PKI FQDN**, linked to its DNS record when one is bound. With the DNS integration on, a name that is *not* bound is shown as plain text with an **unbound** marker — the form binds every name it sets, so an unbound one arrived by another route (the API, an import, or before the integration was enabled). Without the integration every name is unbound, so no marker is shown. It also shows a **warning banner** when the identity has no matching unmanaged DNS record in NetBox, or when that record is not active. That one is advisory and never blocks a save: netbox-plugin-dns is optional, and the record may legitimately live in DNS that NetBox does not manage.

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

### Stork agent endpoint

`STORK_AGENT_SERVER_URL` in the generated agent env is built from an explicit choice, not a preference order, because getting it wrong fails registration outright — **the Stork agent has no skip-verification option for registration**, only for its connection to Kea.

| Field | Meaning |
|---|---|
| `endpoint_type` | `dns` (default) or `ip` — how agents address this server. |
| `endpoint_record_id` | The netbox-plugin-dns record the name is bound to, when that plugin is installed. |
| `endpoint_fqdn` | The name agents dial. Derived from the bound record; normalised lower-case with any trailing dot stripped. |

With `endpoint_type: dns` the name is taken from the bound record, falling back to the `dns_name` on the IPAM address. That fallback keeps existing deployments working, but it is deliberately the *second* choice: IPAM's `dns_name` records the **host**, which is not necessarily the **service** name the certificate was issued for. Preferring it silently is how a URL that looks correct fails verification.

Saving with `endpoint_type: dns` and no name available anywhere is rejected — there would be nothing to render.

!!! warning "TLS over an IP address"

    Choosing `endpoint_type: ip` with `use_tls` is allowed but flagged on the detail page. Agents cannot verify the certificate unless it carries an IP subject alternative name, which most internal CAs will not issue. It is permitted rather than blocked because such a certificate is possible, if unusual.

The endpoint name and the certificate on the Stork listener are **one decision, not two**. Server trust has exactly two real answers, and neither is a skip flag: the endpoint name must match a SAN on the certificate, and the agent host must trust the issuing CA.

!!! note "`skip_tls_cert_verification` is about Kea, not the server"

    That field on the agent group renders `STORK_AGENT_SKIP_TLS_CERT_VERIFICATION`, which governs the agent's connection to **Kea's control API**. It has no effect on registration with the Stork server. It appears under its own *Kea Connection* heading for that reason.

## Declines and pool starvation

A client that sends `DHCPDECLINE` puts the address into probation, and Kea's default
`decline-probation-period` is **86400 seconds** — a full day per declined address. A
client stuck in a decline loop therefore walks a pool: the declined lease is gone, so its
next `DHCPDISCOVER` is answered with a *fresh* address, and so on.

### Lease timers

`valid-lifetime`, `renew-timer` (T1) and `rebind-timer` (T2) can be set at **three** levels,
and Kea resolves them in this order: **client class → subnet → global**. All three are
modelled:

| Level | Fields |
|---|---|
| `DHCPServer` (global) | `valid_lifetime` (default 3600), `max_valid_lifetime` (7200), `renew_timer`, `rebind_timer` |
| `Subnet` | `valid_lifetime`, `max_lifetime`, `renew_timer`, `rebind_timer` |
| `ClientClass` | `valid_lifetime`, `renew_timer`, `rebind_timer` — needs Kea 1.9.5+ |

The timers are optional at every level; left blank, nothing is emitted and the client picks
its own T1/T2 from the lease time.

!!! warning "Set the parameters, not the options"

    Kea *generates* the wire options from these values — option 51 from `valid-lifetime`,
    58 from `renew-timer`, 59 from `rebind-timer` — and applies conditions when doing so: it
    sends option 59 only when `rebind-timer` is below `valid-lifetime`, and option 58 only
    when `renew-timer` is below `rebind-timer`. Misordered values are **not** an error in
    Kea; the options are simply not sent, so the configuration looks right and does nothing.
    This plugin rejects that ordering at save time instead.

    For the same reason the option definitions shipped here deliberately exclude codes
    **50, 51, 53, 55, 58, 59** and **61** — the protocol machinery. They cannot be set as
    option data, and should not be.

### `decline_probation_period` on DHCPServer

Global only — `decline-probation-period` appears in Kea's `GLOBAL4_PARAMETERS` and in
neither `SUBNET4_PARAMETERS` nor `SHARED_NETWORK4_PARAMETERS`, which is why it lives on the
server rather than the subnet alongside `valid_lifetime`. It has no wire option at all; it
is purely server-side behaviour. Leave it blank to omit the key
and take Kea's default; set it to shorten the window. `0` is a legitimate value meaning
"return the address immediately", and is emitted as such rather than treated as blank.

Shortening probation bounds how long a declined address is unusable. It does **not** bound
the walk — see below.

### `user_context` on ClientClass and Subnet

A free-form JSON object emitted as Kea's `user-context`. Hook libraries read their
configuration from it; `libdhcp_limits.so` takes its limits from here:

```json
{"limits": {"rate-limit": "10 packets per second"}}
```

It must be a JSON **object** — Kea reads it as a map and refuses to start otherwise, so a
list or scalar is rejected at save time instead.

!!! tip "Rate-limiting declines is ISC's own recommendation"

    ISC's [Limiting DHCP DECLINE](https://kb.isc.org/docs/limiting-dhcp-decline) describes
    exactly this: a client class that matches DECLINE messages, plus the limits hook, to stop
    "any single client (MAC address) from declining more than three IP addresses per hour".
    Combine it with `template_test` so the class spawns one subclass per MAC and the budget
    is per client rather than shared:

    ```
    test expression:  ifelse(pkt4.msgtype == 4, hexstring(pkt4.mac, ':'), '')
    template class:   yes
    user context:     {"limits": {"rate-limit": "3 packets per hour"}}
    ```

    ISC pairs it with a shorter probation: the 24-hour default is "excessive for public
    networks", where "values well under an hour are often appropriate".

### `template_test` on ClientClass

Renders the test expression as `template-test` instead of `test`. Kea evaluates it per
packet and spawns a subclass named `SPAWN_<class>_<value>` for each distinct result — one
class definition yielding one class per client. Both the template name and the spawned name
are associated with the packet, so a subnet or pool may restrict on either: the template
name matches any client the expression yields a value for, a spawned name matches one
specific value.

### What actually bounds the walk

Neither of the above stops one device eating a pool. Two existing features do:

- **Contain the offenders.** Restrict a small, dedicated pool to a client class matching
  the misbehaving device types (by MAC OUI or vendor class) using a subnet pool's
  **client class**. A device that declines in a loop then exhausts that pool, not the whole
  subnet.
- **Pin them.** A static reservation makes a looping client re-offered the *same* address
  every time, so the loop costs one address instead of a pool.

`libdhcp_ping_check.so` is in the hook catalogue and configurable through a hook's
parameters, but temper expectations: it helps when an address is genuinely occupied, and
declines from dual-homed hosts answering ARP for their own other interface are false
conflicts that a ping check will not see.

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
