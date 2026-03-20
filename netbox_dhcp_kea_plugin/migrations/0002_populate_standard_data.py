from itertools import zip_longest

from django.db import migrations

# Standard DHCPv4 options from KEA documentation (RFC 2132 and others)
# https://kea.readthedocs.io/en/latest/arm/dhcp4-srv.html#id5
STANDARD_DHCP4_OPTIONS = [
    # (name, code, option_type, is_array, description)
    ("time-offset", 2, "int32", False, "Time offset in seconds from UTC"),
    ("routers", 3, "ipv4-address", True, "Default gateway routers"),
    ("time-servers", 4, "ipv4-address", True, "Time servers"),
    ("name-servers", 5, "ipv4-address", True, "IEN 116 name servers"),
    ("domain-name-servers", 6, "ipv4-address", True, "DNS servers"),
    ("log-servers", 7, "ipv4-address", True, "MIT-LCS UDP log servers"),
    ("cookie-servers", 8, "ipv4-address", True, "Cookie servers"),
    ("lpr-servers", 9, "ipv4-address", True, "LPR print servers"),
    ("impress-servers", 10, "ipv4-address", True, "Impress servers"),
    ("resource-location-servers", 11, "ipv4-address", True, "Resource location servers"),
    ("boot-size", 13, "uint16", False, "Boot file size in 512-byte blocks"),
    ("merit-dump", 14, "string", False, "Path for core dump"),
    ("domain-name", 15, "fqdn", False, "Domain name for client"),
    ("swap-server", 16, "ipv4-address", False, "Swap server address"),
    ("root-path", 17, "string", False, "Root disk path"),
    ("extensions-path", 18, "string", False, "Extensions path"),
    ("ip-forwarding", 19, "boolean", False, "Enable IP forwarding"),
    ("non-local-source-routing", 20, "boolean", False, "Enable non-local source routing"),
    ("policy-filter", 21, "ipv4-address", True, "Policy filter addresses"),
    ("max-dgram-reassembly", 22, "uint16", False, "Maximum datagram reassembly size"),
    ("default-ip-ttl", 23, "uint8", False, "Default IP TTL"),
    ("path-mtu-aging-timeout", 24, "uint32", False, "Path MTU aging timeout"),
    ("path-mtu-plateau-table", 25, "uint16", True, "Path MTU plateau table"),
    ("interface-mtu", 26, "uint16", False, "Interface MTU"),
    ("all-subnets-local", 27, "boolean", False, "All subnets are local"),
    ("broadcast-address", 28, "ipv4-address", False, "Broadcast address"),
    ("perform-mask-discovery", 29, "boolean", False, "Perform mask discovery"),
    ("mask-supplier", 30, "boolean", False, "Mask supplier"),
    ("router-discovery", 31, "boolean", False, "Router discovery"),
    ("router-solicitation-address", 32, "ipv4-address", False, "Router solicitation address"),
    ("static-routes", 33, "ipv4-address", True, "Static routes"),
    ("trailer-encapsulation", 34, "boolean", False, "Trailer encapsulation"),
    ("arp-cache-timeout", 35, "uint32", False, "ARP cache timeout"),
    ("ieee802-3-encapsulation", 36, "boolean", False, "Ethernet encapsulation"),
    ("default-tcp-ttl", 37, "uint8", False, "Default TCP TTL"),
    ("tcp-keepalive-interval", 38, "uint32", False, "TCP keepalive interval"),
    ("tcp-keepalive-garbage", 39, "boolean", False, "TCP keepalive garbage"),
    ("nis-domain", 40, "string", False, "NIS domain name"),
    ("nis-servers", 41, "ipv4-address", True, "NIS servers"),
    ("ntp-servers", 42, "ipv4-address", True, "NTP servers"),
    ("vendor-encapsulated-options", 43, "empty", False, "Vendor Specific Information"),
    ("netbios-name-servers", 44, "ipv4-address", True, "NetBIOS name servers"),
    ("netbios-dd-server", 45, "ipv4-address", True, "NetBIOS datagram distribution servers"),
    ("netbios-node-type", 46, "uint8", False, "NetBIOS node type"),
    ("netbios-scope", 47, "string", False, "NetBIOS scope"),
    ("font-servers", 48, "ipv4-address", True, "X Window font servers"),
    ("x-display-manager", 49, "ipv4-address", True, "X Window display managers"),
    ("dhcp-option-overload", 52, "uint8", False, "DHCP option overload"),
    ("dhcp-server-identifier", 54, "ipv4-address", False, "DHCP server identifier"),
    ("dhcp-message", 56, "string", False, "DHCP message"),
    ("dhcp-max-message-size", 57, "uint16", False, "Maximum DHCP message size"),
    ("vendor-class-identifier", 60, "string", False, "Vendor class identifier"),
    ("nwip-domain-name", 62, "string", False, "NetWare/IP domain name"),
    ("nwip-suboptions", 63, "binary", False, "NetWare/IP suboptions"),
    ("nisplus-domain-name", 64, "string", False, "NIS+ domain name"),
    ("nisplus-servers", 65, "ipv4-address", True, "NIS+ servers"),
    ("tftp-server-name", 66, "string", False, "TFTP server name"),
    ("boot-file-name", 67, "string", False, "Boot file name"),
    ("mobile-ip-home-agent", 68, "ipv4-address", True, "Mobile IP home agents"),
    ("smtp-server", 69, "ipv4-address", True, "SMTP servers"),
    ("pop-server", 70, "ipv4-address", True, "POP3 servers"),
    ("nntp-server", 71, "ipv4-address", True, "NNTP servers"),
    ("www-server", 72, "ipv4-address", True, "WWW servers"),
    ("finger-server", 73, "ipv4-address", True, "Finger servers"),
    ("irc-server", 74, "ipv4-address", True, "IRC servers"),
    ("streettalk-server", 75, "ipv4-address", True, "StreetTalk servers"),
    ("streettalk-directory-assistance-server", 76, "ipv4-address", True, "StreetTalk directory servers"),
    ("user-class", 77, "binary", False, "User class"),
    ("slp-directory-agent", 78, "record", True, "Service Location Protocol", "boolean, ipv4-address"),
    (
        "slp-service-scope",
        79,
        "record",
        False,
        "SLP scope - string that acts as a logical grouping or boundary for services on a network",
        "boolean, string",
    ),
    ("nds-servers", 85, "ipv4-address", True, "NDS servers (eDirectory)"),
    ("nds-tree-name", 86, "string", False, "NDS tree name"),
    ("nds-context", 87, "string", False, "Novell Directory Services (NDS) context"),
    (
        "bcms-controller-names",
        88,
        "fqdn",
        False,
        "Broadcast and Multicast Service Controller (BCMS) Controller Domain Name (RFC 4280)",
    ),
    ("bcms-controller-address", 89, "ipv4-address", False, "BCMCS Controller IPv4 address option (RFC 4280)"),
    ("client-system", 93, "uint16", False, "Client System Architecture (RFC 4578)"),
    ("client-ndi", 94, "record", False, "Client Network Device Interface (RFC 4578)", "uint8, uint8, uint8"),
    ("uuid-guid", 97, "record", False, "UUID/GUID-based Client Identifier", "uint8, binary"),
    ("uap-servers", 98, "string", False, "Open Group's User Authentication Protocol servers"),
    ("geoconf-civic", 99, "binary", False, "Geoconf civic location"),
    ("pcode", 100, "string", False, "IEEE 1003.1 TZ string"),
    ("tcode", 101, "string", False, "Reference to TZ database"),
    ("v6-only-preferred", 108, "uint32", False, "IPv6-only preferred"),
    ("netinfo-server-address", 112, "ipv4-address", True, "NetInfo parent server addresses"),
    ("netinfo-server-tag", 113, "string", False, "NetInfo parent server tag"),
    ("v4-captive-portal", 114, "string", False, "Captive portal URL"),
    ("auto-config", 116, "uint8", False, "Auto-configure"),
    ("name-service-search", 117, "uint16", True, "Name service search order"),
    ("domain-search", 119, "fqdn", True, "Domain search list"),
    ("classless-static-route", 121, "internal", False, "Classless Static Route Option (RFC 3442)"),
    ("cablelabs-client-conf", 122, "empty", False, "CableLabs Client Configuration (RFC 3495)"),
    ("vivso-suboptions", 125, "uint32", False, "Vendor-Identifying Vendor-Specific Options"),
    ("pana-agent", 136, "ipv4-address", True, "PANA authentication agents"),
    ("v4-lost", 137, "fqdn", False, "LoST server"),
    ("capwap-ac-v4", 138, "ipv4-address", True, "CAPWAP access controllers"),
    (
        "sip-ua-cs-domains",
        141,
        "fqdn",
        True,
        "List of domain names to search for SIP User Agent Configuration (RFC6011)",
    ),
    (
        "v4-sztp-redirect",
        142,
        "tuple",
        True,
        "This option provides a list of URIs for SZTP bootstrap servers (RFC8572)",
    ),
    (
        "rdnss-selection",
        146,
        "record",
        True,
        "This option provides parameters for SZTP bootstrap process (RFC6731)",
        "uint8, ipv4-address, ipv4-address, fqdn",
    ),
    (
        "v4-portparams",
        159,
        "record",
        False,
        "This option is used to configure a set of ports bound to a shared IPv4 address (RFC7618)",
        "uint8, psid",
    ),
    ("v4-dnr", 162, "record", False, "Encrypted DNS Server (RFC9463)", "uint16, uint16, uint8, fqdn, binary"),
    (
        "option-6rd",
        212,
        "record",
        False,
        "OPTION_6RD with N/4 6rd BR addresses (RFC5969)",
        "uint8, uint8, ipv6-address, ipv4-address",
    ),
    ("v4-access-domain", 213, "fqdn", True, "Access Network Domain Name (RFC5986)"),
]

