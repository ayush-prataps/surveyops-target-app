import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path so services are importable from tests
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure default Postgres environment variables match CI workflow
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_USER", "app")
os.environ.setdefault("POSTGRES_PASSWORD", "app")
os.environ.setdefault("POSTGRES_DB", "app")

from auth.main import app as auth_app
from inventory.main import app as inventory_app
from orders.main import app as orders_app
from payment.main import app as payment_app


@pytest.fixture
def auth_client():
    return TestClient(auth_app)


@pytest.fixture
def inventory_client():
    return TestClient(inventory_app)


@pytest.fixture
def orders_client():
    return TestClient(orders_app)


@pytest.fixture
def payment_client():
    return TestClient(payment_app)
