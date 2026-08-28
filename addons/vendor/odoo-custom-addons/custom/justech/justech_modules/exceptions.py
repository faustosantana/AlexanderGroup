from odoo.exceptions import UserError


class JustechLicenseError(UserError):
    """Raised when a Justech feature is not licensed or inactive."""
