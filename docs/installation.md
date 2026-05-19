---
title: Installation
description: Install the plugin into a NetBox deployment.
---

# Installation

## Compatibility

| NetBox Version | Plugin Version |
|----------------|----------------|
| 4.5            | 0.8.x          |

## Install

### With pip

```bash
pip install git+https://github.com/LuPo/netbox-dhcp-kea-plugin
```

### With netbox-docker

Add the package to your `plugin_requirements.txt`:

```text
git+https://github.com/LuPo/netbox-dhcp-kea-plugin
```

See the [netbox-docker plugin instructions](https://github.com/netbox-community/netbox-docker/wiki/Using-Netbox-Plugins) for the full procedure.

## Enable the plugin

Add the package to `PLUGINS` in your NetBox configuration (`configuration.py` for bare-metal installs or `plugins.py` for netbox-docker):

```python
PLUGINS = [
    "netbox_dhcp_kea_plugin",
]
```

## Run migrations

```bash
python manage.py migrate
```

## Configure

Plugin behaviour is controlled through `PLUGINS_CONFIG`. See **[Configuration](configuration.md)** for the complete list of settings, defaults, and per-feature toggles (Stork, netbox-dns linking, DDNS, model defaults, demo data).
