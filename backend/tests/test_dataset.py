import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp

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


def xenium_like(X: np.ndarray, obsm_keys=("X_umap_rna",)) -> Dataset:
    # Real Xenium exports mix genes with protein and control features in var.
    var = pd.DataFrame({"feature_types": ["Gene Expression", "Gene Expression",
                                          "Protein Expression", "Negative Control Probe"]},
                       index=["CD3E", "EPCAM", "p_CD45", "NegPrb1"])
    adata = ad.AnnData(X=sp.csr_matrix(X.astype(np.float32)), var=var,
                       obs=pd.DataFrame(index=[f"c{i}" for i in range(X.shape[0])]))
    adata.obsm["spatial"] = np.zeros((X.shape[0], 2), dtype=np.float32)
    for k in obsm_keys:
        adata.obsm[k] = np.zeros((X.shape[0], 2), dtype=np.float32)
    return Dataset(adata)


def test_only_gene_features_are_exposed():
    ds = xenium_like(np.array([[1, 3, 900, 1], [4, 0, 50, 0]]))
    assert ds.genes == ["CD3E", "EPCAM"]
    assert ds.n_genes == 2 and ds.n_excluded_features == 2
    assert ds.search_genes("p_") == []


def test_raw_counts_are_log_normalized_over_genes_only():
    counts = np.array([[1, 3, 900, 1], [4, 0, 50, 0]])
    ds = xenium_like(counts)
    assert ds.normalization.startswith("normalize_total + log1p")
    gene_counts = counts[:, :2].astype(float)
    totals = gene_counts.sum(axis=1, keepdims=True)
    expected = np.log1p(gene_counts / totals * np.median(totals))   # scanpy default target_sum
    np.testing.assert_allclose(ds.expression("CD3E"), expected[:, 0], rtol=1e-5)
    np.testing.assert_allclose(ds.expression("EPCAM"), expected[:, 1], rtol=1e-5)


def test_lognormalized_input_is_left_alone():
    ds = xenium_like(np.array([[0.5, 1.2, 3.3, 0.0], [0.0, 2.7, 0.1, 0.4]]))
    assert ds.normalization == "as provided"
    np.testing.assert_allclose(ds.expression("EPCAM"), [1.2, 2.7], rtol=1e-6)


def test_default_embedding_prefers_rna_umap():
    ds = xenium_like(np.ones((2, 4)), obsm_keys=("X_umap_protein", "X_umap_rna"))
    assert ds.default_embedding() == "umap_rna"
    assert xenium_like(np.ones((2, 4)), obsm_keys=("X_umap",)).default_embedding() == "umap"
    assert xenium_like(np.ones((2, 4)), obsm_keys=()).default_embedding() is None


def test_categorical_keeps_order_and_drops_unused_categories():
    s = pd.Categorical(["Tumor", "Unassigned", "T cell", "Tumor"],
                       categories=["Tumor", "Stroma", "T cell", "Unassigned"])
    col = make({"cell_type": s}).obs_column("cell_type")
    assert col.categories == ["Tumor", "T cell"]          # "Stroma" has no cells
    assert col.codes.tolist() == [0, -1, 1, 0]
