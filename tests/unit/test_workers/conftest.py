import importlib
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_worker_loggers(monkeypatch):
    """Inject a dummy logger into all worker modules so process_message can log."""
    module_names = [
        "workers.validation.consumer",
        "workers.scraper.consumer",
        "workers.decision.consumer",
        "workers.notification.consumer",
        "workers.scheduler.scheduler",
    ]
    dummy_logger = MagicMock()
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            monkeypatch.setattr(module, "logger", dummy_logger)
        except Exception:
            pass
    return dummy_logger
