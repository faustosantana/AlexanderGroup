import hashlib
import secrets


def hash_admin_key(env, key):
    """Return stable SHA-256 hex digest for a Justech admin key (never store plaintext)."""
    pepper = (
        env["ir.config_parameter"]
        .sudo()
        .get_param("justech_modules.admin_key_pepper", "justech-admin-pepper-v1")
    )
    payload = f"{pepper}:{key.strip()}".encode()
    return hashlib.sha256(payload).hexdigest()


def fingerprint_from_hash(key_hash):
    if not key_hash:
        return "—"
    return f"JA-••••-{key_hash[-8:].upper()}"


def generate_admin_key():
    """Generate a one-time displayable admin key."""
    return f"JT-{secrets.token_hex(8).upper()}"
