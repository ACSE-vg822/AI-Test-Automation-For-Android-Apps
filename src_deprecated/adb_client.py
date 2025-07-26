from ppadb.client import Client as AdbClient
import logging

def connect_adb():
    client = AdbClient(host="127.0.0.1", port=5037)
    devices = client.devices()
    if not devices:
        logging.critical("❌ No ADB devices connected.")
        raise RuntimeError("No ADB devices connected.")
    device = devices[0]
    logging.info(f"📱 Connected to device: {device.serial}")
    return device
