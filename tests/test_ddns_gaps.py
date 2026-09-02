"""DDNS gaps found by audit: the vault backend, missing Kea keys, validation.

Fixtures are reused from test_ddns_models, which already builds a D2 daemon,
a TSIG key and a zone with a resolvable nameserver.
"""

import pytest
from django.core.exceptions import ValidationError

from tests.test_ddns_models import (  # noqa: F401
    d2_daemon,
    d2_listener_ip,
    forward_zone,
    name_server,
    tsig_key,
)


@pytest.mark.django_db
class TestVaultSecretBackend:
    """The vault option was selectable but had no resolver, so choosing it
    made config generation raise TSIGSecretBackendError.

    NetBox never contacts the secret store: the backend emits a reference for
    the deployment to substitute on the target.
    """

    def _key(self, **kwargs):
        from netbox_dhcp_kea_plugin.models import TSIGKey

        defaults = {
            "name": "vault-key",
            "algorithm": "HMAC-SHA256",
            "secret_backend": "vault",
            "secret_ref": "kea/tsig/vault-key#secret",
        }
        defaults.update(kwargs)
        return TSIGKey.objects.create(**defaults)

    def test_it_emits_a_reference_not_a_secret(self):
        key = self._key()

        entry = key.to_kea_dict()

        assert entry["secret"] == "${BAO:kea/tsig/vault-key#secret}"
        assert entry["name"] == "vault-key"
        assert entry["algorithm"] == "hmac-sha256"

    def test_the_stored_secret_is_never_emitted(self):
        """Even if a plaintext value lingers on the row, vault must not use it."""
        key = self._key(name="vault-with-leftover", secret_plaintext="c3VwZXItc2VjcmV0")

        assert "c3VwZXItc2VjcmV0" not in key.to_kea_dict()["secret"]

    def test_the_template_is_configurable(self, settings, monkeypatch):
        monkeypatch.setitem(
            settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"],
            "ddns_secret_reference_template",
            "VAULT[{ref}]",
        )
        key = self._key(name="vault-custom")

        assert key.to_kea_dict()["secret"] == "VAULT[kea/tsig/vault-key#secret]"

    def test_a_missing_reference_is_reported_clearly(self):
        from netbox_dhcp_kea_plugin.models import TSIGKey
        from netbox_dhcp_kea_plugin.secret_backends import TSIGSecretBackendError

        key = TSIGKey(name="vault-noref", algorithm="HMAC-SHA256", secret_backend="vault")

        with pytest.raises(TSIGSecretBackendError) as exc:
            key.to_kea_dict()

        assert "no secret reference" in str(exc.value)

    def test_plaintext_still_returns_the_secret(self):
        import base64

        secret = base64.b64encode(b"x" * 32).decode()  # HMAC-SHA256 natural length
        key = self._key(
            name="plain-key", secret_backend="plaintext", secret_ref="", secret_plaintext=secret
        )

        assert key.to_kea_dict()["secret"] == secret

    def test_the_daemon_reports_that_substitution_is_needed(
        self, d2_daemon, forward_zone, name_server  # noqa: F811
    ):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        assert d2_daemon.requires_secret_substitution() is False

        forward_zone.nameservers.add(name_server)
        DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=forward_zone, tsig_key=self._key())

        assert d2_daemon.requires_secret_substitution() is True

    def test_a_plaintext_only_daemon_needs_no_substitution(
        self, d2_daemon, forward_zone, name_server, tsig_key  # noqa: F811
    ):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        forward_zone.nameservers.add(name_server)
        DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=forward_zone, tsig_key=tsig_key)

        assert d2_daemon.requires_secret_substitution() is False


