import anndata as ad
import numpy as np
import pandas as pd

from sde.dataset import Dataset


def make(obs: dict) -> Dataset:
    n = len(next(iter(obs.values())))
    adata = ad.AnnData(X=np.zeros((n, 2), dtype=np.float32),
                       obs=pd.DataFrame(obs, index=[f"c{i}" for i in range(n)]))
    adata.obsm["spatial"] = np.zeros((n, 2), dtype=np.float32)
    return Dataset(adata)


def test_string_column_codes_and_unannotated():
    col = make({"cell_type": ["T", "B", "Unknown", None, "T", ""]}).obs_column("cell_type")
    assert col.categories == ["B", "T"]
    assert col.codes.tolist() == [1, 0, -1, -1, 1, -1]


def test_categorical_keeps_order_and_drops_unused_categories():
    s = pd.Categorical(["Tumor", "Unassigned", "T cell", "Tumor"],
                       categories=["Tumor", "Stroma", "T cell", "Unassigned"])
    col = make({"cell_type": s}).obs_column("cell_type")
    assert col.categories == ["Tumor", "T cell"]          # "Stroma" has no cells
    assert col.codes.tolist() == [0, -1, 1, 0]
