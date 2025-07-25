import uiautomator2 as u2
import time
import sys
import os
import base64
from datetime import datetime
from dotenv import load_dotenv
import openai

# === Load environment ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# === Config ===
DESTINATION = "Tin factory"
UBER_PACKAGE = "com.ubercab"
PRICE_XPATH = "//android.widget.TextView[contains(@text, '₹')]"
UBER_GO_XPATH = "//android.widget.TextView[contains(@text, 'Uber Go')]"
SCREENSHOT_DIR = "screenshots"


# === Helper: Screenshot & GPT Fallback ===
def take_screenshot(d, label: str) -> str:
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%H%M%S')
    path = f"{SCREENSHOT_DIR}/{label}_{timestamp}.png"
    d.screenshot(path)
    return path

def gpt_fallback(image_path: str, prompt: str) -> str:
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful Android automation assistant. Only return the exact result asked."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=100,
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ GPT fallback failed: {e}")
        return None


# === Core steps ===
def connect_to_device():
    print("🔌 Connecting to device...")
    return u2.connect()

def launch_uber(d):
    print("🚀 Launching Uber...")
    d.app_start(UBER_PACKAGE)
    time.sleep(5)

def enter_destination(d):
    print("📍 Tapping destination input...")
    if not d(text="Enter your destination").wait(timeout=10):
        ss = take_screenshot(d, "missing_destination_input")
        fallback_prompt = (
            f"Where is the 'Enter your destination' input field to reach '{DESTINATION}' in this Uber app screenshot? "
            f"Reply with a command like: d(text='...').click()"
        )
        suggestion = gpt_fallback(ss, fallback_prompt)
        print("🤖 GPT Suggestion:\n", suggestion)
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
        ss = take_screenshot(d, "missing_suggestion")
        fallback_prompt = (
            f"Tap on the correct suggestion for destination '{DESTINATION}' in the Uber app. "
            f"Return exact UIAutomator2 command like d.xpath('...').click()"
        )
        suggestion = gpt_fallback(ss, fallback_prompt)
        print("🤖 GPT Suggestion:\n", suggestion)
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
        print("⚠️ Price not found — trying GPT fallback...")
        ss = take_screenshot(d, "price_fallback")
        price = gpt_fallback(
            ss,
            f"This is the ride options screen of Uber. Extract the *Uber Go* price for destination '{DESTINATION}'. "
            f"Only reply with the price like ₹199 or ₹204."
        )
        if price:
            print(f"✅ [GPT] Uber Go Price to {DESTINATION}: {price}")
        else:
            print("❌ [GPT] Could not extract price from screenshot.")


# === Main ===
def main():
    d = connect_to_device()
    launch_uber(d)
    enter_destination(d)
    select_suggestion(d)
    wait_for_price_screen(d)
    extract_price(d)

if __name__ == "__main__":
    main()
