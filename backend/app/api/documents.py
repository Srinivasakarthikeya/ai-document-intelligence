import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import MAX_FILES_PER_UPLOAD
from ..db import get_db
from ..models import Document, ProcessingEvent
from ..schemas import DocumentDetail, DocumentPage, FieldUpdate, Stats, UploadResult
from ..services import validator
from ..services.pipeline import process_document, revalidate
from ..services.storage import UploadRejected, store_upload

router = APIRouter(prefix="/api")
IN_PROGRESS = ("queued", "ocr", "classifying", "extracting", "validating")


def _get(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


def _event(db, doc, stage, message):
    db.add(ProcessingEvent(document_id=doc.id, stage=stage, message=message))


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/documents", response_model=list[UploadResult], status_code=201)
async def upload(background: BackgroundTasks, files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    """Upload one or more files. Identical files (same SHA-256) return the existing record instead of reprocessing."""
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(400, f"Upload at most {MAX_FILES_PER_UPLOAD} files at a time.")
    results = []
    for f in files:
        try:
            stored = await store_upload(f)
        except UploadRejected as e:
            raise HTTPException(e.status_code, str(e)) from e

        existing = db.query(Document).filter(Document.file_hash == stored.sha256).first()
        if existing:
            stored.path.unlink(missing_ok=True)
            results.append(UploadResult.model_validate(existing).model_copy(update={"duplicate": True}))
            continue

        doc = Document(filename=stored.filename, stored_path=str(stored.path), mime_type=f.content_type or "",
                       size_bytes=stored.size, file_hash=stored.sha256)
        db.add(doc)
        db.flush()
        _event(db, doc, "queued", "Uploaded and queued.")
        db.commit()
        db.refresh(doc)
        background.add_task(process_document, doc.id)
        results.append(UploadResult.model_validate(doc))
    return results


def _filtered(db: Session, status: str | None, doc_type: str | None, q: str | None):
    query = db.query(Document)
    if status == "processing":
        query = query.filter(Document.status.in_(IN_PROGRESS))
    elif status:
        query = query.filter(Document.status == status)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Document.filename.ilike(like), Document.raw_text.ilike(like)))
    return query


@router.get("/documents", response_model=DocumentPage)
def list_documents(
    status: str | None = Query(None, description="completed | needs_review | failed | processing"),
    doc_type: str | None = None,
    q: str | None = Query(None, description="Search filename and extracted text"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = _filtered(db, status, doc_type, q)
    total = query.count()
    items = query.order_by(Document.created_at.desc(), Document.id.desc()).offset(offset).limit(limit).all()
    return DocumentPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    return _get(db, doc_id)


@router.get("/documents/{doc_id}/file")
def get_file(doc_id: int, db: Session = Depends(get_db)):
    doc = _get(db, doc_id)
    if not Path(doc.stored_path).exists():
        raise HTTPException(410, "The original file is no longer on disk.")
    return FileResponse(doc.stored_path, filename=doc.filename, content_disposition_type="inline")


@router.patch("/documents/{doc_id}/fields", response_model=DocumentDetail)
def update_fields(doc_id: int, body: FieldUpdate, db: Session = Depends(get_db)):
    """Human-in-the-loop correction: overwrite values (marked manual, confidence 1.0) and re-run validation."""
    doc = _get(db, doc_id)
    if doc.status in IN_PROGRESS:
        raise HTTPException(409, "Wait for processing to finish before editing.")
    fields = dict(doc.fields or {})
    for key, value in body.fields.items():
        if value in (None, ""):
            fields.pop(key, None)
        else:
            fields[key] = {"value": value, "confidence": 1.0, "source": "manual"}
    doc.fields = fields
    revalidate(doc)
    doc.reviewed_at = None
    _event(db, doc, "edited", f"Edited {', '.join(body.fields)}.")
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/documents/{doc_id}/approve", response_model=DocumentDetail)
def approve(doc_id: int, force: bool = False, db: Session = Depends(get_db)):
    """Reviewer sign-off. Blocked while validation errors remain unless force=true."""
    doc = _get(db, doc_id)
    if doc.status in IN_PROGRESS:
        raise HTTPException(409, "Wait for processing to finish before approving.")
    errors, _ = validator.counts(doc.validation or [])
    if errors and not force:
        raise HTTPException(409, f"{errors} validation error(s) remain. Fix them or approve with force=true.")
    doc.status, doc.reviewed_at = "completed", datetime.now(timezone.utc)
    _event(db, doc, "approved", "Approved by reviewer" + (f" with {errors} open error(s)." if errors else "."))
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/documents/{doc_id}/reprocess", response_model=DocumentDetail)
def reprocess(doc_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    doc = _get(db, doc_id)
    if doc.status in IN_PROGRESS:
        raise HTTPException(409, "Already processing.")
    doc.status, doc.error = "queued", None
    _event(db, doc, "queued", "Reprocessing requested.")
    db.commit()
    background.add_task(process_document, doc.id)
    db.refresh(doc)
    return doc


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = _get(db, doc_id)
    Path(doc.stored_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()


@router.get("/stats", response_model=Stats)
def stats(db: Session = Depends(get_db)):
    by_status = dict(db.query(Document.status, func.count()).group_by(Document.status).all())
    by_type = dict(db.query(Document.doc_type, func.count()).filter(Document.doc_type.isnot(None))
                   .group_by(Document.doc_type).all())
    avg = db.query(func.avg(Document.processing_ms)).scalar()
    return Stats(total=sum(by_status.values()), by_status=by_status, by_type=by_type,
                 avg_processing_ms=int(avg) if avg is not None else None)


EXPORT_FIELDS = ["invoice_number", "po_number", "vendor", "merchant", "bill_to", "invoice_date", "date",
                 "order_date", "due_date", "subtotal", "tax", "total", "currency", "gstin"]


@router.get("/export.csv")
def export_csv(status: str | None = None, doc_type: str | None = None, q: str | None = None,
               db: Session = Depends(get_db)):
    """Flat CSV of every matching document's key fields — ready for Excel or an ERP import."""
    docs = _filtered(db, status, doc_type, q).order_by(Document.id).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "filename", "type", "status", "reviewed", *EXPORT_FIELDS, "errors", "warnings"])
    for d in docs:
        f = d.fields or {}
        e, w = validator.counts(d.validation or [])
        writer.writerow([d.id, d.filename, d.doc_type or "", d.status, "yes" if d.reviewed_at else "no",
                         *[(f.get(k) or {}).get("value", "") for k in EXPORT_FIELDS], e, w])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="documents.csv"'})
