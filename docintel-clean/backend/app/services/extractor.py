"""Rule-based field extraction tuned per document type. Each field returns value + confidence."""
import re
from datetime import datetime

MONEY = r"(?:₹|Rs\.?|INR|\$|USD|€|EUR|£)?\s?([0-9]{1,3}(?:[,][0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"
DATE_PATTERNS = [
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+\d{4})\b",
    r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
]
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%y", "%d %b %Y", "%d %B %Y",
                "%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y"]


def normalize_date(raw: str) -> str | None:
    cleaned = raw.replace(".", "").replace(",", ", ").replace("  ", " ").strip()
    for fmt in DATE_FORMATS:
        for candidate in (cleaned, cleaned.replace(", ", " ")):
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                continue
    return None


def to_number(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _field(value, confidence, source=None):
    return {"value": value, "confidence": round(confidence, 2), "source": source}


def _labeled(text, labels, value_pattern=r"([A-Za-z0-9\-/#]+)"):
    for label in labels:
        m = re.search(rf"{label}\s*[:#.]?\s*{value_pattern}", text, re.IGNORECASE)
        if m:
            return m.group(1).strip(), m.group(0).strip()
    return None, None


def _labeled_amount(text, labels):
    for label in labels:
        m = re.search(rf"^.*?\b{label}\b[^\n0-9]*?{MONEY}\s*$", text, re.IGNORECASE | re.MULTILINE)
        if m:
            return to_number(m.group(1)), m.group(0).strip()
    return None, None


def _labeled_date(text, labels):
    for label in labels:
        for pat in DATE_PATTERNS:
            m = re.search(rf"{label}\s*[:.]?\s*{pat}", text, re.IGNORECASE)
            if m:
                return normalize_date(m.group(1)), m.group(0).strip()
    return None, None


def _any_date(text):
    for pat in DATE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m and (d := normalize_date(m.group(1))):
            return d, m.group(0)
    return None, None


def _currency(text):
    for sym, code in [("₹", "INR"), ("Rs", "INR"), ("INR", "INR"), ("$", "USD"), ("USD", "USD"),
                      ("€", "EUR"), ("EUR", "EUR"), ("£", "GBP")]:
        if sym in text:
            return code
    return None


def _party(text, labels):
    for label in labels:
        m = re.search(rf"{label}\s*[:]?\s*\n?\s*([^\n]{{2,80}})", text, re.IGNORECASE)
        if m:
            return m.group(1).strip(), m.group(0).strip()
    return None, None


def _line_items(text):
    """Lines shaped like: <description> <qty> <unit price> <amount>."""
    items = []
    pattern = re.compile(rf"^\s*([A-Za-z][A-Za-z0-9 &()\-/.,]{{2,60}}?)\s+(\d+(?:\.\d+)?)\s+{MONEY}\s+{MONEY}\s*$", re.MULTILINE)
    for m in pattern.finditer(text):
        desc = m.group(1).strip()
        if re.search(r"total|tax|gst|subtotal|amount", desc, re.IGNORECASE):
            continue
        items.append({"description": desc, "quantity": to_number(m.group(2)),
                      "unit_price": to_number(m.group(3)), "amount": to_number(m.group(4))})
    return items


SKIP_HEADER = re.compile(r"invoice|receipt|purchase order|bill|gstin|@|\d{4,}", re.IGNORECASE)


def _header_name(text):
    """First short line near the top that looks like a company name rather than a doc title/number."""
    for line in [l.strip() for l in text.splitlines() if l.strip()][:6]:
        if 2 < len(line) < 60 and not SKIP_HEADER.search(line):
            return line
    return None


def extract_common(text):
    fields = {}
    emails = sorted(set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)))
    if emails:
        fields["emails"] = _field(emails, 0.95)
    phones = sorted(set(p.strip() for p in re.findall(r"(?:\+\d{1,3}[\s-]?)?\(?\d{3,5}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}", text) if len(re.sub(r"\D", "", p)) >= 10))
    if phones:
        fields["phones"] = _field(phones, 0.8)
    gst = re.search(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b", text)
    if gst:
        fields["gstin"] = _field(gst.group(1), 0.95, gst.group(0))
    if cur := _currency(text):
        fields["currency"] = _field(cur, 0.85)
    return fields


def extract_invoice(text):
    f = {}
    v, s = _labeled(text, [r"invoice\s*(?:no|number|#)", r"inv\s*(?:no|#)", r"bill\s*no"])
    if v: f["invoice_number"] = _field(v, 0.9, s)
    v, s = _labeled_date(text, [r"invoice\s*date", r"date\s*of\s*issue", r"\bdate"])
    if v: f["invoice_date"] = _field(v, 0.85, s)
    v, s = _labeled_date(text, [r"due\s*date", r"payment\s*due"])
    if v: f["due_date"] = _field(v, 0.85, s)
    v, s = _party(text, [r"(?:from|seller|vendor)\s*:"])
    if v:
        f["vendor"] = _field(v, 0.8, s)
    elif header := _header_name(text):
        f["vendor"] = _field(header, 0.6, header)
    v, s = _party(text, [r"bill(?:ed)?\s*to", r"customer"])
    if v: f["bill_to"] = _field(v, 0.75, s)
    v, s = _labeled_amount(text, [r"sub\s*-?total"])
    if v is not None: f["subtotal"] = _field(v, 0.85, s)
    v, s = _labeled_amount(text, [r"(?:total\s*)?(?:tax|gst|vat|igst|cgst\s*\+\s*sgst)"])
    if v is not None: f["tax"] = _field(v, 0.8, s)
    v, s = _labeled_amount(text, [r"grand\s*total", r"total\s*amount(?:\s*due)?", r"amount\s*due", r"total"])
    if v is not None: f["total"] = _field(v, 0.9, s)
    items = _line_items(text)
    if items: f["line_items"] = _field(items, 0.7)
    return f


def extract_receipt(text):
    f = {}
    if merchant := _header_name(text):
        f["merchant"] = _field(merchant, 0.6, merchant)
    v, s = _any_date(text)
    if v: f["date"] = _field(v, 0.8, s)
    v, s = _labeled_amount(text, [r"total", r"amount\s*paid"])
    if v is not None: f["total"] = _field(v, 0.85, s)
    m = re.search(r"\b(visa|mastercard|amex|rupay|upi|cash)\b", text, re.IGNORECASE)
    if m: f["payment_method"] = _field(m.group(1).upper(), 0.8, m.group(0))
    items = _line_items(text)
    if items: f["line_items"] = _field(items, 0.65)
    return f


def extract_purchase_order(text):
    f = {}
    v, s = _labeled(text, [r"p\.?o\.?\s*(?:no|number|#)", r"purchase\s*order\s*(?:no|number|#)"])
    if v: f["po_number"] = _field(v, 0.9, s)
    v, s = _labeled_date(text, [r"(?:po|order)\s*date", r"\bdate"])
    if v: f["order_date"] = _field(v, 0.85, s)
    v, s = _party(text, [r"vendor\s*:?", r"supplier"])
    if v: f["vendor"] = _field(v, 0.75, s)
    v, s = _party(text, [r"ship\s*to"])
    if v: f["ship_to"] = _field(v, 0.75, s)
    v, s = _labeled_amount(text, [r"grand\s*total", r"total"])
    if v is not None: f["total"] = _field(v, 0.85, s)
    items = _line_items(text)
    if items: f["line_items"] = _field(items, 0.7)
    return f


def extract_report(text):
    f = {}
    title = next((l.strip() for l in text.splitlines() if len(l.strip()) > 5), None)
    if title: f["title"] = _field(title, 0.6, title)
    v, s = _any_date(text)
    if v: f["report_date"] = _field(v, 0.7, s)
    m = re.search(r"\b(Q[1-4])\s*(?:FY)?\s*'?(\d{2,4})\b", text)
    if m: f["period"] = _field(f"{m.group(1)} {m.group(2)}", 0.85, m.group(0))
    m = re.search(r"executive\s+summary\s*:?\s*\n?(.{20,600}?)(?:\n\s*\n|$)", text, re.IGNORECASE | re.DOTALL)
    if m: f["summary"] = _field(" ".join(m.group(1).split()), 0.7)
    metrics = re.findall(r"([A-Za-z][A-Za-z ]{2,30}):\s*(" + MONEY + r"%?)", text)
    if metrics:
        f["key_metrics"] = _field([{"name": k.strip(), "value": v.strip()} for k, v, _ in metrics[:10]], 0.6)
    return f


def extract_contract(text):
    f = {}
    m = re.search(r"between\s+([^(\n,]{2,80}?)\s*(?:\([^)]*\)\s*)?,?\s*and\s+([^(\n,]{2,80}?)\s*(?:\(|,|\.\s|\n)", text, re.IGNORECASE)
    if m: f["parties"] = _field([m.group(1).strip(), m.group(2).strip()], 0.65, m.group(0)[:160])
    v, s = _labeled_date(text, [r"effective\s*(?:date|from|as of)", r"dated", r"made on"])
    if v: f["effective_date"] = _field(v, 0.8, s)
    m = re.search(r"governed by the laws of\s+([A-Za-z ,]+?)[.\n]", text, re.IGNORECASE)
    if m: f["governing_law"] = _field(m.group(1).strip(), 0.85, m.group(0))
    m = re.search(r"term of\s+(\d+\s*(?:months?|years?))", text, re.IGNORECASE)
    if m: f["term"] = _field(m.group(1), 0.8, m.group(0))
    return f


EXTRACTORS = {
    "invoice": extract_invoice,
    "receipt": extract_receipt,
    "purchase_order": extract_purchase_order,
    "report": extract_report,
    "contract": extract_contract,
}


def extract_fields(text: str, doc_type: str) -> dict:
    fields = extract_common(text)
    fn = EXTRACTORS.get(doc_type)
    if fn:
        fields.update(fn(text))
    return fields
