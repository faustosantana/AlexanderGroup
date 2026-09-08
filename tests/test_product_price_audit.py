"""Local classification tests for the product-price audit (no Odoo writes)."""

from tools.alexander_product_master.price_classify import classify_price


def test_zero_professional_services_keep():
    rec = classify_price({"name": "Servicios profesionales", "list_price": 0})
    assert rec["price_status"] == "ZERO_PRICE"
    assert rec["recommended_action"] == "KEEP"


def test_zero_other_product_review():
    rec = classify_price({"name": "Taladro DeWalt", "list_price": 0})
    assert rec["price_status"] == "ZERO_PRICE"
    assert rec["recommended_action"] == "ZERO_PRICE_REVIEW"


def test_aligned_history_is_ok():
    rec = classify_price(
        {
            "name": "CEMENTO GRIS",
            "list_price": 365.31,
            "recent_avg_price": 365.31,
            "last_invoice_price": 365.31,
        }
    )
    assert rec["price_status"] == "PRICE_OK"
    assert rec["recommended_action"] == "KEEP"


def test_suspicious_high():
    rec = classify_price(
        {
            "name": "PINTURA",
            "list_price": 10000,
            "recent_avg_price": 1000,
            "last_invoice_price": 1000,
        }
    )
    assert rec["price_status"] == "SUSPICIOUS_HIGH"


def test_suspicious_low():
    rec = classify_price(
        {
            "name": "PINTURA",
            "list_price": 100,
            "recent_avg_price": 1000,
            "last_invoice_price": 1000,
        }
    )
    assert rec["price_status"] == "SUSPICIOUS_LOW"


def test_historical_difference_is_candidate():
    rec = classify_price(
        {
            "name": "GRAVA",
            "list_price": 2054.91,
            "recent_avg_price": 1217.70,
            "last_invoice_price": 1217.70,
        }
    )
    assert rec["price_status"] == "HISTORICAL_PRICE_DIFFERENCE"
    assert rec["recommended_action"] == "UPDATE_CANDIDATE"


def test_no_history():
    rec = classify_price({"name": "TONER HP", "list_price": 5645})
    assert rec["price_status"] == "NO_SALES_HISTORY"
    assert rec["recommended_action"] == "NO_ACTION"


def test_pricelist_dependent():
    rec = classify_price(
        {
            "name": "TV TCL",
            "list_price": 100,
            "pricelist_items": [{"pricelist": "Mayorista"}],
        }
    )
    assert rec["price_status"] == "PRICE_LIST_DEPENDENT"
    assert rec["recommended_action"] == "PRICELIST_REVIEW"
