import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0009_subnetpool"),
    ]

    operations = [
        # 1. Add the new client_class ForeignKey (nullable)
        migrations.AddField(
            model_name="subnet",
            name="client_class",
            field=models.ForeignKey(
                blank=True,
                help_text="Client class that restricts which clients can use this subnet (KEA client-class)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="subnet_restrictions",
                to="netbox_dhcp_kea_plugin.clientclass",
            ),
        ),
        # 2. Rename the M2M field from client_classes to evaluate_additional_classes
        migrations.RenameField(
            model_name="subnet",
            old_name="client_classes",
            new_name="evaluate_additional_classes",
        ),
        # 3. Update the field definition (related_name and help_text) on the renamed M2M
        migrations.AlterField(
            model_name="subnet",
            name="evaluate_additional_classes",
            field=models.ManyToManyField(
                blank=True,
                help_text="Additional client classes to evaluate for clients in this subnet (KEA evaluate-additional-classes)",
                related_name="subnet_evaluations",
                to="netbox_dhcp_kea_plugin.clientclass",
            ),
        ),
    ]
