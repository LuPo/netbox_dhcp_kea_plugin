---
title: Configuration
description: PLUGINS_CONFIG reference — every setting, default value, and per-feature toggle.
---

# Configuration

All plugin behaviour is controlled through `PLUGINS_CONFIG` in your NetBox configuration:

```python
PLUGINS_CONFIG = {
    "netbox_dhcp_kea_plugin": {
        "top_level_menu": True,
        "menu_name": "DHCP KEA",
        "enable_stork": True,
        "enable_netbox_dns": False,
        "enable_ddns": False,
    },
}
```

Every setting is optional; omitted keys fall back to their default.

## Core settings

| Setting | Default | Description |
|---|---|---|
| `top_level_menu` | `True` | Display the plugin as a top-level menu in NetBox's navigation rather than nested under "Plugins". |
| `menu_name` | `"DHCP KEA"` | Label used for the plugin menu. |
| `enable_stork` | `True` | Toggle ISC Stork monitoring integration. When `False`, all Stork-related menu entries, form fields, filters, API endpoints, and UI affordances are hidden. |
| `enable_netbox_dns` | `False` | Toggle linking of DNS A / AAAA / CNAME records (from [`netbox-plugin-dns`](https://github.com/peteeckel/netbox-plugin-dns)) as IP sources on `OptionData`. Required for `enable_ddns`. |
| `enable_ddns` | `False` | Toggle the optional Kea 3.0+ Dynamic DNS subsystem (D2 daemons, TSIG keys, DDNS domains, DDNS policies). Requires `enable_netbox_dns: True`. |
| `ddns_secret_backend` | `"plaintext"` | Backend identifier consulted by `TSIGKey.get_secret()`. Only `"plaintext"` is shipped today; `"vault"` is reserved. |
| `d2_default_control_socket_path` | `"/tmp/kea-dhcp-ddns-ctrl.sock"` | Pre-fills the control socket field on new `D2Daemon` rows. |
| `model_defaults` | *(see below)* | Per-model default values, including reservation modes and lease lifetimes. |

## Model defaults

Default values for new `DHCPServer` and `Subnet` rows can be overridden:

```python
PLUGINS_CONFIG = {
    "netbox_dhcp_kea_plugin": {
        "model_defaults": {
            "Subnet": {
                "valid_lifetime": 3600,
                "max_lifetime": 7200,
                "reservations_global": False,
                "reservations_in_subnet": True,
                "reservations_out_of_pool": True,
                "reservations_only": False,
            },
        },
    },
}
```

The `reservations_*` keys under `model_defaults.Subnet` control the **server-level defaults** applied to new DHCP servers. Individual subnets inherit from their server and may override per-subnet — see [Features — Reservation modes](features.md#reservation-modes) for the inheritance rules.

## Disabling optional features

To turn off Stork integration entirely:

```python
PLUGINS_CONFIG = {
    "netbox_dhcp_kea_plugin": {
        "enable_stork": False,
    },
}
```

When a feature flag is off, the corresponding nav entries, URL patterns, API routes, form fields, and serializer fields are all suppressed. The underlying database tables remain in place but are unused; flipping the flag back on restores access.

## Demo data

The plugin ships a `generate_kea_demo_data` management command that populates a fresh install with realistic example objects. Configure the data quantities through `PLUGINS_CONFIG`:

```python
PLUGINS_CONFIG = {
    "netbox_dhcp_kea_plugin": {
        "demo_data": {
            "enabled": True,            # Required unless using --force on the CLI
            "vendor_option_spaces": 3,
            "option_definitions_per_space": 5,
            "option_data": 10,
            "client_classes": 5,
            "dhcp_servers": 3,
            "ha_relationships": 1,
            "subnets": 5,
        },
    },
}
```

See [Usage — Demo data](usage.md#demo-data) for the CLI invocation.
