import { useState } from "react";
import Icon from "./Icon.jsx";
import {
  FIELD_ORDER, KEY_FIELDS, READ_ONLY, displayValue, editValue, fieldLabel, money, parseInput, ruleField,
} from "../lib/format.js";

function issuesByField(validation = []) {
  const map = {};
  for (const c of validation) {
    if (c.level === "ok") continue;
    const key = ruleField(c.rule);
    if (key) (map[key] ||= []).push(c);
  }
  return map;
}

function FieldRow({ k, field, issues, currency, editable, onSave, missing }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const start = () => { setDraft(editValue(k, field?.value)); setError(""); setEditing(true); };
  const save = async () => {
    const parsed = parseInput(k, draft);
    if (parsed.error) return setError(parsed.error);
    setSaving(true);
    try { await onSave({ [k]: parsed.value }); setEditing(false); }
    catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  const worst = issues?.some((i) => i.level === "error") ? "error" : issues?.length ? "warning" : null;
  const conf = field?.confidence;

  return (
    <tr className={`${worst ? `row-${worst}` : ""} ${missing ? "row-missing" : ""}`} id={`field-${k}`}>
      <th scope="row">
        {worst && <span className={`marker marker-${worst}`} aria-label={worst} />}
        {fieldLabel(k)}
      </th>
      <td>
        {editing ? (
          <div className="edit">
            <input autoFocus value={draft} disabled={saving} aria-label={`Edit ${fieldLabel(k)}`}
              aria-invalid={!!error} placeholder={missing ? "Add value" : ""}
              onChange={(e) => { setDraft(e.target.value); setError(""); }}
              onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }} />
            <button className="btn btn-sm btn-primary" onClick={save} disabled={saving}>{saving ? "Saving" : "Save"}</button>
            <button className="btn btn-sm" onClick={() => setEditing(false)}>Cancel</button>
            {error && <p className="field-error">{error}</p>}
          </div>
        ) : missing ? (
          <span className="missing">Not found in document</span>
        ) : (
          <span className="value">{displayValue(k, field.value, currency)}</span>
        )}
        {!editing && issues?.map((i) => <p key={i.rule} className="issue-note">{i.message}</p>)}
      </td>
      <td className="conf-cell">
        {field?.source === "manual" ? <span className="tag">Edited</span> : conf != null && (
          <span className="conf" title={`${Math.round(conf * 100)}% confidence`}>
            <span className="conf-bar"><span style={{ width: `${conf * 100}%` }} /></span>
            {Math.round(conf * 100)}%
          </span>
        )}
      </td>
      <td className="act-cell">
        {editable && !editing && !READ_ONLY.has(k) && (
          <button className="icon-btn" onClick={start} aria-label={`${missing ? "Add" : "Edit"} ${fieldLabel(k)}`}>
            <Icon name={missing ? "plus" : "pencil"} size={15} />
          </button>
        )}
      </td>
    </tr>
  );
}

export default function FieldsPanel({ doc, editable, onSave }) {
  const fields = doc.fields || {};
  const issues = issuesByField(doc.validation);
  const currency = fields.currency?.value;
  const missing = (doc.validation || [])
    .filter((c) => c.rule.startsWith("required:") && c.level === "error")
    .map((c) => c.rule.split(":")[1]);

  const keys = Object.keys(fields).filter((k) => k !== "line_items");
  const ordered = [...FIELD_ORDER.filter((k) => keys.includes(k)), ...keys.filter((k) => !FIELD_ORDER.includes(k))];
  const rows = [...missing.filter((k) => !fields[k]), ...ordered];

  const facts = (KEY_FIELDS[doc.doc_type] || []).filter((k) => fields[k]);
  const items = fields.line_items?.value || [];

  if (!rows.length && !items.length) {
    return (
      <div className="empty-panel">
        <p>No fields were extracted.</p>
        <p className="muted">Check the Text tab to see what was read from the document.</p>
      </div>
    );
  }

  return (
    <div className="fields-panel">
      {facts.length > 0 && (
        <dl className="facts">
          {facts.map((k) => (
            <div key={k} className={k === "total" ? "fact fact-total" : "fact"}>
              <dt>{fieldLabel(k)}</dt>
              <dd>{displayValue(k, fields[k].value, currency)}</dd>
            </div>
          ))}
        </dl>
      )}

      <table className="fields">
        <thead><tr><th>Field</th><th>Value</th><th>Confidence</th><th><span className="sr-only">Actions</span></th></tr></thead>
        <tbody>
          {rows.map((k) => (
            <FieldRow key={k} k={k} field={fields[k]} issues={issues[k]} currency={currency}
              editable={editable} onSave={onSave} missing={!fields[k]} />
          ))}
        </tbody>
      </table>

      {items.length > 0 && (
        <section className="items-wrap">
          <h3 className="sub">Line items</h3>
          {issues.line_items?.map((i) => <p key={i.rule} className={`issue-note issue-${i.level}`}>{i.message}</p>)}
          <table className="fields items">
            <thead><tr><th>Description</th><th>Qty</th><th>Unit price</th><th>Amount</th></tr></thead>
            <tbody>
              {items.map((it, i) => {
                const off = it.quantity != null && it.unit_price != null && it.amount != null
                  && Math.abs(it.quantity * it.unit_price - it.amount) > 0.02;
                return (
                  <tr key={i} className={off ? "row-error" : ""}>
                    <td>{off && <span className="marker marker-error" aria-label="error" />}{it.description}</td>
                    <td>{it.quantity}</td>
                    <td>{money(it.unit_price, currency)}</td>
                    <td>{money(it.amount, currency)}</td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr><td colSpan={3}>Sum of line items</td>
                <td>{money(items.reduce((s, it) => s + (it.amount || 0), 0), currency)}</td></tr>
            </tfoot>
          </table>
        </section>
      )}
    </div>
  );
}
