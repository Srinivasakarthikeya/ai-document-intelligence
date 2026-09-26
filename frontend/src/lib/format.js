export const IN_PROGRESS = ["queued", "ocr", "classifying", "extracting", "validating"];
export const isBusy = (s) => IN_PROGRESS.includes(s);

export const TYPE_LABEL = {
  invoice: "Invoice", receipt: "Receipt", purchase_order: "Purchase order",
  report: "Report", contract: "Contract", other: "Other",
};

export const STATUS_LABEL = {
  queued: "Queued", ocr: "Reading", classifying: "Classifying", extracting: "Extracting",
  validating: "Validating", completed: "Verified", needs_review: "Needs review", failed: "Failed",
};

export const FIELD_LABEL = {
  invoice_number: "Invoice number", invoice_date: "Invoice date", due_date: "Due date", vendor: "Vendor",
  bill_to: "Bill to", subtotal: "Subtotal", tax: "Tax", total: "Total", currency: "Currency", gstin: "GSTIN",
  emails: "Emails", phones: "Phones", merchant: "Merchant", date: "Date", payment_method: "Payment method",
  po_number: "PO number", order_date: "Order date", ship_to: "Ship to", title: "Title", report_date: "Report date",
  period: "Period", summary: "Summary", key_metrics: "Key metrics", parties: "Parties",
  effective_date: "Effective date", governing_law: "Governing law", term: "Term", line_items: "Line items",
};
export const fieldLabel = (k) => FIELD_LABEL[k] || k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

/** The facts a reviewer checks first, per document type, in reading order. */
export const KEY_FIELDS = {
  invoice: ["vendor", "invoice_number", "invoice_date", "due_date", "total"],
  receipt: ["merchant", "date", "payment_method", "total"],
  purchase_order: ["vendor", "po_number", "order_date", "total"],
  contract: ["parties", "effective_date", "term", "governing_law"],
  report: ["title", "period", "report_date"],
  other: ["emails", "phones"],
};

export const FIELD_ORDER = [
  "vendor", "merchant", "bill_to", "ship_to", "invoice_number", "po_number", "invoice_date", "order_date", "date",
  "due_date", "subtotal", "tax", "total", "currency", "payment_method", "gstin", "title", "period", "report_date",
  "summary", "parties", "effective_date", "term", "governing_law", "emails", "phones", "key_metrics",
];

export const NUMERIC = new Set(["subtotal", "tax", "total"]);
export const DATE = new Set(["invoice_date", "due_date", "date", "order_date", "report_date", "effective_date"]);
export const LIST = new Set(["emails", "phones", "parties"]);
export const READ_ONLY = new Set(["line_items", "key_metrics"]);

/** Which field a validation rule is about, so issues can sit next to the value they concern. */
export function ruleField(rule) {
  const [kind, key] = rule.split(":");
  if (key) return key;
  return { totals_reconcile: "total", positive_total: "total", due_after_issue: "due_date",
           line_item_math: "line_items", line_items_sum: "line_items" }[kind] || null;
}

export function money(value, currency) {
  if (typeof value !== "number") return String(value ?? "");
  try {
    return new Intl.NumberFormat(undefined, { style: currency ? "currency" : "decimal", currency: currency || undefined,
      minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
  } catch {
    return value.toFixed(2);
  }
}

export function displayValue(key, value, currency) {
  if (value == null || value === "") return "";
  if (NUMERIC.has(key)) return money(value, currency);
  if (DATE.has(key)) {
    const d = new Date(`${value}T00:00:00`);
    return isNaN(d) ? value : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }
  if (Array.isArray(value)) return value.map((v) => (typeof v === "object" ? `${v.name}: ${v.value}` : v)).join(", ");
  return String(value);
}

export function editValue(key, value) {
  if (value == null) return "";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

/** Parse what the reviewer typed; returns { value } or { error }. */
export function parseInput(key, raw) {
  const s = raw.trim();
  if (!s) return { value: "" };
  if (NUMERIC.has(key)) {
    const n = Number(s.replace(/[,\s₹$€£]/g, ""));
    return isNaN(n) ? { error: "Enter a number, like 1180.50" } : { value: n };
  }
  if (DATE.has(key)) {
    return /^\d{4}-\d{2}-\d{2}$/.test(s) && !isNaN(new Date(s)) ? { value: s } : { error: "Use YYYY-MM-DD" };
  }
  if (LIST.has(key)) return { value: s.split(",").map((x) => x.trim()).filter(Boolean) };
  return { value: s };
}

export function relTime(iso) {
  const diff = (Date.now() - new Date(iso)) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function bytes(n) {
  if (!n) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export const METHOD_LABEL = { native: "Embedded PDF text", ocr: "OCR", hybrid: "Embedded text + OCR", plain: "Plain text" };
