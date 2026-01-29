# NetBox DHCP-KEA Plugin

A NetBox plugin for managing ISC KEA DHCP server configurations. This plugin extends NetBox with comprehensive DHCP infrastructure management, including server configuration, option definitions, client classification, High Availability relationships, and DHCP relay information for network devices.

* Free software: GPL-3.0-only
* Documentation: https://LuPo.github.io/netbox-dhcp-kea-plugin/

## Overview

This plugin bridges the gap between NetBox IPAM and ISC KEA DHCP server configuration by:

- Linking NetBox Prefixes to DHCP server configurations
- Managing DHCP options (standard and vendor-specific)
- Configuring client classification with KEA test expressions
- Supporting High Availability (HA) deployments
- Providing DHCP relay target information for network device configuration
- Generating KEA-compatible configuration output

## Features

### Core Models

- **DHCP Servers**: Manage ISC KEA DHCP server instances linked to NetBox IP addresses
- **Vendor Option Spaces**: Define vendor-specific option spaces with enterprise IDs
- **Option Definitions**: Create custom DHCP option definitions (KEA `option-def`)
- **Option Data**: Configure DHCP option values (KEA `option-data`)
- **Client Classes**: Configure client classification rules with KEA test expressions
- **Prefix DHCP Config**: Link NetBox Prefixes to DHCP configurations with pools and options
- **HA Relationships**: Configure High Availability relationships between DHCP servers

### High Availability (HA) Support

- Configure HA relationships with multiple modes: hot-standby, load-balancing, passive-backup
- Define server roles within HA clusters (primary, secondary, standby, backup)
- Automatic configuration sync from primary to all HA peers
- HA-aware KEA config generation ensures consistent configurations across all peers
- Protection against orphaned configs (cannot delete/demote primary with existing configs)
- Easy config migration when switching primary servers
- UI intelligently hides config management options for non-primary servers

### DHCP Relay Support

The plugin provides DHCP relay target information for configuring `ip helper-address` on Layer 3 network devices:

- **Integrated with Prefix API**: Query `/api/ipam/prefixes/{id}/` to get relay targets directly
- **Dedicated lookup endpoint**: Query by prefix CIDR with VRF support
- **HA-aware**: Returns all server IPs in an HA relationship for redundant relay configuration

### Integration with NetBox

- DHCP configuration tab on Prefix detail pages
- Direct integration with NetBox's Prefix API (adds `dhcp_config` field)
- Full REST API support for all models
- Tag support on all models
- Change logging and audit trail
- Bulk import/export capabilities

## Compatibility

| NetBox Version | Plugin Version |
|----------------|----------------|
|     4.5        |      0.2.0     |

## Installation

### Using pip

```bash
pip install git+https://github.com/LuPo/netbox-dhcp-kea-plugin
```

### Using netbox-docker

Add to your `plugin_requirements.txt`:

```
git+https://github.com/LuPo/netbox-dhcp-kea-plugin
```

