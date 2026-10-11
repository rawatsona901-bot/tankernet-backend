import os
import pytest

# Configure environment variables for mock/offline testing
os.environ["MOCK_DYNAMODB"] = "true"
os.environ["USE_LOCAL_PARSER"] = "true"
os.environ["MOCK_IOT"] = "true"
os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"

from src.services.dynamodb_service import reset_in_memory_db


@pytest.fixture(autouse=True)
def setup_mock_db():
    """Reset the in-memory database and re-seed 3-city tankers before each test."""
    reset_in_memory_db()
    yield
