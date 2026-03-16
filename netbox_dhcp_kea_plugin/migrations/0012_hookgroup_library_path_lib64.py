from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0011_alter_subnet_option_data_alter_subnet_server"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hookgroup",
            name="library_path",
            field=models.CharField(
                blank=True,
                default="/usr/lib64/kea/hooks",
                help_text=(
                    "Base path where hook libraries are installed (e.g., /usr/lib64/kea/hooks). "
                    "Leave empty to use only the library filename."
                ),
                max_length=255,
            ),
        ),
    ]