@pytest.mark.django_db
class TestMissingKeaKeys:
    """Keys Kea accepts that the plugin never emitted."""

    def test_dns_server_timeout_is_emitted_when_set(self, d2_daemon):  # noqa: F811
        d2_daemon.dns_server_timeout = 1000
        d2_daemon.save()

        assert d2_daemon.to_kea_dict()["DhcpDdns"]["dns-server-timeout"] == 1000

    def test_it_is_absent_when_unset(self, d2_daemon):  # noqa: F811
        assert "dns-server-timeout" not in d2_daemon.to_kea_dict()["DhcpDdns"]

    def test_max_queue_size_is_emitted_when_set(self, dhcp_server_factory, d2_daemon):  # noqa: F811
        server = dhcp_server_factory(name="kea-ddns-queue", ip_suffix=221)
        server.d2_daemon = d2_daemon
        server.ddns_max_queue_size = 2048
        server.save()

        assert server.effective_ddns_block()["max-queue-size"] == 2048

    def test_max_queue_size_is_absent_when_unset(self, dhcp_server_factory, d2_daemon):  # noqa: F811
        server = dhcp_server_factory(name="kea-ddns-noqueue", ip_suffix=222)
        server.d2_daemon = d2_daemon
        server.save()

        assert "max-queue-size" not in server.effective_ddns_block()

    def test_the_ddns_block_carries_user_context(self, dhcp_server_factory, d2_daemon):  # noqa: F811
        server = dhcp_server_factory(name="kea-ddns-ctx", ip_suffix=223)
        server.d2_daemon = d2_daemon
        server.ddns_user_context = {"note": "primary"}
        server.save()

        assert server.effective_ddns_block()["user-context"] == {"note": "primary"}

    def test_a_domain_carries_user_context(
        self, d2_daemon, forward_zone, name_server  # noqa: F811
    ):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        forward_zone.nameservers.add(name_server)
        domain = DDNSDomain.objects.create(
            d2_daemon=d2_daemon, zone=forward_zone, user_context={"owner": "netops"}
        )

        assert domain.to_kea_dict()["user-context"] == {"owner": "netops"}


@pytest.mark.django_db
class TestDomainNeedsAResolvableNameserver:
    """An empty dns-servers list is a config KEA refuses to load.

    to_kea_dict() silently skips nameservers with no resolvable address, so a
    zone with none rendered "dns-servers": [] and failed on the server while
    looking correct in NetBox.
    """

    def test_a_zone_with_a_resolvable_nameserver_is_valid(
        self, d2_daemon, forward_zone, name_server  # noqa: F811
    ):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        forward_zone.nameservers.add(name_server)
        domain = DDNSDomain(d2_daemon=d2_daemon, zone=forward_zone)

        domain.clean()

        assert domain.to_kea_dict()["dns-servers"]

    def test_a_zone_with_no_resolvable_nameserver_is_rejected(self, d2_daemon):  # noqa: F811
        from netbox_dns.models import NameServer, View, Zone

        from netbox_dhcp_kea_plugin.models import DDNSDomain

        view, _ = View.objects.get_or_create(name="default")
        soa = NameServer.objects.get_or_create(name="ns-soa.example.net")[0]
        # A zone whose nameserver has no A/AAAA record anywhere.
        zone, _ = Zone.objects.get_or_create(
            name="unresolvable.example.net",
            view=view,
            defaults={"soa_mname": soa, "soa_rname": "hostmaster.example.net"},
        )

        domain = DDNSDomain(d2_daemon=d2_daemon, zone=zone)

        with pytest.raises(ValidationError) as exc:
            domain.clean()

        assert "zone" in exc.value.message_dict
        assert "empty list" in exc.value.message_dict["zone"][0]


@pytest.mark.django_db
class TestDDNSPolicyTTLExclusivity:
    """KEA rejects ddns-ttl alongside ddns-ttl-percent / -min / -max."""

    def _policy(self, **kwargs):
        from netbox_dhcp_kea_plugin.models import DDNSPolicy

        return DDNSPolicy(name="ttl-policy", **kwargs)

    def test_an_absolute_ttl_alone_is_fine(self):
        self._policy(ddns_ttl=600).clean()

    def test_a_percentage_alone_is_fine(self):
        self._policy(ddns_ttl_percent="0.5").clean()

    def test_min_and_max_without_an_absolute_ttl_are_fine(self):
        self._policy(ddns_ttl_min=300, ddns_ttl_max=900).clean()

    @pytest.mark.parametrize(
        "field,value",
        [("ddns_ttl_percent", "0.5"), ("ddns_ttl_min", 300), ("ddns_ttl_max", 900)],
    )
    def test_an_absolute_ttl_conflicts_with_each_of_the_others(self, field, value):
        policy = self._policy(ddns_ttl=600, **{field: value})

        with pytest.raises(ValidationError) as exc:
            policy.clean()

        assert "ddns_ttl" in exc.value.message_dict
        assert field in exc.value.message_dict
