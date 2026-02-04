from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0003_clientclass_test_expression_optional"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="clientclass",
            name="local_definitions",
        ),
    ]
