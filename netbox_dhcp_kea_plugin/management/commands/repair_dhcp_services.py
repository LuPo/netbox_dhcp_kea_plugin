"""Idempotent repair for DHCPServer.service back-references.

For every DHCPServer that has a ``service_template`` but a null ``service`` FK,
link the existing matching Application Service if one exists, otherwise create
it from the template. Safe to run repeatedly — produces no duplicates.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from netbox_dhcp_kea_plugin.models import DHCPServer


class Command(BaseCommand):
    help = "Relink DHCPServer.service for servers that have a template but a null service FK."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        candidates = DHCPServer.objects.filter(
            service_template__isnull=False, service__isnull=True
        )

        if not candidates.exists():
            self.stdout.write(self.style.SUCCESS("Nothing to repair — all templated servers have a service FK."))
            return

        repaired = 0
        skipped = 0
        for server in candidates:
            if dry_run:
                # Resolve what the link target would be without writing.
                target = self._preview_target(server)
                if target is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[dry-run] {server.name} (id={server.pk}): no parent object on IP — would skip."
                        )
                    )
                    skipped += 1
                else:
                    verb = "link existing" if target.pk else "create"
                    self.stdout.write(
                        f"[dry-run] {server.name} (id={server.pk}): would {verb} Service "
                        f"'{server.service_template.name}'."
                    )
                    repaired += 1
                continue

            with transaction.atomic():
                server._create_service_from_template()
                server.refresh_from_db(fields=["service"])

            if server.service_id is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"{server.name} (id={server.pk}): could not link a service "
                        "(IP has no parent object). Skipped."
                    )
                )
                skipped += 1
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{server.name} (id={server.pk}): linked Service id={server.service_id}."
                    )
                )
                repaired += 1

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(f"{prefix}Done. {repaired} repaired, {skipped} skipped.")
        )

    @staticmethod
    def _preview_target(server):
        """Return the Service that would be linked (existing or a sentinel with
        pk=None meaning 'would create'), or None if the IP has no parent."""
        from django.contrib.contenttypes.models import ContentType

        from ipam.models import Service

        if not server.ip_address or not server.ip_address.assigned_object:
            return None
        parent = server.ip_address.assigned_object.parent_object
        if not parent:
            return None
        existing = Service.objects.filter(
            parent_object_type=ContentType.objects.get_for_model(parent),
            parent_object_id=parent.pk,
            name=server.service_template.name,
            protocol=server.service_template.protocol,
        ).first()
        return existing or Service()  # Service() has pk=None → "would create"
