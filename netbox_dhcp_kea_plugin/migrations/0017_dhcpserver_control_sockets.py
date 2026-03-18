from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0016_stork_log_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="dhcpserver",
            name="ctrl_socket_http_enabled",
            field=models.BooleanField(
                default=False,
                verbose_name="Enable HTTP control socket",
                help_text="Enable the HTTP control socket for this KEA server",
            ),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ctrl_socket_http_address",
            field=models.CharField(
                max_length=255,
                default="127.0.0.1",
                blank=True,
                verbose_name="HTTP socket address",
                help_text="IP address for the HTTP control socket (e.g., 127.0.0.1)",
            ),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ctrl_socket_http_port",
            field=models.PositiveIntegerField(
                default=8000,
                null=True,
                blank=True,
                verbose_name="HTTP socket port",
                help_text="Port number for the HTTP control socket (e.g., 8000)",
            ),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ctrl_socket_unix_enabled",
            field=models.BooleanField(
                default=False,
                verbose_name="Enable Unix control socket",
                help_text="Enable the Unix domain socket for this KEA server",
            ),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ctrl_socket_unix_path",
            field=models.CharField(
                max_length=255,
                default="/var/run/kea/kea-dhcp4-socket",
                blank=True,
                verbose_name="Unix socket path",
                help_text="File path for the Unix domain socket (e.g., /var/run/kea/kea-dhcp4-socket)",
            ),
        ),
    ]
