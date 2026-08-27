from . import models
from . import services
from . import wizards


def post_init_hook(env):
    env["justech.do.purchase.emission.config"].ensure_configs_for_companies()
    user = env["res.users"]._justech_find_fiscal_regularization_default()
    if user:
        companies = env["res.company"].search(
            [("justech_do_fiscal_regularization_user_id", "=", False)]
        )
        if companies:
            companies.write({"justech_do_fiscal_regularization_user_id": user.id})


def _assign_fiscal_regularization_responsible(env):
    """Post-migrate / upgrade helper — no hardcode de UID."""
    user = env["res.users"]._justech_find_fiscal_regularization_default()
    if not user:
        return
    companies = env["res.company"].search(
        [("justech_do_fiscal_regularization_user_id", "=", False)]
    )
    companies.write({"justech_do_fiscal_regularization_user_id": user.id})
