from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0004_optiondata_ip_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="optiondata",
            name="record_manual_fields",
            field=models.JSONField(
                blank=True,
                null=True,
                help_text="For record-type options with IP sources: JSON dict mapping field positions to manual values.",
            ),
        ),
    ]
