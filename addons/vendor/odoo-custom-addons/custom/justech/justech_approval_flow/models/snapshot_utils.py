# -*- coding: utf-8 -*-

from markupsafe import Markup, escape

SNAPSHOT_LINE_LIMIT = 8


def tax_key(taxes):
    return tuple(sorted(taxes.ids))


def _line_cells(row):
    if len(row) >= 4:
        name, qty, price, amount = row[0], row[1], row[2], row[3]
    else:
        name, qty, amount = row[0], row[1], row[2]
        price = None
    return name, qty, price, amount


def format_snapshot_html(lines, extra_rows=None, extra_line_count=0):
    """Build email-safe HTML. Lines are (name, qty, amount) or (name, qty, price, amount)."""
    rows = []
    for row in lines[:SNAPSHOT_LINE_LIMIT]:
        name, qty, price, amount = _line_cells(row)
        price_txt = "-" if price is None else "%.2f" % (price or 0.0)
        rows.append(
            "<tr>"
            "<td style='padding:8px 6px;border-bottom:1px solid #e5e7eb;'>%s</td>"
            "<td style='padding:8px 6px;border-bottom:1px solid #e5e7eb;text-align:right;'>%s</td>"
            "<td style='padding:8px 6px;border-bottom:1px solid #e5e7eb;text-align:right;'>%s</td>"
            "<td style='padding:8px 6px;border-bottom:1px solid #e5e7eb;text-align:right;'>%s</td>"
            "</tr>"
            % (
                escape(name or ""),
                escape("%.2f" % (qty or 0.0)),
                escape(price_txt),
                escape("%.2f" % (amount or 0.0)),
            )
        )
    if extra_line_count:
        rows.append(
            "<tr><td colspan='4' style='padding:8px 6px;color:#64748b;'>+ %s artículos adicionales</td></tr>"
            % extra_line_count
        )
    extra = ""
    if extra_rows:
        extra = "<p style='margin:12px 0 0 0;'>%s</p>" % "<br/>".join(extra_rows)
    body = "".join(rows) or "<tr><td colspan='4'>Sin líneas</td></tr>"
    return Markup(
        "<table role='presentation' width='100%%' cellpadding='0' cellspacing='0' style='border-collapse:collapse;'>%s</table>%s"
        % (body, extra)
    )
