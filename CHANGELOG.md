# Changelog

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
