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

        matrix = adata.layers[layer] if layer else adata.X
        # Column (per-gene) lookups dominate, so keep a CSC copy for sparse input.
        self._expr = matrix.tocsc() if sp.issparse(matrix) else np.asarray(matrix)
        self._gene_index = {g: i for i, g in enumerate(adata.var_names)}
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
        return self.adata.n_vars

    # -- embeddings ---------------------------------------------------------

    def embedding_names(self) -> list[str]:
        names = []
        for key, value in self.adata.obsm.items():
            arr = np.asarray(value) if not hasattr(value, "to_numpy") else value.to_numpy()
            if arr.ndim == 2 and arr.shape[1] >= 2:
                names.append(key.removeprefix("X_"))
        return names

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
            unannotated = is_unannotated(s)
            labels = s.astype("string")
            kept = labels[~unannotated]
            if isinstance(s.dtype, pd.CategoricalDtype):
                # Preserve the annotation's own category order.
                order = [str(c) for c in s.cat.categories]
                present = set(kept.unique())
                categories = [c for c in order if c in present]
            else:
                categories = sorted(kept.unique())
            lookup = {c: i for i, c in enumerate(categories)}
            codes = np.full(len(s), -1, dtype=np.int32)
            codes[~unannotated] = kept.map(lookup).to_numpy(dtype=np.int32)
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
        names = list(self.adata.var_names)
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
            "embeddings": self.embedding_names(),
            "obs_columns": self.obs_columns(),
            "default_color_column": self.detection.column,
            "default_color_reason": self.detection.reason,
            "has_polygons": False,
        }
