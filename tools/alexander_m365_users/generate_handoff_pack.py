"""Genera Excel y PDF de entrega. Las claves salen de env, no se escriben en Git."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from catalog import PEOPLE

OUT_DIR = Path(os.environ.get("HANDOFF_OUT", "/opt/cursor/artifacts"))
TODAY = date.today().isoformat()
M365_PW = os.environ.get("M365_TEMP_PASSWORD") or ""
ODOO_PW = os.environ.get("ODOO_TEMP_PASSWORD") or ""
STANDARD = "Microsoft 365 Business Standard (O365_BUSINESS_PREMIUM)"

ROWS = [
    {
        "person": "Luis Joel Aquino Casado",
        "m365": "luis.aquino@inversionesdoralex.com",
        "odoo": "luis.aquino@inversionesdoralex.com",
        "odoo_id": 13,
        "role": "Ventas + Compras",
        "sales": "YES",
        "purchase": "YES",
        "invoicing": "NO",
        "acct_admin": "NO",
        "odoo_admin": "NO",
        "odoo_pw_mode": "temp",
    },
    {
        "person": "Janny Chantal Montero",
        "m365": "janny.montero@inversionesdoralex.com",
        "odoo": "janny.montero@inversionesdoralex.com",
        "odoo_id": 14,
        "role": "Ventas + Compras",
        "sales": "YES",
        "purchase": "YES",
        "invoicing": "NO",
        "acct_admin": "NO",
        "odoo_admin": "NO",
        "odoo_pw_mode": "temp",
    },
    {
        "person": "Elianny Nicole Sanchez Javier",
        "m365": "elianny.sanchez@inversionesdoralex.com",
        "odoo": "elianny.sanchez@inversionesdoralex.com",
        "odoo_id": 15,
        "role": "Ventas + Compras",
        "sales": "YES",
        "purchase": "YES",
        "invoicing": "NO",
        "acct_admin": "NO",
        "odoo_admin": "NO",
        "odoo_pw_mode": "temp",
    },
    {
        "person": "Leopordo Jimenez",
        "m365": "leopordo.jimenez@inversionesdoralex.com",
        "odoo": "leopordo.jimenez@inversionesdoralex.com",
        "odoo_id": 16,
        "role": "Ventas + Compras",
        "sales": "YES",
        "purchase": "YES",
        "invoicing": "NO",
        "acct_admin": "NO",
        "odoo_admin": "NO",
        "odoo_pw_mode": "temp",
    },
    {
        "person": "Geilin Rosario Suero",
        "m365": "geilin.rosario@inversionesdoralex.com",
        "odoo": "geilin.rosario@inversionesdoralex.com",
        "odoo_id": 17,
        "role": "Ventas + Compras + Facturacion",
        "sales": "YES",
        "purchase": "YES",
        "invoicing": "YES",
        "acct_admin": "NO",
        "odoo_admin": "NO",
        "odoo_pw_mode": "temp",
    },
    {
        "person": "Alexander Pina Aquino",
        "m365": "alexander.pina@inversionesdoralex.com",
        "odoo": "alexander.pina@inversionesdoralex.com",
        "odoo_id": 5,
        "role": "Administrador general Odoo",
        "sales": "YES",
        "purchase": "YES",
        "invoicing": "YES",
        "acct_admin": "YES",
        "odoo_admin": "YES",
        "odoo_pw_mode": "keep",
    },
]


def _style_header(ws, row, cols):
    fill = PatternFill("solid", fgColor="1F4E79")
    font = Font(color="FFFFFF", bold=True)
    thin = Border(
        left=Side(style="thin", color="BFBFBF"),
        right=Side(style="thin", color="BFBFBF"),
        top=Side(style="thin", color="BFBFBF"),
        bottom=Side(style="thin", color="BFBFBF"),
    )
    for col in range(1, cols + 1):
        cell = ws.cell(row, col)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = thin


def _autosize(ws):
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = 12
        for cell in col:
            width = max(width, min(48, len(str(cell.value or "")) + 2))
        ws.column_dimensions[letter].width = width


def write_xlsx(path: Path):
    wb = Workbook()
    cred = wb.active
    cred.title = "Credenciales"
    cred.append(
        [
            "PERSONA",
            "MICROSOFT_LOGIN",
            "MICROSOFT_TEMP_PASSWORD",
            "M365_CHANGE_FIRST_LOGIN",
            "ODOO_LOGIN",
            "ODOO_TEMP_PASSWORD",
            "ODOO_URL",
        ]
    )
    for row in ROWS:
        odoo_pw = (
            "SIN CAMBIO — usar clave Odoo actual"
            if row["odoo_pw_mode"] == "keep"
            else ODOO_PW
        )
        cred.append(
            [
                row["person"],
                row["m365"],
                M365_PW,
                "YES",
                row["odoo"],
                odoo_pw,
                "https://doralexgroup.cloud",
            ]
        )
    _style_header(cred, 1, 7)
    _autosize(cred)

    mx = wb.create_sheet("Matriz")
    mx.append(
        [
            "PERSONA",
            "M365_UPN",
            "M365_LICENSE",
            "MAILBOX_SMTP",
            "FORCE_CHANGE",
            "ODOO_USER_ID",
            "ODOO_LOGIN",
            "COMPANIES",
            "SALES",
            "PURCHASE",
            "INVOICING",
            "ACCOUNTING_ADMIN",
            "ODOO_ADMIN",
            "ROL",
        ]
    )
    for row in ROWS:
        mx.append(
            [
                row["person"],
                row["m365"],
                STANDARD,
                row["m365"],
                "YES",
                row["odoo_id"],
                row["odoo"],
                "6 (Blue Elite, Pinaria, Dominion, Doralex, Mayuma, Rempart)",
                row["sales"],
                row["purchase"],
                row["invoicing"],
                row["acct_admin"],
                row["odoo_admin"],
                row["role"],
            ]
        )
    _style_header(mx, 1, 14)
    _autosize(mx)

    info = wb.create_sheet("Notas")
    notes = [
        ("Fecha", TODAY),
        ("Dominio", "inversionesdoralex.com (verificado)"),
        ("Licencia actual", STANDARD),
        ("SKU_ID", "f245ecc8-75af-4f8e-b61f-27d8114de5f3"),
        (
            "Nota licencia",
            "Asignada ahora porque no hay Kiosk. Cambiar cuando venza la prueba.",
        ),
        ("Odoo", "https://doralexgroup.cloud"),
        ("Outlook web", "https://outlook.office.com"),
        ("Alexander Odoo", "Mismo usuario uid 5. No se duplico. Login nuevo."),
        ("Alexander Odoo clave", "No se reseteo. Sigue su clave actual."),
        ("No tocar", "admin@doralex.onmicrosoft.com / alex@doralex.onmicrosoft.com"),
        ("Backup Odoo", "pre_alexander_users_permissions_20260907_122013"),
        ("Empresas", "Las 6 operativas. Default: INVERSIONES DORALEX,S.RL."),
    ]
    info.append(["CLAVE", "VALOR"])
    for k, v in notes:
        info.append([k, v])
    _style_header(info, 1, 2)
    _autosize(info)
    wb.save(path)


def write_pdf(path: Path):
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="Usuarios Alexander Group — Microsoft 365 + Odoo",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "T",
        parent=styles["Heading1"],
        fontSize=14,
        textColor=colors.HexColor("#1F4E79"),
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#1F4E79"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body = ParagraphStyle("B", parent=styles["Normal"], fontSize=8.5, leading=11)
    cell = ParagraphStyle("C", parent=styles["Normal"], fontSize=7, leading=9)
    story = [
        Paragraph("Alexander Group — Usuarios Microsoft 365 + Odoo", title),
        Paragraph(
            "Entrega %s. Uso interno. No reenviar por correo automatico." % TODAY, body
        ),
        Paragraph(
            "Licencia temporal asignada: <b>%s</b>. "
            "Cambiar a Exchange Online Kiosk u otra cuando venza la prueba." % STANDARD,
            body,
        ),
        Paragraph(
            "Odoo: https://doralexgroup.cloud &nbsp;&nbsp; Outlook: https://outlook.office.com",
            body,
        ),
        Paragraph("1. Credenciales", h2),
    ]
    cred_header = [
        Paragraph(x, cell)
        for x in [
            "Persona",
            "Microsoft",
            "Clave M365",
            "Odoo",
            "Clave Odoo",
        ]
    ]
    cred_data = [cred_header]
    for row in ROWS:
        odoo_pw = (
            "SIN CAMBIO (clave actual)" if row["odoo_pw_mode"] == "keep" else ODOO_PW
        )
        cred_data.append(
            [
                Paragraph(row["person"], cell),
                Paragraph(row["m365"], cell),
                Paragraph(M365_PW, cell),
                Paragraph(row["odoo"], cell),
                Paragraph(odoo_pw, cell),
            ]
        )
    t = Table(
        cred_data,
        colWidths=[1.5 * inch, 2.1 * inch, 1.35 * inch, 2.1 * inch, 1.4 * inch],
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BFBFBF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7F9FC")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t)
    story.append(
        Paragraph(
            "Microsoft: cambiar clave en el primer inicio. Odoo: clave distinta a Microsoft.",
            body,
        )
    )
    story.append(Paragraph("2. Matriz de roles", h2))
    mx_header = [
        Paragraph(x, cell)
        for x in [
            "Persona",
            "Odoo ID",
            "Sales",
            "Purchase",
            "Factura",
            "Acct Admin",
            "Odoo Admin",
            "Licencia M365",
            "Buzon SMTP",
        ]
    ]
    mx_data = [mx_header]
    for row in ROWS:
        mx_data.append(
            [
                Paragraph(row["person"], cell),
                Paragraph(str(row["odoo_id"]), cell),
                Paragraph(row["sales"], cell),
                Paragraph(row["purchase"], cell),
                Paragraph(row["invoicing"], cell),
                Paragraph(row["acct_admin"], cell),
                Paragraph(row["odoo_admin"], cell),
                Paragraph("Business Standard", cell),
                Paragraph(row["m365"], cell),
            ]
        )
    t2 = Table(
        mx_data,
        colWidths=[
            1.45 * inch,
            0.55 * inch,
            0.5 * inch,
            0.65 * inch,
            0.55 * inch,
            0.7 * inch,
            0.7 * inch,
            1.05 * inch,
            1.85 * inch,
        ],
    )
    t2.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BFBFBF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7F9FC")),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(t2)
    story.append(PageBreak())
    story.append(Paragraph("3. Notas operativas", h2))
    bullets = [
        "Dominio verificado: inversionesdoralex.com. UPN final @inversionesdoralex.com.",
        "Licencia SKU O365_BUSINESS_PREMIUM (Microsoft 365 Business Standard). 6 asignadas. Quedan 15 disponibles (25 prepaid).",
        "Alexander Odoo es el mismo uid 5 (antes inversionesdoralex@gmail.com). No se creo un segundo usuario.",
        "Alexander Microsoft nuevo: alexander.pina@inversionesdoralex.com. No se toco admin@ ni alex@ onmicrosoft.",
        "Empresas: las 6 operativas. Default INVERSIONES DORALEX,S.RL.",
        "Luis, Janny, Elianny, Leopordo: ventas + compras. No publican facturas. No Settings.",
        "Geilin: facturacion operativa. No es Accounting Admin ni Settings.",
        "Alexander: administrador general funcional de Odoo. No es superuser id 1.",
        "Backup: pre_alexander_users_permissions_20260907_122013.",
        "No se tocaron facturas historicas, NCF, apertura, reportes ni website.",
        "Cuando venza la prueba Standard, cambiar a Kiosk u otra licencia de correo.",
    ]
    for item in bullets:
        story.append(Paragraph("• " + item, body))
        story.append(Spacer(1, 4))
    assert PEOPLE  # catalog imported for consistency
    doc.build(story)


def main():
    if not M365_PW or not ODOO_PW:
        raise SystemExit("M365_TEMP_PASSWORD and ODOO_TEMP_PASSWORD required")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    xlsx = OUT_DIR / "Alexander_Usuarios_Odoo_M365_20260907.xlsx"
    pdf = OUT_DIR / "Alexander_Usuarios_Odoo_M365_20260907.pdf"
    write_xlsx(xlsx)
    write_pdf(pdf)
    print(str(xlsx))
    print(str(pdf))


if __name__ == "__main__":
    main()
