# NetBox DHCP-KEA Plugin

> This project was developed using AI-assisted coding tools. It is undergoing review for accuracy, stability, security, and performance. If you encounter any problems, please feel free to open an issue or contribute a pull request!

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

- **DHCP Servers**: Manage ISC KEA DHCP server instances linked to NetBox IP addresses, with control socket and HA peer configuration
- **Vendor Option Spaces**: Define vendor-specific option spaces with enterprise IDs
- **Option Definitions**: Create custom DHCP option definitions (KEA `option-def`)
- **Option Data**: Configure DHCP option values (KEA `option-data`)
- **Client Classes**: Configure client classification rules with KEA test expressions
- **Subnets**: Link NetBox Prefixes to DHCP subnet configurations with pools and options
- **HA Relationships**: Configure High Availability relationships between DHCP servers
- **Stork Servers**: Manage ISC Stork monitoring server instances
- **Stork Agent Groups**: Configure Stork agent groups that link DHCP servers to a Stork monitoring server

### Stork Monitoring Integration

- Manage ISC Stork server and agent group configurations directly from NetBox
- Generate environment files (`/etc/stork/server.env`, `/etc/stork/agent.env`) for automated deployment
- Configurable log levels (DEBUG, INFO, WARN, ERROR) for both server and agent
- Prometheus exporter settings per agent group (address, port, per-subnet stats)
- TLS and authentication options for Stork server connections
- Stork features are fully optional — disable with `enable_stork: False` in plugin settings
- API endpoints support `Accept: text/plain` for easy integration with Ansible `uri` module

### High Availability (HA) Support

- Configure HA relationships with multiple modes: hot-standby, load-balancing, passive-backup
- Define server roles within HA clusters (primary, secondary, standby, backup)
- HA peer connection split into discrete fields: address (IP), port (default: 8080), and TLS toggle — the full URL is reconstructed automatically for KEA config output
- Automatic configuration sync from primary to all HA peers
- HA-aware KEA config generation ensures consistent configurations across all peers
- Protection against orphaned configs (cannot delete/demote primary with existing configs)
- Easy config migration when switching primary servers
- UI intelligently hides config management options for non-primary servers

### Control Socket Support

DHCP servers can be configured with KEA control sockets for management access:

- **HTTP control socket**: Address (validated as IP) and port for the HTTP control agent
- **Unix control socket**: File path for the Unix domain socket
- **Dynamic form fields**: Selecting a control socket type instantly shows/hides the relevant fields (uses the same HTMX pattern as NetBox's 802.1Q VLAN mode selector — no save or page reload required)
- **Validation**: HA port and HTTP control socket port are validated to be different when both are active, preventing accidental port conflicts
- **IP validation**: Both `ha_address` and `ctrl_socket_http_address` are validated as proper IP addresses (IPv4 or IPv6)

### DHCP Reservations

The plugin automatically discovers DHCP reservations from NetBox IP address assignments:

- **Auto-discovery**: IP addresses assigned to interfaces (device or VM) that are marked as Primary IP or OOB IP are collected as KEA host reservations
- **MAC address validation**: Only reservations with a `hw-address` (MAC address on the interface) are included in KEA configuration output — KEA requires either `hw-address` or `duid` for each reservation, and entries without either cause `kea-dhcp4.service` validation to fail
- **UI warnings**: The reservations tab highlights entries without a MAC address in yellow with a warning, explaining they will be excluded from the generated config
- **FHRP filtering**: FHRP group addresses are automatically excluded from reservations

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
|     4.5        |      0.5.5     |

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
        'enable_stork': True,        # Enable Stork monitoring integration (default: True)
    },
}
```

#### Plugin Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `top_level_menu` | `True` | Display plugin as a top-level menu in the NetBox navigation |
| `menu_name` | `'DHCP KEA'` | Label for the plugin menu |
| `enable_stork` | `True` | Enable ISC Stork monitoring integration. When `False`, all Stork-related menu items, form fields, filters, API endpoints, and UI elements are hidden |

To disable Stork integration:

```python
PLUGINS_CONFIG = {
    'netbox_dhcp_kea_plugin': {
        'enable_stork': False,
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
2. **Configure HA** (optional): Set up HA relationships, assign server roles, and configure HA peer address/port/TLS
3. **Configure Control Sockets** (optional): Enable HTTP and/or Unix control sockets on DHCP servers
4. **Configure Stork** (optional): Set up Stork servers and agent groups for monitoring
5. **Define Options**: Create option definitions for vendor-specific options, or use standard DHCP options
6. **Create Option Data**: Define option values to apply to client classes or prefixes
7. **Set Up Client Classes**: Configure client classification rules with KEA test expressions
8. **Configure Prefixes**: Link NetBox Prefixes to DHCP servers with pools and options

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
            "url": "http://192.168.1.10:8080/"
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
            "url": "http://192.168.1.10:8080/"
        },
        "relay_targets": ["192.168.1.10", "192.168.1.11"]
    }
}
```

#### Method 3: From Subnet

```bash
GET /api/plugins/netbox-dhcp-kea-plugin/subnets/{id}/relay-config/
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
- Host reservations (auto-discovered from NetBox IP assignments with MAC addresses)
- Control sockets (if configured)
- HA configuration (if applicable)

