import pytest
from fastapi.testclient import TestClient

from sde.api import create_app
from sde.dataset import Dataset
from sde.demo import make_demo


@pytest.fixture(scope="session")
def demo_adata():
    adata, _ = make_demo(n_cells=2_000, seed=1)
    return adata


@pytest.fixture(scope="session")
def dataset(demo_adata):
    return Dataset(demo_adata, platform="xenium")


@pytest.fixture(scope="session")
def client(dataset):
    return TestClient(create_app(dataset))
