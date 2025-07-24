import subprocess
import re
import logging

def get_launcher_apps():
    logging.info("🔍 Fetching installed apps...")
    output = subprocess.check_output("adb shell pm list packages", shell=True, text=True)
    pkgs = [line.replace("package:", "").strip() for line in output.strip().splitlines()]
    
    label_map = {}
    for pkg in pkgs:
        label = pkg.split(".")[-1].replace("_", " ").capitalize()
        label_map[label] = pkg
    return label_map

def fuzzy_match(app_name: str, label_map: dict) -> tuple:
    app_name = app_name.lower()
    matches = {label: pkg for label, pkg in label_map.items() if app_name in label.lower()}
    if not matches:
        logging.error(f"No match found for '{app_name}'")
        logging.info("📦 Available apps:")
        for label, pkg in sorted(label_map.items()):
            logging.info(f"{label:<20} → {pkg}")
        raise ValueError("Try again with a matching keyword from the list.")
    return next(iter(matches.items()))