#### DHCP Server HA Fields

When creating or updating DHCP servers via the API, HA peer connection details are specified as discrete fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ha_address` | string | `""` | IP address for HA communication (validated as IPv4/IPv6) |
| `ha_port` | integer | `8080` | Port for HA communication |
| `ha_tls` | boolean | `false` | Use TLS (HTTPS) for HA communication |
| `ha_url` | string | *(read-only)* | Computed URL from address/port/TLS (e.g. `http://192.168.1.1:8080/`) |

The `ha_url` field is read-only in API responses — it is reconstructed from `ha_address`, `ha_port`, and `ha_tls`. The KEA configuration JSON (`high-availability` peer `url`) uses this computed URL, so downstream KEA configs require no changes.

**Validation rules:**
- `ha_address` and `ctrl_socket_http_address` must be valid IP addresses when provided
- `ha_port` must differ from `ctrl_socket_http_port` when the HTTP control socket is enabled

### Stork Configuration Generation

When Stork integration is enabled (`enable_stork: True`), the plugin can generate environment files for ISC Stork server and agent deployment.

#### Stork Server Environment File

Generate an environment file suitable for `/etc/stork/server.env`:

```bash
GET /api/plugins/netbox-dhcp-kea-plugin/stork-servers/{id}/config/
```

Returns plain text (`text/plain`) with environment variables for the Stork server, including database connection, REST API, and metrics settings.

#### Stork Agent Environment File

Generate an environment file suitable for `/etc/stork/agent.env`:

```bash
# Generic template with placeholder for STORK_AGENT_HOST
GET /api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/{id}/config/

# Resolved for a specific DHCP server (replaces placeholder with server IP)
GET /api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/{id}/config/?server={dhcp_server_id}
```

Returns plain text with environment variables for the Stork agent, including server connection, Prometheus exporter, and logging settings.

#### Ansible Integration

The config endpoints return `text/plain` content, making them easy to consume with Ansible:

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

### REST API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/plugins/netbox-dhcp-kea-plugin/dhcp-servers/` | DHCP server management |
| `/api/plugins/netbox-dhcp-kea-plugin/dhcp-servers/{id}/kea-config/` | Generate KEA config |
| `/api/plugins/netbox-dhcp-kea-plugin/vendor-option-spaces/` | Vendor option spaces |
| `/api/plugins/netbox-dhcp-kea-plugin/option-definitions/` | Option definitions |
| `/api/plugins/netbox-dhcp-kea-plugin/option-data/` | Option data/values |
| `/api/plugins/netbox-dhcp-kea-plugin/client-classes/` | Client classifications |
| `/api/plugins/netbox-dhcp-kea-plugin/subnets/` | Subnet (prefix DHCP) configurations |
| `/api/plugins/netbox-dhcp-kea-plugin/subnets/{id}/relay-config/` | Relay config for subnet |
| `/api/plugins/netbox-dhcp-kea-plugin/subnet-pools/` | Subnet pool configurations |
| `/api/plugins/netbox-dhcp-kea-plugin/ha-relationships/` | HA relationships |
| `/api/plugins/netbox-dhcp-kea-plugin/relay-config/?prefix=X` | Lookup relay config by prefix |
| `/api/plugins/netbox-dhcp-kea-plugin/stork-servers/` | Stork server management |
| `/api/plugins/netbox-dhcp-kea-plugin/stork-servers/{id}/config/` | Generate Stork server env file |
| `/api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/` | Stork agent group management |
| `/api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/{id}/config/` | Generate Stork agent env file |

> **Note:** Stork API endpoints are only available when `enable_stork` is `True` in plugin settings.


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
            'subnets': 5,
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
