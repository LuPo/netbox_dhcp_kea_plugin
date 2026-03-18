from django.db import migrations, models


def migrate_booleans_to_choice(apps, schema_editor):
    """Convert ctrl_socket_http_enabled + ctrl_socket_unix_enabled booleans into ctrl_socket_type."""
    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    for server in DHCPServer.objects.all():
        http_on = server.ctrl_socket_http_enabled
        unix_on = server.ctrl_socket_unix_enabled
        if http_on and unix_on:
            server.ctrl_socket_type = "both"
        elif http_on:
            server.ctrl_socket_type = "http"
        elif unix_on:
            server.ctrl_socket_type = "unix"
        else:
            server.ctrl_socket_type = ""
        server.save(update_fields=["ctrl_socket_type"])


def migrate_choice_to_booleans(apps, schema_editor):
    """Reverse: convert ctrl_socket_type back into the two boolean fields."""
    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    for server in DHCPServer.objects.all():
        server.ctrl_socket_http_enabled = server.ctrl_socket_type in ("http", "both")
        server.ctrl_socket_unix_enabled = server.ctrl_socket_type in ("unix", "both")
        server.save(update_fields=["ctrl_socket_http_enabled", "ctrl_socket_unix_enabled"])


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0019_storkserver_stork_version_default"),
    ]

    operations = [
        # 1. Add the new choice field
        migrations.AddField(
            model_name="dhcpserver",
            name="ctrl_socket_type",
            field=models.CharField(
                max_length=10,
                choices=[
                    ("", "Disabled"),
                    ("http", "HTTP"),
                    ("unix", "Unix"),
                    ("both", "HTTP + Unix"),
                ],
                blank=True,
                default="",
                verbose_name="Control socket type",
                help_text="Type of control socket to enable for this KEA server",
            ),
        ),
        # 2. Populate from existing booleans
        migrations.RunPython(
            migrate_booleans_to_choice,
            migrate_choice_to_booleans,
        ),
        # 3. Remove old boolean fields
        migrations.RemoveField(
            model_name="dhcpserver",
            name="ctrl_socket_http_enabled",
        ),
        migrations.RemoveField(
            model_name="dhcpserver",
            name="ctrl_socket_unix_enabled",
        ),
    ]
