from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0018_dhcpserver_ha_url_split"),
    ]

    operations = [
        migrations.AlterField(
            model_name="storkserver",
            name="stork_version",
            field=models.CharField(
                blank=True,
                default="stable",
                help_text="Stork server version (e.g., 2.4.0 or 'stable')",
                max_length=20,
            ),
        ),
    ]
