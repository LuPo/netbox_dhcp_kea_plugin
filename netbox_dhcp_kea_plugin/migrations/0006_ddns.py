import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("extras", "0134_owner"),
        ("ipam", "0086_gfk_indexes"),
        ("netbox_dhcp_kea_plugin", "0005_optiondata_record_manual_fields"),
        ("netbox_dns", "0001_squashed_netbox_dns_0_22"),
    ]

    operations = [
        migrations.CreateModel(
            name="TSIGKey",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("algorithm", models.CharField(default="HMAC-SHA256", max_length=20)),
                ("digest_bits", models.PositiveIntegerField(blank=True, null=True)),
                ("secret_backend", models.CharField(default="plaintext", max_length=20)),
                (
                    "secret_plaintext",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                (
                    "secret_ref",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag"),
                ),
            ],
            options={
                "verbose_name": "TSIG Key",
                "verbose_name_plural": "TSIG Keys",
                "ordering": ("name",),
                "permissions": [("view_secret_tsigkey", "Can view TSIG key plaintext secret")],
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="D2Daemon",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("port", models.PositiveIntegerField(default=53001)),
                (
                    "control_socket_path",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                ("ncr_protocol", models.CharField(default="UDP", max_length=3)),
                ("ncr_format", models.CharField(default="JSON", max_length=4)),
                (
                    "ip_address",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="d2_daemons",
                        to="ipam.ipaddress",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag"),
                ),
            ],
            options={
                "verbose_name": "D2 Daemon",
                "verbose_name_plural": "D2 Daemons",
                "ordering": ("name",),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="DDNSPolicy",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("ddns_send_updates", models.BooleanField(blank=True, null=True)),
                ("ddns_override_no_update", models.BooleanField(blank=True, null=True)),
                (
                    "ddns_override_client_update",
                    models.BooleanField(blank=True, null=True),
                ),
                (
                    "ddns_replace_client_name",
                    models.CharField(blank=True, default="", max_length=20),
                ),
                (
                    "ddns_generated_prefix",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "ddns_qualifying_suffix",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "hostname_char_set",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "hostname_char_replacement",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("ddns_update_on_renew", models.BooleanField(blank=True, null=True)),
                (
                    "ddns_conflict_resolution_mode",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                (
                    "ddns_ttl_percent",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=6, null=True),
                ),
                ("ddns_ttl", models.PositiveIntegerField(blank=True, null=True)),
                ("ddns_ttl_min", models.PositiveIntegerField(blank=True, null=True)),
                ("ddns_ttl_max", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "tags",
                    taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag"),
                ),
            ],
            options={
                "verbose_name": "DDNS Policy",
                "verbose_name_plural": "DDNS Policies",
                "ordering": ("name",),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name="DDNSDomain",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                (
                    "d2_daemon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="domains",
                        to="netbox_dhcp_kea_plugin.d2daemon",
                    ),
                ),
                (
                    "zone",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="netbox_dns.zone",
                    ),
                ),
                (
                    "tsig_key",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="domains",
                        to="netbox_dhcp_kea_plugin.tsigkey",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag"),
                ),
            ],
            options={
                "verbose_name": "DDNS Domain",
                "verbose_name_plural": "DDNS Domains",
                "ordering": ("d2_daemon", "zone"),
                "unique_together": {("d2_daemon", "zone")},
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="d2_daemon",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="servers",
                to="netbox_dhcp_kea_plugin.d2daemon",
            ),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ddns_enable_updates",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ddns_sender_ip",
            field=models.CharField(blank=True, default="", max_length=45),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ddns_sender_port",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dhcpserver",
            name="ddns_policy",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="servers",
                to="netbox_dhcp_kea_plugin.ddnspolicy",
            ),
        ),
        migrations.AddField(
            model_name="dhcpharelationship",
            name="d2_daemon",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ha_relationships",
                to="netbox_dhcp_kea_plugin.d2daemon",
            ),
        ),
        migrations.AddField(
            model_name="dhcpharelationship",
            name="ddns_enable_updates",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="dhcpharelationship",
            name="ddns_policy",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ha_relationships",
                to="netbox_dhcp_kea_plugin.ddnspolicy",
            ),
        ),
        migrations.AddField(
            model_name="subnet",
            name="ddns_policy",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="subnets",
                to="netbox_dhcp_kea_plugin.ddnspolicy",
            ),
        ),
        migrations.AddField(
            model_name="clientclass",
            name="ddns_policy",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="client_classes",
                to="netbox_dhcp_kea_plugin.ddnspolicy",
            ),
        ),
    ]
