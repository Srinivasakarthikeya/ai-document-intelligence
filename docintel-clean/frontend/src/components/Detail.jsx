import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { METHOD_LABEL, TYPE_LABEL, bytes, isBusy, IN_PROGRESS } from "../lib/format.js";
import Stamp from "./Stamp.jsx";
import Icon from "./Icon.jsx";
import FieldsPanel from "./FieldsPanel.jsx";
import SidePanel from "./SidePanel.jsx";
import { useToast } from "./Toaster.jsx";

const STEPS = ["Upload", "Read", "Classify", "Extract", "Validate"];

function Progress({ status }) {
  const idx = IN_PROGRESS.indexOf(status);
  const done = !isBusy(status);
  return (
    <ol className="progress" aria-label="Processing progress">
      {STEPS.map((s, i) => {
        const state = done || i < idx ? "done" : i === idx ? "now" : "todo";
        return <li key={s} className={`p-${state}`} aria-current={state === "now" ? "step" : undefined}>{s}</li>;
      })}
    </ol>
  );
}

function ConfirmButton({ children, confirmLabel, onConfirm, className = "btn", disabled }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 3500);
    return () => clearTimeout(t);
  }, [armed]);
  return (
    <button className={`${className} ${armed ? "armed" : ""}`} disabled={disabled}
      onClick={() => (armed ? (setArmed(false), onConfirm()) : setArmed(true))}>
      {armed ? confirmLabel : children}
    </button>
  );
}

function Header({ doc, busyAction, act }) {
  const errors = (doc.validation || []).filter((c) => c.level === "error").length;
  const warnings = (doc.validation || []).filter((c) => c.level === "warning").length;
  const processing = isBusy(doc.status);
  const approved = doc.status === "completed" && doc.reviewed_at;

  return (
    <header className="detail-head">
      <div className="title-block">
        <h2 title={doc.filename}>{doc.filename}</h2>
        <p className="meta">
          {doc.doc_type ? `${TYPE_LABEL[doc.doc_type]} · ${Math.round((doc.type_confidence || 0) * 100)}% confident` : "Not classified yet"}
          {doc.ocr_method && ` · ${METHOD_LABEL[doc.ocr_method]}`}
          {doc.size_bytes ? ` · ${bytes(doc.size_bytes)}` : ""}
          {doc.processing_ms != null && ` · ${(doc.processing_ms / 1000).toFixed(1)} s`}
        </p>
      </div>
      <div className="head-actions">
        <Stamp status={doc.status} reviewed={!!doc.reviewed_at} large />
        {!processing && doc.status !== "failed" && !approved && (
          errors ? (
            <ConfirmButton className="btn" confirmLabel={`Approve with ${errors} error${errors > 1 ? "s" : ""}?`}
              disabled={!!busyAction} onConfirm={() => act("approve", true)}>
              <Icon name="shield" /> Approve anyway
            </ConfirmButton>
          ) : (
            <button className="btn btn-primary" disabled={!!busyAction} onClick={() => act("approve")}>
              <Icon name="check" /> {busyAction === "approve" ? "Approving" : warnings ? "Approve" : "Mark reviewed"}
            </button>
          )
        )}
        <button className="icon-btn bordered" title="Reprocess" aria-label="Reprocess" disabled={processing || !!busyAction}
          onClick={() => act("reprocess")}><Icon name="refresh" /></button>
        <a className="icon-btn bordered" title="Export JSON" aria-label="Export JSON"
          href={`data:application/json,${encodeURIComponent(JSON.stringify({ id: doc.id, filename: doc.filename,
            type: doc.doc_type, status: doc.status, fields: doc.fields, validation: doc.validation }, null, 2))}`}
          download={`${doc.filename.replace(/\.[^.]+$/, "")}.json`}><Icon name="download" /></a>
        <ConfirmButton className="icon-btn bordered danger" confirmLabel="Delete?" disabled={!!busyAction}
          onConfirm={() => act("delete")}><Icon name="trash" /></ConfirmButton>
      </div>
    </header>
  );
}

