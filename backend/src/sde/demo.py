"""Synthetic Xenium-like dataset for development and tests.

Mimics an annotated Xenium output: an .h5ad with log-normalized X, obsm["spatial"] (microns),
obsm["X_umap"], a text `cell_type` column (with some "Unassigned"), numeric `leiden`, and a
`cell_boundaries.parquet` in Xenium's one-row-per-vertex layout. The boundary file also holds
cells that are absent from the .h5ad, as if removed by QC.
"""

from __future__ import annotations

from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp

CELL_TYPES = ["Tumor", "T cell", "B cell", "Macrophage", "Endothelial", "Fibroblast"]
MARKERS = {
    "Tumor": ["EPCAM", "CA9", "KRT8"],
    "T cell": ["CD3E", "CD8A", "CD2"],
    "B cell": ["MS4A1", "CD79A", "CD19"],
    "Macrophage": ["CD68", "CD163", "C1QC"],
    "Endothelial": ["PECAM1", "VWF", "KDR"],
    "Fibroblast": ["COL1A1", "PDGFRB", "ACTA2"],
}
FILLER_GENES = [f"GENE{i:03d}" for i in range(30)]
UNASSIGNED_FRACTION = 0.05
QC_DROPPED_FRACTION = 0.03
CELL_SPACING_UM = 12.0
N_VERTICES = 13   # Xenium boundaries: 13 vertices, last repeats the first


def make_demo(n_cells: int = 20_000, seed: int = 0) -> tuple[ad.AnnData, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    n_total = int(n_cells / (1 - QC_DROPPED_FRACTION))
    side = int(np.ceil(np.sqrt(n_total)))

    # Jittered grid of centroids in microns.
    gx, gy = np.meshgrid(np.arange(side), np.arange(side))
    xy = np.column_stack([gx.ravel(), gy.ravel()])[:n_total].astype(float) * CELL_SPACING_UM
    xy += rng.normal(0, CELL_SPACING_UM * 0.15, xy.shape)

    # Spatial structure: tumor core, immune ring, stroma, vessels along stripes.
    extent = side * CELL_SPACING_UM
    r = np.hypot(xy[:, 0] - extent / 2, xy[:, 1] - extent / 2) / (extent / 2)
    types = np.where(r < 0.45, "Tumor", "Fibroblast").astype(object)
    ring = (r >= 0.45) & (r < 0.6)
    types[ring] = rng.choice(["T cell", "B cell", "Macrophage"], ring.sum(), p=[0.5, 0.2, 0.3])
    vessel = (np.abs(np.sin(xy[:, 0] / 90)) < 0.08) & (r >= 0.6)
    types[vessel] = "Endothelial"
    sprinkle = rng.random(n_total) < 0.04
    types[sprinkle] = rng.choice(CELL_TYPES, sprinkle.sum())

    cell_ids = np.array([_xenium_cell_id(i) for i in range(n_total)])
    boundaries = _boundaries(cell_ids, xy, rng)

    keep = rng.random(n_total) >= QC_DROPPED_FRACTION
    idx = np.flatnonzero(keep)[:n_cells]
    xy, types, cell_ids = xy[idx], types[idx], cell_ids[idx]

    genes = [g for t in CELL_TYPES for g in MARKERS[t]] + FILLER_GENES
    gene_pos = {g: j for j, g in enumerate(genes)}
    rate = np.full((len(idx), len(genes)), 0.3)
    for t, markers in MARKERS.items():
        rows = types == t
        for g in markers:
            rate[rows, gene_pos[g]] = 6.0
    counts = rng.poisson(rate)
    lib = np.maximum(counts.sum(axis=1, keepdims=True), 1)
    lognorm = np.log1p(counts / lib * 100).astype(np.float32)

    label = types.copy()
    label[rng.random(len(idx)) < UNASSIGNED_FRACTION] = "Unassigned"
    leiden = pd.Series(types).map({t: str(i) for i, t in enumerate(CELL_TYPES)}).to_numpy()

    centers = {t: rng.normal(0, 8, 2) for t in CELL_TYPES}
    umap = np.array([centers[t] for t in types]) + rng.normal(0, 1.0, (len(idx), 2))

    adata = ad.AnnData(
        X=sp.csr_matrix(lognorm),
        obs=pd.DataFrame({
            "cell_type": pd.Categorical(label, categories=CELL_TYPES + ["Unassigned"]),
            "leiden": pd.Categorical(leiden),
            "transcript_counts": counts.sum(axis=1).astype(np.int32),
            "cell_area": rng.gamma(9, 10, len(idx)).astype(np.float32),
        }, index=pd.Index(cell_ids, name="cell_id")),
        var=pd.DataFrame(index=pd.Index(genes, name="gene")),
    )
    adata.layers["counts"] = sp.csr_matrix(counts.astype(np.float32))
    adata.obsm["spatial"] = xy.astype(np.float32)
    adata.obsm["X_umap"] = umap.astype(np.float32)
    return adata, boundaries


def write_demo(out: str | Path, n_cells: int = 20_000, seed: int = 0) -> tuple[Path, Path]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    adata, boundaries = make_demo(n_cells, seed)
    h5ad = out / "demo_annotated.h5ad"
    parquet = out / "cell_boundaries.parquet"
    adata.write_h5ad(h5ad)
    boundaries.to_parquet(parquet, index=False)
    return h5ad, parquet


def _xenium_cell_id(i: int) -> str:
    # Xenium style: 8 letters a-p encoding a number, plus a dataset suffix.
    letters = []
    for _ in range(8):
        letters.append(chr(ord("a") + i % 16))
        i //= 16
    return "".join(reversed(letters)) + "-1"


def _boundaries(cell_ids: np.ndarray, xy: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    n = len(cell_ids)
    angles = np.linspace(0, 2 * np.pi, N_VERTICES)        # last vertex == first
    radius = CELL_SPACING_UM * 0.42 * rng.uniform(0.8, 1.15, (n, 1))
    wobble = 1 + 0.12 * np.sin(angles * rng.integers(2, 5, (n, 1)) + rng.uniform(0, 6.3, (n, 1)))
    wobble[:, -1] = wobble[:, 0]
    vx = xy[:, [0]] + radius * wobble * np.cos(angles)
    vy = xy[:, [1]] + radius * wobble * np.sin(angles)
    return pd.DataFrame({
        "cell_id": np.repeat(cell_ids, N_VERTICES),
        "vertex_x": vx.ravel().astype(np.float32),
        "vertex_y": vy.ravel().astype(np.float32),
        "label_id": np.repeat(np.arange(1, n + 1, dtype=np.int32), N_VERTICES),
    })
