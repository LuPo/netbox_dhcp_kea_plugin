from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0002_optiondefinition_is_standard"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clientclass",
            name="test_expression",
            field=models.TextField(
                blank=True,
                help_text="KEA test expression for client classification (e.g., \"option[60].text == 'MS-UC-Client'\"). Leave empty for unconditional classes that always match when evaluated.",
            ),
        ),
        migrations.AddField(
            model_name="clientclass",
            name="only_in_additional_list",
            field=models.BooleanField(
                default=False,
                help_text="When enabled, this class is only evaluated when explicitly listed in a subnet's evaluate-additional-classes, not for every packet. The class is still defined in the server's global client-classes, but KEA won't auto-evaluate it.",
            ),
        ),
    ]
