# Changelog

## 0.2.4 (2026-02-05)

### Added
- **Hook Support**
  - New `Hook` and `HookGroup` models for managing KEA hook libraries
  - Views and UI for configuring hook libraries on DHCP servers

- **Option Definition Improvements**
  - Collect option-defs at server level for proper VIVSO (Vendor-Identifying Vendor-Specific Options) rendering
  - Add `id` field to PrefixDHCPConfig output for better identification

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
  - Hidden "Assigned Prefixes" tab, "Global Option Data" and "Client Classes" boxes for non-primary HA servers

- **Form Enhancements**
  - Auto-redirect to primary server when assigning prefixes to non-primary HA servers
  - User notification when config is saved to primary instead of selected server

### Changed
- `PrefixDHCPConfigTable` now uses custom `ViewEditActionsColumn` for better action buttons
- DHCP Server detail view reorganized for HA information display

## 0.1.0 (2026-01-18)

* Initial implementation of the core models.
