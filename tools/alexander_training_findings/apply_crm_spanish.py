# ruff: noqa
"""STAGING/DEV only: rename default English CRM stages/teams. No partner names."""

if env.cr.dbname not in {"doralex_ent_staging", "doralex_dev"}:
    raise RuntimeError("Refuse CRM rename outside DEV/STAGING: %s" % env.cr.dbname)

STAGES = {
    "New": "Nuevo",
    "Qualified": "Calificado",
    "Proposition": "Propuesta",
    "Won": "Ganado",
    "Lost": "Perdido",
}
TEAMS = {
    "Sales": "Ventas",
    "Point of Sale": "Punto de venta",
    "Website": "Sitio web",
}

changed = []
for stage in env["crm.stage"].sudo().search([]):
    spanish = STAGES.get(stage.name)
    if spanish:
        stage.write({"name": spanish})
        changed.append({"stage": spanish})
for team in env["crm.team"].sudo().search([]):
    spanish = TEAMS.get(team.name)
    if spanish:
        team.write({"name": spanish})
        changed.append({"team": spanish})
print(changed)
env.cr.commit()
