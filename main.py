from src_deprecated.logger import setup_logger
from src_deprecated.adb_client import connect_adb
from src_deprecated.app_discovery import get_launcher_apps, fuzzy_match
from src_deprecated.screenshot import save_screenshot
from src_deprecated.actions import launch_app  # You can import more when needed

import time

# --- Setup Logger ---
logger = setup_logger()

# --- Connect to ADB ---
device = connect_adb()

# --- Get Installed Apps ---
label_map = get_launcher_apps()

# --- Ask user what to launch ---
user_input = input("Enter app name to launch (e.g. 'sky', 'zomato', 'uber'): ")
label, selected_pkg = fuzzy_match(user_input, label_map)

# --- Launch the App ---
launch_app(device, selected_pkg)

# --- Optional: Wait and Take Screenshot ---
time.sleep(2)
save_screenshot(device, app_name=label)
