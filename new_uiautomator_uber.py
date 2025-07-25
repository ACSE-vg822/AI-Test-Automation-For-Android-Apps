import uiautomator2 as u2
import time
import os
import base64
import json
import re
from datetime import datetime
from dotenv import load_dotenv
import openai

# === Setup ===
load_dotenv(override=True)
openai.api_key = os.getenv("OPENAI_API_KEY")
UBER_PACKAGE = "com.ubercab"
SCREENSHOT_DIR = "screenshots"

# === Device Connection ===
def connect_to_device():
    print("🔌 Connecting to device...")
    return u2.connect()

def launch_app(d):
    print("🚀 Launching Uber...")
    d.app_start(UBER_PACKAGE)
    time.sleep(5)

# === Screenshot + GPT fallback ===
def take_screenshot(d, label="fallback"):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S")
    path = os.path.join(SCREENSHOT_DIR, f"{label}_{timestamp}.png")
    d.screenshot(path)
    print(f"📸 Screenshot saved: {path}")
    print(f"🖼️ Screenshot size: {os.path.getsize(path) / 1024:.2f} KB")
    return path

def gpt_fallback(image_path, label=None):
    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")

    # Use a concise, reusable prompt
    if label:
        prompt = (
            f"This is a screenshot of a mobile app. "
            f"Extract the price (₹, $, etc.) shown next to '{label}'. "
            f"Only reply with the price, like ₹249.94 or $12.99. Do not explain."
        )
    else:
        prompt = (
            "This is a screenshot of a mobile app. "
            "Extract the main price (₹, $, etc.) visible. Only reply with the price. Do not explain."
        )

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful UI automation assistant. Only return the exact result asked."
                },
                {
                    "role": "user",
                    "content": [
                        { "type": "text", "text": prompt },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_img}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=100,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```[a-zA-Z]*", "", raw).strip("`").strip()
        return raw
    except Exception as e:
        print(f"❌ GPT fallback failed: {e}")
        return None

def gpt_fallback_action(image_path, user_request):
    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")
    prompt = (
        "This is a screenshot of a mobile app. The automation failed to find or interact with the expected element. "
        f"The user request is: '{user_request}'. "
        "What is the next UI action (click/type) to progress toward this goal? "
        "Reply with a single JSON object, e.g., { \"action\": \"click\", \"target\": \"text='...'\" }. "
        "Do not explain."
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful UI automation assistant. Only return the exact result asked."
                },
                {
                    "role": "user",
                    "content": [
                        { "type": "text", "text": prompt },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_img}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=150,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```[a-zA-Z]*", "", raw).strip("`").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"❌ GPT fallback action failed: {e}")
        return None

def extract_label_from_request(user_request):
    # Add more ride types as needed
    ride_types = ["Uber Go", "Auto", "Request Any", "UberX", "Uber Pool"]
    for ride in ride_types:
        if ride.lower() in user_request.lower():
            return ride
    return None

# === Plan generation ===
def generate_plan(user_request):
    print(f"🧠 Generating plan for: '{user_request}'")
    # Read UI text from uber.txt if available
    ui_text = ""
    try:
        with open("app_context/uber.txt", "r", encoding="utf-8") as f:
            ui_text = f.read()
    except Exception as e:
        print(f"⚠️ Could not read uber.txt: {e}")
    system_prompt = f"""
You are a mobile automation planner. The following is the visible UI text on the screen:
{ui_text}

Generate a step-by-step plan for automating the Uber app using uiautomator2.

Each step should be:
- Directly mappable to uiautomator2 methods
- Written in JSON format like:
[
  {{ "action": "click", "target": "text='Search'" }},
  {{ "action": "type", "value": "Wireless Headphones" }},
  {{ "action": "click", "target": "xpath=//android.widget.TextView[contains(@text, 'Wireless Headphones')]" }},
  {{ "action": "wait", "target": "xpath=//android.widget.TextView[contains(@text, '$')]" }},
  {{ "action": "extract", "target": "xpath=(//android.widget.TextView[contains(@text, '$')])[1]" }}
]
Only output valid JSON array — no markdown or explanations.
"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            { "role": "system", "content": system_prompt },
            { "role": "user", "content": user_request }
        ],
        max_tokens=500,
        temperature=0.2
    )

    raw = response.choices[0].message.content.strip()
    print("🪵 Raw LLM output:\n", raw)

    try:
        # Auto-fix if wrapped in code block
        if raw.startswith("```"):
            raw = re.sub(r"```(json)?", "", raw).strip("`")
        return json.loads(raw)
    except Exception as e:
        print("❌ Plan parsing failed:", e)
        return []


# === Main Executor ===
def execute_plan(d, plan, user_request):
    label_from_request = extract_label_from_request(user_request)
    i = 0
    failed_nav_fallbacks = 0  # Track consecutive failed click/type fallbacks
    while i < len(plan):
        step = plan[i]
        print(f"\n➡️ Step {i+1}: {step}")
        action = step.get("action")
        target = step.get("target")
        value = step.get("value")

        if action == "click":
            success = False
            if target and target.startswith("text="):
                text_val = target.replace("text=", "").strip("'\"")
                if d(text=text_val).exists(timeout=5):
                    d(text=text_val).click()
                    success = True
            elif target and target.startswith("xpath="):
                xpath_val = target.replace("xpath=", "")
                if d.xpath(xpath_val).exists:
                    d.xpath(xpath_val).click()
                    success = True
                else:
                    match = re.search(r"'([^']+)'", xpath_val)
                    if match:
                        fallback_text = match.group(1)
                        if d(text=fallback_text).exists(timeout=5):
                            d(text=fallback_text).click()
                            success = True
            if not success:
                print("⚠️ Step failed: Click failed: Target not found")
                failed_nav_fallbacks += 1
                if failed_nav_fallbacks >= 2:
                    print("🔄 Too many navigation failures, switching to extraction fallback!")
                    ss = take_screenshot(d, f"step_{i+1}_extract_fallback")
                    suggestion = gpt_fallback(ss, label_from_request)
                    print("🤖 GPT Extracted:", suggestion)
                    if suggestion:
                        print(f"✅ Final Result: {suggestion}")
                        return suggestion  # EARLY EXIT
                    # If extraction fails, continue as before
                else:
                    ss = take_screenshot(d, f"step_{i+1}_click_fallback")
                    suggestion = gpt_fallback_action(ss, user_request)
                    print("🤖 GPT Fallback Suggestion:", suggestion)
                    if suggestion and isinstance(suggestion, dict):
                        plan.insert(i+1, suggestion)  # Try the suggestion next
                    else:
                        print("⚠️ No valid fallback action from GPT. Skipping.")
                i += 1
                continue
            else:
                failed_nav_fallbacks = 0  # Reset on success

        elif action == "type":
            try:
                d.send_keys(value, clear=True)
                failed_nav_fallbacks = 0  # Reset on success
            except Exception as e:
                print(f"⚠️ Step failed: Type failed: {e}")
                failed_nav_fallbacks += 1
                if failed_nav_fallbacks >= 2:
                    print("🔄 Too many navigation failures, switching to extraction fallback!")
                    ss = take_screenshot(d, f"step_{i+1}_extract_fallback")
                    suggestion = gpt_fallback(ss, label_from_request)
                    print("🤖 GPT Extracted:", suggestion)
                    if suggestion:
                        print(f"✅ Final Result: {suggestion}")
                        return suggestion  # EARLY EXIT
                else:
                    ss = take_screenshot(d, f"step_{i+1}_type_fallback")
                    suggestion = gpt_fallback_action(ss, user_request)
                    print("🤖 GPT Fallback Suggestion:", suggestion)
                    if suggestion and isinstance(suggestion, dict):
                        plan.insert(i+1, suggestion)  # Try the suggestion next
                    else:
                        print("⚠️ No valid fallback action from GPT. Skipping.")
                i += 1
                continue

        elif action == "wait":
            xpath_val = target.replace("xpath=", "")
            if not d.xpath(xpath_val).wait(timeout=10):
                print("⚠️ Step failed: Wait failed: XPath not visible")
                # Optionally add fallback here

        elif action == "extract":
            xpath_val = target.replace("xpath=", "")
            try:
                elems = d.xpath(xpath_val).all()
                print(f"🔍 Found {len(elems)} ₹ elements")
                for i_elem, e in enumerate(elems):
                    try:
                        txt = e.get_text()
                        print(f"[{i_elem}] → {txt}")
                        if label_from_request and label_from_request in txt:
                            print(f"✅ Extracted Value: {txt}")
                            return txt  # EARLY EXIT
                        if not label_from_request and ("Auto" in txt or i_elem == 1):
                            print(f"✅ Extracted Value: {txt}")
                            return txt  # EARLY EXIT
                    except Exception as ex:
                        print(f"❌ Couldn’t extract from {i_elem}: {ex}")
                raise Exception("No valid ₹ element matched")
            except Exception as e:
                # Retry logic: wait up to 15s for any price to appear
                print("⏳ Waiting for price to load...")
                found = False
                for retry in range(7):  # 7*2s = 14s
                    time.sleep(2)
                    elems = d.xpath(xpath_val).all()
                    if elems:
                        print(f"🔍 Retry {retry+1}: Found {len(elems)} ₹ elements")
                        for i_elem, e in enumerate(elems):
                            try:
                                txt = e.get_text()
                                print(f"[{i_elem}] → {txt}")
                                if label_from_request and label_from_request in txt:
                                    print(f"✅ Extracted Value: {txt}")
                                    return txt  # EARLY EXIT
                                if not label_from_request and ("Auto" in txt or i_elem == 1):
                                    print(f"✅ Extracted Value: {txt}")
                                    return txt  # EARLY EXIT
                            except Exception as ex:
                                print(f"❌ Couldn’t extract from {i_elem}: {ex}")
                        found = True
                        break
                if not found:
                    print("⚠️ Step failed: No valid ₹ element matched after retries")
                    ss = take_screenshot(d, f"step_{i+1}_fallback")
                    # Use the explicit label from user request for fallback
                    suggestion = gpt_fallback(ss, label_from_request)
                    print("🤖 GPT Extracted:", suggestion)
                    return suggestion  # EARLY EXIT

        else:
            print(f"⚠️ Step failed: Unknown action '{action}' in plan. Skipping.")
        i += 1

# === Main ===
def main():
    user_prompt = input("📝 What do you want to do?\n> ").strip()
    d = connect_to_device()
    launch_app(d)
    plan = generate_plan(user_prompt)
    if plan:
        result = execute_plan(d, plan, user_prompt)
        if result is not None:
            print(f"✅ Final Result: {result}")
            return  # Stop further execution after extraction

if __name__ == "__main__":
    main()
