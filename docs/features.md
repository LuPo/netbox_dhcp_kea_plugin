---
title: Features
description: Detailed reference for every model and feature exposed by the plugin.
---

# Features

This page is the reference catalogue of every model and capability the plugin exposes. For task-oriented walkthroughs see [Usage](usage.md); for design-level explanations of specific patterns see the [Guides](guides/index.md).

## Core models

- **DHCP Servers** — ISC Kea DHCP server instances linked to NetBox `IPAddress` objects, with HA peer details and control socket configuration.
- **Vendor Option Spaces** — Vendor-specific option spaces identified by an IANA enterprise number; used for true vendor-encapsulated suboption stacks (option 125 / VIVSO).
- **Option Definitions** — Custom DHCP option definitions (Kea `option-def`).
- **Option Data** — DHCP option values (Kea `option-data`); attachable to servers, client classes, subnets, and subnet pools.
- **Client Classes** — Client classification rules expressed as Kea test expressions.
- **Subnets** — Link NetBox `Prefix` rows to DHCP subnet configurations with pools and options.
- **Subnet Pools** — Pool-level configuration attached to a NetBox `IPRange` inside a subnet, optionally class-restricted with its own option data.
- **HA Relationships** — High-availability groupings of DHCP servers (hot-standby, load-balancing, passive-backup).
- **Stork Servers** — ISC Stork monitoring server instances (optional, gated by `enable_stork`).
- **Stork Agent Groups** — Stork agent configurations linking DHCP servers to a Stork monitoring server.
- **TSIG Keys, D2 Daemons, DDNS Domains, DDNS Policies** — Kea 3.0+ Dynamic DNS modelling (optional, gated by `enable_ddns`).

## High Availability (HA)

- Modes supported: `hot-standby`, `load-balancing`, `passive-backup`.
- Per-server roles: `primary`, `secondary`, `standby`, `backup`.
- HA peer connection is split into discrete fields (address, port, TLS toggle); the full URL is reconstructed automatically for Kea config output.
- Automatic configuration sync from the primary to all HA peers.
- HA-aware config generation guarantees consistent output across peers.
- **Shared HA basic-auth credentials** — one optional user/password pair on the relationship, not on each member. It is written onto every peer entry Kea receives, including each server's own, so every member requires the same secret on its HA listener and presents it when dialling its peers. Leaving it blank keeps the HA channel unauthenticated.
- Protection against orphaned configs — the primary cannot be deleted or demoted while subnets and client classes reference it.
- Easy primary migration when promoting a former secondary.
- UI hides config-management controls on non-primary peers.

## Control sockets

DHCP servers can be configured with Kea control sockets for management access:

