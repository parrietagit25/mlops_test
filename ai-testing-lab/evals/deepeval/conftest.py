import os

import pytest


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return os.getenv("API_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def judge_model():
    from local_model import OllamaJudgeModel

    return OllamaJudgeModel()
