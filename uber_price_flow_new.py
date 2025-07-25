import os
import time
import json
import re
import base64
import subprocess
import openai
from src.filter_ui_elements import extract_ui_elements

# === CONFIG ===
OPENAI_API_KEY = "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"  # TODO: Replace with your OpenAI API key
openai.api_key = OPENAI_API_KEY

UBER_PACKAGE = "com.ubercab"
SCREENSHOT_DIR = "screenshots"
UI_XML_PATH = "view.xml"
UI_JSON_PATH = "ui_elements.json"

PLAN = [
    {
        "name": "launch_uber",
        "description": "Launch the Uber app",
        "prompt": None
    },
    {
        "name": "set_drop_location",
        "description": "Type 'HSR Layout' and select the appropriate suggestion",
        "prompt": (
            "Type 'HSR Layout' in the drop location field if needed.\n"
            "Then tap the most appropriate suggestion (usually the first).\n"
            "Only proceed when the location has been confirmed."
        )
    },
    {
        "name": "find_price",
        "description": "Find the Uber Go price",
        "prompt": "Is the Uber Go price visible? If yes, extract it. If not, what should I do next?"
    }
]

# === ADB HELPERS ===
def run_adb(cmd):
    return subprocess.run(["adb"] + cmd, capture_output=True).stdout

def launch_uber():
    print("\n🚀 Launching Uber app...")
    run_adb(["shell", "monkey", "-p", UBER_PACKAGE, "1"])
    time.sleep(5)

def take_screenshot(step):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"step{step}.png")
    with open(path, "wb") as f:
        f.write(subprocess.check_output(["adb", "exec-out", "screencap", "-p"]))
    return path

def dump_ui_xml():
    run_adb(["shell", "uiautomator", "dump", f"/sdcard/{UI_XML_PATH}"])
    run_adb(["pull", f"/sdcard/{UI_XML_PATH}", UI_XML_PATH])

# === GPT CALL ===
def ask_vlm(prompt, screenshot_path, ui_elements):
    with open(screenshot_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an Android automation agent."},
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": f"""
TASK: Find Uber Go price to HSR Layout.

UI ELEMENTS:
{json.dumps(ui_elements, indent=2)}

QUESTION:
{prompt}

Return ONLY one of the following JSON outputs:

1. If the Uber Go price is visible on the screen, extract the exact visible price and return:
   {{ "goal_achieved": true, "result": "<visible_price>" }}

   ⚠️ Do NOT invent a number. You must extract exactly what is seen visually.

2. If the price is not yet visible, return a tap or type action:
   - {{ "tap": {{ "x": ..., "y": ... }} }}
   - {{ "type": "..." }}

Return only a valid JSON object. Do not include explanations or surrounding text.
"""
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_b64}",
                        "detail": "high"
                    }
                }
            ]}
        ],
        temperature=0.2,
        max_tokens=600
    )
    return response.choices[0].message.content

def parse_reply(reply):
    try:
        return json.loads(re.search(r"\{.*\}", reply, re.DOTALL).group(0))
    except:
        return {}

def input_text(text):
    run_adb(["shell", "input", "text", text.replace(" ", "%s")])
    time.sleep(1)

def perform_click(x, y):
    run_adb(["shell", "input", "tap", str(x), str(y)])
    time.sleep(2)

# === MAIN ===
def main():
    last_action = None

    for step_num, step in enumerate(PLAN, 1):
        print(f"\n=== Step: {step['name']} ===\n{step['description']}")

        if step["name"] == "launch_uber":
            launch_uber()
            continue

        retry_count = 0
        while retry_count < 10:
            screenshot = take_screenshot(step_num)
            dump_ui_xml()
            extract_ui_elements(UI_XML_PATH, UI_JSON_PATH)
            with open(UI_JSON_PATH, "r") as f:
                ui_elements = json.load(f)

            reply = ask_vlm(step["prompt"], screenshot, ui_elements)
            parsed = parse_reply(reply)

            if parsed.get("goal_achieved"):
                print(f"✅ Goal Achieved: {parsed.get('result')}")
                return

            elif "tap" in parsed:
                perform_click(parsed["tap"]["x"], parsed["tap"]["y"])
                if last_action == "typed" and step["name"] == "set_drop_location":
                    print("✅ Confirmed destination after typing.")
                    break
                last_action = "tapped"

            elif "type" in parsed:
                input_text(parsed["type"])
                last_action = "typed"

            else:
                print("❌ LLM reply unclear. Stopping.")
                return

            retry_count += 1

if __name__ == "__main__":
    main()
