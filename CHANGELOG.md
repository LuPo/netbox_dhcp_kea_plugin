# Changelog

## 0.6.0 (2026-03-29)

### Added
- **KEA Reservation Mode Flags**
  - Three reservation mode flags on both DHCP Server and Subnet models: `reservations-global`, `reservations-in-subnet`, `reservations-out-of-pool`
  - Server-level flags set the global `Dhcp4` block defaults; subnet-level flags can override per-subnet or inherit from the server
  - Subnet fields are nullable (tri-state): `None` = inherit from server (omitted from KEA subnet config), `True`/`False` = explicit per-subnet override
  - `reservations_only` flag on Subnet disables dynamic pool generation entirely (subnet-only, not a KEA global parameter)
  - `Subnet.get_effective_reservation_flag()` helper and `effective_reservations_*` properties resolve inherited values

- **Global Reservation Placement**
  - When `reservations-global` is effective for a subnet, reservations are placed in the `Dhcp4.reservations` array without `ip-address` (only `hw-address` + `hostname`)
  - `DHCPServer.to_kea_dict()` collects global reservations from all subnets where effective `reservations_global` is `True`

- **Pool Generation Modes**
  - `reservations_out_of_pool=True` (default): pools built from available IPs only, excluding assigned addresses
  - `reservations_out_of_pool=False`: pools cover the full usable prefix range (KEA handles reservation/pool overlap at runtime)
  - `reservations_only=True`: no pools generated — only reserved hosts get IPs
  - IP Ranges defined in NetBox always take priority over computed pools

- **Configurable Defaults**
  - Reservation mode defaults configurable via `PLUGINS_CONFIG` under `model_defaults.Subnet`
  - Applies to new DHCP server instances; new subnets default to "Inherit from Server"

- **UI Updates**
  - Subnet form shows tri-state select (Inherit from Server / Yes / No) for reservation mode fields
  - Subnet detail page shows "Inherit (server: ...)" with resolved effective value when set to inherit
  - DHCP Server form and detail page include "Reservation Mode Defaults" section
  - Filterset and table columns for reservation flags on both Server and Subnet

- **Comprehensive Tests**
  - 38 tests covering all flag combinations, inheritance, pool generation, global reservation collection, and end-to-end KEA config output

### Changed
- Subnet reservation mode fields changed from non-nullable `BooleanField` to nullable `BooleanField(null=True, default=None)` to support server inheritance
- `get_default_reservations_*` functions and `get_model_default` helper moved earlier in `models.py` (before `DHCPServer` class) for reuse

### Migrations
- `0003_subnet_reservation_modes` — adds 4 reservation fields to Subnet
- `0004_alter_subnet_reservations_global_and_more` — switches to callable defaults
- `0005_dhcpserver_reservation_modes` — adds 3 reservation fields to DHCPServer
- `0006_subnet_nullable_reservation_flags` — makes Subnet fields nullable + data migration converting old defaults to `None` (inherit)

## 0.5.5 (2026-03-18)

### Added
- **Stork Server `db_user` Field**
  - New `db_user` field on `StorkServer` model (CharField, default: `"stork"`) for PostgreSQL database user name
  - `to_env_content()` now outputs `STORK_DATABASE_USER_NAME` in the generated environment file
  - Field included across serializer, forms (edit, import), detail template ("Database Connection" card), and tests
  - Database migration (`0021`) adds the field

- **DHCP Reservation MAC Address Validation**
  - `get_kea_reservations()` now filters out reservations that lack a `hw-address` (MAC address), preventing `kea-dhcp4.service` validation failures — KEA requires either `hw-address` or `duid` for each reservation
  - `get_reservations()` still returns all reservations (including those without MAC) for UI display, with a new `has_hw_address` metadata flag
  - Subnet reservations template highlights MAC-less reservations in yellow with a warning icon and tooltip
  - Warning alert below the reservations table explains why highlighted rows are excluded from KEA config and how to fix them (assign a MAC address to the interface in NetBox)
  - KEA Reservations Configuration JSON panel now correctly reflects only valid (MAC-bearing) reservations

- **Stork Server Form Default**
  - `stork_version` field on `StorkServerForm` now pre-populates with `"stable"` when creating a new Stork server instance

