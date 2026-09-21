"""Manual de usuario Doralex — presencia, crédito y capturas."""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANUAL = REPO / "docs" / "manual_usuario"


def test_manual_credits_fausto_santana_justech():
    html = (MANUAL / "index.html").read_text(encoding="utf-8")
    readme = (MANUAL / "README.md").read_text(encoding="utf-8")
    assert "Fausto Santana" in html
    assert "Justech" in html
    assert "Fausto Santana | Justech" in html
    assert "Fausto Santana | Justech" in readme
    assert "doralexgroup.cloud" in html
    assert "Formato Propet" in html
    assert (
        "nunca es el documento oficial" in html.lower()
        or "Nunca es el documento oficial" in html
    )
    assert "Número de Comprobante Fiscal" in html
    assert "OC / PO" in html
    assert "Conduce" in html


def test_manual_has_required_screenshots():
    needed = [
        "01_login.png",
        "02_inicio.png",
        "03_cotizacion_cabecera.png",
        "04_imprimir_cotizacion.png",
        "05_cotizacion_oc_po.png",
        "06_factura_cabecera.png",
        "07_imprimir_factura.png",
        "08_entrega_conduce.png",
        "cotizacion_oficial.png",
        "formato_propet_cotizacion.png",
        "factura_oficial.png",
        "formato_propet_factura.png",
        "conduce.png",
        "cotizacion_con_oc_po.png",
    ]
    for name in needed:
        path = MANUAL / "imagenes" / name
        assert path.is_file(), name
        assert path.stat().st_size > 8000, name
        assert name in (MANUAL / "index.html").read_text(encoding="utf-8")
