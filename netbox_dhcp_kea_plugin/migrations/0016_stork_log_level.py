from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0015_dhcpserver_stork_agent_group_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="storkserver",
            name="log_level",
            field=models.CharField(
                choices=[
                    ("DEBUG", "Debug"),
                    ("INFO", "Info"),
                    ("WARN", "Warning"),
                    ("ERROR", "Error"),
                ],
                default="INFO",
                help_text="Logging level for the Stork server (DEBUG, INFO, WARN, ERROR)",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="storkagentgroup",
            name="log_level",
            field=models.CharField(
                choices=[
                    ("DEBUG", "Debug"),
                    ("INFO", "Info"),
                    ("WARN", "Warning"),
                    ("ERROR", "Error"),
                ],
                default="INFO",
                help_text="Logging level for the Stork agent (DEBUG, INFO, WARN, ERROR)",
                max_length=10,
            ),
        ),
    ]