- **Plugin `model_defaults` Configuration**
  - New `model_defaults` setting in `PLUGINS_CONFIG` allows operators to configure default field values per model
  - `model_defaults.Subnet.valid_lifetime` — default valid lifetime for new subnets (default: `3600`)
  - `model_defaults.Subnet.max_lifetime` — default max lifetime for new subnets (default: `7200`)
  - Defaults apply to both the model layer (`Subnet.objects.create()`) and the form (pre-populated fields when adding a new subnet)

### Changed
- **Dynamic Control Socket Form Fields**
  - Control socket fields (HTTP address/port, Unix path) now update dynamically when changing the "Control socket type" dropdown — no save/reload required
  - Uses NetBox's `HTMXSelect` widget on `ctrl_socket_type`, matching the same UX pattern NetBox uses for 802.1Q VLAN mode on interfaces
  - Converted `fieldsets` on `DHCPServerForm` from a static class attribute to a `@property` so that `InlineFields` labels (e.g. "HTTP Socket") are omitted when their child fields are not relevant, preventing orphaned labels in the form

### Fixed
- Orphaned "HTTP Socket" label remained visible in the DHCP Server edit form when "Unix" was selected as the control socket type
- Reservations without a MAC address on their interface no longer cause `kea-dhcp4.service` config validation to fail
- **Subnet `valid_lifetime` validation enforced on `save()`** — `valid_lifetime` can no longer exceed `max_lifetime` when saving programmatically (e.g. via API or scripts); previously the check only ran during form validation (`clean()`)

## 0.5.3 (2026-03-18)

### Added
- **HA Address/Port/TLS Fields**
  - Split `ha_url` (URLField) into three separate fields on `DHCPServer`:
    - `ha_address` — IP address for HA communication (CharField)
    - `ha_port` — Port for HA communication (PositiveIntegerField, default: 8080)
    - `ha_tls` — Use TLS/HTTPS for HA communication (BooleanField, default: False)
  - New `ha_url` read-only property reconstructs the full URL (e.g. `http://192.168.1.1:8080/`) from the three fields
  - KEA configuration JSON output (`high-availability` peer `url`) remains a full URL — no downstream config changes required

- **IP Address Validation**
  - `ha_address` is validated as a valid IP address (IPv4 or IPv6) using Python's `ipaddress` module
  - `ctrl_socket_http_address` is validated as a valid IP address when provided

- **Port Collision Validation**
  - `ha_port` and `ctrl_socket_http_port` are validated to be different when the HTTP control socket is enabled, preventing accidental port conflicts on the same server

- **Form Layout Improvements**
  - HA fields use `InlineFields` for compact layout: `ha_address` and `ha_port` inline as "HA Peer", `ha_tls` and `ha_auto_failover` inline as "HA Options"

### Changed
- **BREAKING**: `ha_url` field removed from database — replaced by `ha_address`, `ha_port`, `ha_tls`
  - Migration `0018` parses existing `ha_url` values with `urllib.parse.urlparse` to populate the new fields automatically
  - API serializer exposes `ha_address`, `ha_port`, `ha_tls` as writable fields and `ha_url` as a read-only computed field
  - Import form accepts `ha_address`, `ha_port`, `ha_tls` instead of `ha_url`
  - Table columns updated: `ha_address`, `ha_port`, `ha_tls` replace `ha_url`
- Default HA port changed from 8000 to 8080 (including fallback URLs in relay-config endpoints)
- DHCP Server detail template now shows HA Address, HA Port, HA TLS (badge), computed HA URL, and HA Auto Failover

## 0.5.2 (2026-03-18)

### Added
- **Control Socket Support for DHCP Servers**
  - New `ctrl_socket_http_enabled` (BooleanField), `ctrl_socket_http_address` (CharField, default `127.0.0.1`), and `ctrl_socket_http_port` (PositiveIntegerField, default `8000`) fields for HTTP control socket configuration
  - New `ctrl_socket_unix_enabled` (BooleanField) and `ctrl_socket_unix_path` (CharField, default `/var/run/kea/kea-dhcp4-socket`) fields for Unix domain socket configuration
  - `DHCPServer.get_control_sockets()` method generates KEA-compatible `control-sockets` configuration list
  - `to_kea_dict()` now includes `control-sockets` in the generated `Dhcp4` configuration when sockets are enabled
  - Model validation: required fields enforced when a socket type is enabled (address + port for HTTP; path for Unix)
  - Full integration across serializers, forms (edit, import, filter), filtersets, tables, and detail template
  - Database migration (`0017`) adds the control socket fields to `DHCPServer`
  - Comprehensive test suite (`test_control_sockets.py`) covering model defaults, validation, `to_kea_dict` output, API, forms, filters, and tables

