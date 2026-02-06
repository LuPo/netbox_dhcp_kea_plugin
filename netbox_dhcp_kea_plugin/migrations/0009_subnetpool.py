import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0008_rename_prefixdhcpconfig_to_subnet"),
        ("ipam", "0001_initial"),
        ("extras", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubnetPool",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                (
                    "last_updated",
                    models.DateTimeField(auto_now=True, null=True),
                ),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                (
                    "description",
                    models.CharField(blank=True, max_length=200),
                ),
                (
                    "subnet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subnet_pools",
                        to="netbox_dhcp_kea_plugin.subnet",
                    ),
                ),
                (
                    "ip_range",
                    models.OneToOneField(
                        help_text="NetBox IP Range that defines this pool's address boundaries",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dhcp_pool_config",
                        to="ipam.iprange",
                    ),
                ),
                (
                    "client_class",
                    models.ForeignKey(
                        blank=True,
                        help_text="Client class that restricts which clients can obtain addresses from this pool (KEA client-class)",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pool_restrictions",
                        to="netbox_dhcp_kea_plugin.clientclass",
                    ),
                ),
                (
                    "evaluate_additional_classes",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Additional client classes to evaluate for clients in this pool (KEA evaluate-additional-classes)",
                        related_name="pool_evaluations",
                        to="netbox_dhcp_kea_plugin.clientclass",
                    ),
                ),
                (
                    "option_data",
                    models.ManyToManyField(
                        blank=True,
                        help_text="DHCP options specific to this pool (KEA option-data)",
                        related_name="pool_configs",
                        to="netbox_dhcp_kea_plugin.optiondata",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem",
                        to="extras.Tag",
                    ),
                ),
            ],
            options={
                "verbose_name": "Subnet Pool",
                "verbose_name_plural": "Subnet Pools",
                "ordering": ("subnet", "ip_range"),
            },
        ),
    ]
