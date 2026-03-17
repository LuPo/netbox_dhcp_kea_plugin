import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("extras", "0001_initial"),
        ("ipam", "0001_initial"),
        ("netbox_dhcp_kea_plugin", "0012_hookgroup_library_path_lib64"),
    ]

    operations = [
        migrations.CreateModel(
            name="StorkServer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                ("name", models.CharField(max_length=100, unique=True, help_text="Name of this Stork server instance")),
                ("description", models.CharField(blank=True, max_length=200)),
                (
                    "status",
                    models.CharField(
                        default="active",
                        help_text="Operational status of this Stork server",
                        max_length=50,
                        verbose_name="status",
                    ),
                ),
                (
                    "ip_address",
                    models.ForeignKey(
                        help_text="IP address of the Stork server (from NetBox IPAM)",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stork_servers",
                        to="ipam.ipaddress",
                    ),
                ),
                (
                    "rest_port",
                    models.PositiveIntegerField(
                        default=8080,
                        help_text="Port for the Stork REST API and Web UI (default: 8080)",
                    ),
                ),
                (
                    "rest_base_url",
                    models.CharField(
                        blank=True,
                        default="/",
                        help_text="Base URL path if Stork UI is served from a subdirectory (e.g., /stork/)",
                        max_length=255,
                    ),
                ),
                (
                    "use_tls",
                    models.BooleanField(
                        default=False,
                        help_text="Whether the Stork server REST API uses TLS/SSL",
                    ),
                ),
                (
                    "db_host",
                    models.CharField(
                        default="localhost",
                        help_text="PostgreSQL database host for Stork",
                        max_length=255,
                    ),
                ),
                (
                    "db_port",
                    models.PositiveIntegerField(
                        default=5432,
                        help_text="PostgreSQL database port",
                    ),
                ),
                (
                    "db_name",
                    models.CharField(
                        default="stork",
                        help_text="PostgreSQL database name",
                        max_length=100,
                    ),
                ),
                (
                    "db_ssl_mode",
                    models.CharField(
                        choices=[
                            ("disable", "Disable"),
                            ("require", "Require"),
                            ("verify-ca", "Verify CA"),
                            ("verify-full", "Verify Full"),
                        ],
                        default="disable",
                        help_text="SSL mode for the database connection",
                        max_length=20,
                    ),
                ),
                (
                    "enable_metrics",
                    models.BooleanField(
                        default=False,
                        help_text="Enable the Prometheus /metrics endpoint on the Stork server",
                    ),
                ),
                (
                    "grafana_url",
                    models.URLField(
                        blank=True,
                        help_text="URL of the Grafana instance integrated with this Stork server",
                    ),
                ),
                (
                    "default_agent_registration",
                    models.CharField(
                        choices=[
                            ("agent-token", "Agent Token (manual approval in UI)"),
                            ("server-token", "Server Token (auto-approval)"),
                        ],
                        default="agent-token",
                        help_text="Default method for registering new Stork agents",
                        max_length=20,
                    ),
                ),
                (
                    "stork_version",
                    models.CharField(
                        blank=True,
                        help_text="Installed Stork server version (e.g., 1.18.0)",
                        max_length=20,
                    ),
                ),
                ("tags", taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag")),
            ],
            options={
                "ordering": ("name",),
                "verbose_name": "Stork Server",
                "verbose_name_plural": "Stork Servers",
            },
        ),
        migrations.CreateModel(
            name="StorkAgentGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=100,
                        unique=True,
                        help_text="Name of this Stork agent configuration group",
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, help_text="Description of this agent group configuration"),
                ),
                (
                    "stork_server",
                    models.ForeignKey(
                        blank=True,
                        help_text="The Stork server these agents report to (not required for Prometheus-only mode)",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="agent_groups",
                        to="netbox_dhcp_kea_plugin.storkserver",
                    ),
                ),
                (
                    "operating_mode",
                    models.CharField(
                        choices=[
                            ("both", "Both (Stork + Prometheus)"),
                            ("prometheus-only", "Prometheus Only"),
                            ("stork-only", "Stork Only"),
                        ],
                        default="both",
                        help_text="Agent operating mode: both roles, Prometheus exporter only, or Stork communication only",
                        max_length=20,
                    ),
                ),
                (
                    "agent_port",
                    models.PositiveIntegerField(
                        default=8080,
                        help_text="Port the Stork agent listens on for gRPC connections from the server (default: 8080)",
                    ),
                ),
                (
                    "prometheus_exporter_address",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="IP address or hostname for the Prometheus exporter to listen on (e.g., 0.0.0.0). Required when operating mode includes Prometheus.",
                        max_length=255,
                    ),
                ),
                (
                    "prometheus_exporter_port",
                    models.PositiveIntegerField(
                        blank=True,
                        default=None,
                        help_text="Port for the Prometheus statistics exporter (e.g., 9547). Required when operating mode includes Prometheus.",
                        null=True,
                    ),
                ),
                (
                    "prometheus_per_subnet_stats",
                    models.BooleanField(
                        default=True,
                        help_text="Enable per-subnet statistics export to Prometheus (disable for very large networks)",
                    ),
                ),
                (
                    "skip_tls_cert_verification",
                    models.BooleanField(
                        default=False,
                        help_text="Skip TLS certificate verification when the agent connects to Kea over TLS with self-signed certificates",
                    ),
                ),
                (
                    "servers",
                    models.ManyToManyField(
                        blank=True,
                        help_text="DHCP servers that use this Stork agent configuration",
                        related_name="stork_agent_groups",
                        to="netbox_dhcp_kea_plugin.dhcpserver",
                    ),
                ),
                ("tags", taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag")),
            ],
            options={
                "ordering": ("name",),
                "verbose_name": "Stork Agent Group",
                "verbose_name_plural": "Stork Agent Groups",
            },
        ),
    ]
