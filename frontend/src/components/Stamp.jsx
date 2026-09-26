import { STATUS_LABEL, isBusy } from "../lib/format.js";

export default function Stamp({ status, reviewed, large = false }) {
  const tone = status === "completed" ? "ok" : status === "needs_review" ? "warn" : status === "failed" ? "bad" : "busy";
  const label = status === "completed" && reviewed ? "Approved" : STATUS_LABEL[status] || status;
  return (
    <span className={`stamp stamp-${tone} ${large ? "stamp-lg" : ""}`} role="status">
      {isBusy(status) && <span className="spinner" aria-hidden="true" />}
      {label}
    </span>
  );
}
