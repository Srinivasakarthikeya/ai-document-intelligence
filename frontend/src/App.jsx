import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./lib/api.js";
import { IN_PROGRESS, isBusy } from "./lib/format.js";
import Sidebar from "./components/Sidebar.jsx";
import Detail from "./components/Detail.jsx";
import Icon from "./components/Icon.jsx";
import { useToast } from "./components/Toaster.jsx";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.txt";

function useDebounced(value, ms = 250) {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

function Welcome({ onPick }) {
  return (
    <div className="welcome">
      <Icon name="file" size={40} />
      <h2>Drop a document to begin</h2>
      <p>Invoices, receipts, purchase orders, reports and contracts. Scans and photos are read with OCR.</p>
      <ol className="steps">
        <li><strong>Read</strong><span>Embedded PDF text, or Tesseract OCR for scans</span></li>
        <li><strong>Understand</strong><span>ML classifies the type and extracts its fields</span></li>
        <li><strong>Check</strong><span>Business rules flag missing or inconsistent values</span></li>
        <li><strong>Review</strong><span>Fix anything flagged, then approve</span></li>
      </ol>
      <button className="btn btn-primary btn-lg" onClick={onPick}><Icon name="upload" /> Choose files</button>
      <p className="muted small">Try the files in <code>samples/</code>, including one with deliberate errors.</p>
    </div>
  );
}

export default function App() {
  const [docs, setDocs] = useState([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [selected, setSelected] = useState(null);
  const [filters, setFilters] = useState({ q: "", status: "", doc_type: "" });
  const [uploads, setUploads] = useState([]);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef();
  const searchRef = useRef();
  const dragDepth = useRef(0);
  const toast = useToast();
  const q = useDebounced(filters.q);

  const refresh = useCallback(async () => {
    try {
      const [page, s] = await Promise.all([api.list({ status: filters.status, doc_type: filters.doc_type, q, limit: 200 }), api.stats()]);
      setDocs(page.items);
      setTotal(page.total);
      setStats(s);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [filters.status, filters.doc_type, q]);

  useEffect(() => { refresh(); }, [refresh]);

  const anyBusy = docs.some((d) => isBusy(d.status));
  useEffect(() => {
    if (!anyBusy && !offline) return;
    const t = setInterval(refresh, offline ? 4000 : 1500);
    return () => clearInterval(t);
  }, [anyBusy, offline, refresh]);

  // Select the first document when nothing is selected.
  useEffect(() => { if (!selected && docs.length) setSelected(docs[0].id); }, [docs, selected]);

  const handleFiles = useCallback(async (fileList) => {
    const files = [...(fileList || [])];
    if (!files.length) return;
    const id = Math.random().toString(36).slice(2);
    setUploads((u) => [...u, { id, count: files.length, progress: 0 }]);
    try {
      const created = await api.upload(files, (p) => setUploads((u) => u.map((x) => (x.id === id ? { ...x, progress: p } : x))));
      const dupes = created.filter((d) => d.duplicate);
      const fresh = created.length - dupes.length;
      if (fresh) toast(`${fresh} file${fresh > 1 ? "s" : ""} uploaded. Processing now`);
      if (dupes.length) toast(`${dupes.length} already uploaded, opened the existing record`);
      await refresh();
      if (created[0]) setSelected(created[0].id);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setUploads((u) => u.filter((x) => x.id !== id));
    }
  }, [refresh, toast]);

  // Page-wide drag and drop.
  useEffect(() => {
    const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
    const enter = (e) => { if (!hasFiles(e)) return; e.preventDefault(); dragDepth.current++; setDragging(true); };
    const over = (e) => { if (hasFiles(e)) e.preventDefault(); };
    const leave = () => { dragDepth.current = Math.max(0, dragDepth.current - 1); if (!dragDepth.current) setDragging(false); };
    const drop = (e) => { if (!hasFiles(e)) return; e.preventDefault(); dragDepth.current = 0; setDragging(false); handleFiles(e.dataTransfer.files); };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
    };
  }, [handleFiles]);

  // Keyboard: "/" or Cmd/Ctrl+K search, j/k or arrows move through the list, "u" upload.
  useEffect(() => {
    const onKey = (e) => {
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) {
        e.preventDefault(); searchRef.current?.focus(); return;
      }
      if (e.key === "Escape" && typing) { e.target.blur(); return; }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "u") { fileInput.current?.click(); return; }
      const step = e.key === "j" || e.key === "ArrowDown" ? 1 : e.key === "k" || e.key === "ArrowUp" ? -1 : 0;
      if (!step || !docs.length) return;
      e.preventDefault();
      const i = docs.findIndex((d) => d.id === selected);
      const next = docs[Math.min(docs.length - 1, Math.max(0, i + step))];
      if (next) setSelected(next.id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [docs, selected]);

  const by = stats?.by_status || {};
  const counts = { all: stats?.total || 0, needs_review: by.needs_review, completed: by.completed, failed: by.failed };
  const processing = IN_PROGRESS.reduce((s, k) => s + (by[k] || 0), 0);
  const pick = () => fileInput.current?.click();
  const noDocsAtAll = !loading && stats?.total === 0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand-wrap">
          <h1 className="brand">Docket</h1>
          <span className="tagline">Document intelligence</span>
        </div>
        {stats && stats.total > 0 && (
          <dl className="tally">
            <div><dt>Documents</dt><dd>{stats.total}</dd></div>
            <div><dt>To review</dt><dd>{by.needs_review || 0}</dd></div>
            <div><dt>Verified</dt><dd>{by.completed || 0}</dd></div>
            {processing > 0 && <div><dt>Processing</dt><dd>{processing}</dd></div>}
            {stats.avg_processing_ms != null && <div><dt>Avg time</dt><dd>{(stats.avg_processing_ms / 1000).toFixed(1)}<small>s</small></dd></div>}
          </dl>
        )}
        <div className="top-actions">
          {stats?.total > 0 && (
            <a className="btn" href={api.exportUrl({ status: filters.status, doc_type: filters.doc_type, q })} download>
              <Icon name="download" /> Export CSV
            </a>
          )}
          <button className="btn btn-primary" onClick={pick}><Icon name="upload" /> Upload <kbd className="kbd-inv">U</kbd></button>
          <input ref={fileInput} type="file" multiple hidden accept={ACCEPT}
            onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }} />
        </div>
      </header>

      {offline && (
        <div className="banner" role="alert">
          <Icon name="alert" /> Can't reach the API. Start the backend with <code>uvicorn app.main:app --reload</code>. Retrying…
        </div>
      )}

      {noDocsAtAll ? <main className="main-empty"><Welcome onPick={pick} /></main> : (
        <main className="layout">
          <Sidebar ref={searchRef} docs={docs} total={total} loading={loading} counts={counts} filters={filters}
            setFilters={setFilters} selected={selected} onSelect={setSelected} uploads={uploads} onPick={pick} />
          <section className="main" aria-live="polite">
            {selected ? (
              <Detail key={selected} id={selected} onChanged={refresh}
                onDeleted={() => { setSelected(null); refresh(); }} />
            ) : !loading && (
              <div className="placeholder"><p>Select a document to review it.</p></div>
            )}
          </section>
        </main>
      )}

      {dragging && (
        <div className="drop-overlay" aria-hidden="true">
          <div><Icon name="upload" size={36} /><p>Drop to upload</p><span>PDF, PNG, JPG, TIFF or TXT, up to 20 MB each</span></div>
        </div>
      )}
    </div>
  );
}
