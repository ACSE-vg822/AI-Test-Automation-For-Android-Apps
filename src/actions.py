import time
import logging

def launch_app(device, package_name):
    logging.info(f"🚀 Launching app: {package_name}")
    device.shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
    time.sleep(3)

def force_stop_app(device, package_name):
    logging.info(f"🛑 Force stopping: {package_name}")
    device.shell(f"am force-stop {package_name}")

def clear_app_data(device, package_name):
    logging.info(f"🧹 Clearing app data: {package_name}")
    device.shell(f"pm clear {package_name}")

def start_activity(device, package_name, activity):
    full = f"{package_name}/{activity}"
    logging.info(f"🎯 Starting activity: {full}")
    device.shell(f"am start -n {full}")

def tap(device, x, y):
    logging.info(f"👆 Tapping at ({x}, {y})")
    device.shell(f"input tap {x} {y}")

def input_text(device, text):
    clean_text = text.replace(" ", "%s")
    logging.info(f"⌨️ Inputting text: {text}")
    device.shell(f'input text "{clean_text}"')

def swipe(device, x1, y1, x2, y2, duration=300):
    logging.info(f"🌀 Swiping from ({x1},{y1}) → ({x2},{y2})")
    device.shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")
