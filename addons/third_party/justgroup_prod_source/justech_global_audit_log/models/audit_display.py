"""Human-readable labels and snapshot filtering for forensic audit display."""

MODEL_LABELS = {
    "res.partner": "Contacto",
    "sale.order": "Cotización",
    "product.template": "Producto",
    "account.move": "Factura",
    "account.payment": "Pago",
    "stock.picking": "Transferencia",
    "stock.move": "Movimiento de stock",
    "pos.order": "Venta POS",
    "pos.session": "Sesión POS",
}

IMPORTANT_FIELDS = {
    "res.partner": (
        "name",
        "vat",
        "phone",
        "mobile",
        "email",
        "street",
        "city",
        "country_id",
        "customer_rank",
        "supplier_rank",
        "user_id",
    ),
    "sale.order": (
        "name",
        "partner_id",
        "date_order",
        "state",
        "amount_total",
        "currency_id",
        "user_id",
        "client_order_ref",
        "payment_term_id",
    ),
    "product.template": (
        "name",
        "default_code",
        "list_price",
        "standard_price",
        "type",
        "categ_id",
        "taxes_id",
    ),
    "account.move": (
        "name",
        "partner_id",
        "invoice_date",
        "state",
        "amount_total",
        "ref",
        "journal_id",
        "currency_id",
    ),
}

FIELD_LABELS = {
    "name": "Nombre",
    "vat": "RNC/Cédula",
    "phone": "Teléfono",
    "mobile": "Móvil",
    "email": "Correo",
    "street": "Dirección",
    "city": "Ciudad",
    "country_id": "País",
    "customer_rank": "Tipo cliente",
    "supplier_rank": "Tipo proveedor",
    "user_id": "Vendedor",
    "partner_id": "Cliente",
    "date_order": "Fecha",
    "state": "Estado",
    "amount_total": "Total",
    "currency_id": "Moneda",
    "client_order_ref": "Referencia cliente",
    "payment_term_id": "Plazo de pago",
    "default_code": "Código interno",
    "list_price": "Precio venta",
    "standard_price": "Costo",
    "type": "Tipo",
    "categ_id": "Categoría",
    "taxes_id": "Impuestos",
    "invoice_date": "Fecha",
    "ref": "NCF",
    "journal_id": "Diario",
    "note": "Notas",
}

TECHNICAL_SNAPSHOT_KEYS = frozenset(
    {
        "access_url",
        "access_token",
        "access_warning",
        "activity_ids",
        "activity_state",
        "activity_type_id",
        "activity_user_id",
        "message_ids",
        "message_follower_ids",
        "message_partner_ids",
        "message_needaction",
        "message_has_error",
        "message_attachment_count",
        "message_main_attachment_id",
        "website_message_ids",
        "display_name",
        "__last_update",
        "write_date",
        "write_uid",
        "create_date",
        "create_uid",
        "id",
    }
)

ACTION_LABELS = {
    "create": "Creó",
    "write": "Modificó",
    "unlink": "Eliminó",
    "event": "Evento",
}


def label_for_field(field_key, field_description=None):
    if field_key in ("__create__", "__unlink__", "__event__"):
        return ""
    if field_description and field_description not in field_key:
        return field_description
    return FIELD_LABELS.get(field_key, field_key.replace("_", " ").capitalize())


def model_label(model_name, model_description=None):
    return MODEL_LABELS.get(model_name) or model_description or model_name or "Documento"


def display_scalar(value, log=None):
    if value in (False, None, ""):
        return "vacío"
    text = str(value).strip()
    if text in ("False", "0.00", "0"):
        return "vacío"
    if text.startswith("{") or text.startswith("["):
        return "…"
    if len(text) > 160:
        return f"{text[:160]}…"
    return text


def parse_snapshot(raw):
    import json

    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def is_relevant_snapshot_value(value):
    if value in (False, None, "", "False", 0, 0.0, "0", "0.0", "0.00"):
        return False
    text = str(value).strip()
    if not text or text == "[]":
        return False
    if text.startswith("{") or text.startswith("["):
        return False
    return True


def important_field_items(model_name, data):
    keys = IMPORTANT_FIELDS.get(model_name, ())
    items = []
    seen = set()
    for key in keys:
        if key not in data or key in TECHNICAL_SNAPSHOT_KEYS:
            continue
        value = data.get(key)
        if not is_relevant_snapshot_value(value):
            continue
        label = label_for_field(key)
        items.append((label, str(value)))
        seen.add(key)
    if items:
        return items
    for key, value in sorted(data.items()):
        if key in TECHNICAL_SNAPSHOT_KEYS or key in seen or key.startswith("_"):
            continue
        if not is_relevant_snapshot_value(value):
            continue
        items.append((label_for_field(key), str(value)))
        if len(items) >= 8:
            break
    return items


