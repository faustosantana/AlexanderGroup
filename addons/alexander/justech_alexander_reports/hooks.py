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
    companies._dx_sync_report_brand_colors()
    for company in companies:
        vals = {}
        if layout:
            vals["external_report_layout_id"] = layout.id
        if paper:
            vals["paperformat_id"] = paper.id
        if vals:
            company.write(vals)
    env["ir.actions.report"]._dx_attach_invoice_edi_pdf()
    leftover = (
        env["ir.actions.report"]
        .sudo()
        .search(
            [
                (
                    "report_name",
                    "=",
                    "justech_alexander_reports.report_saleorder_conduce",
                )
            ]
        )
    )
    leftover.unlink()
    env["ir.actions.report"]._dx_disable_broken_studio_composition()
    env["ir.actions.report"]._dx_restore_company_paperformats()
    env["ir.actions.report"]._dx_restore_report_url()
