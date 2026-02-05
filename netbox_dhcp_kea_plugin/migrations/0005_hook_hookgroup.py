import django.contrib.postgres.fields
import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("extras", "0122_charfield_null_choices"),
        ("netbox_dhcp_kea_plugin", "0004_remove_clientclass_local_definitions"),
    ]

    operations = [
        migrations.CreateModel(
            name="Hook",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Human-readable name for this hook library",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "library_name",
                    models.CharField(
                        help_text="Library filename (e.g., libdhcp_lease_cmds.so) or full path for custom hooks",
                        max_length=255,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Description of what this hook library does",
                    ),
                ),
                (
                    "is_standard",
                    models.BooleanField(
                        default=False,
                        help_text="Whether this is a standard KEA hook library (pre-populated, read-only)",
                    ),
                ),
                (
                    "allowed_processes",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("kea-ctrl-agent", "KEA Control Agent"),
                                ("kea-dhcp4", "KEA DHCPv4"),
                                ("kea-dhcp6", "KEA DHCPv6"),
                                ("kea-dhcp-ddns", "KEA DHCP-DDNS"),
                            ],
                            max_length=20,
                        ),
                        default=list,
                        help_text="KEA processes that can load this hook library",
                        size=None,
                    ),
                ),
                (
                    "parameters",
                    models.JSONField(
                        blank=True,
                        help_text="Hook library parameters as JSON (will be passed to KEA configuration)",
                        null=True,
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag"),
                ),
            ],
            options={
                "verbose_name": "Hook",
                "verbose_name_plural": "Hooks",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="HookGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Unique name for this hook group",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Description of this hook group",
                    ),
                ),
                (
                    "library_path",
                    models.CharField(
                        blank=True,
                        default="/usr/lib/kea/hooks",
                        help_text="Base path where hook libraries are installed (e.g., /usr/lib/kea/hooks). Leave empty to use only the library filename.",
                        max_length=255,
                    ),
                ),
                (
                    "hooks",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Hooks included in this group",
                        related_name="hook_groups",
                        to="netbox_dhcp_kea_plugin.hook",
                    ),
                ),
                (
                    "servers",
                    models.ManyToManyField(
                        blank=True,
                        help_text="DHCP servers that use this hook group",
                        related_name="hook_groups",
                        to="netbox_dhcp_kea_plugin.dhcpserver",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag"),
                ),
            ],
            options={
                "verbose_name": "Hook Group",
                "verbose_name_plural": "Hook Groups",
                "ordering": ("name",),
            },
        ),
    ]
