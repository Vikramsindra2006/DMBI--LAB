from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def groceries():
    from market_basket.core import load_upload
    return load_upload((ROOT / "Dataset/groceries.csv").read_bytes(), "groceries.csv")


@pytest.fixture(scope="session")
def analysis(groceries):
    from market_basket.core import run_analysis
    return run_analysis(groceries)
