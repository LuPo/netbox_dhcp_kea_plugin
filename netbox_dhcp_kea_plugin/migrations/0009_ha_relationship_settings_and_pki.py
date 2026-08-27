# Squashed from 0009-0013, none of which was ever released, into the single
# migration that carries a 0.9.0 database to 0.10.0.
#
# The data steps are kept rather than dropped: a database restored at 0008 still
# holds the per-server HA credentials and proxy flag that these move onto the
# relationship, and losing them would silently unauthenticate the HA channel.

from django.db import migrations, models


def move_credentials_to_relationship(apps, schema_editor):
    """Lift each relationship's HA credentials off its member servers.

    The primary is the authority: it is where the rest of the HA configuration
    is already resolved from. Only if the primary has none do we fall back to
    any member that does, so a cluster whose credentials were set on the standby
    alone does not silently lose them.
    """
    DHCPHARelationship = apps.get_model("netbox_dhcp_kea_plugin", "DHCPHARelationship")

    for relationship in DHCPHARelationship.objects.all():
        members = relationship.servers.order_by("name")
        source = members.filter(ha_role="primary").first()
        if source is None or not source.ha_basic_auth_user:
            source = members.exclude(ha_basic_auth_user="").first()
        if source is None:
            continue

        relationship.ha_basic_auth_user = source.ha_basic_auth_user
        relationship.ha_basic_auth_password = source.ha_basic_auth_password
        relationship.save(update_fields=["ha_basic_auth_user", "ha_basic_auth_password"])


def push_credentials_back_to_servers(apps, schema_editor):
    """Reverse: write the shared pair onto every member.

    Every member gets the same values, which is the symmetric configuration the
    forward migration exists to produce — not necessarily the asymmetric one that
    was there before.
    """
    DHCPHARelationship = apps.get_model("netbox_dhcp_kea_plugin", "DHCPHARelationship")

    for relationship in DHCPHARelationship.objects.all():
        relationship.servers.update(
            ha_basic_auth_user=relationship.ha_basic_auth_user,
            ha_basic_auth_password=relationship.ha_basic_auth_password,
        )


def move_proxy_flag_to_relationship(apps, schema_editor):
    """Enable the proxy on any relationship that had it on at least one member.

    A mixed cluster never worked in either direction, so any member with the
    flag set is taken as the intent for the whole relationship rather than
    trying to pick a majority.
    """
    DHCPHARelationship = apps.get_model("netbox_dhcp_kea_plugin", "DHCPHARelationship")

    for relationship in DHCPHARelationship.objects.all():
        if relationship.servers.filter(ha_proxy_enabled=True).exists():
            relationship.ha_proxy_enabled = True
            relationship.save(update_fields=["ha_proxy_enabled"])


def push_proxy_flag_back_to_servers(apps, schema_editor):
    """Reverse: every member takes the relationship's value."""
    DHCPHARelationship = apps.get_model("netbox_dhcp_kea_plugin", "DHCPHARelationship")

    for relationship in DHCPHARelationship.objects.all():
        relationship.servers.update(ha_proxy_enabled=relationship.ha_proxy_enabled)


def _allowed_zone_suffixes():
    from django.conf import settings

    cfg = settings.PLUGINS_CONFIG.get("netbox_dhcp_kea_plugin", {})
    return [s.lstrip(".").lower() for s in cfg.get("pki_allowed_zone_suffixes") or []]


