import { useEffect, useMemo, useRef, useState } from "react";
import DeckGL from "@deck.gl/react";
import { OrthographicView, type OrthographicViewState } from "@deck.gl/core";
import { ScatterplotLayer } from "@deck.gl/layers";

interface Props {
  id: string;
  title: string;
  /** Flat [x0, y0, x1, y1, ...]. */
  positions: Float32Array;
  /** Flat RGBA, 4 bytes per cell. */
  colors: Uint8Array;
  /** Image-style y axis (down) for tissue coordinates; math-style (up) for UMAP. */
  flipY: boolean;
  /** Point radius: in data units for spatial (microns), in pixels for UMAP. */
  radius: { units: "common" | "pixels"; size: number };
}

function bounds(xy: Float32Array) {
  let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
  for (let i = 0; i < xy.length; i += 2) {
    const x = xy[i], y = xy[i + 1];
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  return { x0, y0, x1, y1 };
}

function fitView(b: ReturnType<typeof bounds>, width: number, height: number): OrthographicViewState {
  const dx = Math.max(b.x1 - b.x0, 1e-6), dy = Math.max(b.y1 - b.y0, 1e-6);
  const scale = Math.min(width / dx, height / dy) * 0.92;
  return { target: [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2, 0], zoom: Math.log2(scale) };
}

export default function ScatterView({ id, title, positions, colors, flipY, radius }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewState, setViewState] = useState<OrthographicViewState | null>(null);
  const extent = useMemo(() => bounds(positions), [positions]);

  // Fit the whole embedding once the container has a size, and again when the data changes.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    if (width > 0 && height > 0) setViewState(fitView(extent, width, height));
  }, [extent]);

  // deck.gl's shaders take 3-component positions; pad z = 0 once per embedding.
  const positions3 = useMemo(() => {
    const n = positions.length / 2;
    const out = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      out[i * 3] = positions[i * 2];
      out[i * 3 + 1] = positions[i * 2 + 1];
    }
    return out;
  }, [positions]);

  const view = useMemo(() => new OrthographicView({ id, flipY }), [id, flipY]);

  const layer = useMemo(() => new ScatterplotLayer({
    id: `${id}-cells`,
    data: {
      length: positions3.length / 3,
      attributes: {
        getPosition: { value: positions3, size: 3 },
        getFillColor: { value: colors, size: 4, normalized: true },
      },
    },
    radiusUnits: radius.units,
    getRadius: radius.size,
    radiusMinPixels: 0.6,
    stroked: false,
    pickable: false,
  }), [id, positions3, colors, radius.units, radius.size]);

  const resetView = () => {
    const el = containerRef.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    setViewState(fitView(extent, width, height));
  };

  return (
    <section className="panel">
      <header className="panel-header">
        <h2>{title}</h2>
        <button type="button" onClick={resetView}>Reset view</button>
      </header>
      <div className="panel-canvas" ref={containerRef}>
        {viewState && (
          <DeckGL
            views={view}
            viewState={viewState}
            onViewStateChange={({ viewState: vs }) => setViewState(vs as OrthographicViewState)}
            controller={{ scrollZoom: { smooth: false, speed: 0.02 } }}
            layers={[layer]}
          />
        )}
      </div>
    </section>
  );
}
