import time
import logging

def launch_app(device, package_name):
    logging.info(f"🚀 Launching app: {package_name}")
    device.shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
    time.sleep(3)
