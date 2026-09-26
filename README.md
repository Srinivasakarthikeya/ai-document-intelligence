# AI-Powered Business Document Intelligence System

   ![Docket review workspace](screenshot.png)

Upload invoices, receipts, purchase orders, reports and contracts. The system reads them (native PDF text or OCR for scans), classifies the document type with an ML model, extracts structured fields, validates them against business rules, and stores everything in SQL — searchable from a React dashboard with live processing status.

**Stack:** Python · FastAPI · SQLAlchemy (SQLite / PostgreSQL) · Tesseract OCR · pdfplumber · scikit-learn · React (Vite) · Docker

## Pipeline

```
Upload -> OCR -> Classify -> Extract -> Validate -> Verified | Needs review | Failed
```

- **OCR** (`services/ocr.py`): pdfplumber text per page; pages with < 40 chars fall back to Tesseract at 300 dpi with grayscale, autocontrast, sharpen and upscaling.
- **Classify** (`services/classifier.py`): TF-IDF (word 1–2 grams + char 3–5 grams, robust to OCR noise) + Logistic Regression. Keyword fallback if no model is trained.
- **Extract** (`services/extractor.py`): per-type rules with confidence scores — invoice no., dates (normalized to ISO), vendor, bill-to, subtotal/tax/total, currency, GSTIN, emails, phones, line items, PO no., ship-to, contract parties, term, governing law, report period and metrics.
- **Validate** (`services/validator.py`): required fields, subtotal + tax = total, qty × price = amount, line-item sum, due ≥ issue date, future dates, positive totals, low-confidence flags.
- **Track** (`services/pipeline.py`): every stage writes a `ProcessingEvent` (stage, message, duration) that the UI shows as a live timeline.

Users can correct any field in the UI (human-in-the-loop); corrections are marked `manual` and validation re-runs.

## Review workspace (frontend)

- **Side-by-side review:** extracted fields on the left, the original document on the right.
- **Issues inline:** each validation problem is marked on the field it affects; missing required fields appear as empty rows you can fill.
- **Edit and re-check:** inline edits are type-checked (numbers, `YYYY-MM-DD` dates) and validation re-runs instantly.
- **Approval flow:** approve when clean, or explicitly "approve anyway" with open errors (two-step confirm).
- **Fast:** page-wide drag-and-drop with upload progress, live pipeline progress, keyboard shortcuts (`/` search, `j`/`k` move, `u` upload).
- **Monochrome:** status is conveyed by fill and line style, not colour, so it stays readable for colour-blind users.

## Backend hardening

- Uploads are streamed with a size cap, checked by file signature (a renamed `.exe` is rejected), and de-duplicated by SHA-256.
- Timezone-aware timestamps, structured logging, a global error handler, and per-document processing time.
- Existing SQLite databases are upgraded in place when new columns are added.

## Project structure

```
backend/
  app/
    main.py              REST API
    models.py            Document, ProcessingEvent (SQLAlchemy)
    services/            ocr, classifier, extractor, validator, pipeline
    ml/train_classifier.py
  tests/                 pytest (unit + API + OCR)
  scripts_make_samples.py
frontend/src/            React dashboard
samples/                 test documents (native PDF, scanned PNG, one with deliberate errors)
```

## Run locally

Prereqs: Python 3.10+, Node 18+, Tesseract + Poppler
(`sudo apt install tesseract-ocr poppler-utils` · `brew install tesseract poppler` · Windows: UB Mannheim Tesseract installer, add to PATH).

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.ml.train_classifier
uvicorn app.main:app --reload          # API docs: http://localhost:8000/docs

# frontend (new terminal)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

Tests: `cd backend && pytest -q`

## Run with Docker (PostgreSQL)

```bash
docker compose up --build              # UI: http://localhost:3000  API: http://localhost:8000/docs
```

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/documents` | Upload one or more files (multipart `files`) |
| GET | `/api/documents?q=&status=&doc_type=` | List, full-text search, filter |
| GET | `/api/documents/{id}` | Fields, validation, raw text, timeline |
| PATCH | `/api/documents/{id}/fields` | Correct fields and re-validate |
| POST | `/api/documents/{id}/approve?force=` | Reviewer sign-off (blocked by open errors unless forced) |
| POST | `/api/documents/{id}/reprocess` | Re-run the pipeline |
| GET | `/api/export.csv?status=&doc_type=&q=` | Flat CSV of key fields for Excel / ERP import |
| GET | `/api/documents/{id}/file` | Original file |
| DELETE | `/api/documents/{id}` | Delete |
| GET | `/api/stats` | Counts by status and type |

## Training on real data

The bundled classifier trains on a synthetic template corpus so the repo works out of the box — its ~100% score is on synthetic data, not a real-world number. For real accuracy, put labeled text in `backend/data/<label>/*.txt` (e.g. OCR output from RVL-CDIP or SROIE) and run:

```bash
python -m app.ml.train_classifier --data data/
```

## Next steps

- Layout-aware extraction (LayoutLMv3 / Donut) or an LLM with a JSON schema — `extractor.extract_fields` is the single entry point.
- Celery + Redis instead of FastAPI `BackgroundTasks` for scaling.
- PostgreSQL `tsvector` full-text indexes for large corpora.
