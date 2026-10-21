---
title: Installation
description: Install the plugin into a NetBox deployment.
---

# Installation

## Compatibility

| NetBox | Plugin           | netbox-plugin-dns |
|--------|------------------|-------------------|
| 4.7    | 0.10.3 and later | 1.7               |
| 4.6    | 0.9.0 and later  | 1.6               |
| 4.5    | 0.8.x            | 1.5               |

[netbox-plugin-dns](https://github.com/peteeckel/netbox-plugin-dns) is required since 0.8.0: the DDNS models reference its zones, and a migration depends on it, so NetBox neither starts nor migrates without it. Install the release that matches your NetBox version from the table. Its integration features stay off until you turn them on; see `enable_netbox_dns` in [Configuration](configuration.md).

## Install

### With pip

```bash
pip install netbox-dhcp-kea-plugin "netbox-plugin-dns~=1.7.0"
```

On NetBox 4.6, use `netbox-plugin-dns~=1.6.0`. To run the unreleased state of `main`, install the plugin with `pip install git+https://github.com/LuPo/netbox_dhcp_kea_plugin` instead.

### With netbox-docker

Add both packages to your `plugin_requirements.txt`:

```text
netbox-dhcp-kea-plugin
netbox-plugin-dns~=1.7.0
```

See the [netbox-docker plugin instructions](https://github.com/netbox-community/netbox-docker/wiki/Using-Netbox-Plugins) for the full procedure.

## Enable the plugin

Add both plugins to `PLUGINS` in your NetBox configuration (`configuration.py` for bare-metal installs or `plugins.py` for netbox-docker):

```python
PLUGINS = [
    "netbox_dns",
    "netbox_dhcp_kea_plugin",
]
```

## Run migrations

```bash
python manage.py migrate
```

## Configure

Plugin behaviour is controlled through `PLUGINS_CONFIG`. See **[Configuration](configuration.md)** for the complete list of settings, defaults, and per-feature toggles (Stork, netbox-dns linking, DDNS, model defaults, demo data).
