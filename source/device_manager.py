import uiautomator2 as u2
import time
from source.logger import logger

def connect_to_device():
    """Connect to the Android device using uiautomator2."""
    logger.info("🔌 Connecting to device...")
    return u2.connect()

def launch_app(d, package_name):
    """Launch the specified app on the device."""
    logger.info(f"🚀 Launching {package_name}...")
    d.app_start(package_name)
    time.sleep(5) 