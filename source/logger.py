import os
import logging

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)

# Prevent adding handlers multiple times
if not logger.handlers:
    # File handler
    file_handler = logging.FileHandler("logs/agent.log", mode="a")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
    logger.addHandler(console_handler)
