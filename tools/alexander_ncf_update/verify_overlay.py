# ruff: noqa
"""Confirm diagnostic fields and module version. Read-only. No consume."""


def run(env):
    mod = (
        env["ir.module.module"].sudo().search([("name", "=", "justech_alexander_base")])
    )
    print("MODULE", mod.name, mod.state, mod.latest_version)
    Range = env["justech.do.ncf.range"]
    print("HAS_LAST", "dx_ncf_last_used_display" in Range._fields)
    print("HAS_LEVEL", "dx_ncf_balance_level" in Range._fields)
    print("HAS_PREVIEW", hasattr(Range, "dx_preview_next_ncf"))
    for code, prefix, expect in (
        ("DOR", "B15", "B1500000152"),
        ("MAY", "B15", "B1500000113"),
        ("REM", "B15", "B1500000112"),
    ):
        co = env["res.company"].sudo().search([("dx_short_code", "=", code)], limit=1)
        rng = Range.sudo().search(
            [
                ("company_id", "=", co.id),
                ("prefix", "=", prefix),
                ("sequence_start", "<", 99100000),
            ],
            limit=1,
        )
        before = rng.next_sequence
        preview = rng.dx_preview_next_ncf()
        after = rng.next_sequence
        print(
            "PREVIEW",
            code,
            preview,
            "expect",
            expect,
            "consumed",
            after != before,
            "level",
            rng.dx_ncf_balance_level,
            "last",
            rng.dx_ncf_last_used_display,
        )
        if preview != expect or after != before:
            raise SystemExit("PREVIEW_FAIL_%s" % code)
    blu = env["res.company"].sudo().search([("dx_short_code", "=", "BLU")], limit=1)
    if blu:
        blu_b15 = Range.sudo().search(
            [("company_id", "=", blu.id), ("prefix", "=", "B15")]
        )
        print(
            "BLU_B15",
            [(r.id, r.state, r.next_sequence, r.sequence_end) for r in blu_b15],
        )
    print("B17", Range.sudo().search_count([("prefix", "=", "B17")]))
    print("OVERLAY_QA=PASS")
    return True


run(env)
