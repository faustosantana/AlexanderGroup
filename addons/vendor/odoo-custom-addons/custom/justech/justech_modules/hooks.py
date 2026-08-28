def pre_init_hook(cr_or_env):
    """Cleanup duplicates and migrate legacy license_key before constraints apply."""
    cr = getattr(cr_or_env, "cr", cr_or_env)
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'justech_license_company'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        DELETE FROM justech_license_company a
        USING justech_license_company b
        WHERE a.id > b.id
          AND a.license_id = b.license_id
          AND a.company_id = b.company_id
        """
    )
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'justech_license' AND column_name = 'license_key'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'justech_license' AND column_name = 'license_key_hash'
        """
    )
    if not cr.fetchone():
        return
    # Hash migration deferred to post_init (needs env for pepper); column prep only here.


def post_init_hook(env):
    env["justech.license"].migrate_plaintext_license_keys()
    env["justech.license"].backfill_missing_license_hashes()
    env["justech.license.service"].register_platform_seed()
    from .hooks_register import register_all_installed_manifests

    register_all_installed_manifests(env)
    _setup_internal_admin_users(env)


def _setup_internal_admin_users(env):
    """Assign internal groups and bootstrap access shells (no auto keys)."""
    Access = env["justech.admin.access"].sudo()
    groups = [
        env.ref("justech_modules.group_justech_internal_admin"),
        env.ref("justech_modules.group_justech_license_manager"),
    ]
    admin_group = env.ref("justech_admin.group_justech_admin_user", raise_if_not_found=False)
    gov_group = env.ref("hellenia_governance.group_governance_manager", raise_if_not_found=False)
    if admin_group:
        groups.append(admin_group)
    if gov_group:
        groups.append(gov_group)

    for login in ("it@justech.do", "fausto@justech.do"):
        user = env["res.users"].search([("login", "=", login)], limit=1)
        if not user:
            continue
        user.write({"group_ids": [(4, g.id) for g in groups]})
        existing = Access.search(
            [("user_id", "=", user.id), ("company_id", "=", user.company_id.id)],
            limit=1,
        )
        if not existing:
            Access.ensure_access_shell(user, company=user.company_id, access_level="owner")