- **Stork Integration Tests**
  - Added comprehensive test coverage for Stork server and agent group models, forms, API, and configuration generation
  - Removed unused import from migration and fixed stray return in `test_clientclass_redirect.py`

### Changed
- **Form Layout with InlineFields**
  - Refactored form `fieldsets` across the plugin to use `InlineFields` for grouping related inputs:
    - `DHCPServerForm`: HTTP socket address/port, HA credentials
    - `StorkServerForm`: DB host/port, version/log level
    - `StorkAgentGroupForm`: Prometheus address/port, version/log level
    - `HookForm`: library name / standard flag
  - Added/adjusted `tags` fieldsets on all applicable forms
  - `fieldsets` placed at class level (not inside `Meta`) to match NetBox rendering expectations
  - Updated tests to collect field names from both top-level strings and `InlineFields` groups

## 0.5.1 (2026-03-18)

### Added
- **Stork Monitoring Integration**
  - New `StorkServer` model for managing ISC Stork monitoring server instances
  - New `StorkAgentGroup` model for configuring Stork agent groups linked to DHCP servers
  - `StorkServer.to_env_content()` generates environment files suitable for `/etc/stork/server.env`
  - `StorkAgentGroup.to_env_content()` generates environment files suitable for `/etc/stork/agent.env`
  - Configurable `log_level` field (DEBUG, INFO, WARN, ERROR) on both Stork models, defaulting to INFO
  - Prometheus exporter settings per agent group (address, port, per-subnet stats)
  - TLS and authentication options for Stork server connections
  - Full CRUD views, forms, serializers, filters, tables, and templates for both Stork models

- **Stork Configuration API Endpoints**
  - `GET /api/plugins/netbox-dhcp-kea-plugin/stork-servers/{id}/config/` returns plain-text server env file
  - `GET /api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/{id}/config/` returns generic agent env template with `<AGENT_HOST_IP>` placeholder
  - `GET /api/plugins/netbox-dhcp-kea-plugin/stork-agent-groups/{id}/config/?server={id}` returns resolved agent env file with concrete DHCP server IP
  - Custom `PlainTextRenderer` for DRF ensures `Accept: text/plain` works correctly (e.g. Ansible `uri` module)

- **Stork Optionality (`enable_stork` Setting)**
  - New plugin setting `enable_stork` (default: `True`) to toggle all Stork features
  - When disabled: Stork menu items, form fields, filter fields, API endpoints, and UI elements are all hidden
  - Gating applied across navigation, forms (`DHCPServerForm`, `DHCPServerFilterForm`, `DHCPServerImportForm`), filtersets (`DHCPServerFilterSet`), API serializers (`DHCPServerSerializer`), API URL routes, and UI URL routes

- **Plugin Settings Documentation**
  - Added `enable_stork` to README configuration section
  - Added plugin settings reference table to README
  - Added Stork configuration generation and Ansible integration examples to README
  - Added Stork API endpoints to REST API reference table

### Changed
- **BREAKING**: Converted `StorkAgentGroup.servers` from ManyToMany to `DHCPServer.stork_agent_group` ForeignKey — each DHCP server can now belong to at most one Stork agent group
  - Data migration (`0015`) copies existing M2M assignments to the new FK column (first group by PK wins if a server belonged to multiple groups)
  - Migration (`0016`) adds `log_level` fields to both Stork models

## 0.3.0 (2026-02-06)

### Added
- **Subnet Pool Model**
  - New `SubnetPool` model for pool-level DHCP configuration, annotating NetBox `IPRange` objects with KEA pool-level settings
  - Pool-level `client_class` FK for restricting which clients can obtain addresses from a pool (KEA `client-class`)
  - Pool-level `evaluate_additional_classes` M2M for triggering client class evaluation at pool scope (KEA `evaluate-additional-classes`)
  - Pool-level `option_data` M2M for pool-specific DHCP options (KEA `option-data`)
  - `pool_range` property for consistent template-friendly display of pool address ranges
  - Full CRUD views, forms, serializers, filters, and tables for SubnetPool management
  - Database migration (`0009`) creates the SubnetPool model

