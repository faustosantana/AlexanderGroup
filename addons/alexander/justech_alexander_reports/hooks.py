def post_init_hook(env):
    layout = env.ref(
        "justech_alexander_reports.external_layout_doralex",
        raise_if_not_found=False,
    )
    paper = env.ref(
        "justech_alexander_reports.paperformat_doralex_a4",
        raise_if_not_found=False,
    )
    companies = env["res.company"].sudo().search([("dx_short_code", "!=", False)])
    for company in companies:
        vals = {}
        if layout:
            vals["external_report_layout_id"] = layout.id
        if paper:
            vals["paperformat_id"] = paper.id
        if vals:
            company.write(vals)
