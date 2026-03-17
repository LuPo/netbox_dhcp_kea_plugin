# Changelog

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