# Pad every tuple to exactly 6 elements (record-type options have a 6th field).
padded_options = ([val for val, _ in zip_longest(row, range(6), fillvalue="")] for row in STANDARD_DHCP4_OPTIONS)

# Standard KEA hook libraries with their allowed processes
# Based on ISC KEA documentation: https://kea.readthedocs.io/en/latest/arm/hooks.html
STANDARD_HOOKS = [
    {
        "name": "BOOTP",
        "library_name": "libdhcp_bootp.so",
        "description": "Provides BOOTP protocol support for legacy clients that do not support DHCP.",
        "allowed_processes": ["kea-dhcp4"],
    },
    {
        "name": "Class Commands",
        "library_name": "libdhcp_class_cmds.so",
        "description": "Provides commands for managing client classes at runtime without restarting the server.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Config Backend Commands",
        "library_name": "libdhcp_cb_cmds.so",
        "description": "Provides commands for managing configuration backend (database) entries.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "DDNS Tuning",
        "library_name": "libdhcp_ddns_tuning.so",
        "description": "Allows fine-tuning of Dynamic DNS updates, including hostname generation and conflict resolution.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Flexible Identifier",
        "library_name": "libdhcp_flex_id.so",
        "description": "Allows using arbitrary expressions to identify clients, beyond the standard hardware address or client ID.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Flexible Option",
        "library_name": "libdhcp_flex_option.so",
        "description": "Enables setting option values based on expressions evaluated at runtime.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Forensic Logging",
        "library_name": "libdhcp_legal_log.so",
        "description": "Provides detailed forensic logging of all lease assignments for legal/compliance purposes.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "GSS-TSIG",
        "library_name": "libddns_gss_tsig.so",
        "description": "Enables secure DNS updates using GSS-TSIG (Kerberos) authentication with Active Directory.",
        "allowed_processes": ["kea-dhcp-ddns"],
    },
    {
        "name": "High Availability",
        "library_name": "libdhcp_ha.so",
        "description": "Provides high availability functionality with automatic failover between DHCP servers.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Host Cache",
        "library_name": "libdhcp_host_cache.so",
        "description": "Caches host reservations in memory to improve performance when using external databases.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Host Commands",
        "library_name": "libdhcp_host_cmds.so",
        "description": "Provides commands for managing host reservations at runtime without restarting the server.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Lease Commands",
        "library_name": "libdhcp_lease_cmds.so",
        "description": "Provides commands for managing leases at runtime, including adding, updating, and deleting leases.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Lease Query",
        "library_name": "libdhcp_lease_query.so",
        "description": "Implements the DHCPv4/DHCPv6 Leasequery protocol (RFC 4388/RFC 5007).",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Limits",
        "library_name": "libdhcp_limits.so",
        "description": "Provides rate limiting and lease limiting capabilities to protect against abuse.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "MySQL Host Backend",
        "library_name": "libdhcp_mysql.so",
        "description": "Enables storing host reservations in a MySQL database.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Performance Monitor",
        "library_name": "libdhcp_perfmon.so",
        "description": "Monitors and reports DHCP server performance metrics.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Ping Check",
        "library_name": "libdhcp_ping_check.so",
        "description": "Checks if an IP address is in use before assigning it by sending ICMP echo requests.",
        "allowed_processes": ["kea-dhcp4"],
    },
    {
        "name": "PostgreSQL Host Backend",
        "library_name": "libdhcp_pgsql.so",
        "description": "Enables storing host reservations in a PostgreSQL database.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "RADIUS",
        "library_name": "libdhcp_radius.so",
        "description": "Integrates with RADIUS servers for authentication and accounting.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Role-Based Access Control",
        "library_name": "libdhcp_rbac.so",
        "description": "Provides role-based access control for the KEA control agent API.",
        "allowed_processes": ["kea-ctrl-agent"],
    },
    {
        "name": "Run Script",
        "library_name": "libdhcp_run_script.so",
        "description": "Executes external scripts at various hook points in the DHCP processing lifecycle.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Statistics Commands",
        "library_name": "libdhcp_stat_cmds.so",
        "description": "Provides extended commands for querying and managing DHCP statistics.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "Subnet Commands",
        "library_name": "libdhcp_subnet_cmds.so",
        "description": "Provides commands for managing subnets at runtime without restarting the server.",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
    {
        "name": "User Check",
        "library_name": "libdhcp_user_chk.so",
        "description": "Example hook that demonstrates user registry checking (typically used as a template).",
        "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
    },
]


def populate_standard_options(apps, schema_editor):
    """Populate the database with standard DHCPv4 option definitions."""
    OptionDefinition = apps.get_model("netbox_dhcp_kea_plugin", "OptionDefinition")

    for name, code, option_type, is_array, description, record_types in padded_options:
        if not OptionDefinition.objects.filter(
            code=code, option_space="dhcp4", vendor_option_space__isnull=True
        ).exists():
            OptionDefinition.objects.create(
                name=name,
                code=code,
                option_type=option_type,
                option_space="dhcp4",
                vendor_option_space=None,
                is_array=is_array,
                encapsulate="",
                record_types=record_types,
                description=description,
                is_standard=True,
            )


def remove_standard_options(apps, schema_editor):
    """Remove standard options (for migration reversal)."""
    OptionDefinition = apps.get_model("netbox_dhcp_kea_plugin", "OptionDefinition")
    OptionDefinition.objects.filter(is_standard=True).delete()


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
        ("netbox_dhcp_kea_plugin", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(populate_standard_options, remove_standard_options),
        migrations.RunPython(create_standard_hooks, remove_standard_hooks),
    ]