- **Subnet Client Class Restriction**
  - New `client_class` FK on `Subnet` model for a single restricting client class (KEA `client-class`)
  - Separates the restricting class concept from additional evaluated classes, aligning with KEA semantics
  - Database migration (`0010`) adds the field and renames the existing M2M

- **KEA Client Class Validation**
  - Subnet-level: raises `ValidationError` if restricting `client_class` has `only_in_additional_list=True` (subnet would be permanently unreachable since no higher scope triggers evaluation)
  - Pool-level: raises `ValidationError` if restricting `client_class` has `only_in_additional_list=True` and the parent subnet does not include the class in `evaluate_additional_classes`
  - Cross-field validation: restricting `client_class` cannot also appear in `evaluate_additional_classes` on the same object (both model and form level)

- **Redundant Evaluate-Additional-Classes Notifications**
  - Info notification card on Subnet detail page when `evaluate_additional_classes` contains classes without `only_in_additional_list` enabled (KEA already evaluates these globally, making the listing redundant)
  - Info notification card on Subnet Pool detail page with the same detection
  - Lists each redundant class with its name and test expression, with guidance to enable `only_in_additional_list` or remove the class from `evaluate-additional-classes`

- **Server-Level Misconfiguration Detection**
  - New `DHCPServer.get_unreachable_subnet_restrictions()` method to find subnets with unreachable restricting classes
  - New `DHCPServer.get_unreachable_pool_restrictions()` method to find pools with unreachable restricting classes
  - HA-aware: standby/secondary servers return empty lists (they inherit config from the primary)
  - Danger alert cards on DHCP Server detail page listing unreachable subnets and pools with explanations and links

- **Demo Data Generation for Subnet Pools**
  - `generate_kea_demo_data` command now creates IP Ranges and SubnetPool configurations
  - Demonstrates correct KEA patterns: normal global classes as restrictions, `only_in_additional_list` classes with proper subnet-level evaluation, and pool-level `evaluate-additional-classes`
  - Demo cleanup handles SubnetPool and IPRange objects

- **Test Coverage**
  - New unit tests for SubnetPool behavior, Subnet client class validations, server-level unreachable restriction helpers, KEA output consistency, and redundant evaluate-additional-classes detection.

### Changed
- **BREAKING**: Renamed `client_classes` M2M field on `Subnet` to `evaluate_additional_classes` to align with KEA terminology
- Subnet form: `evaluate_additional_classes` field now filters dropdown to show only client classes assigned to the selected server with `only_in_additional_list` enabled
- Subnet Pool form: `evaluate_additional_classes` field now filters dropdown to show only client classes with `only_in_additional_list` enabled
- Added `server_id` filter to `ClientClassFilterSet` for API-level filtering of client classes by server assignment
  - API consumers must update field references from `client_classes` to `evaluate_additional_classes`
  - Database migration (`0010`) handles the rename automatically
- `Subnet.get_all_subnet_client_classes()` and new `Subnet.get_all_pool_client_classes()` helpers collect client classes across both subnet and pool scopes
- `DHCPServer.to_kea_dict()` now includes pool-level client classes in the generated KEA configuration
- `DHCPServer.get_unused_only_in_additional_list_classes()` now also checks pool-level class references

### Fixed
- Pool address range display mismatch between list view and detail view (detail view was including subnet mask on addresses)

## 0.2.5 (2026-02-06)

### Changed
- **BREAKING**: Renamed `PrefixDHCPConfig` model to `Subnet` to align with KEA subnet terminology and avoid confusion with NetBox's IPAM `Prefix` model
  - All class names updated: `SubnetSerializer`, `SubnetViewSet`, `SubnetFilterSet`, `SubnetForm`, `SubnetTable`, `SubnetView`, etc.
  - URL path segments changed from `prefix-configs/` to `subnets/`
  - API endpoint changed from `prefix-dhcp-configs/` to `subnets/`
  - URL names changed from `prefixdhcpconfig_*` to `subnet_*`
  - Django permissions changed from `*_prefixdhcpconfig` to `*_subnet`
  - Template files renamed: `prefixdhcpconfig.html` → `subnet.html`, `prefixdhcpconfig_reservations.html` → `subnet_reservations.html`
  - Navigation menu label changed from "DHCP Prefixes" to "Subnets"
  - Database migration (`0008`) handles the model and table rename automatically