def link_existing_dns_records(apps, schema_editor):
    """Seed pki_fqdn from a deliberate DNS record naming the server's own IP.

    Deliberately conservative. Only an *unmanaged*, active A/AAAA record whose
    address equals the server's IP is used:

    - Managed records are excluded because netbox_dns regenerates them from IPAM
      and they carry the host's IPAM name, not the service name a certificate is
      issued for. Linking one would produce a confidently wrong pin, which fails
      later at the TLS handshake — worse than a blank field, which fails loudly
      at save time as soon as the proxy is enabled.
    - CNAMEs cannot be matched at all: they carry no address (``ip_address`` is
      None for anything that is not an address record). The PKI convention is a
      service CNAME, so most hosts are expected to stay blank here and have the
      name set by an operator.

    No-ops when netbox_dns is not installed.
    """
    try:
        Record = apps.get_model("netbox_dns", "Record")
    except LookupError:
        return

    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    suffixes = _allowed_zone_suffixes()

    for server in DHCPServer.objects.exclude(ip_address=None).select_related("ip_address"):
        address = getattr(server.ip_address, "address", None)
        if address is None:
            continue

        candidates = Record.objects.filter(
            ip_address=str(address.ip),
            managed=False,
            status="active",
            type__in=("A", "AAAA"),
        ).order_by("name")

        for record in candidates:
            # Normalised exactly as the model does: no trailing dot, lower-case.
            fqdn = (record.fqdn or "").strip().rstrip(".").lower()
            if not fqdn:
                continue
            if suffixes and not any(fqdn.endswith(suffix) for suffix in suffixes):
                continue
            server.pki_fqdn = fqdn
            server.save(update_fields=["pki_fqdn"])
            break


def clear_pki_fqdn(apps, schema_editor):
    """Reverse: the column is about to be dropped, so just blank it."""
    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    DHCPServer.objects.update(pki_fqdn="")


def bind_existing_identities(apps, schema_editor):
    """Bind servers whose pki_fqdn already matches a DNS record.

    0011 seeded names from address records without recording which record they
    came from, so those identities are unbound. Match them back by name, taking
    only unmanaged records — a managed one carries the host's IPAM name and is
    regenerated, so binding to it would protect and then delete the wrong thing.
    """
    try:
        Record = apps.get_model("netbox_dns", "Record")
    except LookupError:
        return

    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")

    for server in DHCPServer.objects.exclude(pki_fqdn="").filter(pki_record_id=None):
        record = Record.objects.filter(fqdn__iexact=f"{server.pki_fqdn}.", managed=False).order_by("pk").first()
        if record is not None:
            server.pki_record_id = record.pk
            server.save(update_fields=["pki_record_id"])


def unbind_identities(apps, schema_editor):
    """Reverse: the column is about to be dropped; pki_fqdn survives on its own."""
    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    DHCPServer.objects.update(pki_record_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_dhcp_kea_plugin", "0008_dhcpserver_ctrl_socket_proxy_enabled_and_more"),
    ]

    operations = [
        # HA basic-auth credentials: relationship-wide shared secret.
        migrations.AddField(
            model_name="dhcpharelationship",
            name="ha_basic_auth_user",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="dhcpharelationship",
            name="ha_basic_auth_password",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(
            move_credentials_to_relationship,
            push_credentials_back_to_servers,
        ),
        migrations.RemoveField(
            model_name="dhcpserver",
            name="ha_basic_auth_user",
        ),
        migrations.RemoveField(
            model_name="dhcpserver",
            name="ha_basic_auth_password",
        ),
        # Reverse proxy: all or nothing for the cluster.
        migrations.AddField(
            model_name="dhcpharelationship",
            name="ha_proxy_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            move_proxy_flag_to_relationship,
            push_proxy_flag_back_to_servers,
        ),
        migrations.RemoveField(
            model_name="dhcpserver",
            name="ha_proxy_enabled",
        ),
        # PKI identity, then the binding to the DNS record it came from.
        migrations.AddField(
            model_name="dhcpserver",
            name="pki_fqdn",
            field=models.CharField(blank=True, max_length=253),
        ),
        migrations.RunPython(link_existing_dns_records, clear_pki_fqdn),
        migrations.AddField(
            model_name="dhcpserver",
            name="pki_record_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(bind_existing_identities, unbind_identities),
        # Stork exporter behind the proxy.
        migrations.AddField(
            model_name="dhcpserver",
            name="stork_proxy_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
