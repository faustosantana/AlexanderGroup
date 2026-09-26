# ruff: noqa
"""Diagnostic SQL search for authorized next/last B15 strings. Read-only."""

NEEDLES = (
    "B1500000151",
    "B1500000152",
    "B1500000110",
    "B1500000111",
    "B1500000112",
    "B1500000113",
    "B1300000016",
    "B1300000017",
)


def run(env):
    env.cr.execute("""
        SELECT table_schema, table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND data_type IN ('character varying', 'text')
          AND table_name NOT LIKE 'ir_%'
          AND table_name NOT LIKE '_%'
        ORDER BY table_name, column_name
        """)
    cols = env.cr.fetchall()
    hits = []
    for schema, table, column in cols:
        try:
            env.cr.execute(
                'SELECT COUNT(*) FROM "%s" WHERE %s'
                % (
                    table,
                    " OR ".join(['"%s" = %%s' % column] * len(NEEDLES)),
                ),
                list(NEEDLES),
            )
            count = env.cr.fetchone()[0]
        except Exception as exc:  # noqa: BLE001
            env.cr.rollback()
            continue
        if not count:
            continue
        env.cr.execute(
            'SELECT id, "%s" FROM "%s" WHERE %s LIMIT 40'
            % (
                column,
                table,
                " OR ".join(['"%s" = %%s' % column] * len(NEEDLES)),
            ),
            list(NEEDLES),
        )
        rows = env.cr.fetchall()
        hits.append({"table": table, "column": column, "count": count, "rows": rows})
        print("HIT", table, column, count, rows[:12])
    print("SQL_HIT_TABLES", len(hits))
    return hits


run(env)
