"""Business-rule validation. Each check: {rule, level: error|warning|ok, message}."""
from datetime import date

REQUIRED = {
    "invoice": ["invoice_number", "invoice_date", "total"],
    "receipt": ["date", "total"],
    "purchase_order": ["po_number", "total"],
    "report": ["title"],
    "contract": ["parties", "effective_date"],
}
LOW_CONFIDENCE = 0.6
TYPE_CONFIDENCE_MIN = 0.5
TOLERANCE = 0.02  # 2 paise / cents rounding slack


def _v(fields, key):
    f = fields.get(key)
    return f["value"] if f else None


def validate(doc_type: str, type_conf: float, fields: dict) -> list[dict]:
    checks = []

    def add(rule, level, message):
        checks.append({"rule": rule, "level": level, "message": message})

    if type_conf < TYPE_CONFIDENCE_MIN:
        add("classification_confidence", "warning", f"Document type '{doc_type}' predicted with low confidence ({type_conf:.0%}).")

    for key in REQUIRED.get(doc_type, []):
        if _v(fields, key) in (None, "", []):
            add(f"required:{key}", "error", f"Missing required field '{key}'.")
        else:
            add(f"required:{key}", "ok", f"'{key}' present.")

    subtotal, tax, total = _v(fields, "subtotal"), _v(fields, "tax"), _v(fields, "total")
    if subtotal is not None and tax is not None and total is not None:
        if abs(subtotal + tax - total) <= TOLERANCE:
            add("totals_reconcile", "ok", "Subtotal + tax equals total.")
        else:
            add("totals_reconcile", "error", f"Subtotal ({subtotal}) + tax ({tax}) ≠ total ({total}).")

    items = _v(fields, "line_items") or []
    if items:
        bad = [i["description"] for i in items
               if None not in (i["quantity"], i["unit_price"], i["amount"])
               and abs(i["quantity"] * i["unit_price"] - i["amount"]) > TOLERANCE]
        if bad:
            add("line_item_math", "error", f"Quantity × unit price mismatch on: {', '.join(bad[:3])}.")
        else:
            add("line_item_math", "ok", f"{len(items)} line item(s) check out.")
        target = subtotal if subtotal is not None else (total if tax is None else None)
        line_sum = sum(i["amount"] or 0 for i in items)
        if target is not None and abs(line_sum - target) > TOLERANCE:
            add("line_items_sum", "warning", f"Line items sum to {line_sum:.2f}, expected {target:.2f}.")

    inv_d, due_d = _v(fields, "invoice_date"), _v(fields, "due_date")
    if inv_d and due_d and due_d < inv_d:
        add("due_after_issue", "error", "Due date is before invoice date.")
    for key in ("invoice_date", "date", "order_date"):
        d = _v(fields, key)
        if d and d > date.today().isoformat():
            add(f"future_date:{key}", "warning", f"'{key}' is in the future ({d}).")

    if total is not None and total <= 0:
        add("positive_total", "error", "Total must be greater than zero.")

    for key, f in fields.items():
        if f and f.get("source") != "manual" and f.get("confidence", 1) < LOW_CONFIDENCE:
            add(f"low_confidence:{key}", "warning", f"'{key}' extracted with low confidence — please review.")

    return checks


def counts(checks: list[dict]) -> tuple[int, int]:
    return (sum(c["level"] == "error" for c in checks), sum(c["level"] == "warning" for c in checks))


def outcome(checks: list[dict]) -> str:
    return "needs_review" if any(c["level"] in ("error", "warning") for c in checks) else "completed"
