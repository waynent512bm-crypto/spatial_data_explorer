"""Loads an annotated .h5ad and serves the arrays the frontend needs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp

from .annotation import Detection, detect_celltype_column, is_categorical_like, is_unannotated

GENE_SEARCH_LIMIT = 20
GENE_FEATURE_TYPE = "Gene Expression"
COUNT_CHECK_ROWS = 2000


def gene_mask(var: pd.DataFrame) -> np.ndarray:
    """Genes only: drops protein, control probe and codeword features when `feature_types` says so."""
    if "feature_types" not in var.columns:
        return np.ones(len(var), dtype=bool)
    return (var["feature_types"].astype(str) == GENE_FEATURE_TYPE).to_numpy()


def looks_like_counts(matrix) -> bool:
    """True if a sample of rows holds only non-negative integers, i.e. raw counts, not log-normalized."""
    rows = matrix[:COUNT_CHECK_ROWS]
    values = rows.data if sp.issparse(rows) else np.asarray(rows).ravel()
    values = values[values != 0]
    return values.size > 0 and bool((values >= 0).all() and np.allclose(values, np.round(values)))


def log_normalize(matrix):
    """scanpy normalize_total + log1p, the same defaults as the analysis notebooks."""
    import scanpy as sc

    tmp = ad.AnnData(X=matrix.astype(np.float32) if sp.issparse(matrix) else np.asarray(matrix, np.float32))
    sc.pp.normalize_total(tmp)
    sc.pp.log1p(tmp)
    return tmp.X


@dataclass
class ObsColumn:
    name: str
    kind: str                      # "categorical" | "numeric"
    categories: list[str] = field(default_factory=list)
    codes: np.ndarray | None = None    # int32, -1 = unannotated (categorical only)
    values: np.ndarray | None = None   # float32, NaN = missing (numeric only)


class Dataset:
    def __init__(self, adata: ad.AnnData, *, platform: str = "unknown", layer: str | None = None,
                 source: str = ""):
        if "spatial" not in adata.obsm:
            raise ValueError('.h5ad has no obsm["spatial"] (cell centroid coordinates)')
        if layer is not None and layer not in adata.layers:
            raise ValueError(f"layer {layer!r} not found; available: {list(adata.layers)}")

        self.adata = adata
        self.platform = platform
        self.layer = layer
        self.source = source
        self.detection: Detection = detect_celltype_column(adata.obs)

        mask = gene_mask(adata.var)
        self.genes: list[str] = list(adata.var_names[mask])
        self.n_excluded_features = int((~mask).sum())
        matrix = (adata.layers[layer] if layer else adata.X)[:, mask]
        if looks_like_counts(matrix):
            matrix = log_normalize(matrix)
            self.normalization = "normalize_total + log1p (auto: raw counts detected)"
        else:
            self.normalization = "as provided"
        # Column (per-gene) lookups dominate, so keep a CSC copy for sparse input.
        self._expr = matrix.tocsc() if sp.issparse(matrix) else np.asarray(matrix)
        self._gene_index = {g: i for i, g in enumerate(self.genes)}
        self._obs_cache: dict[str, ObsColumn] = {}

    @classmethod
    def from_h5ad(cls, path: str | Path, **kwargs) -> "Dataset":
        path = Path(path)
        return cls(ad.read_h5ad(path), source=str(path), **kwargs)

    @property
    def n_cells(self) -> int:
        return self.adata.n_obs

    @property
    def n_genes(self) -> int:
        return len(self.genes)

    # -- embeddings ---------------------------------------------------------

    def embedding_names(self) -> list[str]:
        names = []
        for key, value in self.adata.obsm.items():
            arr = np.asarray(value) if not hasattr(value, "to_numpy") else value.to_numpy()
            if arr.ndim == 2 and arr.shape[1] >= 2:
                names.append(key.removeprefix("X_"))
        return names

    def default_embedding(self) -> str | None:
        """Non-spatial embedding shown next to the tissue: plain umap, then an RNA umap, then any umap."""
        names = [n for n in self.embedding_names() if n != "spatial"]
        for pick in (lambda n: n == "umap", lambda n: "umap" in n and "rna" in n, lambda n: "umap" in n):
            match = next((n for n in names if pick(n)), None)
            if match:
                return match
        return names[0] if names else None

    def embedding(self, name: str) -> np.ndarray:
        for key in (name, f"X_{name}"):
            if key in self.adata.obsm:
                value = self.adata.obsm[key]
                arr = value.to_numpy() if hasattr(value, "to_numpy") else np.asarray(value)
                return np.ascontiguousarray(arr[:, :2], dtype=np.float32)
        raise KeyError(name)

    # -- obs ----------------------------------------------------------------

    def obs_columns(self) -> list[dict]:
        out = []
        for c in self.adata.obs.columns:
            s = self.adata.obs[c]
            if is_categorical_like(s):
                out.append({"name": c, "kind": "categorical"})
            elif pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
                out.append({"name": c, "kind": "numeric"})
        return out

    def obs_column(self, name: str) -> ObsColumn:
        if name in self._obs_cache:
            return self._obs_cache[name]
        if name not in self.adata.obs.columns:
            raise KeyError(name)
        s = self.adata.obs[name]

        if is_categorical_like(s):
            # Classify each distinct label once, then remap integer codes: fast for ~1M cells.
            # Category order follows the annotation's own Categorical order (else sorted).
            cat = s if isinstance(s.dtype, pd.CategoricalDtype) else s.astype("category")
            labels = pd.Series(cat.cat.categories)
            old = cat.cat.codes.to_numpy()
            used = np.bincount(old[old >= 0], minlength=len(labels)) > 0
            keep = used & ~is_unannotated(labels)
            categories = [str(c) for c in labels[keep]]
            remap = np.full(len(labels), -1, dtype=np.int32)
            remap[keep] = np.arange(keep.sum(), dtype=np.int32)
            codes = np.where(old >= 0, remap[np.maximum(old, 0)], -1).astype(np.int32)
            col = ObsColumn(name, "categorical", categories=categories, codes=codes)
        elif pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            col = ObsColumn(name, "numeric", values=s.to_numpy(dtype=np.float32, na_value=np.nan))
        else:
            raise ValueError(f"obs column {name!r} is neither categorical nor numeric")

        self._obs_cache[name] = col
        return col

    def category_colors(self, name: str) -> list[str] | None:
        """Colors scanpy stored for this column (obs order of categories), if any."""
        colors = self.adata.uns.get(f"{name}_colors")
        s = self.adata.obs[name]
        if colors is None or not isinstance(s.dtype, pd.CategoricalDtype):
            return None
        by_label = dict(zip((str(c) for c in s.cat.categories), colors))
        return [by_label.get(c) for c in self.obs_column(name).categories]

    # -- genes --------------------------------------------------------------

    def search_genes(self, query: str, limit: int = GENE_SEARCH_LIMIT) -> list[str]:
        q = query.strip().lower()
        names = self.genes
        if not q:
            return names[:limit]
        prefix = [g for g in names if g.lower().startswith(q)]
        contains = [g for g in names if q in g.lower() and not g.lower().startswith(q)]
        return (prefix + contains)[:limit]

    def expression(self, gene: str) -> np.ndarray:
        if gene not in self._gene_index:
            raise KeyError(gene)
        j = self._gene_index[gene]
        if sp.issparse(self._expr):
            col = self._expr[:, j].toarray().ravel()
        else:
            col = self._expr[:, j]
        return np.ascontiguousarray(col, dtype=np.float32)

    # -- summary ------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "source": self.source,
            "platform": self.platform,
            "n_cells": self.n_cells,
            "n_genes": self.n_genes,
            "expression_layer": self.layer or "X",
            "expression_normalization": self.normalization,
            "n_excluded_features": self.n_excluded_features,
            "embeddings": self.embedding_names(),
            "default_embedding": self.default_embedding(),
            "obs_columns": self.obs_columns(),
            "default_color_column": self.detection.column,
            "default_color_reason": self.detection.reason,
            "has_polygons": False,
        }
