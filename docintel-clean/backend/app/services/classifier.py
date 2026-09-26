"""Document type classifier: TF-IDF + Logistic Regression, with a keyword fallback."""
import joblib

from ..config import MODEL_PATH

LABELS = ["invoice", "receipt", "purchase_order", "report", "contract", "other"]

KEYWORDS = {
    "invoice": ["invoice", "bill to", "amount due", "due date", "invoice no", "gstin", "tax invoice"],
    "receipt": ["receipt", "thank you for your purchase", "cashier", "change", "paid by", "card ending"],
    "purchase_order": ["purchase order", "po number", "ship to", "vendor", "requested by", "p.o."],
    "report": ["executive summary", "quarterly", "report", "findings", "conclusion", "revenue", "kpi"],
    "contract": ["agreement", "party", "hereinafter", "terms and conditions", "termination", "governing law"],
}

_model = None


def _load():
    global _model
    if _model is None and MODEL_PATH.exists():
        _model = joblib.load(MODEL_PATH)
    return _model


def _keyword_classify(text: str) -> tuple[str, float]:
    t = text.lower()
    scores = {label: sum(t.count(k) for k in kws) for label, kws in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    if total == 0:
        return "other", 0.0
    return best, round(scores[best] / total, 3)


def classify(text: str) -> tuple[str, float]:
    if not text.strip():
        return "other", 0.0
    model = _load()
    if model is None:
        return _keyword_classify(text)
    probs = model.predict_proba([text])[0]
    idx = probs.argmax()
    return str(model.classes_[idx]), round(float(probs[idx]), 3)
