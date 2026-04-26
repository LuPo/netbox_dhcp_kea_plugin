"""TSIG key secret backends.

Abstracts secret storage so a future Vault / external-secret backend can be
plugged in without schema changes. v1 ships only the ``plaintext`` backend,
which returns the value stored in ``TSIGKey.secret_plaintext`` verbatim.

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


TSIG_SECRET_BACKENDS = {
    "plaintext": _plaintext_backend,
}


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
    backend_name = tsig_key.secret_backend or get_plugin_config(
        "netbox_dhcp_kea_plugin", "ddns_secret_backend"
    )
    try:
        backend = TSIG_SECRET_BACKENDS[backend_name]
    except KeyError as exc:
        raise TSIGSecretBackendError(
            f"Unknown TSIG secret backend '{backend_name}'. "
            f"Available: {sorted(TSIG_SECRET_BACKENDS)}"
        ) from exc
    return backend(tsig_key)
