import logging

import pytest

from sysmonitor.logger import LOGGER_NAME


@pytest.fixture(autouse=True)
def _reset_sysmonitor_logger():
    """Detach and close handlers on the shared 'sysmonitor' logger after each test.

    get_logger() configures a module-level singleton; without this, a test's
    RotatingFileHandler stays open and (on Windows) blocks tmp_path cleanup.
    """
    yield
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
