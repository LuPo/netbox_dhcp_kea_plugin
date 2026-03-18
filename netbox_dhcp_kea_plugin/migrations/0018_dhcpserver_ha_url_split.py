import urllib.parse

from django.db import migrations, models


def split_ha_url(apps, schema_editor):
    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    for server in DHCPServer.objects.all():
        if not server.ha_url:
            continue
        parsed = urllib.parse.urlparse(server.ha_url)
        server.ha_address = parsed.hostname or ""
        server.ha_port = parsed.port if parsed.port else 8080
        server.ha_tls = parsed.scheme == "https"
        server.save(update_fields=["ha_address", "ha_port", "ha_tls"])


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0017_dhcpserver_control_sockets"),
    ]

    operations = [
        migrations.AddField(
            model_name="dhcpserver",
            name="ha_address",
            field=models.CharField(
                max_length=255,
                blank=True,
                default="",
                help_text="IP address for HA communication",
            ),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ha_port",
            field=models.PositiveIntegerField(
                default=8080,
                null=True,
                blank=True,
                help_text="Port for HA communication",
            ),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ha_tls",
            field=models.BooleanField(
                default=False,
                help_text="Use TLS (HTTPS) for HA communication",
            ),
        ),
        migrations.RunPython(
            split_ha_url,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="dhcpserver",
            name="ha_url",
        ),
    ]
