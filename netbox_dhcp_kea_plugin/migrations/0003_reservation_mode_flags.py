"""Add reservation mode flags to Subnet and DHCPServer.

Subnet flags are nullable (None = inherit from server, True/False = explicit override).
DHCPServer flags are non-nullable and serve as global Dhcp4-level defaults.
"""

import netbox_dhcp_kea_plugin.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_dhcp_kea_plugin", "0002_populate_standard_data"),
    ]

    operations = [
        # Subnet: nullable reservation flags (None = inherit from server)
        migrations.AddField(
            model_name="subnet",
            name="reservations_global",
            field=models.BooleanField(
                null=True,
                blank=True,
                default=None,
                verbose_name="Reservations Global",
                help_text="Look for host reservations in the global scope. Leave blank to inherit from server.",
            ),
        ),
        migrations.AddField(
            model_name="subnet",
            name="reservations_in_subnet",
            field=models.BooleanField(
                null=True,
                blank=True,
                default=None,
                verbose_name="Reservations In-Subnet",
                help_text="Look for host reservations within this subnet. Leave blank to inherit from server.",
            ),
        ),
        migrations.AddField(
            model_name="subnet",
            name="reservations_out_of_pool",
            field=models.BooleanField(
                null=True,
                blank=True,
                default=None,
                verbose_name="Reservations Out-of-Pool",
                help_text="Exclude reserved addresses from dynamic pool allocation. Leave blank to inherit from server.",
            ),
        ),
        migrations.AddField(
            model_name="subnet",
            name="reservations_only",
            field=models.BooleanField(
                default=netbox_dhcp_kea_plugin.models.get_default_reservations_only,
                verbose_name="Reservations Only",
                help_text="Disable dynamic pool allocation — only reserved hosts will receive an IP from this subnet",
            ),
        ),
        # DHCPServer: non-nullable reservation flags (global Dhcp4 defaults)
        migrations.AddField(
            model_name="dhcpserver",
            name="reservations_global",
            field=models.BooleanField(
                default=netbox_dhcp_kea_plugin.models.get_default_reservations_global,
                verbose_name="Reservations Global",
                help_text="Default: look for host reservations in the global scope (subnets can override)",
            ),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="reservations_in_subnet",
            field=models.BooleanField(
                default=netbox_dhcp_kea_plugin.models.get_default_reservations_in_subnet,
                verbose_name="Reservations In-Subnet",
                help_text="Default: look for host reservations within subnets (subnets can override)",
            ),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="reservations_out_of_pool",
            field=models.BooleanField(
                default=netbox_dhcp_kea_plugin.models.get_default_reservations_out_of_pool,
                verbose_name="Reservations Out-of-Pool",
                help_text="Default: exclude reserved addresses from dynamic pool allocation (subnets can override)",
            ),
        ),
    ]
