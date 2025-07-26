import uiautomator2 as u2
import time
import os
import base64
import json
import re
from datetime import datetime
from dotenv import load_dotenv
import openai
import logging
from source.logger import setup_logger

# === Setup ===
load_dotenv(override=True)
openai.api_key = os.getenv("OPENAI_API_KEY")
UBER_PACKAGE = "com.ubercab"
SCREENSHOT_DIR = "screenshots"

# Setup logging
logger = setup_logger()

# === Device Connection ===
def connect_to_device():
    logger.info("🔌 Connecting to device...")
    return u2.connect()

def launch_app(d):
    logger.info("🚀 Launching Uber...")
    d.app_start(UBER_PACKAGE)
    time.sleep(5)

# === Screenshot + GPT fallback ===
def take_screenshot(d, label="fallback"):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S")
    path = os.path.join(SCREENSHOT_DIR, f"{label}_{timestamp}.png")
    d.screenshot(path)
    logger.info(f"📸 Screenshot saved: {path}")
    logger.info(f"🖼️ Screenshot size: {os.path.getsize(path) / 1024:.2f} KB")
    return path

def gpt_fallback(image_path, user_request):
    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")

    # Read app context for better understanding
    app_context = ""
    try:
        with open("app_context/uber.txt", "r", encoding="utf-8") as f:
            app_context = f.read()
    except Exception as e:
        logger.warning(f"⚠️ Could not read uber.txt for fallback: {e}")

    # Use a more specific prompt with app context
    prompt = f"""This is a screenshot of the mobile app. The user request is: '{user_request}'.

App Context:
{app_context}

Extract the most relevant information from the screenshot to fulfill the user's request. 
Look for prices, times, availability or any information that matches what the user is asking for.

Only reply with the extracted value. Do not explain or add any formatting."""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a mobile automation assistant. Extract only the requested information from the screenshot. Return only the value, no explanations."
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
        return raw
    except Exception as e:
        logger.error(f"❌ GPT fallback failed: {e}")
        return None

