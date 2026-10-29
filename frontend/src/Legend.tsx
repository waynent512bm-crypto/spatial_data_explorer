import { useMemo } from "react";
import type { ObsColumnData } from "./api";
import { rgbToCss, UNANNOTATED_KEY, UNANNOTATED_RGB, VIRIDIS_CSS, type RGB } from "./colors";

interface Props {
  column: ObsColumnData;
  palette: RGB[];
  hidden: ReadonlySet<number>;
  onToggle: (key: number) => void;
  onSetAll: (visible: boolean) => void;
}

function formatNumber(v: number | null): string {
  if (v === null) return "–";
  return Math.abs(v) >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : v.toPrecision(3);
}

export default function Legend({ column, palette, hidden, onToggle, onSetAll }: Props) {
  const counts = useMemo(() => {
    if (!("codes" in column)) return null;
    const c = new Array(column.meta.categories.length).fill(0);
    for (const code of column.codes) if (code >= 0) c[code]++;
    return c as number[];
  }, [column]);

  if (column.meta.kind === "numeric") {
    return (
      <div className="legend">
        <div className="colorbar" style={{ background: VIRIDIS_CSS }} />
        <div className="colorbar-labels">
          <span>{formatNumber(column.meta.min)}</span>
          <span>{formatNumber(column.meta.max)}</span>
        </div>
        <p className="muted small">Gray: missing value</p>
      </div>
    );
  }

  const meta = column.meta;
  const rows = meta.categories.map((label, i) => ({ key: i, label, rgb: palette[i], count: counts?.[i] ?? 0 }));
  if (meta.unannotated_count > 0) {
    rows.push({ key: UNANNOTATED_KEY, label: "Unannotated", rgb: UNANNOTATED_RGB, count: meta.unannotated_count });
  }

  return (
    <div className="legend">
      <div className="legend-actions">
        <button type="button" onClick={() => onSetAll(true)}>Show all</button>
        <button type="button" onClick={() => onSetAll(false)}>Hide all</button>
      </div>
      <ul>
        {rows.map((r) => (
          <li key={r.key}>
            <button
              type="button"
              className={`legend-item${hidden.has(r.key) ? " is-hidden" : ""}`}
              onClick={() => onToggle(r.key)}
              title={hidden.has(r.key) ? "Click to show" : "Click to hide"}
            >
              <span className="swatch" style={{ background: rgbToCss(r.rgb) }} />
              <span className="legend-label">{r.label}</span>
              <span className="legend-count">{r.count.toLocaleString()}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
