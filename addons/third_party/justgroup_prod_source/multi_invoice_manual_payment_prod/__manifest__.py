{
    "name": "Multi Invoice Manual Payment",
    "version": "19.0.1.5.4",
    "summary": "Una transferencia → un account.payment → N conciliaciones → un recibo.",
    "category": "Accounting/Accounting",
    "author": "DynamicsPM / Justech",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "views/multi_invoice_manual_payment_views.xml",
        "views/report_payment_receipt.xml",
    ],
    "installable": True,
    "application": False,
}
