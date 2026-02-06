from django.db import migrations, models


def migrate_is_active_to_status(apps, schema_editor):
    """Convert is_active boolean to status CharField."""
    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    for server in DHCPServer.objects.all():
        if server.is_active:
            server.status = "active"
        else:
            server.status = "offline"
        server.save()


def migrate_status_to_is_active(apps, schema_editor):
    """Reverse migration: convert status back to is_active."""
    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    for server in DHCPServer.objects.all():
        server.is_active = server.status == "active"
        server.save()


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0006_populate_standard_hooks"),
    ]

    operations = [
        # Add the new status field with a default value
        migrations.AddField(
            model_name="dhcpserver",
            name="status",
            field=models.CharField(
                default="active",
                max_length=50,
            ),
        ),
        # Migrate data from is_active to status
        migrations.RunPython(migrate_is_active_to_status, migrate_status_to_is_active),
        # Remove the old is_active field
        migrations.RemoveField(
            model_name="dhcpserver",
            name="is_active",
        ),
    ]
