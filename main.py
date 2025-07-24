import os
import time
import io
import subprocess
import re
import logging
from PIL import Image
from ppadb.client import Client as AdbClient

# --- Logging setup ---
os.makedirs("logs", exist_ok=True)
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

# --- Utils ---
def get_launcher_apps():
    logging.info("🔍 Fetching installed apps...")
    output = subprocess.check_output("adb shell pm list packages -3", shell=True, text=True)
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

def save_screenshot(device, app_name, save_dir="screenshots"):
    os.makedirs(save_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{app_name.lower()}_{timestamp}.png"
    filepath = os.path.join(save_dir, filename)

    raw = device.screencap()
    image = Image.open(io.BytesIO(raw))
    image.save(filepath)
    logging.info(f"📸 Screenshot saved to: {filepath}")

# --- Connect to ADB ---
client = AdbClient(host="127.0.0.1", port=5037)
devices = client.devices()
if not devices:
    logging.critical("❌ No ADB devices connected.")
    raise RuntimeError("No ADB devices connected.")
device = devices[0]
logging.info(f"📱 Connected to device: {device.serial}")

# --- App Selection & Execution ---
label_map = get_launcher_apps()
user_input = input("Enter app name to launch (e.g. 'sky', 'zomato', 'uber'): ")
label, selected_pkg = fuzzy_match(user_input, label_map)

logging.info(f"🚀 Launching {label} → {selected_pkg}")
device.shell(f"monkey -p {selected_pkg} -c android.intent.category.LAUNCHER 1")
time.sleep(5)

save_screenshot(device, app_name=label)
