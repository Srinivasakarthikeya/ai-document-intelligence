from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import extractor, validator

SAMPLES = Path(__file__).resolve().parent.parent.parent / "samples"

INVOICE = """INVOICE
Acme Corp
Invoice No: INV-1001
Invoice Date: 01/08/2026
Due Date: 31/08/2026
Bill To: Globex
Widget 2 50.00 100.00
Subtotal: 100.00
Tax: 18.00
Total: 118.00"""


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # runs lifespan -> creates tables
        yield c


def _upload(client, name, data, mime="text/plain"):
    r = client.post("/api/documents", files=[("files", (name, data, mime))])
    return r


# --- unit ---------------------------------------------------------------

def test_invoice_extraction():
    f = extractor.extract_fields(INVOICE, "invoice")
    assert f["invoice_number"]["value"] == "INV-1001"
    assert f["invoice_date"]["value"] == "2026-08-01"
    assert f["total"]["value"] == 118.0
    assert f["line_items"]["value"][0]["amount"] == 100.0


def test_validation_catches_bad_totals():
    f = extractor.extract_fields(INVOICE.replace("Total: 118.00", "Total: 150.00"), "invoice")
    checks = validator.validate("invoice", 0.95, f)
    assert any(c["rule"] == "totals_reconcile" and c["level"] == "error" for c in checks)


def test_manual_fields_skip_low_confidence_warning():
    fields = {"vendor": {"value": "X", "confidence": 1.0, "source": "manual"},
              "title": {"value": "Y", "confidence": 0.3, "source": None}}
    rules = {c["rule"] for c in validator.validate("report", 0.9, fields)}
    assert "low_confidence:title" in rules and "low_confidence:vendor" not in rules


# --- API ----------------------------------------------------------------

def test_upload_process_edit_approve(client):
    r = _upload(client, "inv.txt", INVOICE.encode())
    assert r.status_code == 201
    doc_id = r.json()[0]["id"]

    doc = client.get(f"/api/documents/{doc_id}").json()  # BackgroundTasks run before TestClient returns
    assert doc["doc_type"] == "invoice"
    assert doc["processing_ms"] is not None
    assert doc["created_at"].endswith("+00:00")
    assert [e["stage"] for e in doc["events"]][:5] == ["queued", "ocr", "classifying", "extracting", "validating"]

    r = client.patch(f"/api/documents/{doc_id}/fields", json={"fields": {"total": 118.0}})
    assert r.json()["fields"]["total"]["source"] == "manual"

    r = client.post(f"/api/documents/{doc_id}/approve")
    assert r.status_code == 200 and r.json()["status"] == "completed" and r.json()["reviewed_at"]


def test_approve_blocked_by_errors_unless_forced(client):
    bad = INVOICE.replace("Total: 118.00", "Total: 999.00").replace("INV-1001", "INV-1002")
    doc_id = _upload(client, "bad.txt", bad.encode()).json()[0]["id"]
    assert client.post(f"/api/documents/{doc_id}/approve").status_code == 409
    assert client.post(f"/api/documents/{doc_id}/approve", params={"force": True}).status_code == 200


def test_duplicate_upload_returns_existing(client):
    body = INVOICE.replace("INV-1001", "INV-7777").encode()
    first = _upload(client, "a.txt", body).json()[0]
    second = _upload(client, "b.txt", body).json()[0]
    assert second["duplicate"] is True and second["id"] == first["id"]


def test_list_is_paginated_and_searchable(client):
    page = client.get("/api/documents", params={"q": "INV-1001", "limit": 1}).json()
    assert page["total"] >= 1 and len(page["items"]) == 1


def test_export_csv(client):
    r = client.get("/api/export.csv")
    assert r.status_code == 200 and r.text.splitlines()[0].startswith("id,filename,type,status")


def test_rejects_unsupported_type(client):
    assert _upload(client, "x.exe", b"MZ", "application/octet-stream").status_code == 400


def test_rejects_spoofed_extension(client):
    assert _upload(client, "fake.pdf", b"not a pdf at all", "application/pdf").status_code == 400


def test_scanned_image_ocr(client):
    img = SAMPLES / "invoice_scanned.png"
    if not img.exists():
        pytest.skip("run scripts_make_samples.py first")
    doc_id = _upload(client, "scan.png", img.read_bytes(), "image/png").json()[0]["id"]
    doc = client.get(f"/api/documents/{doc_id}").json()
    assert doc["ocr_method"] == "ocr"
    assert doc["fields"]["invoice_number"]["value"] == "INV-2041"
