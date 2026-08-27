"""Integrity for the soft binding between a DHCPServer and its PKI DNS record.

``DHCPServer.pki_record_id`` holds a ``netbox_dns.Record`` primary key without a
ForeignKey, because a real FK would make netbox-plugin-dns mandatory for every
installation (a string FK to an app outside ``INSTALLED_APPS`` is a
``fields.E300`` system-check error, which aborts ``migrate`` and ``runserver``).

These handlers restore what the FK would have enforced, and are connected only
when netbox_dns is importable:

- **The record cannot be deleted while bound** — what ``on_delete=PROTECT``
  would do. Deleting it would leave a certificate pinned to a name nothing
  serves, and PKI onboarding refuses names that do not resolve.
- **Deleting the server deletes the record** — the record exists to name that
  host in the PKI, so it should not outlive it. Only when no other server is
  bound to it.
- **Renaming the record re-derives ``pki_fqdn``** — the whole point of the
  binding is that one string cannot drift from the certificate.
"""

from django.db.models import ProtectedError
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver


def connect_dns_signals():
    """Wire the netbox_dns handlers, if that plugin is installed.

    Called from ``DHCPKEAConfig.ready()``. A no-op without netbox_dns, which is
    the supported configuration — the identity is then typed as free text.
    """
    try:
        from netbox_dns.models import Record as DNSRecord
    except ImportError:
        return False

    @receiver(pre_delete, sender=DNSRecord, dispatch_uid="netbox_dhcp_kea_plugin.protect_bound_pki_record")
    def protect_bound_pki_record(sender, instance, **kwargs):
        from .models import DHCPServer

        bound = DHCPServer.objects.filter(pki_record_id=instance.pk)
        if bound.exists():
            names = ", ".join(sorted(bound.values_list("name", flat=True)))
            raise ProtectedError(
                f"Cannot delete DNS record '{instance}': it is the PKI identity of {names}. "
                "Clear the PKI DNS record on those servers first.",
                set(bound),
            )

    @receiver(post_save, sender=DNSRecord, dispatch_uid="netbox_dhcp_kea_plugin.resync_pki_fqdn")
    def resync_pki_fqdn(sender, instance, **kwargs):
        """Keep the published name identical to the record it is bound to."""
        from .models import DHCPServer

        fqdn = DHCPServer.normalize_pki_fqdn(instance.fqdn)
        for server in DHCPServer.objects.filter(pki_record_id=instance.pk).exclude(pki_fqdn=fqdn):
            # update() would skip save(), and this must not recurse into the
            # record; a targeted field update is enough.
            DHCPServer.objects.filter(pk=server.pk).update(pki_fqdn=fqdn)

    return True


@receiver(post_delete, dispatch_uid="netbox_dhcp_kea_plugin.delete_bound_pki_record")
def delete_bound_pki_record(sender, instance, **kwargs):
    """Delete the DNS record a deleted server was bound to.

    Registered unconditionally but filtered by sender here, because DHCPServer
    cannot be imported at module import time. Bulk deletes go through
    ``post_delete`` too, so this covers the list-view path as well as the
    per-object one.
    """
    from .models import DHCPServer

    if sender is not DHCPServer or not instance.pki_record_id:
        return

    try:
        from netbox_dns.models import Record as DNSRecord
    except ImportError:
        return

    # Another server may name itself with the same record; it stays its identity.
    if DHCPServer.objects.filter(pki_record_id=instance.pki_record_id).exists():
        return

    DNSRecord.objects.filter(pk=instance.pki_record_id).delete()
