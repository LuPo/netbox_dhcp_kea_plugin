"""Integrity for the soft bindings between plugin objects and DNS records.

Two fields hold a ``netbox_dns.Record`` primary key without a ForeignKey:
``DHCPServer.pki_record_id`` and ``StorkServer.endpoint_record_id``. A real FK
would make netbox-plugin-dns mandatory for every installation — a string FK to
an app outside ``INSTALLED_APPS`` is a ``fields.E300`` system-check error, which
aborts ``migrate`` and ``runserver``.

These handlers restore what the FK would have enforced, and are connected only
when netbox_dns is importable:

- **The record cannot be deleted while bound** — what ``on_delete=PROTECT``
  would do. Deleting it would leave a name that nothing serves, which for a
  certificate means a client with nothing to verify against.
- **Deleting the owner deletes the record** — it names that host, so it should
  not outlive it. Only when nothing else is bound to it.
- **Renaming the record re-derives the stored name** — the point of binding is
  that the published string cannot drift from what DNS actually serves.

Both bindings behave identically, so they are described once in
``_dns_bindings()`` and the handlers iterate rather than being written twice.
"""

from django.db.models import ProtectedError
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver


def _dns_bindings():
    """Every (model, id field, derived name field) triple bound to a DNS record."""
    from .models import DHCPServer, StorkServer

    return (
        (DHCPServer, "pki_record_id", "pki_fqdn"),
        (StorkServer, "endpoint_record_id", "endpoint_fqdn"),
    )


def connect_dns_signals():
    """Wire the netbox_dns handlers, if that plugin is installed.

    Called from ``DHCPKEAConfig.ready()``. A no-op without netbox_dns, which is
    the supported configuration — names are then typed as free text.
    """
    try:
        from netbox_dns.models import Record as DNSRecord
    except ImportError:
        return False

    @receiver(pre_delete, sender=DNSRecord, dispatch_uid="netbox_dhcp_kea_plugin.protect_bound_record")
    def protect_bound_record(sender, instance, **kwargs):
        holders = []
        protected = set()
        for model, id_field, _ in _dns_bindings():
            bound = model.objects.filter(**{id_field: instance.pk})
            if bound.exists():
                label = model._meta.verbose_name
                holders += [f"{label} {name}" for name in sorted(bound.values_list("name", flat=True))]
                protected |= set(bound)

        if holders:
            raise ProtectedError(
                f"Cannot delete DNS record '{instance}': it is the identity of {', '.join(holders)}. "
                "Clear the record on those objects first.",
                protected,
            )

    @receiver(post_save, sender=DNSRecord, dispatch_uid="netbox_dhcp_kea_plugin.resync_bound_fqdn")
    def resync_bound_fqdn(sender, instance, **kwargs):
        """Keep every published name identical to the record it is bound to."""
        from .models import normalize_fqdn

        fqdn = normalize_fqdn(instance.fqdn)
        for model, id_field, fqdn_field in _dns_bindings():
            stale = model.objects.filter(**{id_field: instance.pk}).exclude(**{fqdn_field: fqdn})
            # update() rather than save(): this must not recurse into the record,
            # and a targeted field write is all that is needed.
            stale.update(**{fqdn_field: fqdn})

    return True


@receiver(post_delete, dispatch_uid="netbox_dhcp_kea_plugin.delete_bound_record")
def delete_bound_record(sender, instance, **kwargs):
    """Delete the DNS record a deleted object was bound to.

    Registered unconditionally but filtered by sender here, because the models
    cannot be imported at module import time. Bulk deletes emit ``post_delete``
    too, so this covers the list-view path as well as the per-object one.
    """
    bindings = _dns_bindings()
    binding = next((b for b in bindings if b[0] is sender), None)
    if binding is None:
        return

    record_id = getattr(instance, binding[1], None)
    if not record_id:
        return

    try:
        from netbox_dns.models import Record as DNSRecord
    except ImportError:
        return

    # Anything else naming itself with the same record keeps it.
    for model, id_field, _ in bindings:
        if model.objects.filter(**{id_field: record_id}).exists():
            return

    DNSRecord.objects.filter(pk=record_id).delete()
