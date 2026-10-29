// Typed client for the backend API (docs/PLAN.md §6).

export interface ObsColumnInfo {
  name: string;
  kind: "categorical" | "numeric";
}

export interface DatasetSummary {
  source: string;
  platform: string;
  n_cells: number;
  n_genes: number;
  expression_layer: string;
  embeddings: string[];
  obs_columns: ObsColumnInfo[];
  default_color_column: string | null;
  default_color_reason: string;
  has_polygons: boolean;
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
  return (await res.json()) as T;
}

type TypedArray = Float32Array | Int32Array | Uint32Array;
const ARRAY_TYPES: Record<string, new (buf: ArrayBuffer) => TypedArray> = {
  float32: Float32Array,
  int32: Int32Array,
  uint32: Uint32Array,
};

/** Fetches a binary array endpoint; the backend sends little-endian data plus X-Dtype / X-Shape headers. */
export async function getArray(path: string): Promise<{ data: TypedArray; shape: number[] }> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
  const dtype = res.headers.get("X-Dtype") ?? "float32";
  const shape = (res.headers.get("X-Shape") ?? "").split(",").map(Number);
  const Ctor = ARRAY_TYPES[dtype];
  if (!Ctor) throw new Error(`${path}: unsupported dtype ${dtype}`);
  return { data: new Ctor(await res.arrayBuffer()), shape };
}

export const api = {
  health: () => getJson<{ status: string; version: string }>("/api/health"),
  dataset: () => getJson<DatasetSummary>("/api/dataset"),
};
