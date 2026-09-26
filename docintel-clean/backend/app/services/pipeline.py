"""Orchestrates OCR -> classify -> extract -> validate, logging each stage for status tracking."""
import logging
import time

from ..db import SessionLocal
from ..models import Document, ProcessingEvent
from . import ocr, classifier, extractor, validator

log = logging.getLogger("docintel.pipeline")


def _stage(db, doc, stage, fn):
    doc.status = stage
    db.commit()
    start = time.perf_counter()
    result, message = fn()
    ms = int((time.perf_counter() - start) * 1000)
    db.add(ProcessingEvent(document_id=doc.id, stage=stage, message=message, duration_ms=ms))
    db.commit()
    log.info("doc=%s stage=%s ms=%s %s", doc.id, stage, ms, message)
    return result


def process_document(doc_id: int) -> None:
    db = SessionLocal()
    doc = db.get(Document, doc_id)
    if doc is None:
        db.close()
        return
    started = time.perf_counter()
    try:
        doc.reviewed_at = None

        def do_ocr():
            text, method = ocr.extract_text(doc.stored_path)
            doc.raw_text, doc.ocr_method = text, method
            return text, f"Read {len(text):,} characters via {method}."
        text = _stage(db, doc, "ocr", do_ocr)

        def do_classify():
            label, conf = classifier.classify(text)
            doc.doc_type, doc.type_confidence = label, conf
            return (label, conf), f"Classified as {label} ({conf:.0%})."
        label, conf = _stage(db, doc, "classifying", do_classify)

        def do_extract():
            fields = extractor.extract_fields(text, label)
            doc.fields = fields
            return fields, f"Extracted {len(fields)} field(s)."
        fields = _stage(db, doc, "extracting", do_extract)

        def do_validate():
            checks = validator.validate(label, conf, fields)
            doc.validation = checks
            e, w = validator.counts(checks)
            return checks, f"{e} error(s), {w} warning(s)."
        checks = _stage(db, doc, "validating", do_validate)

        doc.status = validator.outcome(checks)
        doc.processing_ms = int((time.perf_counter() - started) * 1000)
        db.add(ProcessingEvent(document_id=doc.id, stage=doc.status, message="Processing finished."))
        db.commit()
    except Exception as exc:  # noqa: BLE001 — any failure must land the doc in 'failed', not stuck mid-pipeline
        log.exception("doc=%s failed", doc_id)
        db.rollback()
        doc = db.get(Document, doc_id)
        doc.status, doc.error = "failed", f"{type(exc).__name__}: {exc}"
        doc.processing_ms = int((time.perf_counter() - started) * 1000)
        db.add(ProcessingEvent(document_id=doc.id, stage="failed", message=str(exc)))
        db.commit()
    finally:
        db.close()


def revalidate(doc: Document) -> None:
    doc.validation = validator.validate(doc.doc_type or "other", doc.type_confidence or 0, doc.fields or {})
    doc.status = validator.outcome(doc.validation)
