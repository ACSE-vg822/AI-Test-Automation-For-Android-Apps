import subprocess
import time
import json
import os
import openai
import re

# === CONFIGURATION ===
from dotenv import load_dotenv
import openai

load_dotenv()  # Load from .env if exists

# Use env variable
openai.api_key = os.getenv("OPENAI_API_KEY")


UBER_PACKAGE = "com.ubercab"
SCREENSHOT_DIR = "screenshots"
UI_XML_PATH = "view.xml"
UI_JSON_PATH = "ui_elements.json"

# === PLAN DEFINITION ===
PLAN = [
    {
        "name": "launch_uber",
        "description": "Launch the Uber app",
        "action": "launch_uber",
        "prompt": None,
        "stop_condition": None
    },
    {
        "name": "set_drop_location",
        "description": "Set drop location to 'Indiranagar'",
        "action": "interact",
        "prompt": "What should I click to set drop location to 'Indiranagar'? If typing is needed, instruct to type it.",
        "stop_condition": lambda reply: "indiranagar" in reply.lower() and ("typed" in reply.lower() or "entered" in reply.lower() or "input" in reply.lower())
    },
    {
        "name": "select_drop_suggestion",
        "description": "Select the first suggestion for 'Indiranagar' after typing.",
        "action": "interact",
        "prompt": "What should I click to select the first suggestion for 'Indiranagar' as the drop location? Respond with the center coordinates (x, y) of the correct suggestion.",
        "stop_condition": lambda reply: "selected" in reply.lower() or "done" in reply.lower() or "drop location set" in reply.lower()
    },
    {
        "name": "find_uber_go_price",
        "description": "Find the price for Uber Go",
        "action": "interact",
        "prompt": "What should I click to find the Uber Go price? If the price is visible, reply with the Uber Go price and say DONE.",
        "stop_condition": lambda reply: "done" in reply.lower() or "uber go price" in reply.lower()
    }
]

# === HELPER FUNCTIONS ===
def run_adb(cmd):
    result = subprocess.run(["adb"] + cmd, capture_output=True)
    if result.returncode != 0:
        print(f"ADB error: {result.stderr.decode()}")
    return result.stdout

def launch_uber():
    print("\n🚀 Launching Uber app...")
    run_adb(["shell", "monkey", "-p", UBER_PACKAGE, "1"])
    time.sleep(5)  # Wait for app to launch

def take_screenshot(step):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    local_path = os.path.join(SCREENSHOT_DIR, f"uber_step{step}.png")
    with open(local_path, "wb") as f:
        f.write(subprocess.check_output(["adb", "exec-out", "screencap", "-p"]))
    print(f"📸 Screenshot saved: {local_path}")
    return local_path

def dump_ui_xml():
    run_adb(["shell", "uiautomator", "dump", f"/sdcard/{UI_XML_PATH}"])
    run_adb(["pull", f"/sdcard/{UI_XML_PATH}", UI_XML_PATH])
    print(f"📝 UI XML dumped: {UI_XML_PATH}")

def parse_ui_elements():
    subprocess.run(["python", "src/filter_ui_elements.py", UI_XML_PATH, UI_JSON_PATH])
    with open(UI_JSON_PATH, "r", encoding="utf-8") as f:
        elements = json.load(f)
    print(f"🔍 Parsed {len(elements)} actionable UI elements.")
    return elements

def ask_gpt4o(screenshot_path, ui_elements, prompt):
    # TODO: Refine the prompt for best results
    full_prompt = f"""
You are an expert Android UI automation agent. Here is the parsed UI element list (JSON):
{json.dumps(ui_elements, indent=2)}

{prompt}
Respond with the center coordinates (x, y) and a short reason. If the goal is achieved, reply with the Uber Go price and say DONE.
"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful UI automation assistant."},
            {"role": "user", "content": full_prompt}
        ]
    )
    reply = response.choices[0].message.content
    print(f"🤖 GPT-4o says: {reply}")
    return reply

def extract_coordinates(gpt_reply):
    match = re.search(r"\((\d+),\s*(\d+)\)", gpt_reply)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r'"x"\s*:\s*(\d+)[,\s]+"y"\s*:\s*(\d+)', gpt_reply)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None

def extract_text_to_type(gpt_reply):
    # Look for instructions like: type 'Indiranagar' or type "Indiranagar"
    match = re.search(r"type ['\"]([^'\"]+)['\"]", gpt_reply, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def input_text(text):
    print(f"⌨️  Typing text: {text}")
    # ADB input text requires spaces to be replaced with %s
    safe_text = text.replace(' ', '%s')
    run_adb(["shell", "input", "text", safe_text])
    time.sleep(2)

def perform_click(x, y):
    print(f"👉 Clicking at ({x}, {y})")
    run_adb(["shell", "input", "tap", str(x), str(y)])
    time.sleep(2)  # Wait for UI to update

def main():
    step_counter = 1
    for step in PLAN:
        print(f"\n=== Step: {step['name']} ===\n{step['description']}")
        if step["action"] == "launch_uber":
            launch_uber()
            continue
        while True:
            screenshot_path = take_screenshot(step_counter)
            dump_ui_xml()
            ui_elements = parse_ui_elements()
            gpt_reply = ask_gpt4o(screenshot_path, ui_elements, step["prompt"])
            # Check stop condition
            stop_condition = step.get("stop_condition")
            if stop_condition and stop_condition(gpt_reply):
                print(f"\n🎉 Step '{step['name']}' complete: {gpt_reply}")
                break
            # Prioritize typing if present
            text_to_type = extract_text_to_type(gpt_reply)
            if text_to_type:
                input_text(text_to_type)
            coords = extract_coordinates(gpt_reply)
            if coords:
                perform_click(*coords)
            elif not text_to_type:
                print("❌ Could not extract coordinates or text to type from GPT-4o reply. Stopping.")
                return
            step_counter += 1

if __name__ == "__main__":
    main() 