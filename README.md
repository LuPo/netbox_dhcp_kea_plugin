# NetBox DHCP-KEA Plugin

A NetBox plugin for managing ISC KEA DHCP server configurations. This plugin provides models and interfaces to manage DHCP servers, options, client classifications, and links them to NetBox Prefixes.

* Free software: GPL-3.0-only
* Documentation: https://LuPo.github.io/netbox-dhcp-kea-plugin/


## Features

This plugin provides comprehensive management of ISC KEA DHCP server configurations:

### Core Models

- **DHCP Servers**: Manage ISC KEA DHCP server instances with IP addresses and ports
- **DHCP Options**: Define DHCP options (DHCPv4/DHCPv6) with codes and values
- **Client Classes**: Configure client classification rules with test expressions
- **Prefix DHCP Config**: Link NetBox Prefixes to DHCP configurations
- **HA Relationships**: Configure High Availability relationships between DHCP servers
- **HA Peers**: Define server roles (primary, secondary, standby, backup) within HA clusters

### Key Capabilities

- Associate DHCP configurations with NetBox native Prefixes
- Define DHCP pools with lease lifetimes
- Assign DHCP options to prefixes and client classes
- Client classification support with KEA test expressions
- Prefix detail page integration showing DHCP information
- Full REST API support for all models
- Tag support on all models
- Change logging and audit trail

### High Availability (HA) Support

- Configure HA relationships with multiple modes: hot-standby, load-balancing, passive-backup
- Define server roles within HA clusters (primary, secondary, standby, backup)
- Automatic configuration sync from primary to all HA peers
- HA-aware KEA config generation ensures consistent configurations across all peers
- Protection against orphaned configs (cannot delete/demote primary with existing configs)
- Easy config migration when switching primary servers
- UI intelligently hides config management options for non-primary servers

### Integration with NetBox

The plugin injects DHCP configuration information directly into NetBox Prefix detail pages, displaying:
- Associated DHCP server
- Pool configuration
- Lease lifetimes
- Applied DHCP options
- Client class assignments

## Compatibility

| NetBox Version | Plugin Version |
|----------------|----------------|
|     4.0        |      0.2.0     |
|     4.0        |      0.1.0     |

## Installing

For adding to a NetBox Docker setup see
[the general instructions for using netbox-docker with plugins](https://github.com/netbox-community/netbox-docker/wiki/Using-Netbox-Plugins).

While this is still in development and not yet on pypi you can install with pip:

```bash
pip install git+https://github.com/LuPo/netbox-dhcp-kea-plugin
```

or by adding to your `local_requirements.txt` or `plugin_requirements.txt` (netbox-docker):

```bash
git+https://github.com/LuPo/netbox-dhcp-kea-plugin
```

Enable the plugin in `/opt/netbox/netbox/netbox/configuration.py`,
 or if you use netbox-docker, your `/configuration/plugins.py` file :

```python
PLUGINS = [
    'netbox_dhcp_kea_plugin'
]

PLUGINS_CONFIG = {
    "netbox_dhcp_kea_plugin": {},
}
```

After enabling the plugin, run migrations:

```bash
python manage.py migrate
```

## Usage

### Creating DHCP Infrastructure

1. **Add DHCP Servers**: Navigate to Plugins > DHCP Servers and create your KEA server entries
2. **Define DHCP Options**: Create reusable DHCP options (e.g., DNS servers, domain names)
3. **Create Client Classes**: Set up client classification rules with KEA test expressions
4. **Configure Prefixes**: Link your NetBox Prefixes to DHCP servers with specific configurations

### API Endpoints

The plugin provides REST API endpoints for all models:

- `/api/plugins/netbox-dhcp-kea-plugin/dhcp-servers/`
- `/api/plugins/netbox-dhcp-kea-plugin/dhcp-options/`
- `/api/plugins/netbox-dhcp-kea-plugin/client-classes/`
- `/api/plugins/netbox-dhcp-kea-plugin/prefix-dhcp-configs/`
- `/api/plugins/netbox-dhcp-kea-plugin/dhcp-ha-relationships/`
- `/api/plugins/netbox-dhcp-kea-plugin/dhcp-ha-peers/`

### Example: Creating a DHCP Configuration

```python
from netbox_dhcp_kea_plugin.models import DHCPServer, DHCPOption, PrefixDHCPConfig
from ipam.models import Prefix

# Create DHCP server
server = DHCPServer.objects.create(
    name="dhcp-server-01",
    ip_address="192.168.1.10",
    port=67,
    is_active=True
)

# Create DHCP options
dns_option = DHCPOption.objects.create(
    name="domain-name-servers",
    code=6,
    option_space="dhcp4",
    value="8.8.8.8, 8.8.4.4"
)

# Link to a prefix
prefix = Prefix.objects.get(prefix="192.168.100.0/24")
config = PrefixDHCPConfig.objects.create(
    prefix=prefix,
    server=server,
    is_pool=True,
    valid_lifetime=3600,
    max_lifetime=7200
)
config.options.add(dns_option)
```

## Credits

Based on the NetBox plugin tutorial:

- [demo repository](https://github.com/netbox-community/netbox-plugin-demo)
- [tutorial](https://github.com/netbox-community/netbox-plugin-tutorial)

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [`netbox-community/cookiecutter-netbox-plugin`](https://github.com/netbox-community/cookiecutter-netbox-plugin) project template.


PLUGINS_CONFIG = {
    'netbox_dhcp_kea_plugin': {
        'top_level_menu': False,  # Use Plugins submenu instead
        'menu_name': 'Custom Name',  # Change menu label
    },
}