## 0.2.4 (2026-02-05)

### Added
- **Hook Support**
  - New `Hook` and `HookGroup` models for managing KEA hook libraries
  - Views and UI for configuring hook libraries on DHCP servers
  - Demo data generation now includes sample HookGroups with standard hooks assigned to servers

- **Option Definition Improvements**
  - Collect option-defs at server level for proper VIVSO (Vendor-Identifying Vendor-Specific Options) rendering
  - Add `id` field to Subnet (formerly PrefixDHCPConfig) output for better identification

### Changed
- **BREAKING**: Replaced `is_active` boolean field with `status` CharField on DHCPServer model
  - Uses `DeviceStatusChoices` from NetBox's dcim.choices for consistency with native models
  - Provides more granular status options (active, planned, staged, failed, offline, decommissioning, inventory)
  - Migration automatically converts `is_active=True` to `status="active"` and `is_active=False` to `status="offline"`
- Updated issue templates for versions and Python compatibility
- Linted tests with Ruff for code quality improvements

### Fixed
- Default `csv_format` to `True`; only emit `False` when explicitly set


## 0.2.3 (2026-02-28)

### Fixed
- Client Class server assignment now correctly notifies users when non-primary HA servers are redirected to primary
- Option data and client classes fields are now hidden when editing non-primary HA servers to prevent confusion

## 0.2.2 (2026-02-04)

### Added
- **Client Class Improvements**
  - Added `only_in_additional_list` field to align with KEA 3.0 behavior
  - Support for `evaluate-additional-classes` subnet-level client class evaluation
  - Made `test_expression` optional to support unconditional client classes
  - Removed deprecated `local_definitions` field
  - UI filtering to show only appropriate client classes in subnet configuration
  - Warning indicators for unused `only_in_additional_list` classes on server detail pages
  - Info indicators for unconditional (empty test) client classes

## 0.2.1 (2026-01-30)

### Added
- **Implement Netbox management command to populate plugin with demo data**
    - Command: `python manage.py generate_kea_demo_data`
    - Accepts optional arguments `--clear`, `--force`, `--purge-demo-data`
    - Enable configuration of number of DHCP servers, prefixes, option data, and client classes to generate via plugin settings
    - Creates sample DHCP servers, HA relationships, prefixes, option data, and client classes for testing and demonstration purposes

## 0.2.0 (2026-01-27)

### Added
- **High Availability (HA) Support**
  - New `DHCPHARelationship` model for managing HA relationships between DHCP servers
  - New `DHCPHAPeer` model for defining server roles (primary, secondary, standby, backup) in HA relationships
  - Support for KEA HA modes: hot-standby, load-balancing, passive-backup
  - Automatic config sync from primary to all HA peers via `get_effective_*` methods
  - HA-aware `to_kea_dict()` method that generates consistent configs across HA peers
  - Protection against deleting or changing role of primary peer with existing configs
  - `migrate_configs_to_new_primary()` helper for safely switching primary servers

- **UI Improvements**
  - Renamed "Prefix Configs" to "DHCP Prefixes" in navigation
  - Added view (eye) button alongside edit button in DHCP Prefixes list
  - Added HA Assignment and HA Role fields to DHCP Server detail view
  - HA standby servers show info badge and card explaining config sync
  - Hidden "Subnets" tab, "Global Option Data" and "Client Classes" boxes for non-primary HA servers

- **Form Enhancements**
  - Auto-redirect to primary server when assigning prefixes to non-primary HA servers
  - User notification when config is saved to primary instead of selected server

### Changed
- `SubnetTable` (formerly `PrefixDHCPConfigTable`) now uses custom `ViewEditActionsColumn` for better action buttons
- DHCP Server detail view reorganized for HA information display

## 0.1.0 (2026-01-18)

* Initial implementation of the core models.
