from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0007_dhcpserver_status"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="PrefixDHCPConfig",
            new_name="Subnet",
        ),
    ]
