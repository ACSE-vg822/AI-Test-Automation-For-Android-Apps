import os
import logging

os.makedirs("logs", exist_ok=True)

def setup_logger():
    logging.basicConfig(
        filename="logs/agent.log",
        filemode="a",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter("%(levelname)s | %(message)s")
    console.setFormatter(formatter)
    logging.getLogger().addHandler(console)
    return logging.getLogger()