- **HTTP control socket** — IP-validated address and port for the HTTP command channel.
- **Unix control socket** — Filesystem path for the Unix domain socket.
- **Dynamic form fields** — Selecting a control-socket type instantly shows or hides the relevant fields (uses the same HTMX pattern as NetBox's 802.1Q VLAN mode selector — no save or page reload required).
- **Validation** — `ha_port` must differ from `ctrl_socket_http_port` when the HTTP control socket is enabled; `ha_address` and `ctrl_socket_http_address` must be valid IP addresses.

The plugin emits Kea 3.0's plural `control-sockets` array (`socket-type: http` with `socket-address` / `socket-port`, and `socket-type: unix` with `socket-name`). The standalone `kea-ctrl-agent` (Control Agent) is **removed in Kea 3.0** — the DHCP daemons open their HTTP / Unix control sockets directly, which is exactly what this block models. You no longer configure a separate CA process.

### Is a control socket necessary?

It depends entirely on what you want Kea to *do*. A control socket is **not** required to serve DHCP. It **is** required for the following:

| Use case | Control socket | Why |
|---|---|---|
| Plain DHCP leasing | Not needed | `kea-dhcp4` / `kea-dhcp6` serve leases with no command channel at all. |
| **High Availability** | Required (HTTP) | HA peers communicate over HTTP. Each peer's `high-availability` config references the other's control-channel URL; lease updates and HA state sync flow through it. Without an HTTP socket, HA cannot form. |
| **Stork monitoring** | Required (Unix or HTTP) | The Stork agent connects to the daemon's control socket to pull config and statistics — a Unix socket is the usual local choice. Without it, Stork sees nothing. |
| **Live management** — `config-reload`, lease commands, statistics via the command API | Required | All command-channel operations go through it. If you only push a full config file and restart the service, you don't need it. |

!!! note "HA port vs. control-socket port"

    In Kea 3.0, HA peers connect to each other's HTTP **control socket** endpoint. Make sure each server's HA peer URL (`ha_url`) points at a reachable HTTP control socket on the partner. The plugin forces `ha_port` and `ctrl_socket_http_port` to differ, which assumes a multi-listener setup — confirm this matches how your peers actually reach one another.

D2 daemons have their own separate control socket (`control_socket_path`) — see [Dynamic DNS (DDNS)](#dynamic-dns-ddns).

## Reservation modes

Kea's reservation-mode flags are supported at both the **server** (global) and **subnet** (per-subnet) level, following Kea's native inheritance model.

### Server-level defaults

Every DHCP server has three reservation-mode flags that surface in the `Dhcp4` global block:

| Flag | Default | Meaning |
|---|---|---|
| `reservations-global` | `False` | Look for host reservations in the global scope. |
| `reservations-in-subnet` | `True` | Look for host reservations within each subnet. |
| `reservations-out-of-pool` | `True` | Exclude reserved addresses from dynamic pool allocation. |

Defaults are configurable through `PLUGINS_CONFIG` — see [Configuration — Model defaults](configuration.md#model-defaults).

### `reservations-in-subnet`

Controls whether Kea looks for **subnet-scoped** host reservations (reservations attached to a
specific subnet) when servicing a request. Left at its default of `True`, the plugin emits each
subnet's reservations inside that subnet's config block. Those reservations are discovered
automatically from NetBox — IP addresses assigned to device/VM interfaces and flagged Primary or
OOB (see [DHCP reservations](#dhcp-reservations)) — and, where configured, from explicit
host-reservation records. Set it to `False` only if a subnet should ignore subnet-level
reservations entirely (e.g. a pure dynamic subnet, or one relying solely on global reservations).

### `reservations-out-of-pool`

This is a **performance** switch, not a placement rule. It tells Kea where reservations live
relative to the dynamic pools:

- **`True` (plugin default)** — every reservation is guaranteed to be **outside** the dynamic
  pools, so Kea can skip the per-lease "is this pool address reserved for someone else?" check.
  On busy subnets this measurably reduces lease-time work.
- **`False`** — reservations **may sit inside** a pool, so Kea must check each in-pool lease
  against the reservation list before handing it out.

The plugin's reservations are **out-of-pool by construction**: infrastructure addresses come from
device/VM Primary/OOB IPs (which live outside the dynamic ranges), and explicit
host-reservation addresses are taken from the prefix's out-of-pool space. Keeping
`reservations-out-of-pool=True` therefore matches how the plugin models addressing and is the
recommended default. Only flip a subnet to `False` if you deliberately intend to reserve an
address that falls **inside** one of its dynamic pools.

!!! note "How the plugin keeps reservations out-of-pool"

    With `reservations-out-of-pool=True` (the default) the plugin actively keeps explicit
    reservations outside the dynamic pools:

    - the [provisioning endpoint](#allocate-and-reserve-provisioning) only ever allocates from the
      subnet's out-of-pool space (available addresses minus the dynamic pool ranges); and
    - a **manually-entered** Static Reservation whose address falls **inside a dynamic pool range
      is rejected** at validation time.

    Only *fixed* IP-Range pools can clash this way — when a subnet has no explicit IP Range, its
    computed pool is derived from the prefix's available space and automatically excludes every
    assigned (reserved) address. If a subnet sets `reservations-out-of-pool=False` to deliberately
    place an in-pool reservation, that validation steps aside and the in-pool address is accepted.

### Subnet-level overrides

Each subnet can inherit the server defaults or override them:

- **Inherit from server** *(default)* — The flag is omitted from the subnet config and Kea inherits from `Dhcp4`.
- **Yes / No** — Explicit override emitted in the subnet config.

Subnets also expose a `reservations_only` flag (not a Kea global) that disables dynamic pool generation entirely — only reserved hosts receive an IP.

### Global vs. subnet reservation placement

When `reservations-global` is effective for a subnet (either set explicitly or inherited from the server):

- Reservations are placed in the `Dhcp4.reservations` array **without** `ip-address` (only `hw-address` + `hostname`).
- The subnet's own `reservations` key is omitted.

When `reservations-global` is not active, reservations sit at the subnet level with full `ip-address`, `hw-address`, and `hostname`.

## Option data validation & IP source linking

### Type-based validation

Option Data values are validated against the option definition's type when CSV format is used:

- **IP addresses** — `ipv4-address`, `ipv6-address`, `ipv6-prefix` checked as proper addresses or prefixes.
- **Integers** — `uint8` / `uint16` / `uint32` / `int8` / `int16` / `int32` range-checked.
- **Booleans** — must be `true`, `false`, `0`, or `1`.
- **FQDN** — validated as a proper domain name.
- **Arrays** — definitions flagged `is_array=True` accept comma-separated values; single-value definitions reject multiples.

### IP source linking

For IP-typed options (e.g. `routers`, `ntp-servers`), you can link to NetBox objects instead of typing IPs into the Data field:

- **IPAM IP addresses** — link to NetBox IPAM `IPAddress` rows.
- **DNS A / AAAA records** — link to `netbox-plugin-dns` `Record` rows (requires `enable_netbox_dns: True`).
- **DNS CNAME records** — link to CNAME records; the chain is followed to target A records at config-generation time.

When IP sources are linked:

- The Data field is hidden in the form.
- IPs are resolved from the linked objects at Kea config-generation time.
- Changes to the linked address propagate automatically (no Django signals — the relationship is read at render time).
- Array-type options support multiple sources ordered by `ordinal`.
- If every linked source is deleted, the option falls back to the manual Data field.

Enable netbox-dns integration:

```python
PLUGINS_CONFIG = {
    "netbox_dhcp_kea_plugin": {
        "enable_netbox_dns": True,
    },
}
```

## DHCP reservations

A subnet's Kea host reservations come from two sources that are **merged** at config-emission time: reservations **auto-derived** from NetBox infrastructure, and **explicit Static Reservations** you (or an automation tool) create. The merged set is keyed by IP address — an explicit reservation **wins** over a derived one on the same address — and is emitted **ordered by IP**.

### Auto-derived reservations

The plugin auto-discovers reservations from NetBox IP address assignments:

- **Auto-discovery** — IP addresses assigned to device or VM interfaces and flagged as Primary IP or OOB IP are collected as Kea host reservations.
- **MAC address validation** — Only reservations carrying a `hw-address` (MAC on the interface) are included in the emitted Kea configuration. Kea requires either `hw-address` or `duid` on every reservation and will refuse to load any reservation where neither is set.
- **UI warnings** — The reservations tab highlights entries without a MAC in yellow with an explanatory note (they will be excluded from the generated config).
- **FHRP filtering** — FHRP group addresses are automatically excluded.
- **Per-subnet toggle** — the subnet's **Auto Reservations** flag (default **on**) controls whether derived reservations are merged in. Turn it off to emit *only* the subnet's explicit Static Reservations.

### Static reservations

`StaticReservation` is an explicit host reservation that pairs a native NetBox **IP address** with a native **MAC address** — no Device or VM modelling required. This suits endpoints known only by their MAC, such as records fed from a network access control (NAC) system.

- **Native objects** — `ip_address` references an `ipam.IPAddress`, `mac_address` a `dcim.MACAddress` (which may be a standalone MAC with no interface assignment). The reserved IP must fall within the subnet's prefix.
- **One MAC per subnet** — a database constraint plus validation prevent two reservations sharing the same MAC within a subnet (Kea rejects duplicate `hw-address` entries).
- **Hostname** — an optional per-reservation `hostname`; when blank it falls back to the IP's DNS name. Emitted as the Kea `hostname`.
- **Sync metadata** — `source` (a free-form origin tag, e.g. `nac`), `external_id` (the record's identifier in the originating system — globally unique), and `last_synced` support keeping reservations in step with an external source of truth.
- **In the UI** — managed under **DHCP Configuration → Static Reservations**, and surfaced (with a **Static** badge) alongside derived entries in each subnet's **Reservations** tab. The subnet form's IP-address picker is scoped to the selected subnet's prefix.

### Allocate-and-reserve provisioning

When the automation does *not* pick the address itself — it just needs *an* address for a MAC — the plugin exposes an atomic provisioning endpoint. Given a subnet and a MAC, NetBox allocates the next available **out-of-pool** address and creates the reservation in a single transaction:

- **Server-side allocation** — the lowest available out-of-pool address (per the subnet's effective `reservations-out-of-pool` policy — see [Reservation modes](#reservation-modes)) is chosen and created as an `IPAddress`; the **gateway** (`routers_option_offset`) is never handed out.
- **Concurrency-safe** — the subnet's prefix row is locked for the duration, so two simultaneous callers can never receive the same address.
- **Idempotent** — pass an `external_id` and a retry returns the *existing* reservation (HTTP `200`) instead of allocating again (`201`), so a sync source can replay safely.
- **Capacity-aware** — when the subnet has no out-of-pool room (e.g. `reservations-out-of-pool = True` with no dedicated pool range), the call is rejected rather than encroaching on the dynamic pool.

See [Usage — Static reservation provisioning](usage.md#static-reservation-provisioning) for the API call, and the [GraphQL API](graphql.md) to read reservations and each subnet's remaining free-address count in one request.

## DHCP relay support

The plugin surfaces DHCP relay target information so it can be consumed by Layer 3 network device configuration (the classic `ip helper-address` line).

- **Integrated with the Prefix API** — query `/api/ipam/prefixes/{id}/` to receive relay targets inline.
- **Dedicated lookup endpoint** — query by prefix CIDR with VRF support.
- **HA-aware** — returns all server IPs in an HA relationship so redundant helpers can be configured downstream.

See [Usage — Relay configuration](usage.md#relay-configuration) for the API examples and vendor snippets.

## Stork monitoring integration

When [`enable_stork: True`](configuration.md#core-settings) (the default):

- Full management of ISC Stork server and agent group configurations from NetBox.
- Generates environment files suitable for `/etc/stork/server.env` and `/etc/stork/agent.env`.
- Configurable log levels (`DEBUG`, `INFO`, `WARN`, `ERROR`) on server and agent.
- Prometheus exporter settings per agent group: bind address, port, per-subnet statistics toggle.
- TLS and authentication options for Stork server connections.
- All `text/plain` config endpoints are Ansible-friendly via `ansible.builtin.uri` — see [Usage — Stork configuration](usage.md#stork-configuration).

To disable Stork entirely, set `enable_stork: False` in `PLUGINS_CONFIG`.

## Dynamic DNS (DDNS)

Optional Kea 3.0+ DDNS support — models the `kea-dhcp-ddns` (D2) configuration surface and the `ddns-*` policy knobs `kea-dhcp4`/`kea-dhcp6` render at server / subnet / client-class scope.

Gated by `enable_ddns: True` and requires `enable_netbox_dns: True` (zones and nameservers are sourced from `netbox-plugin-dns`; TSIG keys are plugin-local).

### Models

- **`TSIGKey`** — RFC 2845 keys with algorithm choices (`HMAC-MD5` / `SHA1` / `SHA224` / `SHA256` / `SHA384` / `SHA512`), optional digest-bits truncation, and a pluggable `secret_backend` registry (`plaintext` shipped; `vault` reserved). Secret values are auto-generated on save when input is empty or not algorithm-length base64 — paste `tsig-keygen` output verbatim or save and let the plugin mint one. Plaintext reveal is gated by the `view_secret_tsigkey` permission.
- **`D2Daemon`** — one row per logical D2 service. `listener_mode` chooses between **local** (renders `127.0.0.1`; deploy one D2 instance per peer for HA-pair DDNS redundancy) and **remote** (single shared instance pinned to an IPAM record). Each daemon exposes a `/api/plugins/netbox_dhcp_kea_plugin/d2-daemons/<id>/kea-config/` endpoint that emits a complete `kea-dhcp-ddns.conf`.
- **`DDNSDomain`** — binds a `D2Daemon` to a `netbox_dns.Zone`. Forward / reverse direction is derived from the zone name at emission time. Authoritative nameserver IPs are resolved from the zone's `NameServer` rows (A / AAAA / CNAME chain). The create form is multi-zone — pick any combination of forward and reverse zones in one shot.
- **`DDNSPolicy`** — reusable `ddns-*` override group attachable at server / subnet / client-class scope (`ddns-send-updates`, `ddns-override-no-update`, `ddns-replace-client-name`, `ddns-generated-prefix` / `-qualifying-suffix`, `hostname-char-set` / `-replacement`, conflict-resolution mode, TTL knobs). All fields nullable — only the keys you set are emitted, kebab-cased.

### HA-pair precedence

When a `DHCPServer` belongs to an HA relationship and the relationship has its own `d2_daemon` or `ddns_policy` set, the relationship's value wins (peers must agree on the D2 target and the policy knobs). Sender IP and port stay per-server because the local source endpoint is always per-host. The DHCPServer detail page surfaces the effective values with an "inherited from HA relationship" badge.

### Local-D2 redundancy (recommended for HA)

Set `listener_mode: local` on the `D2Daemon` shared by an HA pair, then deploy `kea-dhcp-ddns` on every peer host with the same rendered config. Each peer's `kea-dhcp4` posts NCRs to its own `127.0.0.1:53001`. If the active peer reboots, the standby's local D2 takes over with zero DDNS gap.

### Kea config emission rules

No Python-side merging of override hierarchies. Each non-null `DDNSPolicy.to_kea_overrides()` is emitted verbatim at the JSON level the policy is attached to:

- server-level → `Dhcp4` / `Dhcp6` root
- subnet-level → subnet dict
- class-level → client-class dict

Kea resolves the precedence chain itself when processing packets.

### Bulk edit + quick-add

- `DDNSDomain` has a bulk-edit form for setting `d2_daemon` / `tsig_key` on many rows at once.
- The `tsig_key` field on the DDNS Domain form carries a `+` quick-add button so a new key can be created inline without leaving the form.

## NetBox integration

- DHCP configuration tab on Prefix detail pages.
- Direct integration with NetBox's Prefix API (adds the `dhcp_config` field).
- Full REST API surface for every model.
- Tag support on every model.
- Change logging and audit trail.
- Bulk import / export through NetBox's standard CSV machinery.
