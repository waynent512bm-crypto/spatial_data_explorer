import { useEffect, useState } from "react";
import { api, type DatasetSummary } from "./api";

type Status =
  | { state: "connecting" }
  | { state: "connected"; version: string; dataset: DatasetSummary }
  | { state: "error"; message: string };

export default function App() {
  const [status, setStatus] = useState<Status>({ state: "connecting" });

  useEffect(() => {
    Promise.all([api.health(), api.dataset()])
      .then(([health, dataset]) => setStatus({ state: "connected", version: health.version, dataset }))
      .catch((e: unknown) => setStatus({ state: "error", message: String(e) }));
  }, []);

  return (
    <main className="app">
      <h1>Spatial Data Explorer</h1>
      {status.state === "connecting" && <p>Connecting to backend...</p>}
      {status.state === "error" && (
        <p className="error">Cannot reach backend: {status.message}</p>
      )}
      {status.state === "connected" && (
        <>
          <p className="ok">Connected to backend (v{status.version})</p>
          <dl>
            <dt>File</dt><dd>{status.dataset.source}</dd>
            <dt>Platform</dt><dd>{status.dataset.platform}</dd>
            <dt>Cells</dt><dd>{status.dataset.n_cells.toLocaleString()}</dd>
            <dt>Genes</dt><dd>{status.dataset.n_genes.toLocaleString()}</dd>
            <dt>Color by</dt>
            <dd>
              {status.dataset.default_color_column ?? "(none)"}{" "}
              <span className="muted">(auto-detected: {status.dataset.default_color_reason})</span>
            </dd>
          </dl>
        </>
      )}
    </main>
  );
}
