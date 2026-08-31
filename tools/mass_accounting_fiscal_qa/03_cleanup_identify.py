# -*- coding: utf-8 -*-
"""Identify DXQA mass QA records. DO NOT delete until authorized."""

TAG = "DXQA-MASS-20260831"
print("CLEANUP_EXECUTED = NO")
print("TAG", TAG)
Move = env["account.move"]
Pay = env["account.payment"]
Partner = env["res.partner"]
Product = env["product.product"]
moves = Move.search(["|", ("ref", "like", TAG), ("ref", "like", "DXQA-PROBE-")])
pays = Pay.search(["|", ("memo", "like", TAG), ("payment_reference", "like", "DXQA-")])
partners = Partner.search(
    ["|", ("name", "like", "DXQA "), ("name", "like", "DXQA Customer")]
)
products = Product.search([("default_code", "like", "DXQA-")])
print(
    "MOVES",
    len(moves),
    "PAYMENTS",
    len(pays),
    "PARTNERS",
    len(partners),
    "PRODUCTS",
    len(products),
)
print("MOVE_IDS", moves.ids)
print("PAYMENT_IDS", pays.ids)
print("PARTNER_IDS", partners.ids)
print("PRODUCT_IDS", products.ids)
print(
    "To delete after authorization: account.move (incl. payments moves), account.payment, then partners/products."
)
