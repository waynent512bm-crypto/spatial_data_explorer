import { useEffect, useMemo, useState } from "react";
import { api, type DatasetSummary, type ObsColumnData } from "./api";
import { categoricalColors, categoryPalette, numericColors, UNANNOTATED_KEY } from "./colors";
import Legend from "./Legend";
import ScatterView from "./ScatterView";

// Spatial points approximate a cell (microns); UMAP points are a fixed screen size.
const SPATIAL_RADIUS = { units: "common", size: 5 } as const;
const UMAP_RADIUS = { units: "pixels", size: 1.5 } as const;

type Load<T> = { state: "loading" } | { state: "ready"; value: T } | { state: "error"; message: string };

function useLoad<T>(fn: (() => Promise<T>) | null, deps: unknown[]): Load<T> {
  const [result, setResult] = useState<Load<T>>({ state: "loading" });
  useEffect(() => {
    if (!fn) return;
    let cancelled = false;
    setResult({ state: "loading" });
    fn().then(
      (value) => !cancelled && setResult({ state: "ready", value }),
      (e: unknown) => !cancelled && setResult({ state: "error", message: String(e) }),
    );
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return result;
}

export default function App() {
  const summary = useLoad(() => api.dataset(), []);
  if (summary.state === "loading") return <main className="status">Connecting to backend...</main>;
  if (summary.state === "error") return <main className="status error">Cannot reach backend: {summary.message}</main>;
  return <Explorer summary={summary.value} />;
}

function Explorer({ summary }: { summary: DatasetSummary }) {
  const hasUmap = summary.embeddings.includes("umap");
  const spatial = useLoad(() => api.embedding("spatial"), []);
  const umap = useLoad(hasUmap ? () => api.embedding("umap") : null, [hasUmap]);

  const [colorBy, setColorBy] = useState<string | null>(summary.default_color_column);
  const column = useLoad(colorBy ? () => api.obsColumn(colorBy) : null, [colorBy]);
  const [hidden, setHidden] = useState<Set<number>>(new Set());
  useEffect(() => setHidden(new Set()), [colorBy]);

  const palette = useMemo(() => (
    column.state === "ready" && column.value.meta.kind === "categorical"
      ? categoryPalette(column.value.meta.categories.length, column.value.meta.colors)
      : []
  ), [column]);

  const colors = useMemo(() => {
    if (column.state !== "ready") {
      return new Uint8Array(summary.n_cells * 4).fill(160);   // neutral gray while loading
    }
    const c: ObsColumnData = column.value;
    if ("codes" in c) return categoricalColors(c.codes, palette, hidden);
    return numericColors(c.values, c.meta.min ?? 0, c.meta.max ?? 1);
  }, [column, palette, hidden, summary.n_cells]);

  const toggle = (key: number) => setHidden((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
  const setAll = (visible: boolean) => {
    if (visible || column.state !== "ready" || column.value.meta.kind !== "categorical") {
      setHidden(new Set());
      return;
    }
    setHidden(new Set([...column.value.meta.categories.keys(), UNANNOTATED_KEY]));
  };

  const autoDetected = colorBy !== null && colorBy === summary.default_color_column;

  return (
    <div className="layout">
      <header className="topbar">
        <h1>Spatial Data Explorer</h1>
        <span className="muted">
          {summary.platform} · {summary.n_cells.toLocaleString()} cells · {summary.n_genes.toLocaleString()} genes
        </span>
      </header>

      <div className="views">
        {spatial.state === "ready" ? (
          <ScatterView id="spatial" title="Spatial" positions={spatial.value} colors={colors}
            flipY radius={SPATIAL_RADIUS} />
        ) : (
          <section className="panel placeholder">{spatial.state === "error" ? spatial.message : "Loading spatial..."}</section>
        )}
        {!hasUmap ? (
          <section className="panel placeholder">No UMAP in this dataset (obsm["X_umap"])</section>
        ) : umap.state === "ready" ? (
          <ScatterView id="umap" title="UMAP" positions={umap.value} colors={colors}
            flipY={false} radius={UMAP_RADIUS} />
        ) : (
          <section className="panel placeholder">{umap.state === "error" ? umap.message : "Loading UMAP..."}</section>
        )}
      </div>

      <aside className="sidebar">
        <label className="field">
          <span>Color by</span>
          <select value={colorBy ?? ""} onChange={(e) => setColorBy(e.target.value || null)}>
            {summary.obs_columns.map((c) => (
              <option key={c.name} value={c.name}>{c.name} ({c.kind})</option>
            ))}
          </select>
        </label>
        {autoDetected && (
          <p className="muted small">Auto-detected: {summary.default_color_reason}</p>
        )}
        {column.state === "ready" && (
          <Legend column={column.value} palette={palette} hidden={hidden} onToggle={toggle} onSetAll={setAll} />
        )}
        {column.state === "error" && <p className="error">{column.message}</p>}
        {!colorBy && <p className="muted">No categorical column found to color by.</p>}
      </aside>
    </div>
  );
}
