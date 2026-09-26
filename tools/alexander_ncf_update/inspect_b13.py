# ruff: noqa
"""List every B13 range on every company. Read-only."""


def run(env):
    Range = env["justech.do.ncf.range"].sudo()
    recs = Range.search([("prefix", "=", "B13")])
    print("B13_COUNT", len(recs), "DB", env.cr.dbname)
    for r in recs:
        print(
            "B13",
            r.id,
            r.company_id.dx_short_code,
            r.company_id.name,
            "start",
            r.sequence_start,
            "end",
            r.sequence_end,
            "next",
            r.next_sequence,
            "state",
            r.state,
            "auth",
            r.authorization_number,
            "date_to",
            r.date_to,
            "name",
            r.name,
        )
    return recs


run(env)
