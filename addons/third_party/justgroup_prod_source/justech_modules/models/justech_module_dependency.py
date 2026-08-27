from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class JustechModuleDependency(models.Model):
    _name = "justech.module.dependency"
    _description = "Commercial Module Dependency"
    _order = "module_id, depends_on_module_id"

    module_id = fields.Many2one(
        "justech.module",
        required=True,
        ondelete="cascade",
        index=True,
    )
    depends_on_module_id = fields.Many2one(
        "justech.module",
        required=True,
        ondelete="restrict",
        index=True,
        string="Depends On",
    )
    dependency_type = fields.Selection(
        [
            ("required", "Required"),
            ("optional", "Optional"),
        ],
        default="required",
        required=True,
    )

    _module_dep_unique = models.Constraint(
        "UNIQUE(module_id, depends_on_module_id)",
        "Dependency must be unique per module pair.",
    )
    _no_self_dependency = models.Constraint(
        "CHECK(module_id != depends_on_module_id)",
        "A module cannot depend on itself.",
    )

    @api.constrains("module_id", "depends_on_module_id")
    def _check_no_cycle(self):
        for dep in self:
            if dep._would_create_cycle(dep.module_id, dep.depends_on_module_id):
                raise ValidationError(
                    _("Dependency cycle detected between modules '%(from)s' and '%(to)s'.")
                    % {
                        "from": dep.module_id.code,
                        "to": dep.depends_on_module_id.code,
                    }
                )

    def _would_create_cycle(self, module, target_module, visited=None):
        if not module or not target_module:
            return False
        if module.id == target_module.id:
            return True
        visited = visited or set()
        if module.id in visited:
            return False
        visited.add(module.id)
        Dependency = self.env["justech.module.dependency"]
        for next_dep in Dependency.search(
            [("module_id", "=", target_module.id), ("dependency_type", "=", "required")]
        ):
            if self._would_create_cycle(module, next_dep.depends_on_module_id, visited):
                return True
        return False
