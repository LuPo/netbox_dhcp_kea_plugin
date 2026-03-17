import django.db.models.deletion
from django.db import migrations, models


def migrate_m2m_to_fk(apps, schema_editor):
    """
    Copy data from the StorkAgentGroup.servers M2M table into the new
    DHCPServer.stork_agent_group FK column.

    If a DHCPServer appears in more than one group (shouldn't happen but
    guard against it), the first group (by pk) wins.
    """
    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    StorkAgentGroup = apps.get_model("netbox_dhcp_kea_plugin", "StorkAgentGroup")

    # The auto-created M2M through table follows Django's naming convention:
    #   <app_label>_<model_lower>_<m2m_field_name>
    # i.e. netbox_dhcp_kea_plugin_storkagentgroup_servers
    ThroughModel = StorkAgentGroup.servers.through

    # Build a mapping: dhcpserver_id -> first storkagentgroup_id
    server_to_group = {}
    for row in ThroughModel.objects.order_by("storkagentgroup_id"):
        sid = row.dhcpserver_id
        gid = row.storkagentgroup_id
        if sid not in server_to_group:
            server_to_group[sid] = gid

    if server_to_group:
        for server_id, group_id in server_to_group.items():
            DHCPServer.objects.filter(pk=server_id).update(stork_agent_group_id=group_id)


def migrate_fk_to_m2m(apps, schema_editor):
    """
    Reverse: copy the FK back into the M2M table so we can roll back.
    """
    DHCPServer = apps.get_model("netbox_dhcp_kea_plugin", "DHCPServer")
    StorkAgentGroup = apps.get_model("netbox_dhcp_kea_plugin", "StorkAgentGroup")
    ThroughModel = StorkAgentGroup.servers.through

    for server in DHCPServer.objects.filter(stork_agent_group__isnull=False):
        ThroughModel.objects.get_or_create(
            storkagentgroup_id=server.stork_agent_group_id,
            dhcpserver_id=server.pk,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dhcp_kea_plugin", "0014_storkagentgroup_unify_prometheus_fields"),
    ]

    operations = [
        # 1. Add the nullable FK column on DHCPServer
        migrations.AddField(
            model_name="dhcpserver",
            name="stork_agent_group",
            field=models.ForeignKey(
                blank=True,
                help_text="Stork agent group configuration for this DHCP server",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="servers_new",  # temporary related_name to avoid clash with existing M2M
                to="netbox_dhcp_kea_plugin.storkagentgroup",
            ),
        ),
        # 2. Copy M2M rows into the new FK column
        migrations.RunPython(migrate_m2m_to_fk, migrate_fk_to_m2m),
        # 3. Drop the M2M field from StorkAgentGroup
        migrations.RemoveField(
            model_name="storkagentgroup",
            name="servers",
        ),
        # 4. Update the FK to use the final related_name="servers"
        migrations.AlterField(
            model_name="dhcpserver",
            name="stork_agent_group",
            field=models.ForeignKey(
                blank=True,
                help_text="Stork agent group configuration for this DHCP server",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="servers",
                to="netbox_dhcp_kea_plugin.storkagentgroup",
            ),
        ),
    ]