See [netbox-docker plugin instructions](https://github.com/netbox-community/netbox-docker/wiki/Using-Netbox-Plugins) for details.

### Configuration

Enable the plugin in your NetBox configuration (`configuration.py` or `plugins.py` for netbox-docker):

```python
PLUGINS = [
    'netbox_dhcp_kea_plugin'
]

PLUGINS_CONFIG = {
    'netbox_dhcp_kea_plugin': {
        'top_level_menu': True,      # Use top-level menu (default: True)
        'menu_name': 'DHCP KEA',     # Menu label (default: 'DHCP KEA')
    },
}
```

Run migrations:

```bash
python manage.py migrate
```

## Usage

### Quick Start

1. **Create DHCP Servers**: Navigate to DHCP KEA > DHCP Servers and add your KEA server instances
2. **Configure HA** (optional): Set up HA relationships and assign server roles
3. **Define Options**: Create option definitions for vendor-specific options, or use standard DHCP options
4. **Create Option Data**: Define option values to apply to client classes or prefixes
5. **Set Up Client Classes**: Configure client classification rules with KEA test expressions
6. **Configure Prefixes**: Link NetBox Prefixes to DHCP servers with pools and options

### DHCP Relay Configuration

When configuring DHCP relay on Layer 3 switches/routers, you need the DHCP server IP addresses to use as helper addresses. This plugin provides multiple ways to retrieve this information:

#### Method 1: Query Prefix API Directly

The plugin extends NetBox's Prefix API to include DHCP relay information:

```bash
GET /api/ipam/prefixes/{id}/
```

Response includes:
```json
{
    "id": 123,
    "prefix": "10.0.100.0/24",
    "vrf": null,
    ...
    "dhcp_config": {
        "server": {
            "name": "kea-dhcp-primary",
            "url": "http://192.168.1.10:8000/"
        },
        "relay_targets": ["192.168.1.10", "192.168.1.11"]
    }
}
```

#### Method 2: Lookup by Prefix CIDR

Query the dedicated relay config endpoint:

```bash
# Global VRF
GET /api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=10.0.100.0/24

# Specific VRF
GET /api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=10.0.100.0/24&vrf=CustomerA
```

Response:
```json
{
    "prefix": "10.0.100.0/24",
    "dhcp_config": {
        "server": {
            "name": "kea-dhcp-primary",
            "url": "http://192.168.1.10:8000/"
        },
        "relay_targets": ["192.168.1.10", "192.168.1.11"]
    }
}
```

#### Method 3: From PrefixDHCPConfig

```bash
GET /api/plugins/netbox-dhcp-kea-plugin/prefix-dhcp-configs/{id}/relay-config/
```

#### Using Relay Targets

The `relay_targets` array contains all DHCP server IPs that should receive relayed requests. For HA configurations, this includes all servers in the relationship.

**Cisco IOS/IOS-XE:**
```
interface Vlan100
  ip helper-address 192.168.1.10
  ip helper-address 192.168.1.11
```

**Juniper Junos:**
```
set forwarding-options dhcp-relay server-group DHCP-SERVERS 192.168.1.10
set forwarding-options dhcp-relay server-group DHCP-SERVERS 192.168.1.11
set forwarding-options dhcp-relay group RELAYS active-server-group DHCP-SERVERS
set forwarding-options dhcp-relay group RELAYS interface vlan.100
```

**Arista EOS:**
```
interface Vlan100
  ip helper-address 192.168.1.10
  ip helper-address 192.168.1.11
```

### KEA Configuration Generation

Generate KEA-compatible configuration for a DHCP server:

```bash
GET /api/plugins/netbox-dhcp-kea-plugin/dhcp-servers/{id}/kea-config/
```

This returns a complete `Dhcp4` configuration dictionary including:
- Global options
- Client class definitions
- Subnet configurations with pools
- HA configuration (if applicable)

### REST API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/plugins/netbox-dhcp-kea-plugin/dhcp-servers/` | DHCP server management |
| `/api/plugins/netbox-dhcp-kea-plugin/dhcp-servers/{id}/kea-config/` | Generate KEA config |
| `/api/plugins/netbox-dhcp-kea-plugin/vendor-option-spaces/` | Vendor option spaces |
| `/api/plugins/netbox-dhcp-kea-plugin/option-definitions/` | Option definitions |
| `/api/plugins/netbox-dhcp-kea-plugin/option-data/` | Option data/values |
| `/api/plugins/netbox-dhcp-kea-plugin/client-classes/` | Client classifications |
| `/api/plugins/netbox-dhcp-kea-plugin/prefix-dhcp-configs/` | Prefix DHCP configurations |
| `/api/plugins/netbox-dhcp-kea-plugin/prefix-dhcp-configs/{id}/relay-config/` | Relay config for prefix |
| `/api/plugins/netbox-dhcp-kea-plugin/ha-relationships/` | HA relationships |
| `/api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=X` | Lookup relay config by prefix |


## Demo Data Generation

The plugin includes a management command to generate demo data for testing:

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

Configure demo data generation in `PLUGINS_CONFIG`:

```python
PLUGINS_CONFIG = {
    'netbox_dhcp_kea_plugin': {
        'demo_data': {
            'enabled': True,  # Required unless using --force
            'vendor_option_spaces': 3,
            'option_definitions_per_space': 5,
            'option_data': 10,
            'client_classes': 5,
            'dhcp_servers': 3,
            'ha_relationships': 1,
            'prefix_configs': 5,
        },
    },
}
```

## Screenshots

*Coming soon*

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [`netbox-community/cookiecutter-netbox-plugin`](https://github.com/netbox-community/cookiecutter-netbox-plugin) project template.

Based on the NetBox plugin tutorial:
- [Demo repository](https://github.com/netbox-community/netbox-plugin-demo)
- [Tutorial](https://github.com/netbox-community/netbox-plugin-tutorial)

## License

GPL-3.0-only