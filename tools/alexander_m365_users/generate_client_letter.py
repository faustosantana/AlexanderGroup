"""Carta de entrega para Alexander. Claves solo por env. No se commitea el PDF."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ORANGE = (0.894, 0.376, 0.094)  # #E46018
BLACK = (0.102, 0.102, 0.102)
GRAY = (0.35, 0.35, 0.35)
LINE = (0.88, 0.88, 0.88)
CARD = (0.98, 0.97, 0.96)
WHITE = (1, 1, 1)

W, H = letter
MARGIN = 56
LOGO = Path(os.environ.get("DORALEX_LOGO", "/tmp/brand/DOR.png"))
OUT = Path(
    os.environ.get(
        "CLIENT_LETTER_OUT",
        "/opt/cursor/artifacts/Accesos_Equipo_Alexander_Group.pdf",
    )
)
M365_PW = os.environ["M365_TEMP_PASSWORD"]
ODOO_PW = os.environ["ODOO_TEMP_PASSWORD"]

pdfmetrics.registerFont(
    TTFont("Inter", "/usr/share/fonts/truetype/macos/Inter-Regular.ttf")
)
pdfmetrics.registerFont(
    TTFont("InterMed", "/usr/share/fonts/truetype/macos/Inter-Medium.ttf")
)
pdfmetrics.registerFont(
    TTFont("InterSemi", "/usr/share/fonts/truetype/macos/Inter-SemiBold.ttf")
)
pdfmetrics.registerFont(
    TTFont("InterBold", "/usr/share/fonts/truetype/macos/Inter-Bold.ttf")
)
pdfmetrics.registerFont(
    TTFont("Serif", "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf")
)
pdfmetrics.registerFont(
    TTFont("SerifBold", "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf")
)

PEOPLE = [
    {
        "name": "Luis Joel Aquino Casado",
        "mail": "luis.aquino@inversionesdoralex.com",
        "role": "Ventas y compras",
        "can": "Cotizar, confirmar ventas y crear u confirmar órdenes de compra.",
        "cannot": "No factura, no entra a Ajustes ni administra usuarios.",
        "odoo_pw": ODOO_PW,
    },
    {
        "name": "Janny Chantal Montero",
        "mail": "janny.montero@inversionesdoralex.com",
        "role": "Ventas y compras",
        "can": "Cotizar, confirmar ventas y crear u confirmar órdenes de compra.",
        "cannot": "No factura, no entra a Ajustes ni administra usuarios.",
        "odoo_pw": ODOO_PW,
    },
    {
        "name": "Elianny Nicole Sanchez Javier",
        "mail": "elianny.sanchez@inversionesdoralex.com",
        "role": "Ventas y compras",
        "can": "Cotizar, confirmar ventas y crear u confirmar órdenes de compra.",
        "cannot": "No factura, no entra a Ajustes ni administra usuarios.",
        "odoo_pw": ODOO_PW,
    },
    {
        "name": "Leopordo Jimenez",
        "mail": "leopordo.jimenez@inversionesdoralex.com",
        "role": "Ventas y compras",
        "can": "Cotizar, confirmar ventas y crear u confirmar órdenes de compra.",
        "cannot": "No factura, no entra a Ajustes ni administra usuarios.",
        "odoo_pw": ODOO_PW,
    },
    {
        "name": "Geilin Rosario Suero",
        "mail": "geilin.rosario@inversionesdoralex.com",
        "role": "Ventas, compras y facturación",
        "can": "Además de vender y comprar, crea y publica facturas de cliente.",
        "cannot": "No administra el plan de cuentas, NCF, e-CF ni Ajustes.",
        "odoo_pw": ODOO_PW,
    },
    {
        "name": "Alexander Piña Aquino",
        "mail": "alexander.pina@inversionesdoralex.com",
        "role": "Administrador general de Odoo",
        "can": "Las seis empresas, Ajustes, usuarios, ventas, compras, contabilidad e inventario.",
        "cannot": "Es el mismo usuario de siempre. No se creó una segunda ficha.",
        "odoo_pw": "La contraseña de Odoo que usted ya usa (no se cambió).",
    },
]


def _set(c, rgb):
    c.setFillColorRGB(*rgb)
    c.setStrokeColorRGB(*rgb)


def _wrap(text, width=86):
    return textwrap.wrap(text, width=width)


def header(c, page, total):
    c.setFillColorRGB(*ORANGE)
    c.rect(0, 0, 8, H, fill=1, stroke=0)
    if LOGO.exists():
        c.drawImage(
            ImageReader(str(LOGO)),
            MARGIN,
            H - 92,
            width=78,
            height=78,
            mask="auto",
            preserveAspectRatio=True,
            anchor="c",
        )
    _set(c, BLACK)
    c.setFont("SerifBold", 16)
    c.drawString(MARGIN + 92, H - 48, "Grupo Alexander")
    c.setFont("Inter", 9)
    _set(c, GRAY)
    c.drawString(MARGIN + 92, H - 64, "Inversiones Doralex  ·  Microsoft 365 y Odoo")
    c.setStrokeColorRGB(*ORANGE)
    c.setLineWidth(1.4)
    c.line(MARGIN, H - 104, W - MARGIN, H - 104)
    _set(c, GRAY)
    c.setFont("Inter", 8)
    c.drawRightString(
        W - MARGIN, 28, "Confidencial  ·  página %s de %s" % (page, total)
    )
    c.drawString(MARGIN, 28, "Justech  ·  justech.do  ·  7 de septiembre de 2026")


def footer_rule(c):
    c.setStrokeColorRGB(*LINE)
    c.setLineWidth(0.6)
    c.line(MARGIN, 40, W - MARGIN, 40)


def new_page(c, page, total):
    c.showPage()
    header(c, page, total)
    footer_rule(c)


def paragraph(c, text, x, y, width=86, leading=14, font="Inter", size=10, color=BLACK):
    _set(c, color)
    c.setFont(font, size)
    for line in _wrap(text, width):
        c.drawString(x, y, line)
        y -= leading
    return y


def page_letter(c, total):
    header(c, 1, total)
    footer_rule(c)
    y = H - 136
    _set(c, ORANGE)
    c.setFont("InterSemi", 8)
    c.drawString(MARGIN, y, "ENTREGA DE ACCESOS")
    y -= 28
    _set(c, BLACK)
    c.setFont("SerifBold", 22)
    c.drawString(MARGIN, y, "Cuentas de su equipo")
    y -= 26
    c.setFont("Serif", 12)
    _set(c, GRAY)
    c.drawString(MARGIN, y, "Para Alexander Piña Aquino")
    y -= 36
    y = paragraph(
        c,
        "Estimado Alexander:",
        MARGIN,
        y,
        font="Serif",
        size=11,
    )
    y -= 6
    y = paragraph(
        c,
        "Ya están listas las cuentas con las que su equipo va a trabajar. Cada persona tiene un correo en el dominio inversionesdoralex.com y el mismo usuario en Odoo. Este documento es para que usted se las entregue en persona o por un canal privado. No lo reenvíe por correo masivo.",
        MARGIN,
        y,
        width=92,
        leading=15,
        size=10.5,
    )
    y -= 18
    _set(c, BLACK)
    c.setFont("InterSemi", 11)
    c.drawString(MARGIN, y, "Qué quedó hecho")
    y -= 18
    bullets = [
        "Seis correos nuevos en @inversionesdoralex.com, con buzón activo.",
        "El mismo login sirve para Outlook (correo) y para Odoo.",
        "Usted sigue siendo el administrador general de Odoo. Es el mismo usuario de siempre; solo cambió el correo de acceso. Su contraseña de Odoo no se tocó.",
        "Luis, Janny, Elianny y Leopordo pueden vender y comprar. No pueden facturar ni entrar a Ajustes.",
        "Geilin, además, es quien factura. No administra la contabilidad ni los NCF.",
        "Los seis pueden trabajar en las seis empresas del grupo. La empresa por defecto es Inversiones Doralex.",
    ]
    for item in bullets:
        c.setFillColorRGB(*ORANGE)
        c.circle(MARGIN + 4, y + 3, 2.2, fill=1, stroke=0)
        y = paragraph(c, item, MARGIN + 16, y, width=86, leading=14, size=10)
        y -= 8
    y -= 10
    _set(c, BLACK)
    c.setFont("InterSemi", 11)
    c.drawString(MARGIN, y, "Licencia de Microsoft")
    y -= 18
    y = paragraph(
        c,
        "Hoy les asignamos Microsoft 365 Business Standard, que es la licencia que el tenant tiene disponible (incluye correo y las aplicaciones de Office). Cuando se venza esa prueba, usted la cambia a la licencia definitiva —por ejemplo Exchange Online Kiosk, si solo necesitan correo— sin volver a crear las cuentas.",
        MARGIN,
        y,
        width=92,
        leading=15,
        size=10.5,
    )
    y -= 16
    y = paragraph(
        c,
        "Quedo atento para la entrega y el primer inicio de sesión.",
        MARGIN,
        y,
        font="Serif",
        size=11,
    )
    y -= 22
    c.setFont("InterSemi", 10)
    _set(c, BLACK)
    c.drawString(MARGIN, y, "Fausto Santana")
    y -= 13
    c.setFont("Inter", 9)
    _set(c, GRAY)
    c.drawString(MARGIN, y, "Justech  ·  fausto@justech.do")


def page_how(c, total):
    new_page(c, 2, total)
    y = H - 136
    _set(c, BLACK)
    c.setFont("SerifBold", 18)
    c.drawString(MARGIN, y, "Cómo entrar")
    y -= 28
    y = paragraph(
        c,
        "Cada persona tiene dos puertas: el correo de Microsoft y Odoo. El usuario es el mismo en ambas. Las contraseñas son distintas a propósito.",
        MARGIN,
        y,
        width=92,
        leading=15,
        size=10.5,
    )
    y -= 20

    boxes = [
        (
            "Correo — Microsoft 365",
            [
                "Entre a outlook.office.com o a office.com.",
                "Escriba su correo @inversionesdoralex.com y la contraseña temporal de Microsoft.",
                "El sistema le va a pedir cambiar esa contraseña en el primer inicio. Eso es correcto.",
                "Si Microsoft pide registrar el teléfono (MFA), hágalo. No lo desactivamos.",
            ],
        ),
        (
            "Odoo — doralexgroup.cloud",
            [
                "Entre a https://doralexgroup.cloud",
                "El usuario es el mismo correo @inversionesdoralex.com.",
                "La contraseña de Odoo es otra, no la de Microsoft.",
                "En la esquina de la empresa puede cambiar entre las seis compañías del grupo.",
            ],
        ),
    ]
    for title, lines in boxes:
        c.setFillColorRGB(*CARD)
        c.roundRect(MARGIN, y - 118, W - 2 * MARGIN, 132, 6, fill=1, stroke=0)
        c.setFillColorRGB(*ORANGE)
        c.rect(MARGIN, y - 118, 5, 132, fill=1, stroke=0)
        _set(c, BLACK)
        c.setFont("InterSemi", 12)
        c.drawString(MARGIN + 20, y, title)
        yy = y - 20
        for line in lines:
            yy = paragraph(c, line, MARGIN + 20, yy, width=84, leading=14, size=9.5)
        y -= 152

    y -= 4
    _set(c, BLACK)
    c.setFont("InterSemi", 11)
    c.drawString(MARGIN, y, "Su acceso, Alexander")
    y -= 18
    y = paragraph(
        c,
        "Su correo nuevo es alexander.pina@inversionesdoralex.com. En Microsoft es una cuenta nueva: use la contraseña temporal y cámbiela al entrar. En Odoo no creamos un segundo usuario: actualizamos el que ya tenía (antes inversionesdoralex@gmail.com). Siguen sus documentos, empresas y permisos. La contraseña de Odoo es la que usted ya conocía.",
        MARGIN,
        y,
        width=92,
        leading=15,
        size=10.5,
    )


def _card(c, person, x, y, w, h):
    c.setFillColorRGB(*CARD)
    c.roundRect(x, y, w, h, 6, fill=1, stroke=0)
    c.setFillColorRGB(*ORANGE)
    c.rect(x, y, 5, h, fill=1, stroke=0)
    _set(c, BLACK)
    c.setFont("InterSemi", 11)
    c.drawString(x + 16, y + h - 22, person["name"])
    c.setFont("Inter", 8.5)
    _set(c, ORANGE)
    c.drawString(x + 16, y + h - 36, person["role"].upper())
    _set(c, GRAY)
    c.setFont("Inter", 8)
    c.drawString(x + 16, y + h - 56, "Correo / usuario")
    _set(c, BLACK)
    c.setFont("InterMed", 9)
    c.drawString(x + 16, y + h - 68, person["mail"])
    _set(c, GRAY)
    c.setFont("Inter", 8)
    c.drawString(x + 16, y + h - 86, "Contraseña Microsoft (cambiar al entrar)")
    _set(c, BLACK)
    c.setFont("InterMed", 9)
    c.drawString(x + 16, y + h - 98, M365_PW)
    _set(c, GRAY)
    c.setFont("Inter", 8)
    c.drawString(x + 16, y + h - 116, "Contraseña Odoo")
    _set(c, BLACK)
    c.setFont("InterMed", 8.5)
    for i, line in enumerate(_wrap(person["odoo_pw"], 42)):
        c.drawString(x + 16, y + h - 128 - i * 11, line)


def page_cards(c, total):
    new_page(c, 3, total)
    y = H - 136
    _set(c, BLACK)
    c.setFont("SerifBold", 18)
    c.drawString(MARGIN, y, "Credenciales del equipo")
    y -= 18
    y = paragraph(
        c,
        "Entrégueselas una por una. Microsoft y Odoo no usan la misma contraseña.",
        MARGIN,
        y,
        size=10,
        color=GRAY,
    )
    y -= 16
    gap = 12
    card_w = (W - 2 * MARGIN - gap) / 2
    card_h = 148
    for i, person in enumerate(PEOPLE[:4]):
        col = i % 2
        row = i // 2
        x = MARGIN + col * (card_w + gap)
        yy = y - row * (card_h + gap) - card_h
        _card(c, person, x, yy, card_w, card_h)

    new_page(c, 4, total)
    y = H - 136
    _set(c, BLACK)
    c.setFont("SerifBold", 18)
    c.drawString(MARGIN, y, "Credenciales del equipo")
    y -= 22
    card_w = (W - 2 * MARGIN - gap) / 2
    for i, person in enumerate(PEOPLE[4:]):
        x = MARGIN + i * (card_w + gap)
        _card(c, person, x, y - card_h, card_w, card_h)

    y = y - card_h - 36
    _set(c, BLACK)
    c.setFont("InterSemi", 11)
    c.drawString(MARGIN, y, "Direcciones")
    y -= 18
    y = paragraph(c, "Correo:  outlook.office.com", MARGIN, y, size=10.5)
    y = paragraph(c, "Odoo:  https://doralexgroup.cloud", MARGIN, y, size=10.5)
    y -= 12
    y = paragraph(
        c,
        "Las seis empresas: Inversiones Doralex; Comercializadora de Alimentos Piñaria; Dominion Business; Inversiones El Mayuma; Rempart Group; Blue Elite.",
        MARGIN,
        y,
        width=92,
        leading=15,
        size=10.5,
    )


def page_roles(c, total):
    new_page(c, 5, total)
    y = H - 136
    _set(c, BLACK)
    c.setFont("SerifBold", 18)
    c.drawString(MARGIN, y, "Quién hace qué")
    y -= 26
    for person in PEOPLE:
        c.setFillColorRGB(*ORANGE)
        c.circle(MARGIN + 4, y + 3, 2.2, fill=1, stroke=0)
        _set(c, BLACK)
        c.setFont("InterSemi", 10.5)
        c.drawString(MARGIN + 16, y, person["name"])
        y -= 14
        y = paragraph(
            c,
            person["role"] + ". " + person["can"] + " " + person["cannot"],
            MARGIN + 16,
            y,
            width=84,
            leading=13,
            size=9.5,
            color=GRAY,
        )
        y -= 12
    y -= 8
    _set(c, BLACK)
    c.setFont("InterSemi", 11)
    c.drawString(MARGIN, y, "Lo que no se tocó")
    y -= 18
    for item in (
        "Facturas históricas, NCF, carga de apertura, reportes y el website.",
        "Su cuenta Microsoft anterior (admin@ / alex@ doralex.onmicrosoft.com).",
        "El usuario técnico interno de Odoo.",
    ):
        c.setFillColorRGB(*ORANGE)
        c.circle(MARGIN + 4, y + 3, 2.2, fill=1, stroke=0)
        y = paragraph(c, item, MARGIN + 16, y, width=84, leading=14, size=10)
        y -= 6
    y -= 16
    y = paragraph(
        c,
        "Si al entrar alguien ve un error de permisos, avísenos. No vamos a resolverlo dándole Ajustes a todo el mundo.",
        MARGIN,
        y,
        width=92,
        leading=15,
        size=10.5,
    )


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=letter)
    c.setTitle("Accesos del equipo — Grupo Alexander")
    c.setAuthor("Justech")
    c.setSubject("Cuentas Microsoft 365 y Odoo para Alexander Piña Aquino")
    total = 5
    page_letter(c, total)
    page_how(c, total)
    page_cards(c, total)
    page_roles(c, total)
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
