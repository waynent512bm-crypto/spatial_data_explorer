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

export interface CategoricalMeta {
  name: string;
  kind: "categorical";
  categories: string[];
  colors: (string | null)[] | null;
  unannotated_count: number;
}

export interface NumericMeta {
  name: string;
  kind: "numeric";
  min: number | null;
  max: number | null;
}

export type ObsMeta = CategoricalMeta | NumericMeta;

export type ObsColumnData =
  | { meta: CategoricalMeta; codes: Int32Array }
  | { meta: NumericMeta; values: Float32Array };

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

const enc = encodeURIComponent;

export const api = {
  health: () => getJson<{ status: string; version: string }>("/api/health"),
  dataset: () => getJson<DatasetSummary>("/api/dataset"),

  /** n x 2 coordinates, as a flat Float32Array [x0, y0, x1, y1, ...]. */
  embedding: async (name: string) => (await getArray(`/api/embedding/${enc(name)}`)).data as Float32Array,

  obsColumn: async (column: string): Promise<ObsColumnData> => {
    const [meta, values] = await Promise.all([
      getJson<ObsMeta>(`/api/obs/${enc(column)}`),
      getArray(`/api/obs/${enc(column)}/values`),
    ]);
    return meta.kind === "categorical"
      ? { meta, codes: values.data as Int32Array }
      : { meta, values: values.data as Float32Array };
  },
};
