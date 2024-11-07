import sys
import logging
from pathlib import Path
from loguru import logger
from app.core.config import get_settings

settings = get_settings()

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logging():
    # Remove default handlers
    logging.root.handlers = []
    logging.root.propagate = False

    # Intercept everything at the root logger
    logging.root.handlers = [InterceptHandler()]

    # Set logging levels
    logging.root.setLevel(logging.INFO)
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    # Configure loguru
    logger.configure(
        handlers=[
            {"sink": sys.stdout, "level": logging.INFO},
            {"sink": "logs/app.log", "rotation": "500 MB", "retention": "10 days", "level": logging.INFO},
        ]
    )

    return logger 