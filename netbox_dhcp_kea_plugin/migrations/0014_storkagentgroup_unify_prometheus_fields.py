from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0013_storkserver_storkagentgroup"),
    ]

    operations = [
        # Rename prometheus_kea_exporter_address -> prometheus_exporter_address (idempotent)
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'netbox_dhcp_kea_plugin_storkagentgroup'
                          AND column_name = 'prometheus_kea_exporter_address'
                    ) THEN
                        ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                            RENAME COLUMN "prometheus_kea_exporter_address" TO "prometheus_exporter_address";
                    END IF;
                END $$;
            """,
            reverse_sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'netbox_dhcp_kea_plugin_storkagentgroup'
                          AND column_name = 'prometheus_exporter_address'
                    ) THEN
                        ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                            RENAME COLUMN "prometheus_exporter_address" TO "prometheus_kea_exporter_address";
                    END IF;
                END $$;
            """,
        ),
        # Rename prometheus_kea_exporter_port -> prometheus_exporter_port (idempotent)
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'netbox_dhcp_kea_plugin_storkagentgroup'
                          AND column_name = 'prometheus_kea_exporter_port'
                    ) THEN
                        ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                            RENAME COLUMN "prometheus_kea_exporter_port" TO "prometheus_exporter_port";
                    END IF;
                END $$;
            """,
            reverse_sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'netbox_dhcp_kea_plugin_storkagentgroup'
                          AND column_name = 'prometheus_exporter_port'
                    ) THEN
                        ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                            RENAME COLUMN "prometheus_exporter_port" TO "prometheus_kea_exporter_port";
                    END IF;
                END $$;
            """,
        ),
        # Rename prometheus_kea_per_subnet_stats -> prometheus_per_subnet_stats (idempotent)
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'netbox_dhcp_kea_plugin_storkagentgroup'
                          AND column_name = 'prometheus_kea_per_subnet_stats'
                    ) THEN
                        ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                            RENAME COLUMN "prometheus_kea_per_subnet_stats" TO "prometheus_per_subnet_stats";
                    END IF;
                END $$;
            """,
            reverse_sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'netbox_dhcp_kea_plugin_storkagentgroup'
                          AND column_name = 'prometheus_per_subnet_stats'
                    ) THEN
                        ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                            RENAME COLUMN "prometheus_per_subnet_stats" TO "prometheus_kea_per_subnet_stats";
                    END IF;
                END $$;
            """,
        ),
        # Drop the separate BIND9 exporter fields (now unified into the single exporter)
        migrations.RunSQL(
            sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" DROP COLUMN IF EXISTS "prometheus_bind9_exporter_address";',
            reverse_sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ADD COLUMN IF NOT EXISTS "prometheus_bind9_exporter_address" varchar(255) NOT NULL DEFAULT \'0.0.0.0\';',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" DROP COLUMN IF EXISTS "prometheus_bind9_exporter_port";',
            reverse_sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ADD COLUMN IF NOT EXISTS "prometheus_bind9_exporter_port" integer NOT NULL DEFAULT 9119;',
        ),
        # Drop agent_version (should follow stork server version)
        migrations.RunSQL(
            sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" DROP COLUMN IF EXISTS "agent_version";',
            reverse_sql='ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup" ADD COLUMN IF NOT EXISTS "agent_version" varchar(20) NOT NULL DEFAULT \'\';',
        ),
        # Alter renamed fields to match new model definitions (nullable/blank) — idempotent
        migrations.RunSQL(
            sql=[
                """
                DO $$
                BEGIN
                    ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                        ALTER COLUMN "prometheus_exporter_address" SET DEFAULT '';
                    ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                        ALTER COLUMN "prometheus_exporter_address" DROP NOT NULL;
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END $$;
                """,
            ],
            reverse_sql=[
                """
                DO $$
                BEGIN
                    ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                        ALTER COLUMN "prometheus_exporter_address" SET DEFAULT '0.0.0.0';
                    ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                        ALTER COLUMN "prometheus_exporter_address" SET NOT NULL;
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END $$;
                """,
            ],
        ),
        migrations.RunSQL(
            sql=[
                """
                DO $$
                BEGIN
                    ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                        ALTER COLUMN "prometheus_exporter_port" DROP NOT NULL;
                    ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                        ALTER COLUMN "prometheus_exporter_port" SET DEFAULT NULL;
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END $$;
                """,
            ],
            reverse_sql=[
                """
                DO $$
                BEGIN
                    ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                        ALTER COLUMN "prometheus_exporter_port" SET NOT NULL;
                    ALTER TABLE "netbox_dhcp_kea_plugin_storkagentgroup"
                        ALTER COLUMN "prometheus_exporter_port" SET DEFAULT 9547;
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END $$;
                """,
            ],
        ),
    ]
