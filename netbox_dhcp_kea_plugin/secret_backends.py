"""TSIG key secret backends.

Abstracts secret storage so an external secret store can be plugged in without
schema changes. Two backends ship: ``plaintext`` returns the secret held in the NetBox
database, and ``vault`` returns a *reference* for the deployment to substitute
on the target — NetBox never contacts the secret store itself.

Register additional backends by calling ``register_backend(name, resolver)``
where ``resolver`` is a callable ``(tsig_key) -> str``.
"""

from netbox.plugins.utils import get_plugin_config


class TSIGSecretBackendError(Exception):
    """Raised when a secret cannot be resolved by the configured backend."""


def _plaintext_backend(tsig_key):
    if not tsig_key.secret_plaintext:
        raise TSIGSecretBackendError(
            f"TSIG key '{tsig_key.name}' has no plaintext secret stored."
        )
    return tsig_key.secret_plaintext


def _vault_backend(tsig_key):
    """Return a *reference* to the secret, never the secret itself.

    NetBox deliberately does not talk to OpenBao. It emits a placeholder built
    from ``secret_ref``, and the deployment substitutes it on the target, where
    an agent already holds a certificate and a token. That keeps the secret out
    of NetBox's database, its API responses, and every archived copy of the
    rendered configuration — and removes any token lifecycle from NetBox.

    The rendered configuration is therefore a *template*: still valid JSON, so
    ``kea-dhcp-ddns -t`` parses it, but not deployable until substituted.
    """
    from netbox.plugins.utils import get_plugin_config

    if not tsig_key.secret_ref:
        raise TSIGSecretBackendError(
            f"TSIG key '{tsig_key.name}' uses the vault backend but has no secret reference."
        )

    template = get_plugin_config("netbox_dhcp_kea_plugin", "ddns_secret_reference_template")
    # str.replace rather than str.format: the default template contains "${BAO:"
    # and format() would read "{BAO:" as a field with a format spec.
    return template.replace("{ref}", tsig_key.secret_ref)


TSIG_SECRET_BACKENDS = {
    "plaintext": _plaintext_backend,
    "vault": _vault_backend,
}


def is_reference_backend(name):
    """Whether this backend emits a placeholder rather than a usable secret."""
    return name == "vault"


def backend_name_for(tsig_key):
    """The backend a key resolves through: its own, else the plugin-wide default."""
    return tsig_key.secret_backend or get_plugin_config("netbox_dhcp_kea_plugin", "ddns_secret_backend")


def register_backend(name, resolver):
    """Register a new secret backend.

    ``resolver`` receives the ``TSIGKey`` instance and must return the raw
    secret as a string.
    """
    TSIG_SECRET_BACKENDS[name] = resolver


def resolve_secret(tsig_key):
    """Resolve the raw secret for a TSIGKey via its configured backend.

    Falls back to the plugin-wide default (``ddns_secret_backend``) when the
    key doesn't pin its own backend.
    """
    backend_name = backend_name_for(tsig_key)
    try:
        backend = TSIG_SECRET_BACKENDS[backend_name]
    except KeyError as exc:
        raise TSIGSecretBackendError(
            f"Unknown TSIG secret backend '{backend_name}'. "
            f"Available: {sorted(TSIG_SECRET_BACKENDS)}"
        ) from exc
    return backend(tsig_key)
