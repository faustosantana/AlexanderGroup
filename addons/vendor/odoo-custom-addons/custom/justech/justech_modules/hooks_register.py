"""Shared Justech module registration helpers (F31.1.5)."""

SKIP_MODULES = frozenset(
    {
        "justech_modules_test",
        "justech_report_templates_test",
    }
)


def register_from_manifest_hook(env, module_name):
    """Call from a module post_init_hook after install/upgrade."""
    if module_name in SKIP_MODULES:
        return
    from odoo.modules.module import load_manifest

    manifest = load_manifest(module_name)
    register_data = manifest.get("justech_register")
    if not register_data:
        return
    env["justech.license.service"].register_from_manifest(
        module_name, register_data, manifest=manifest
    )


def register_all_installed_manifests(env):
    """Register every installed Justech/Hellenia module with justech_register."""
    from odoo.modules.module import load_manifest

    service = env["justech.license.service"]
    IrModule = env["ir.module.module"]
    names = IrModule.search(
        [
            ("state", "in", ("installed", "to upgrade")),
            "|",
            ("name", "=like", "justech\\_%"),
            ("name", "=like", "hellenia\\_%"),
        ]
    ).mapped("name")
    for module_name in sorted(set(names)):
        if module_name in SKIP_MODULES or module_name == "justech_modules":
            continue
        try:
            manifest = load_manifest(module_name)
        except Exception:
            continue
        register_data = manifest.get("justech_register")
        if not register_data:
            continue
        service.register_from_manifest(
            module_name, register_data, manifest=manifest
        )