function Summary({ doc }) {
  if (isBusy(doc.status)) return null;
  if (doc.status === "failed") {
    return <div className="summary summary-bad" role="alert"><Icon name="alert" />
      <div><strong>Processing failed.</strong> {doc.error} Try Reprocess, or check the file opens correctly.</div></div>;
  }
  const checks = doc.validation || [];
  const errors = checks.filter((c) => c.level === "error");
  const warnings = checks.filter((c) => c.level === "warning");
  const passed = checks.filter((c) => c.level === "ok").length;
  if (doc.reviewed_at && doc.status === "completed") {
    return <div className="summary summary-ok"><Icon name="shield" />
      <div><strong>Approved</strong> {new Date(doc.reviewed_at).toLocaleString()}. {passed} check{passed === 1 ? "" : "s"} passed.</div></div>;
  }
  if (!errors.length && !warnings.length) {
    return <div className="summary summary-ok"><Icon name="check" />
      <div><strong>All {passed} checks passed.</strong> Review the values, then mark it reviewed.</div></div>;
  }
  const docLevel = checks.filter((c) => c.level !== "ok" && c.rule === "classification_confidence");
  return (
    <div className={`summary ${errors.length ? "summary-bad" : "summary-warn"}`}>
      <Icon name="alert" />
      <div>
        <strong>
          {errors.length ? `${errors.length} error${errors.length > 1 ? "s" : ""}` : ""}
          {errors.length && warnings.length ? " and " : ""}
          {warnings.length ? `${warnings.length} warning${warnings.length > 1 ? "s" : ""}` : ""} to review.
        </strong>{" "}
        Issues are marked next to the fields they affect; fix a value and checks re-run instantly.
        {docLevel.map((c) => <p key={c.rule} className="issue-note">{c.message}</p>)}
      </div>
    </div>
  );
}

export default function Detail({ id, onChanged, onDeleted }) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const toast = useToast();

  const load = useCallback(() => api.get(id).then((d) => { setDoc(d); setError(""); }).catch((e) => setError(e.message)), [id]);
  useEffect(() => { setDoc(null); load(); }, [load]);
  useEffect(() => {
    if (!doc || !isBusy(doc.status)) return;
    const t = setInterval(load, 1000);
    return () => clearInterval(t);
  }, [doc, load]);
  // Tell the list when processing finishes so its stamp updates.
  useEffect(() => { if (doc && !isBusy(doc.status)) onChanged(); }, [doc?.status]); // eslint-disable-line

  async function act(action, force) {
    setBusyAction(action);
    try {
      if (action === "approve") { setDoc(await api.approve(doc.id, force)); toast("Approved"); }
      if (action === "reprocess") { setDoc(await api.reprocess(doc.id)); toast("Reprocessing started"); }
      if (action === "delete") { await api.remove(doc.id); toast(`Deleted ${doc.filename}`); onDeleted(); return; }
      onChanged();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusyAction("");
    }
  }

  async function saveFields(fields) {
    const updated = await api.updateFields(doc.id, fields);
    setDoc(updated);
    onChanged();
    const e = (updated.validation || []).filter((c) => c.level === "error").length;
    toast(e ? `Saved. ${e} error${e > 1 ? "s" : ""} left` : "Saved. No errors left");
  }

  if (error) return <div className="placeholder"><p>{error}</p><button className="btn" onClick={load}>Try again</button></div>;
  if (!doc) return <div className="detail"><div className="sk sk-title" /><div className="sk sk-line" /><div className="sk sk-block" /></div>;

  return (
    <article className="detail" aria-label={doc.filename}>
      <Header doc={doc} busyAction={busyAction} act={act} />
      <Progress status={doc.status} />
      <Summary doc={doc} />
      <div className="workspace">
        <section className="review-pane" aria-label="Extracted fields">
          {isBusy(doc.status) ? (
            <div className="processing-note"><span className="spinner" /> Extracting fields. This usually takes a few seconds.</div>
          ) : (
            <FieldsPanel doc={doc} editable={doc.status !== "failed"} onSave={saveFields} />
          )}
        </section>
        <SidePanel doc={doc} />
      </div>
    </article>
  );
}
