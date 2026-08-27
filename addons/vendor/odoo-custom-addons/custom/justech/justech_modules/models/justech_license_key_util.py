import hashlib


def hash_license_key(env, key):
    """Return stable SHA-256 hex digest for a license key (never store plaintext)."""
    pepper = (
        env["ir.config_parameter"]
        .sudo()
        .get_param("justech_modules.license_pepper", "justech-license-pepper-v1")
    )
    payload = f"{pepper}:{key}".encode()
    return hashlib.sha256(payload).hexdigest()


def fingerprint_from_hash(key_hash):
    """Non-reversible display token for managers."""
    if not key_hash:
        return "—"
    return f"JT-••••-{key_hash[-8:].upper()}"
