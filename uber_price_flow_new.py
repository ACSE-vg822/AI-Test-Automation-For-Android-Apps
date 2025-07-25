import os
import time
import json
import re
import base64
import subprocess
import openai
from src.filter_ui_elements import extract_ui_elements

# === CONFIG ===
from dotenv import load_dotenv
import openai

load_dotenv()  # Load from .env if exists

# Use env variable
openai.api_key = os.getenv("OPENAI_API_KEY")

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
        "description": "Set the destination to Indiranagar by typing it and confirming the suggestion.",
        "prompt": (
            "Is the destination 'Indiranagar' set and ride options screen visible? "
            "If not, tap the input, type 'Indiranagar', and confirm it by tapping the correct suggestion."
        ),
        "force_typing": True
    },
    {
        "name": "find_price",
        "description": "Find the Uber Go price",
        "prompt": "Check if the Uber Go price is visible. If yes, extract it. If not, what should I do next?"
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
def ask_vlm(step, screenshot_path, ui_elements):
    with open(screenshot_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    force_typing_instructions = ""
    if step.get("force_typing"):
        force_typing_instructions = """
IMPORTANT: You MUST type the destination (e.g., 'Indiranagar') manually in the input box. 
Do NOT assume it is already selected even if it appears in suggestions or recent locations.
First tap the destination input, then type, then tap the correct result.
"""

    system_prompt = f"""
You are an Android automation agent. Your job is to complete a mobile UI task based on a screenshot and its XML element hierarchy.

### Task
{step['description']}

{force_typing_instructions}

Only return one of the following:
- {{ "goal_achieved": true, "result": "..." }}
- {{ "tap": {{ "x": ..., "y": ... }} }}
- {{ "type": "..." }}
"""

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"UI ELEMENTS:\n{json.dumps(ui_elements, indent=2)}\n\nQUESTION:\n{step['prompt']}"
                    },
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

def is_edittext_focused(ui_elements):
    for el in ui_elements:
        if el["class"] == "android.widget.EditText" and el.get("focused"):
            return True
    return False

def get_topmost_suggestion(ui_elements):
    # Find the topmost actionable element below the EditText (likely a suggestion)
    suggestions = [el for el in ui_elements if el["clickable"] and el["center"]["y"] > 700]
    if suggestions:
        return min(suggestions, key=lambda el: el["center"]["y"])
    return None

# === MAIN ===
def main():
    for step_num, step in enumerate(PLAN, 1):
        print(f"\n=== Step: {step['name']} ===\n{step['description']}")

        if step["name"] == "launch_uber":
            launch_uber()
            continue

        retries = 0
        typed = False
        while retries < 6:
            screenshot = take_screenshot(step_num)
            dump_ui_xml()
            extract_ui_elements(UI_XML_PATH, UI_JSON_PATH)
            with open(UI_JSON_PATH, "r") as f:
                ui_elements = json.load(f)

            # Special handling for set_drop_location
            if step["name"] == "set_drop_location":
                if not typed:
                    # Tap the EditText if not focused
                    edittext = next((el for el in ui_elements if el["class"] == "android.widget.EditText"), None)
                    if edittext and not edittext.get("focused"):
                        print(f"👉 Tapping EditText at ({edittext['center']['x']}, {edittext['center']['y']})")
                        perform_click(edittext["center"]["x"], edittext["center"]["y"])
                        retries += 1
                        continue
                    elif edittext and edittext.get("focused"):
                        print("⌨️ Typing: Indiranagar")
                        input_text("Indiranagar")
                        typed = True
                        retries += 1
                        continue
                else:
                    # After typing, tap the topmost suggestion
                    suggestion = get_topmost_suggestion(ui_elements)
                    if suggestion:
                        print(f"👉 Tapping top suggestion at ({suggestion['center']['x']}, {suggestion['center']['y']})")
                        perform_click(suggestion["center"]["x"], suggestion["center"]["y"])
                        # After tapping, let the LLM check if goal is achieved
                        typed = False  # Reset for next retry if needed
                    else:
                        print("❌ No suggestion found to tap.")
                        return

            else:
                reply = ask_vlm(step, screenshot, ui_elements)
                parsed = parse_reply(reply)

                if parsed.get("goal_achieved"):
                    print(f"✅ Goal Achieved: {parsed.get('result')}")
                    break
                elif "tap" in parsed:
                    print(f"👉 Tapping at ({parsed['tap']['x']}, {parsed['tap']['y']})")
                    perform_click(parsed["tap"]["x"], parsed["tap"]["y"])
                elif "type" in parsed:
                    print(f"⌨️ Typing: {parsed['type']}")
                    input_text(parsed["type"])
                else:
                    print("❌ Unclear or invalid response. Exiting.")
                    return

            retries += 1

if __name__ == "__main__":
    main()