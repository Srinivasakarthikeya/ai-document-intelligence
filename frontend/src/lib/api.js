const BASE = import.meta.env.VITE_API_URL || "";

async function req(path, opts = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, opts);
  } catch {
    throw new Error("Can't reach the API. Is the backend running on port 8000?");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join(", ") : body.detail;
    const err = new Error(detail || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

const qs = (params) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString();
  return s ? `?${s}` : "";
};

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  list: (params) => req(`/api/documents${qs(params)}`),
  get: (id) => req(`/api/documents/${id}`),
  stats: () => req("/api/stats"),
  updateFields: (id, fields) => req(`/api/documents/${id}/fields`, json("PATCH", { fields })),
  approve: (id, force = false) => req(`/api/documents/${id}/approve${force ? "?force=true" : ""}`, { method: "POST" }),
  reprocess: (id) => req(`/api/documents/${id}/reprocess`, { method: "POST" }),
  remove: (id) => req(`/api/documents/${id}`, { method: "DELETE" }),
  fileUrl: (id) => `${BASE}/api/documents/${id}/file`,
  exportUrl: (params) => `${BASE}/api/export.csv${qs(params)}`,

  /** Upload with real progress events (fetch can't report upload progress). */
  upload(files, onProgress) {
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      [...files].forEach((f) => fd.append("files", f));
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}/api/documents`);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
      xhr.onload = () => {
        let body = {};
        try { body = JSON.parse(xhr.responseText); } catch { /* non-JSON */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body);
        else reject(new Error(body.detail || `Upload failed (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error("Upload failed. Is the backend running?"));
      xhr.send(fd);
    });
  },
};
