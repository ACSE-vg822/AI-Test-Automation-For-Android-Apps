import os
import time
import io
from PIL import Image
import logging

def save_screenshot(device, app_name, save_dir="screenshots"):
    os.makedirs(save_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{app_name.lower()}_{timestamp}.png"
    filepath = os.path.join(save_dir, filename)

    raw = device.screencap()
    image = Image.open(io.BytesIO(raw))
    image.save(filepath)
    logging.info(f"📸 Screenshot saved to: {filepath}")
