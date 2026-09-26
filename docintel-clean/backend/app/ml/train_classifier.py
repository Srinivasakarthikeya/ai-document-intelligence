"""Train the document-type classifier.

Default: synthetic corpus generated from templates (so the repo works out of the box).
Better: drop real labeled .txt files into data/<label>/*.txt and run with --data data/.
    python -m app.ml.train_classifier [--data data/]
"""
import argparse
import random
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline, FeatureUnion

from ..config import MODEL_PATH

random.seed(42)
COMPANIES = ["Acme Corp", "Globex Pvt Ltd", "Initech", "Stark Industries", "Wayne Enterprises", "Tata Supplies",
             "Umbrella LLC", "Hooli", "Nimbus Traders", "Vertex Logistics", "Sunrise Foods", "Orbit Tech"]
ITEMS = ["Laptop", "Office chair", "Printer ink", "Cloud hosting", "Consulting hours", "A4 paper",
         "Router", "Software license", "Desk lamp", "Maintenance fee", "Coffee", "Sandwich"]


def _amt():
    return round(random.uniform(10, 50000), 2)


def _date():
    return f"{random.randint(1, 28):02d}/{random.randint(1, 12):02d}/202{random.randint(3, 6)}"


def _lines(n):
    return "\n".join(f"{random.choice(ITEMS)} {random.randint(1, 9)} {_amt()} {_amt()}" for _ in range(n))


TEMPLATES = {
    "invoice": lambda: f"""{random.choice(['TAX INVOICE', 'Invoice', 'INVOICE'])}
{random.choice(COMPANIES)}
Invoice No: INV-{random.randint(1000, 9999)}
Invoice Date: {_date()}
Due Date: {_date()}
Bill To: {random.choice(COMPANIES)}
{_lines(random.randint(1, 5))}
Subtotal: {_amt()}
{random.choice(['GST', 'Tax', 'VAT'])}: {_amt()}
{random.choice(['Total Amount Due', 'Grand Total', 'Amount Due'])}: {_amt()}
Payment terms: Net {random.choice([15, 30, 45])}""",
    "receipt": lambda: f"""{random.choice(COMPANIES)}
{random.choice(['RECEIPT', 'Sales Receipt', 'Cash Receipt'])}
{_date()} {random.randint(8, 22)}:{random.randint(10, 59)}
Cashier: {random.choice(['Anita', 'Ravi', 'John', 'Meera'])}
{_lines(random.randint(1, 4))}
Total: {_amt()}
Paid by {random.choice(['VISA card ending 4417', 'UPI', 'Cash', 'Mastercard'])}
Change: {round(random.uniform(0, 50), 2)}
Thank you for your purchase!""",
    "purchase_order": lambda: f"""PURCHASE ORDER
PO Number: PO-{random.randint(10000, 99999)}
Order Date: {_date()}
Vendor: {random.choice(COMPANIES)}
Ship To: {random.choice(COMPANIES)} Warehouse
Requested by: Procurement Dept
{_lines(random.randint(1, 5))}
Total: {_amt()}
Authorized signature""",
    "report": lambda: f"""{random.choice(['Quarterly Business Review', 'Annual Performance Report', 'Market Analysis Report'])}
Q{random.randint(1, 4)} FY{random.randint(23, 26)}
Executive Summary
Revenue grew {random.randint(2, 40)}% driven by {random.choice(['new customers', 'pricing changes', 'expansion'])}.
Key findings indicate {random.choice(['strong retention', 'rising costs', 'improved margins'])}.
Revenue: {_amt()}
Operating Margin: {random.randint(5, 40)}%
KPI summary and recommendations follow. Conclusion: continue investment.""",
    "contract": lambda: f"""{random.choice(['SERVICE AGREEMENT', 'NON-DISCLOSURE AGREEMENT', 'MASTER SERVICES AGREEMENT'])}
This Agreement is made between {random.choice(COMPANIES)} (hereinafter "Client") and {random.choice(COMPANIES)} (hereinafter "Provider").
Effective Date: {_date()}
1. Term. This agreement shall have a term of {random.randint(6, 36)} months.
2. Termination. Either party may terminate with 30 days written notice.
3. Confidentiality. Each party shall keep confidential information secret.
4. Governing Law. This agreement is governed by the laws of {random.choice(['India', 'Delaware', 'England'])}.
IN WITNESS WHEREOF the parties have signed.""",
    "other": lambda: random.choice([
        "Meeting notes: discussed roadmap, hiring plan and offsite logistics. Action items assigned.",
        "Dear team, please remember the office will be closed on Friday for maintenance. Regards, Admin",
        "Resume: Software engineer with 3 years experience in Python and React. Education: B.Tech.",
        "Menu: Paneer tikka, Veg biryani, Masala dosa, Filter coffee. Open 8am to 10pm daily.",
        f"Shipping label. Tracking {random.randint(10**9, 10**10)}. Handle with care. Fragile.",
    ]),
}


def synthetic(n_per_class=150):
    X, y = [], []
    for label, fn in TEMPLATES.items():
        for _ in range(n_per_class):
            X.append(fn())
            y.append(label)
    return X, y


def from_dir(root: Path):
    X, y = [], []
    for label_dir in root.iterdir():
        if label_dir.is_dir():
            for f in label_dir.glob("*.txt"):
                X.append(f.read_text(errors="ignore"))
                y.append(label_dir.name)
    return X, y


def build():
    return Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, lowercase=True)),
            # char n-grams make it robust to OCR noise ("lnvoice", "T0tal")
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
        ])),
        ("clf", LogisticRegression(max_iter=2000, C=5.0, class_weight="balanced")),
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=None)
    args = parser.parse_args()
    X, y = from_dir(args.data) if args.data else synthetic()
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    model = build().fit(Xtr, ytr)
    print(classification_report(yte, model.predict(Xte)))
    model.fit(X, y)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