def format_items_inline(items, max_items=4):
    if not items:
        return "—"
    preview = items[:max_items]
    text = " · ".join(f"{label}: {value}" for label, value in preview)
    if len(items) > max_items:
        text += f" · (+{len(items) - max_items} más)"
    return text


def build_display_payload(vals, user_name=None):
    """Build stored forensic display fields from raw audit log values."""
    operation = vals.get("operation_type")
    model_name = vals.get("model_name")
    model_description = vals.get("model_description")
    record_name = vals.get("record_name") or f"#{vals.get('record_id', 0)}"
    field_name = vals.get("field_name")
    field_description = vals.get("field_description")
    old_value = vals.get("old_value") or ""
    new_value = vals.get("new_value") or ""
    user = user_name or "Sistema"

    mlabel = model_label(model_name, model_description)
    action = ACTION_LABELS.get(operation, operation or "")
    doc = f'"{record_name}"' if record_name else f"#{vals.get('record_id', 0)}"

    field_label = label_for_field(field_name, field_description)
    if field_name in ("__create__", "__unlink__", "__event__"):
        field_label_display = "—"
    else:
        field_label_display = field_label or "—"

    before_display = "—"
    after_display = "—"
    changes_rows = []

    if operation == "create" or field_name == "__create__":
        items = important_field_items(model_name, parse_snapshot(new_value))
        after_display = format_items_inline(items)
        for label, value in items:
            changes_rows.append((label, "—", value))
        human_summary = f'{user} creó el {mlabel.lower()} {doc}.'
    elif operation == "unlink" or field_name == "__unlink__":
        items = important_field_items(model_name, parse_snapshot(old_value))
        before_display = format_items_inline(items)
        for label, value in items:
            changes_rows.append((label, value, "—"))
        human_summary = f'{user} eliminó el {mlabel.lower()} {doc}.'
    elif operation == "write":
        before_display = display_scalar(old_value)
        after_display = display_scalar(new_value)
        changes_rows.append((field_label_display, before_display, after_display))
        if field_label_display.lower() in ("teléfono", "phone", "móvil", "mobile"):
            human_summary = (
                f'{user} modificó el {field_label_display.lower()} del {mlabel.lower()} {doc}.'
            )
        else:
            human_summary = (
                f'{user} cambió {field_label_display} de {before_display} a {after_display} '
                f'en el {mlabel.lower()} {doc}.'
            )
    else:
        before_display = display_scalar(old_value) if old_value else "—"
        after_display = display_scalar(new_value) if new_value else "—"
        human_summary = f'{user} registró un evento en {mlabel.lower()} {doc}.'

    search_parts = [
        record_name,
        mlabel,
        human_summary,
        field_label_display,
        before_display,
        after_display,
        old_value if not old_value.startswith("{") else "",
        new_value if not new_value.startswith("{") else "",
    ]
    for part in changes_rows:
        search_parts.extend(part)

    return {
        "human_summary": human_summary,
        "model_label": mlabel,
        "document_label": record_name,
        "field_label_display": field_label_display,
        "before_display": before_display,
        "after_display": after_display,
        "action_label": action,
        "search_text": " ".join(part for part in search_parts if part and part != "—"),
        "changes_rows": changes_rows,
    }


def build_changes_html(rows, operation=None):
    if not rows:
        return "<p>Sin cambios registrados.</p>"
    if operation in ("create",) or (len(rows) > 0 and rows[0][1] == "—" and rows[0][2] != "—"):
        header = "<thead><tr><th>Campo</th><th>Valor creado</th></tr></thead>"
        body = "".join(
            f"<tr><td>{label}</td><td>{after}</td></tr>" for label, _before, after in rows
        )
    elif operation in ("unlink",) or (len(rows) > 0 and rows[0][2] == "—"):
        header = "<thead><tr><th>Campo</th><th>Valor antes de eliminar</th></tr></thead>"
        body = "".join(
            f"<tr><td>{label}</td><td>{before}</td></tr>" for label, before, _after in rows
        )
    else:
        header = "<thead><tr><th>Campo</th><th>Antes</th><th>Después</th></tr></thead>"
        body = "".join(
            f"<tr><td>{label}</td><td>{before}</td><td>{after}</td></tr>"
            for label, before, after in rows
        )
    return (
        '<table class="table table-sm o_audit_changes_table">'
        f"{header}<tbody>{body}</tbody></table>"
    )


def build_timeline_label(log_vals, user_name=None):
    payload = build_display_payload(log_vals, user_name=user_name)
    time_part = ""
    change_date = log_vals.get("change_date")
    if change_date:
        from odoo import fields

        dt = fields.Datetime.to_datetime(change_date)
        time_part = dt.strftime("%I:%M %p").lstrip("0")
    summary = payload["human_summary"]
    if time_part:
        return f"{time_part} — {summary}"
    return summary
