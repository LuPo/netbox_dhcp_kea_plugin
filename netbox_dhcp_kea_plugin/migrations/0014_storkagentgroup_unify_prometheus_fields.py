from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0013_storkserver_storkagentgroup"),
    ]

    operations = [
        # Rename columns directly in the database since migration 0013
        # on disk already declares the new names but the DB has the old ones.
        migrations.RunSQL(
            sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" RENAME COLUMN "prometheus_kea_exporter_address" TO "prometheus_exporter_address";',
            reverse_sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" RENAME COLUMN "prometheus_exporter_address" TO "prometheus_kea_exporter_address";',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" RENAME COLUMN "prometheus_kea_exporter_port" TO "prometheus_exporter_port";',
            reverse_sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" RENAME COLUMN "prometheus_exporter_port" TO "prometheus_kea_exporter_port";',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" RENAME COLUMN "prometheus_kea_per_subnet_stats" TO "prometheus_per_subnet_stats";',
            reverse_sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" RENAME COLUMN "prometheus_per_subnet_stats" TO "prometheus_kea_per_subnet_stats";',
        ),
        # Drop the separate BIND9 exporter fields (now unified into the single exporter)
        migrations.RunSQL(
            sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" DROP COLUMN IF EXISTS "prometheus_bind9_exporter_address";',
            reverse_sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ADD COLUMN "prometheus_bind9_exporter_address" varchar(255) NOT NULL DEFAULT \'0.0.0.0\';',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" DROP COLUMN IF EXISTS "prometheus_bind9_exporter_port";',
            reverse_sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ADD COLUMN "prometheus_bind9_exporter_port" integer NOT NULL DEFAULT 9119;',
        ),
        # Drop agent_version (should follow stork server version)
        migrations.RunSQL(
            sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" DROP COLUMN IF EXISTS "agent_version";',
            reverse_sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ADD COLUMN "agent_version" varchar(20) NOT NULL DEFAULT \'\';',
        ),
        # Alter renamed fields to match new model definitions (nullable/blank)
        migrations.RunSQL(
            sql=[
                'ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ALTER COLUMN "prometheus_exporter_address" SET DEFAULT \'\';',
                'ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ALTER COLUMN "prometheus_exporter_address" DROP NOT NULL;',
            ],
            reverse_sql=[
                'ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ALTER COLUMN "prometheus_exporter_address" SET DEFAULT \'0.0.0.0\';',
                'ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ALTER COLUMN "prometheus_exporter_address" SET NOT NULL;',
            ],
        ),
        migrations.RunSQL(
            sql=[
                'ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ALTER COLUMN "prometheus_exporter_port" DROP NOT NULL;',
                'ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ALTER COLUMN "prometheus_exporter_port" SET DEFAULT NULL;',
            ],
            reverse_sql=[
                'ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ALTER COLUMN "prometheus_exporter_port" SET NOT NULL;',
                'ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ALTER COLUMN "prometheus_exporter_port" SET DEFAULT 9547;',
            ],
        ),
    ]
