"""Fórmulas de retenciones RD (Ley 30-26). Sin IDs de Odoo."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")


def _d(value):
    return Decimal(str(value))


def money(value):
    return _d(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def isr_on_untaxed(untaxed, rate):
    """ISR sobre base sujeta (sin ITBIS)."""
    return money(_d(untaxed) * _d(rate) / Decimal("100"))


def isr_technical_presumed(untaxed, presumed_pct=20, legal_rate=15):
    """15% ISR sobre renta neta presunta = presumed_pct del bruto.

    Efectivo: 20% × 15% = 3% del valor bruto sujeto.
    """
    original = money(untaxed)
    presumed = money(original * _d(presumed_pct) / Decimal("100"))
    withheld = money(presumed * _d(legal_rate) / Decimal("100"))
    return {
        "base_original": original,
        "base_presunta": presumed,
        "tasa": money(legal_rate),
        "retencion": withheld,
        "efectiva_pct": money(_d(presumed_pct) * _d(legal_rate) / Decimal("100")),
    }


def itbis_of_tax(itbis_amount, rate):
    """Retención ITBIS sobre el ITBIS facturado, nunca sobre el subtotal."""
    return money(_d(itbis_amount) * _d(rate) / Decimal("100"))


def invoice_net(untaxed, itbis, isr_withheld=0, itbis_withheld=0, other_withheld=0):
    total = money(_d(untaxed) + _d(itbis))
    withheld = money(_d(isr_withheld) + _d(itbis_withheld) + _d(other_withheld))
    return {
        "untaxed": money(untaxed),
        "itbis": money(itbis),
        "total": total,
        "isr_withheld": money(isr_withheld),
        "itbis_withheld": money(itbis_withheld),
        "other_withheld": money(other_withheld),
        "neto": money(total - withheld),
    }


def professional_pf_example(untaxed=100000, itbis_rate=18):
    itbis = money(_d(untaxed) * _d(itbis_rate) / Decimal("100"))
    isr = isr_on_untaxed(untaxed, 15)
    itbis_wh = itbis_of_tax(itbis, 100)
    return invoice_net(untaxed, itbis, isr_withheld=isr, itbis_withheld=itbis_wh)


def technical_pf_example(untaxed=100000, itbis_rate=18):
    itbis = money(_d(untaxed) * _d(itbis_rate) / Decimal("100"))
    tech = isr_technical_presumed(untaxed)
    itbis_wh = itbis_of_tax(itbis, 100)
    return invoice_net(
        untaxed, itbis, isr_withheld=tech["retencion"], itbis_withheld=itbis_wh
    )


def itbis_30_pj_example(untaxed=100000, itbis_rate=18):
    itbis = money(_d(untaxed) * _d(itbis_rate) / Decimal("100"))
    itbis_wh = itbis_of_tax(itbis, 30)
    return invoice_net(untaxed, itbis, itbis_withheld=itbis_wh)
