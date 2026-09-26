import { forwardRef } from "react";
import Stamp from "./Stamp.jsx";
import Icon from "./Icon.jsx";
import { TYPE_LABEL, relTime, isBusy } from "../lib/format.js";

const TABS = [
  ["", "All"],
  ["needs_review", "Review"],
  ["completed", "Verified"],
  ["failed", "Failed"],
];

function DocRow({ doc, selected, onSelect }) {
  return (
    <li>
      <button className={`doc-row ${selected ? "is-selected" : ""}`} onClick={() => onSelect(doc.id)}
        aria-current={selected ? "true" : undefined}>
        <span className="doc-name" title={doc.filename}>{doc.filename}</span>
        <span className="doc-meta">
          {doc.doc_type ? TYPE_LABEL[doc.doc_type] : isBusy(doc.status) ? "Processing" : "Unclassified"}
          {doc.type_confidence != null && <span className="dim"> {Math.round(doc.type_confidence * 100)}%</span>}
          <span className="dot" aria-hidden="true">·</span>
          {relTime(doc.created_at)}
        </span>
        <Stamp status={doc.status} />
      </button>
    </li>
  );
}

function Skeleton() {
  return (
    <ul className="docs" aria-busy="true">
      {[0, 1, 2, 3].map((i) => (
        <li key={i} className="skeleton-row"><span className="sk sk-line" /><span className="sk sk-short" /></li>
      ))}
    </ul>
  );
}

const Sidebar = forwardRef(function Sidebar(
  { docs, total, loading, counts, filters, setFilters, selected, onSelect, uploads, onPick }, searchRef,
) {
  return (
    <aside className="sidebar" aria-label="Documents">
      <div className="search">
        <Icon name="search" />
        <input ref={searchRef} type="search" placeholder="Search text, numbers, vendors" value={filters.q}
          onChange={(e) => setFilters({ ...filters, q: e.target.value })} aria-label="Search documents" />
        <kbd>/</kbd>
      </div>

      <div className="segmented" role="tablist" aria-label="Filter by status">
        {TABS.map(([value, label]) => (
          <button key={label} role="tab" aria-selected={filters.status === value}
            className={filters.status === value ? "on" : ""} onClick={() => setFilters({ ...filters, status: value })}>
            {label}<span className="count">{value ? counts[value] || 0 : counts.all || 0}</span>
          </button>
        ))}
      </div>

      <select className="type-filter" value={filters.doc_type} aria-label="Filter by type"
        onChange={(e) => setFilters({ ...filters, doc_type: e.target.value })}>
        <option value="">All document types</option>
        {Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>

      {uploads.length > 0 && (
        <ul className="uploads">
          {uploads.map((u) => (
            <li key={u.id}>
              <span>Uploading {u.count} file{u.count > 1 ? "s" : ""}</span>
              <span className="bar"><span style={{ width: `${Math.round(u.progress * 100)}%` }} /></span>
            </li>
          ))}
        </ul>
      )}

      {loading ? <Skeleton /> : docs.length === 0 ? (
        <div className="docs empty">
          {filters.q || filters.status || filters.doc_type ? (
            <>
              <p>No documents match these filters.</p>
              <button className="btn-link" onClick={() => setFilters({ q: "", status: "", doc_type: "" })}>Clear filters</button>
            </>
          ) : (
            <>
              <p>No documents yet.</p>
              <button className="btn-link" onClick={onPick}>Upload your first file</button>
            </>
          )}
        </div>
      ) : (
        <ul className="docs">
          {docs.map((d) => <DocRow key={d.id} doc={d} selected={d.id === selected} onSelect={onSelect} />)}
        </ul>
      )}

      <p className="list-foot">
        {total > docs.length ? `Showing ${docs.length} of ${total}` : `${total} document${total === 1 ? "" : "s"}`}
        <span className="keys"><kbd>j</kbd><kbd>k</kbd> to move</span>
      </p>
    </aside>
  );
});

export default Sidebar;
