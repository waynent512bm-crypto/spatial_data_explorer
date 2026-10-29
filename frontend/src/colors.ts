// Color buffers for deck.gl: one RGBA (Uint8) entry per cell.

export type RGB = [number, number, number];

export const UNANNOTATED_RGB: RGB = [190, 190, 190];
export const UNANNOTATED_KEY = -1;

// scanpy's default palette for <= 20 categories, so colors match the analysis notebook.
const SCANPY_DEFAULT_20 = [
  "#1f77b4", "#ff7f0e", "#279e68", "#d62728", "#aa40fc", "#8c564b", "#e377c2", "#b5bd61",
  "#17becf", "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94", "#f7b6d2",
  "#dbdb8d", "#9edae5", "#ad494a", "#8c6d31",
];

const VIRIDIS: RGB[] = [
  [68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142], [38, 130, 142],
  [31, 158, 137], [53, 183, 121], [109, 205, 89], [180, 222, 44], [253, 231, 37],
];

export function hexToRgb(hex: string): RGB | null {
  const m = /^#?([0-9a-f]{6})([0-9a-f]{2})?$/i.exec(hex.trim());
  if (!m) return null;
  const v = parseInt(m[1], 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}

export function rgbToCss([r, g, b]: RGB): string {
  return `rgb(${r}, ${g}, ${b})`;
}

function hslToRgb(h: number, s: number, l: number): RGB {
  const k = (n: number) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [Math.round(f(0) * 255), Math.round(f(8) * 255), Math.round(f(4) * 255)];
}

/** Palette for n categories: colors stored in the .h5ad first, then scanpy's default, then generated hues. */
export function categoryPalette(n: number, stored?: (string | null)[] | null): RGB[] {
  return Array.from({ length: n }, (_, i) => {
    const fromFile = stored?.[i] ? hexToRgb(stored[i] as string) : null;
    if (fromFile) return fromFile;
    if (n <= SCANPY_DEFAULT_20.length) return hexToRgb(SCANPY_DEFAULT_20[i])!;
    return hslToRgb((i * 137.508) % 360, 0.65, 0.55);   // golden-angle hues
  });
}

export function viridis(t: number): RGB {
  const x = Math.min(1, Math.max(0, t)) * (VIRIDIS.length - 1);
  const i = Math.min(Math.floor(x), VIRIDIS.length - 2);
  const f = x - i;
  const [a, b] = [VIRIDIS[i], VIRIDIS[i + 1]];
  return [0, 1, 2].map((c) => Math.round(a[c] + (b[c] - a[c]) * f)) as RGB;
}

export const VIRIDIS_CSS = `linear-gradient(to right, ${VIRIDIS.map(rgbToCss).join(", ")})`;

/** Hidden categories (including UNANNOTATED_KEY) get alpha 0. */
export function categoricalColors(codes: Int32Array, palette: RGB[], hidden: ReadonlySet<number>): Uint8Array {
  const out = new Uint8Array(codes.length * 4);
  for (let i = 0; i < codes.length; i++) {
    const code = codes[i];
    const rgb = code < 0 ? UNANNOTATED_RGB : palette[code];
    const o = i * 4;
    out[o] = rgb[0];
    out[o + 1] = rgb[1];
    out[o + 2] = rgb[2];
    out[o + 3] = hidden.has(code < 0 ? UNANNOTATED_KEY : code) ? 0 : 255;
  }
  return out;
}

/** Viridis over [min, max]; NaN (missing) is drawn gray like unannotated cells. */
export function numericColors(values: Float32Array, min: number, max: number): Uint8Array {
  const out = new Uint8Array(values.length * 4);
  const span = max > min ? max - min : 1;
  const lut = Array.from({ length: 256 }, (_, i) => viridis(i / 255));
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    const rgb = Number.isFinite(v) ? lut[Math.round(((v - min) / span) * 255)] ?? lut[255] : UNANNOTATED_RGB;
    const o = i * 4;
    out[o] = rgb[0];
    out[o + 1] = rgb[1];
    out[o + 2] = rgb[2];
    out[o + 3] = 255;
  }
  return out;
}
