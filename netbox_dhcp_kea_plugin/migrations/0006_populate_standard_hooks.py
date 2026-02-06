from django.db import migrations

# Standard KEA hook libraries with their allowed processes
# Based on ISC KEA documentation: https://kea.readthedocs.io/en/latest/arm/hooks.html
STANDARD_HOOKS = [
    # BOOTP Support (DHCPv4 only)
    {
        "name": "BOOTP",
        "library_name": "libdhcp_bootp.so",
        "description": "Provides BOOTP protocol support for legacy clients that do not support DHCP.",
        "allowed_processes": ["kea-dhcp4"],
    },
    # Class Commands
    {
        "name": "Class Commands",
        "library_name": "libdhcp_class_cmds.so",
        "description": "Provides commands for managing client classes at runtime without restarting the server.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Configuration Backend Commands
    {
        "name": "Config Backend Commands",
        "library_name": "libdhcp_cb_cmds.so",
        "description": "Provides commands for managing configuration backend (database) entries.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # DDNS Tuning
    {
        "name": "DDNS Tuning",
        "library_name": "libdhcp_ddns_tuning.so",
        "description": "Allows fine-tuning of Dynamic DNS updates, including hostname generation and conflict resolution.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Flexible Identifier
    {
        "name": "Flexible Identifier",
        "library_name": "libdhcp_flex_id.so",
        "description": "Allows using arbitrary expressions to identify clients, beyond the standard hardware address or client ID.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Flexible Option
    {
        "name": "Flexible Option",
        "library_name": "libdhcp_flex_option.so",
        "description": "Enables setting option values based on expressions evaluated at runtime.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Forensic Logging (Legal Log)
    {
        "name": "Forensic Logging",
        "library_name": "libdhcp_legal_log.so",
        "description": "Provides detailed forensic logging of all lease assignments for legal/compliance purposes.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # GSS-TSIG for DDNS
    {
        "name": "GSS-TSIG",
        "library_name": "libddns_gss_tsig.so",
        "description": "Enables secure DNS updates using GSS-TSIG (Kerberos) authentication with Active Directory.",
        "allowed_processes": ["kea-dhcp-ddns"],
    },
    # High Availability
    {
        "name": "High Availability",
        "library_name": "libdhcp_ha.so",
        "description": "Provides high availability functionality with automatic failover between DHCP servers.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Host Cache
    {
        "name": "Host Cache",
        "library_name": "libdhcp_host_cache.so",
        "description": "Caches host reservations in memory to improve performance when using external databases.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Host Commands
    {
        "name": "Host Commands",
        "library_name": "libdhcp_host_cmds.so",
        "description": "Provides commands for managing host reservations at runtime without restarting the server.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Lease Commands
    {
        "name": "Lease Commands",
        "library_name": "libdhcp_lease_cmds.so",
        "description": "Provides commands for managing leases at runtime, including adding, updating, and deleting leases.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Lease Query
    {
        "name": "Lease Query",
        "library_name": "libdhcp_lease_query.so",
        "description": "Implements the DHCPv4/DHCPv6 Leasequery protocol (RFC 4388/RFC 5007).",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Limits
    {
        "name": "Limits",
        "library_name": "libdhcp_limits.so",
        "description": "Provides rate limiting and lease limiting capabilities to protect against abuse.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # MySQL Host Data Source
    {
        "name": "MySQL Host Backend",
        "library_name": "libdhcp_mysql.so",
        "description": "Enables storing host reservations in a MySQL database.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Performance Monitor
    {
        "name": "Performance Monitor",
        "library_name": "libdhcp_perfmon.so",
        "description": "Monitors and reports DHCP server performance metrics.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Ping Check
    {
        "name": "Ping Check",
        "library_name": "libdhcp_ping_check.so",
        "description": "Checks if an IP address is in use before assigning it by sending ICMP echo requests.",
        "allowed_processes": ["kea-dhcp4"],
    },
    # PostgreSQL Host Data Source
    {
        "name": "PostgreSQL Host Backend",
        "library_name": "libdhcp_pgsql.so",
        "description": "Enables storing host reservations in a PostgreSQL database.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # RADIUS
    {
        "name": "RADIUS",
        "library_name": "libdhcp_radius.so",
        "description": "Integrates with RADIUS servers for authentication and accounting.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Role-Based Access Control
    {
        "name": "Role-Based Access Control",
        "library_name": "libdhcp_rbac.so",
        "description": "Provides role-based access control for the KEA control agent API.",
        "allowed_processes": ["kea-ctrl-agent"],
    },
    # Run Script
    {
        "name": "Run Script",
        "library_name": "libdhcp_run_script.so",
        "description": "Executes external scripts at various hook points in the DHCP processing lifecycle.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Statistics Commands
    {
        "name": "Statistics Commands",
        "library_name": "libdhcp_stat_cmds.so",
        "description": "Provides extended commands for querying and managing DHCP statistics.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # Subnet Commands
    {
        "name": "Subnet Commands",
        "library_name": "libdhcp_subnet_cmds.so",
        "description": "Provides commands for managing subnets at runtime without restarting the server.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    # User Check
    {
        "name": "User Check",
        "library_name": "libdhcp_user_chk.so",
        "description": "Example hook that demonstrates user registry checking (typically used as a template).",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
]


def create_standard_hooks(apps, schema_editor):
    """Create standard KEA hook library entries."""
    Hook = apps.get_model("netbox_dhcp_kea_plugin", "Hook")

    for hook_data in STANDARD_HOOKS:
        Hook.objects.get_or_create(
            library_name=hook_data["library_name"],
            defaults={
                "name": hook_data["name"],
                "description": hook_data["description"],
                "is_standard": True,
                "allowed_processes": hook_data["allowed_processes"],
                "parameters": None,
            },
        )


def remove_standard_hooks(apps, schema_editor):
    """Remove standard KEA hook library entries."""
    Hook = apps.get_model("netbox_dhcp_kea_plugin", "Hook")
    library_names = [h["library_name"] for h in STANDARD_HOOKS]
    Hook.objects.filter(library_name__in=library_names, is_standard=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0005_hook_hookgroup"),
    ]

    operations = [
        migrations.RunPython(create_standard_hooks, remove_standard_hooks),
    ]
