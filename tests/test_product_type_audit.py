"""Nature classification for the product-type audit (no Odoo writes)."""

from tools.alexander_product_master.classify import is_service
from tools.alexander_product_master.type_nature import classify_nature, is_physical_good


def _c(name, **kwargs):
    return classify_nature(name, **kwargs)


def test_grava_canonical_is_physical_good():
    rec = _c(
        "Agregado grueso (grava) 3/4",
        current_type="service",
        sale_ok=False,
        purchase_ok=True,
    )
    assert rec["NATURE"] == "PHYSICAL_GOOD"
    assert rec["PROPOSED_TYPE"] == "consu"
    assert rec["PROPOSED_SALE_OK"] is True
    assert rec["PROPOSED_PURCHASE_OK"] is True
    assert rec["PROPOSED_IS_STORABLE"] is False
    assert rec["CONFIDENCE"] == "DETERMINISTIC"
    assert rec["MISMATCH"] == "PHYSICAL_AS_SERVICE"
    assert rec["ACTION"] == "FIX_TYPE_AND_FLAGS"
    assert rec["WRITABLE"] is True


def test_archived_grava_is_not_reactivated():
    rec = _c(
        "(AGREGADO GRUESO) GRAVA 3/4",
        current_type="service",
        active=False,
        sale_ok=True,
        purchase_ok=False,
    )
    assert rec["NATURE"] == "PHYSICAL_GOOD"
    assert rec["ACTION"] == "KEEP_ARCHIVED"
    assert rec["WRITABLE"] is False


def test_arena_and_tools_are_physical_as_service():
    for name in (
        "AGREGADO FINO (ARENA LAVADA)",
        "(AGREGADO FINO) ARENA LAVADA AZUL",
        'DISCO DE CORTE 9" METABO 7/8',
        'PINZA DE CORTE PUNTA LARGA 8" 84-102 STANLEY',
    ):
        rec = _c(name, current_type="service", sale_ok=True, purchase_ok=False)
        assert rec["NATURE"] == "PHYSICAL_GOOD", name
        assert rec["PROPOSED_TYPE"] == "consu", name
        assert rec["PROPOSED_PURCHASE_OK"] is True, name
        assert rec["CONFIDENCE"] == "DETERMINISTIC", name
        assert rec["WRITABLE"] is True, name


def test_real_services_stay_service():
    for name in (
        "Servicios profesionales",
        "Servicio de verificación interna",
        "Bote material natural esponjado fuera del proyecto",
        "CORTE, CARGA Y TRANSPORTE TOSCA",
        "CORTE Y CARGA CALICHE",
        "TRANSPORTE CALICHE",
        "TRASLADO Y REGADO DE STACKED MATERIAL",
        "SERVICIO MATERIAL CALICHE ESPONJADO (35% de 5000 M3)",
        "RAMPA DE ACCESO A EXCAVACION CUADRANTE #2",
        "CAJA CHICA (Feb-Mar 2026) agua y hielo $600/semana",
        "CAJA CHICA (Materiales instalacion motobomba y combustible)",
        "PEAJE (Agosto-Diciembre) y horas fuera de proyecto — total documento PDF",
        "DT 1RA CUBICACION CUADRANTE #2 USD $16,698.33 TASA USD$1=62.30",
        "Event Registration",
        "Field Service",
        "Service on Timesheets",
    ):
        rec = _c(name, current_type="service", sale_ok=True, purchase_ok=False)
        assert rec["NATURE"] == "SERVICE", name
        assert rec["PROPOSED_TYPE"] == "service", name
        assert rec["WRITABLE"] is False, name


def test_professional_services_never_become_goods():
    rec = _c(
        "Servicios profesionales",
        current_type="service",
        sale_ok=True,
        purchase_ok=True,
    )
    assert rec["NATURE"] == "SERVICE"
    assert rec["PROPOSED_TYPE"] == "service"
    assert rec["ACTION"] == "KEEP"
    assert rec["CONFIDENCE"] == "DETERMINISTIC"


def test_valvula_de_servicio_is_physical():
    assert not is_service("Válvula de servicio 1/2")
    rec = _c("Válvula de servicio 1/2", current_type="consu")
    assert rec["NATURE"] == "PHYSICAL_GOOD"
    assert rec["PROPOSED_TYPE"] == "consu"


def test_kit_de_instalacion_is_physical_not_service():
    assert not is_service("KIT DE INSTALACION DE BOMBA")
    rec = _c(
        "KIT DE INSTALACION DE BOMBA",
        current_type="consu",
        purchase_ok=False,
    )
    assert rec["NATURE"] == "PHYSICAL_GOOD"
    assert rec["PROPOSED_TYPE"] == "consu"
    assert rec["ACTION"] == "FIX_PURCHASE_OK"


def test_pinaria_food_is_physical():
    for name in ("CARNE DE RES", "RES MOLIDA", "ARROZ Selecto LA CIGUA GRADO A"):
        rec = _c(name, current_type="consu", purchase_ok=True)
        assert rec["NATURE"] == "PHYSICAL_GOOD", name
        assert rec["PROPOSED_TYPE"] == "consu", name
        assert rec["ACTION"] == "KEEP", name


def test_opening_physical_gets_purchase_ok():
    rec = _c(
        "CEMENTO GRIS (AGLOMERANTE PORTLAND) SANTO DOMINGO 94LB",
        current_type="consu",
        purchase_ok=False,
    )
    assert rec["NATURE"] == "PHYSICAL_GOOD"
    assert rec["ACTION"] == "FIX_PURCHASE_OK"
    assert rec["PROPOSED_PURCHASE_OK"] is True


def test_apertura_historica_is_ambiguous():
    rec = _c(
        "Apertura histórica B1300000016 (sin desglose PDF)",
        current_type="consu",
        purchase_ok=False,
    )
    assert rec["NATURE"] == "AMBIGUOUS"
    assert rec["ACTION"] == "MANUAL_REVIEW"
    assert rec["WRITABLE"] is False


def test_bote_material_catalog_rows_are_services():
    for name in ("BOTE Material Desechable Y Escombro", "Bote Material Inservible"):
        rec = _c(name, current_type="consu", sale_ok=True, purchase_ok=True)
        assert rec["NATURE"] == "SERVICE", name
        assert rec["PROPOSED_TYPE"] == "service", name
        assert rec["MISMATCH"] == "SERVICE_AS_PHYSICAL", name
        assert rec["ACTION"] == "FIX_TYPE", name


def test_nevera_and_taladro_are_goods():
    assert is_physical_good("NEVERA MIDEA 10 PIES")
    assert is_physical_good("Taladro DeWalt 1/2")
    assert not is_physical_good("Servicios profesionales")
    assert not is_physical_good("TRANSPORTE CALICHE")
