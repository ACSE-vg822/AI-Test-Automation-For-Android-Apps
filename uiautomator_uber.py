import uiautomator2 as u2
import time
import sys
import openai
import base64
from datetime import datetime
import os
import os
from dotenv import load_dotenv
import openai

load_dotenv()  # Load from .env if exists

# Use env variable
openai.api_key = os.getenv("OPENAI_API_KEY")


DESTINATION = "Tin factory"
UBER_PACKAGE = "com.ubercab"
PRICE_XPATH = "//android.widget.TextView[contains(@text, '₹')]"
UBER_GO_XPATH = "//android.widget.TextView[contains(@text, 'Uber Go')]"

def connect_to_device():
    print("🔌 Connecting to device...")
    return u2.connect()

def launch_uber(d):
    print("🚀 Launching Uber...")
    d.app_start(UBER_PACKAGE)
    time.sleep(5)

def enter_destination(d):
    print("📍 Tapping 'Enter your destination'...")
    if not d(text="Enter your destination").wait(timeout=10):
        print("❌ Could not find destination input.")
        sys.exit(1)
    d(text="Enter your destination").click()
    time.sleep(1)

    print(f"⌨️ Typing destination: {DESTINATION}")
    d.send_keys(DESTINATION, clear=True)
    time.sleep(2)

def select_suggestion(d):
    print("👉 Tapping top suggestion...")
    suggestion_xpath = f"//android.widget.TextView[contains(@text, '{DESTINATION}')]"
    if not d.xpath(suggestion_xpath).wait(timeout=5):
        print("❌ No matching suggestion found.")
        sys.exit(1)
    d.xpath(suggestion_xpath).click()
    time.sleep(5)

def wait_for_price_screen(d):
    print("🔍 Waiting for price screen...")
    if not d.xpath(UBER_GO_XPATH).wait(timeout=10):
        print("❌ Uber Go options not visible.")
        sys.exit(1)

def extract_price(d):
    print("💰 Extracting price...")
    price_elem = d.xpath(PRICE_XPATH)
    if price_elem.exists:
        price = price_elem.get().get_text()
        print(f"✅ Uber Go Price to {DESTINATION}: {price}")
    else:
        print("❌ Price not found on screen. Trying GPT fallback...")
        price = extract_price_with_gpt(d)
        if price:
            print(f"✅ [GPT] Uber Go Price to {DESTINATION}: {price}")
        else:
            print("❌ [GPT] Could not extract price from screenshot.")

def extract_price_with_gpt(d):
    os.makedirs("screenshots", exist_ok=True)
    timestamp = datetime.now().strftime('%H%M%S')
    filename = f"screenshots/screenshot_{timestamp}.png"
    d.screenshot(filename)

    with open(filename, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an Android app automation assistant."},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "This is a screenshot of the Uber app ride options screen. "
                                f"Please extract the *Uber Go* price to destination '{DESTINATION}'. "
                                "Only reply with the price amount like ₹199 or ₹204."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=50,
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ GPT Fallback failed: {e}")
        return None
def main():
    d = connect_to_device()
    launch_uber(d)
    enter_destination(d)
    select_suggestion(d)
    wait_for_price_screen(d)
    extract_price(d)

if __name__ == "__main__":
    main()
