from src.logger import setup_logger
from src.adb_client import connect_adb
from src.app_discovery import get_launcher_apps, fuzzy_match
from src.screenshot import save_screenshot
import time

logger = setup_logger()

device = connect_adb()
label_map = get_launcher_apps()

user_input = input("Enter app name to launch (e.g. 'sky', 'zomato', 'uber'): ")
label, selected_pkg = fuzzy_match(user_input, label_map)

logger.info(f"🚀 Launching {label} → {selected_pkg}")
device.shell(f"monkey -p {selected_pkg} -c android.intent.category.LAUNCHER 1")
time.sleep(5)

save_screenshot(device, app_name=label)
