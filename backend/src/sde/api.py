"""FastAPI app. Large arrays go out as raw little-endian binary (docs/PLAN.md §6)."""

from __future__ import annotations

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Response

from . import __version__
from .dataset import Dataset


def _binary(arr: np.ndarray, *, dtype: str, shape: tuple[int, ...]) -> Response:
    data = np.ascontiguousarray(arr).astype(np.dtype(dtype).newbyteorder("<"), copy=False)
    return Response(
        content=data.tobytes(),
        media_type="application/octet-stream",
        headers={"X-Dtype": dtype, "X-Shape": ",".join(map(str, shape))},
    )


def create_app(dataset: Dataset) -> FastAPI:
    app = FastAPI(title="Spatial Data Explorer", version=__version__)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/dataset")
    def dataset_summary():
        return dataset.summary()

    @app.get("/api/embedding/{name}")
    def embedding(name: str):
        try:
            coords = dataset.embedding(name)
        except KeyError:
            raise HTTPException(404, f"embedding {name!r} not found")
        return _binary(coords, dtype="float32", shape=coords.shape)

    @app.get("/api/obs/{column}")
    def obs_meta(column: str):
        try:
            col = dataset.obs_column(column)
        except KeyError:
            raise HTTPException(404, f"obs column {column!r} not found")
        except ValueError as e:
            raise HTTPException(400, str(e))
        meta = {"name": col.name, "kind": col.kind}
        if col.kind == "categorical":
            meta["categories"] = col.categories
            meta["colors"] = dataset.category_colors(column)
            meta["unannotated_count"] = int((col.codes < 0).sum())
        else:
            finite = col.values[np.isfinite(col.values)]
            meta["min"] = float(finite.min()) if finite.size else None
            meta["max"] = float(finite.max()) if finite.size else None
        return meta

    @app.get("/api/obs/{column}/values")
    def obs_values(column: str):
        try:
            col = dataset.obs_column(column)
        except KeyError:
            raise HTTPException(404, f"obs column {column!r} not found")
        except ValueError as e:
            raise HTTPException(400, str(e))
        if col.kind == "categorical":
            return _binary(col.codes, dtype="int32", shape=col.codes.shape)
        return _binary(col.values, dtype="float32", shape=col.values.shape)

    @app.get("/api/genes")
    def genes(q: str = "", limit: int = Query(20, ge=1, le=200)):
        return {"genes": dataset.search_genes(q, limit)}

    @app.get("/api/expression/{gene}")
    def expression(gene: str):
        try:
            values = dataset.expression(gene)
        except KeyError:
            raise HTTPException(404, f"gene {gene!r} not found")
        return _binary(values, dtype="float32", shape=values.shape)

    return app
