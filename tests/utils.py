from logging import Logger
import pytest


class MockedLogger(Logger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logs = []

    def _log(self, *args, **kwargs) -> None:
        self.logs.append((args, kwargs))


logger_counter = 0

@pytest.fixture()
def mocked_logger() -> MockedLogger:
    global logger_counter

    logger = MockedLogger(name=f"MockedLogger#{logger_counter}")
    logger_counter += 1

    return logger