def gpt_fallback_action(image_path, user_request, failed_step=None):
    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")
    
    # Read app context for better understanding
    app_context = ""
    try:
        with open("app_context/uber.txt", "r", encoding="utf-8") as f:
            app_context = f.read()
    except Exception as e:
        logger.warning(f"⚠️ Could not read uber.txt for fallback: {e}")
    
    # Build context about the failure
    failure_context = ""
    if failed_step:
        failure_context = f"\nThe automation failed at step: {failed_step}"
    
    prompt = f"""This is a screenshot of the mobile app. The automation failed to find or interact with the expected element.

User Request: '{user_request}'
{failure_context}

App Context:
{app_context}

Based on the screenshot and app context, what is the next UI action needed to progress toward the user's goal?

You must respond with a SINGLE JSON object in this exact format. Following is just an exmaple, your answer should be in accordance with the query and app context:
{{ "action": "click", "target": "text='Button Text'" }}
OR
{{ "action": "click", "target": "xpath=//android.widget.TextView[contains(@text, 'Partial Text')]" }}
OR
{{ "action": "type", "value": "text to type" }}
OR
{{ "action": "extract", "target": "xpath=//android.widget.TextView[contains(@text, '$')]" }}

Valid actions: "click", "type", "wait", "extract"
Valid targets: "text='exact text'", "xpath=//path/to/element"
For typing: use "value" field instead of "target"
For extract: use "target" field with xpath to find elements to extract text from

Only return the JSON object - no explanations or markdown formatting."""
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a mobile automation assistant. You must return ONLY a valid JSON object with action and target/value fields. No explanations."
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
            max_tokens=200,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        
        # Clean up response
        if raw.startswith("```"):
            raw = re.sub(r"```(json)?", "", raw).strip("`").strip()
        
        # Parse and validate JSON
        result = json.loads(raw)
        
        # Validate required fields
        if "action" not in result:
            logger.error("❌ GPT fallback action missing 'action' field")
            return None
        
        if result["action"] == "click" and "target" not in result:
            logger.error("❌ GPT fallback action missing 'target' field for click action")
            return None
        
        if result["action"] == "type" and "value" not in result:
            logger.error("❌ GPT fallback action missing 'value' field for type action")
            return None
        
        if result["action"] == "extract" and "target" not in result:
            logger.error("❌ GPT fallback action missing 'target' field for extract action")
            return None
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ GPT fallback action JSON parsing failed: {e}")
        logger.error(f"Raw response: {raw}")
        return None
    except Exception as e:
        logger.error(f"❌ GPT fallback action failed: {e}")
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
    logger.info(f"🧠 Generating plan for: '{user_request}'")
    # Read UI text from uber.txt if available
    ui_text = ""
    try:
        with open("app_context/uber.txt", "r", encoding="utf-8") as f:
            ui_text = f.read()
    except Exception as e:
        logger.warning(f"⚠️ Could not read uber.txt: {e}")
    system_prompt = f"""
You are a mobile automation planner. The following is a basic flow overview of how major functions work in the app:
{ui_text}

ALWAYS generate a step-by-step plan for navigating the app using uiautomator2 to achieve what the user is asking for.
If you can't complete the plan, generate a fallback plan that will help the user to complete the task or give them information closest to what they are asking for.
BUT **ALWAYS** GENERATE A PLAN.

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
    logger.info("🪵 Raw LLM output:\n" + raw)

    try:
        # Auto-fix if wrapped in code block
        if raw.startswith("```"):
            raw = re.sub(r"```(json)?", "", raw).strip("`")
        return json.loads(raw)
    except Exception as e:
        logger.error(f"❌ Plan parsing failed: {e}")
        return []


# === Main Executor ===
def execute_plan(d, plan, user_request):
    label_from_request = extract_label_from_request(user_request)
    i = 0
    failed_nav_fallbacks = 0  # Track consecutive failed click/type fallbacks
    while i < len(plan):
        step = plan[i]
        logger.info(f"\n➡️ Step {i+1}: {step}")
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
                logger.warning("⚠️ Step failed: Click failed: Target not found")
                failed_nav_fallbacks += 1
                if failed_nav_fallbacks >= 2:
                    logger.info("🔄 Too many navigation failures, switching to extraction fallback!")
                    ss = take_screenshot(d, f"step_{i+1}_extract_fallback")
                    suggestion = gpt_fallback(ss, user_request)
                    logger.info(f"🤖 GPT Extracted: {suggestion}")
                    if suggestion:
                        logger.info(f"✅ Final Result: {suggestion}")
                        return suggestion  # EARLY EXIT
                    # If extraction fails, continue as before
                else:
                    ss = take_screenshot(d, f"step_{i+1}_click_fallback")
                    suggestion = gpt_fallback_action(ss, user_request, f"Step {i+1}: {step}")
                    logger.info(f"🤖 GPT Fallback Suggestion: {suggestion}")
                    if suggestion and isinstance(suggestion, dict):
                        plan.insert(i+1, suggestion)  # Try the suggestion next
                    else:
                        logger.warning("⚠️ No valid fallback action from GPT. Skipping.")
                i += 1
                continue
            else:
                failed_nav_fallbacks = 0  # Reset on success

        elif action == "type":
            try:
                d.send_keys(value, clear=True)
                failed_nav_fallbacks = 0  # Reset on success
            except Exception as e:
                logger.warning(f"⚠️ Step failed: Type failed: {e}")
                failed_nav_fallbacks += 1
                if failed_nav_fallbacks >= 2:
                    logger.info("🔄 Too many navigation failures, switching to extraction fallback!")
                    ss = take_screenshot(d, f"step_{i+1}_extract_fallback")
                    suggestion = gpt_fallback(ss, user_request)
                    logger.info(f"🤖 GPT Extracted: {suggestion}")
                    if suggestion:
                        logger.info(f"✅ Final Result: {suggestion}")
                        return suggestion  # EARLY EXIT
                else:
                    ss = take_screenshot(d, f"step_{i+1}_type_fallback")
                    suggestion = gpt_fallback_action(ss, user_request, f"Step {i+1}: {step}")
                    logger.info(f"🤖 GPT Fallback Suggestion: {suggestion}")
                    if suggestion and isinstance(suggestion, dict):
                        plan.insert(i+1, suggestion)  # Try the suggestion next
                    else:
                        logger.warning("⚠️ No valid fallback action from GPT. Skipping.")
                i += 1
                continue

        elif action == "wait":
            xpath_val = target.replace("xpath=", "")
            if not d.xpath(xpath_val).wait(timeout=10):
                logger.warning("⚠️ Step failed: Wait failed: XPath not visible")
                # Optionally add fallback here

        elif action == "extract":
            xpath_val = target.replace("xpath=", "")
            try:
                elems = d.xpath(xpath_val).all()
                logger.info(f" Found {len(elems)} matching elements while searching for: '{user_request}'")
                for i_elem, e in enumerate(elems):
                    try:
                        txt = e.get_text()
                        logger.info(f"[{i_elem}] → {txt}")
                        if label_from_request and label_from_request in txt:
                            logger.info(f"✅ Extracted Value: {txt}")
                            return txt  # EARLY EXIT
                        if not label_from_request and ("Auto" in txt or i_elem == 1):
                            logger.info(f"✅ Extracted Value: {txt}")
                            return txt  # EARLY EXIT
                    except Exception as ex:
                        logger.error(f"❌ Couldn't extract from {i_elem}: {ex}")
                raise Exception("No valid value matched")
            except Exception as e:
                # Retry logic: wait up to 15s for any value to appear
                logger.info(f"⏳ Waiting for the relevant value for: '{user_request}' to appear...")
                found = False
                for retry in range(7):  # 7*2s = 14s
                    time.sleep(2)
                    elems = d.xpath(xpath_val).all()
                    if elems:
                        logger.info(f"🔍 Retry {retry+1}: Found {len(elems)} matching elements while searching for: '{user_request}'")
                        for i_elem, e in enumerate(elems):
                            try:
                                txt = e.get_text()
                                logger.info(f"[{i_elem}] → {txt}")
                                if label_from_request and label_from_request in txt:
                                    logger.info(f"✅ Extracted Value: {txt}")
                                    return txt  # EARLY EXIT
                                if not label_from_request and ("Auto" in txt or i_elem == 1):
                                    logger.info(f"✅ Extracted Value: {txt}")
                                    return txt  # EARLY EXIT
                            except Exception as ex:
                                logger.error(f"❌ Couldn't extract from {i_elem}: {ex}")
                        found = True
                        break
                if not found:
                    logger.warning(f"⚠️ Step failed: No valid value matched for: '{user_request}' after retries")
                    ss = take_screenshot(d, f"step_{i+1}_fallback")
                    # Use the explicit label from user request for fallback
                    suggestion = gpt_fallback(ss, user_request)
                    logger.info(f"🤖 GPT Extracted: {suggestion}")
                    return suggestion  # EARLY EXIT

        else:
            logger.warning(f"⚠️ Step failed: Unknown action '{action}' in plan. Skipping.")
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
            logger.info(f"✅ Final Result: {result}")
            return  # Stop further execution after extraction

if __name__ == "__main__":
    main()
