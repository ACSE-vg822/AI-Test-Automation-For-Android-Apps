import time
import numpy as np
from ppadb.client import Client as AdbClient
from PIL import Image
import cv2
import io

# Connect to ADB server
client = AdbClient(host="127.0.0.1", port=5037)
devices = client.devices()

if len(devices) == 0:
    raise RuntimeError("No ADB device found.")

device = devices[0]
print(f"Connected to {device.serial}")

# Launch Zomato
zomato_package = "com.application.zomato"  # This is likely outdated
zomato_activity = "com.application.zomato.MainActivity"  # May vary
device.shell(f"monkey -p {zomato_package} -c android.intent.category.LAUNCHER 1")
print("Launched Zomato.")
time.sleep(3)

# Take screenshot
raw = device.screencap()
image = Image.open(io.BytesIO(raw))
image.save("zomato_screen.png")
print("Screenshot saved as zomato_screen.png")
