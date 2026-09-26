import { useState } from "react";
import { api } from "../lib/api.js";
import { METHOD_LABEL } from "../lib/format.js";

function Preview({ doc }) {
  const url = api.fileUrl(doc.id);
  if (/\.(png|jpe?g)$/i.test(doc.filename)) return <img className="preview" src={url} alt={`Original ${doc.filename}`} />;
  if (/\.pdf$/i.test(doc.filename)) return <iframe className="preview" src={`${url}#view=FitH&toolbar=0`} title={doc.filename} />;
  if (/\.txt$/i.test(doc.filename)) return <pre className="raw">{doc.raw_text}</pre>;
  return <a className="btn" href={url}>Download original</a>;
}

function Timeline({ events = [] }) {
  return (
    <ol className="timeline">
      {events.map((e, i) => (
        <li key={i}>
          <div className="tl-head">
            <strong>{e.stage.replace("_", " ")}</strong>
            <time dateTime={e.created_at}>{new Date(e.created_at).toLocaleTimeString()}</time>
          </div>
          <span>{e.message}{e.duration_ms != null && <span className="dim"> · {e.duration_ms} ms</span>}</span>
        </li>
      ))}
    </ol>
  );
}

export default function SidePanel({ doc }) {
  const [tab, setTab] = useState("original");
  const tabs = [["original", "Original"], ["text", "Text"], ["activity", "Activity"]];
  return (
    <section className="side-panel">
      <div className="tabs" role="tablist">
        {tabs.map(([k, v]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{v}</button>
        ))}
      </div>
      <div className="side-body">
        {tab === "original" && <Preview doc={doc} />}
        {tab === "text" && (
          <>
            <p className="muted small">{doc.ocr_method ? `Read with ${METHOD_LABEL[doc.ocr_method] || doc.ocr_method}` : "Not read yet"}
              {doc.raw_text && `, ${doc.raw_text.length.toLocaleString()} characters`}</p>
            <pre className="raw">{doc.raw_text || "No text yet."}</pre>
          </>
        )}
        {tab === "activity" && <Timeline events={doc.events} />}
      </div>
    </section>
  );
}
