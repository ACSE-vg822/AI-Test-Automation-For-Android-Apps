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

# === Smart fallback helper ===
def smart_fallback(d, image_path, step, user_request):
    ui_elements = []
    for el in d.xpath("//*").all():
        try:
            info = el.info
            if info.get("clickable") or info.get("enabled"):
                ui_elements.append({
                    "text": info.get("text", ""),
                    "class": info.get("className", ""),
                    "resource": info.get("resourceName", ""),
                    "bounds": info.get("bounds", "")
                })
        except Exception:
            pass

    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")

    prompt = f"""
You're automating an Android app using uiautomator2.

User's request: "{user_request}"
Step that failed: {json.dumps(step)}

Here are all actionable UI elements:
{json.dumps(ui_elements, indent=2)}

Suggest a single Python command like:
d(text="Auto").click()
"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                { "role": "system", "content": "You are an Android UI automation assistant." },
                { "role": "user", "content": [
                    { "type": "text", "text": prompt },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_img}",
                            "detail": "high"
                        }
                    }
                ]}
            ],
            max_tokens=100,
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ smart_fallback GPT call failed: {e}")
        return None

# === Plan generation ===
def generate_plan(user_request):
    print(f"🧠 Generating plan for: '{user_request}'")
    system_prompt = """
You are a mobile automation planner. Generate a step-by-step plan for automating the Uber app using uiautomator2.

Each step should be:
- Directly mappable to uiautomator2 methods
- Written in JSON format like:
[
  { "action": "click", "target": "text='Enter your destination'" },
  { "action": "type", "value": "Indiranagar" },
  { "action": "click", "target": "xpath=//android.widget.TextView[contains(@text, 'Indiranagar')]" },
  { "action": "wait", "target": "xpath=//android.widget.TextView[contains(@text, 'Auto')]" },
  { "action": "extract", "target": "xpath=(//android.widget.TextView[contains(@text, '₹')])[2]" }
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
    for i, step in enumerate(plan):
        print(f"\n➡️ Step {i+1}: {step}")
        action = step.get("action")
        target = step.get("target")
        value = step.get("value")

        if action == "click":
            success = False
            if target.startswith("text="):
                text_val = target.replace("text=", "").strip("'\"")
                if d(text=text_val).exists(timeout=5):
                    d(text=text_val).click()
                    success = True
            elif target.startswith("xpath="):
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
                # Optionally add fallback here

        elif action == "type":
            d.send_keys(value, clear=True)

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
                for i, e in enumerate(elems):
                    try:
                        txt = e.get_text()
                        print(f"[{i}] → {txt}")
                        if "Auto" in txt or i == 1:
                            print(f"✅ Extracted Value: {txt}")
                            return txt
                    except Exception as ex:
                        print(f"❌ Couldn’t extract from {i}: {ex}")
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
                        for i, e in enumerate(elems):
                            try:
                                txt = e.get_text()
                                print(f"[{i}] → {txt}")
                                if "Auto" in txt or i == 1:
                                    print(f"✅ Extracted Value: {txt}")
                                    return txt
                            except Exception as ex:
                                print(f"❌ Couldn’t extract from {i}: {ex}")
                        found = True
                        break
                if not found:
                    print("⚠️ Step failed: No valid ₹ element matched after retries")
                    ss = take_screenshot(d, f"step_{i+1}_fallback")
                    # Try extracting the label from the step or user_request for reusability
                    label = None
                    if "Auto" in json.dumps(step) or "Auto" in user_request:
                        label = "Auto"
                    elif "Uber Go" in json.dumps(step) or "Uber Go" in user_request:
                        label = "Uber Go"
                    suggestion = gpt_fallback(ss, label)
                    print("🤖 GPT Extracted:", suggestion)
                    return suggestion

        else:
            print("smart fallback wohooo")
            suggestion = smart_fallback(d, ss, step, user_request)
            print("🤖 GPT Smart Command:\n", suggestion)
            if suggestion and suggestion.strip().startswith("d("):
                try:
                    exec(suggestion, {"d": d})
                    continue
                except Exception as ex:
                    print(f"❌ Failed to run GPT suggestion: {ex}")
                    break

# === Main ===
def main():
    user_prompt = input("📝 What do you want to do?\n> ").strip()
    d = connect_to_device()
    launch_app(d)
    plan = generate_plan(user_prompt)
    if plan:
        execute_plan(d, plan, user_prompt)

if __name__ == "__main__":
    main()
