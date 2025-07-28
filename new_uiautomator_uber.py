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
from source.logger import logger

# === Setup ===
load_dotenv(override=True)
openai.api_key = os.getenv("OPENAI_API_KEY")
UBER_PACKAGE = "com.ubercab"
ZOMATO_PACKAGE = "com.application.zomato"
SCREENSHOT_DIR = "screenshots"

# === Configuration ===
# USE_UI_ELEMENTS = True  # Flag to control UI elements extraction and usage

# === App Selection ===
APP_CONTEXT_FILES = {
    "uber": (UBER_PACKAGE, "app_context/uber.txt"),
    "zomato": (ZOMATO_PACKAGE, "app_context/zomato.txt")
}

# === Memory State ===
# Store the generated plan for logging and modification
current_plan = None

# Setup logging
# logger is already imported from source.logger

# === Device Connection ===
def connect_to_device():
    logger.info("🔌 Connecting to device...")
    return u2.connect()

def launch_app(d, package_name):
    logger.info(f"🚀 Launching {package_name}...")
    d.app_start(package_name)
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

def gpt_fallback(d, user_request, app_context_file, initial_screenshot_path=None):
    """
    GPT fallback with scrolling loop for extraction
    Args:
        d: uiautomator2 device object
        user_request: user's request for extraction
        app_context_file: path to app context file
        initial_screenshot_path: optional initial screenshot path (if already taken)
    """
    # Read app context for better understanding
    app_context = ""
    try:
        with open(app_context_file, "r", encoding="utf-8") as f:
            app_context = f.read()
    except Exception as e:
        logger.warning(f"⚠️ Could not read {app_context_file} for fallback: {e}")

    # Use a more specific prompt with app context
    prompt = f"""This is a screenshot of the mobile app. The user request is: '{user_request}'.\n\nApp Context:\n{app_context}\n\nExtract the most relevant information from the screenshot to fulfill the user's request. \nLook for prices, times, availability or any information that matches what the user is asking for.\n\nOnly reply with the extracted value. And add concise explanation of your answer."""

    # Scrolling loop: 5 turns maximum
    for scroll_turn in range(5):
        logger.info(f"🔄 GPT Fallback Scroll Turn {scroll_turn + 1}/5")
        
        # Take screenshot for current scroll position
        if scroll_turn == 0 and initial_screenshot_path:
            # Use the initial screenshot if provided
            image_path = initial_screenshot_path
        else:
            # Take new screenshot
            image_path = take_screenshot(d, f"gpt_fallback_scroll_{scroll_turn}")
        
        # Process screenshot with GPT
        try:
            with open(image_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")

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
            
            # Check if we got a meaningful result
            if raw and raw.lower() not in ["none", "not found", "no information", "n/a", ""]:
                logger.info(f"✅ GPT found answer on scroll turn {scroll_turn + 1}: {raw}")
                return raw
            
            logger.info(f"⚠️ No meaningful answer found on scroll turn {scroll_turn + 1}")
            
        except Exception as e:
            logger.error(f"❌ GPT fallback failed on scroll turn {scroll_turn + 1}: {e}")
        
        # Scroll down for next iteration (except on last turn)
        if scroll_turn < 4:  # Don't scroll on the last turn
            try:
                # Get screen dimensions for scrolling
                screen_width = d.window_size()[0]
                screen_height = d.window_size()[1]
                
                # Scroll from middle to top (swipe up)
                start_x = screen_width // 2
                start_y = int(screen_height * 0.8)  # 80% down
                end_x = screen_width // 2
                end_y = int(screen_height * 0.2)    # 20% down
                
                logger.info(f"📱 Scrolling: ({start_x}, {start_y}) → ({end_x}, {end_y})")
                d.swipe(start_x, start_y, end_x, end_y, duration=0.5)
                time.sleep(1)  # Wait for scroll animation
                
            except Exception as e:
                logger.error(f"❌ Scrolling failed on turn {scroll_turn + 1}: {e}")
                break
    
    logger.warning("⚠️ No answer found after 5 scroll attempts")
    return None

def gpt_fallback_action(image_path, user_request, app_context_file, failed_step=None, ui_elements=None, use_ui_elements=True):
    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")
    
    # Read app context for better understanding
    app_context = ""
    try:
        with open(app_context_file, "r", encoding="utf-8") as f:
            app_context = f.read()
    except Exception as e:
        logger.warning(f"⚠️ Could not read {app_context_file} for fallback: {e}")
    
    # Add UI elements context if available
    ui_elements_context = ""
    if use_ui_elements and ui_elements:
        ui_elements_context = f"\n\nCurrent UI Elements Available:\n{json.dumps(ui_elements, indent=2)}"
        logger.info(f"📱 Using {len(ui_elements)} UI elements for fallback action")
    
    # Build context about the failure
    failure_context = ""
    if failed_step:
        failure_context = f"\nThe automation failed at step: {failed_step}"
    
    prompt = f"""This is a screenshot of the mobile app. The automation failed to find or interact with the expected element.

User Request: '{user_request}'{failure_context}

App Context:
{app_context}{ui_elements_context}

Based on the screenshot and app context, what is the next UI action needed to progress toward the user's goal?

You must respond with a SINGLE JSON object in this exact format. Following is just an example, your answer should be in accordance with the query and app context:

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

# === Plan generation ===
def parse_plan(plan):
    """Parse plan and remove wait actions that come right before extract actions"""
    if not plan:
        return plan
    
    parsed_plan = []
    i = 0
    
    while i < len(plan):
        current_step = plan[i]
        
        # Check if current step is wait and next step is extract
        if (i < len(plan) - 1 and 
            current_step.get("action") == "wait" and 
            plan[i + 1].get("action") == "extract"):
            
            logger.info(f"🗑️ Removing wait action before extract: {current_step}")
            # Skip the wait action, keep the extract action
            i += 1
            parsed_plan.append(plan[i])
        else:
            parsed_plan.append(current_step)
        
        i += 1
    
    return parsed_plan

def generate_plan(user_request, app_context_file, ui_elements=None, use_ui_elements=True):
    logger.info(f"🧠 Generating plan for: '{user_request}'")
    # Read UI text from app context if available
    ui_text = ""
    try:
        with open(app_context_file, "r", encoding="utf-8") as f:
            ui_text = f.read()
    except Exception as e:
        logger.warning(f"⚠️ Could not read {app_context_file}: {e}")
    
    # Add UI elements context if available
    ui_elements_context = ""
    if use_ui_elements and ui_elements:
        ui_elements_context = f"\n\nCurrent UI Elements Available:\n{json.dumps(ui_elements, indent=2)}"
        logger.info(f"📱 Using {len(ui_elements)} UI elements for planning")
    
    system_prompt = f"""
You are a mobile automation planner. The following is a basic flow overview of how major functions work in the app:
{ui_text}{ui_elements_context}

ALWAYS generate a step-by-step plan for navigating the app using uiautomator2 to achieve what the user is asking for.
If you can't complete the plan, generate a fallback plan that will help the user to complete the task or give them information closest to what they are asking for.
BUT **ALWAYS** GENERATE A PLAN.

Each step should be:
- Directly mappable to uiautomator2 methods
- Written in JSON format like:
[
  {{ "action": "click", "target": "xpath=//android.widget.TextView[contains(@text, 'Search')]" }},
  {{ "action": "type", "value": "Wireless Headphones" }},
  {{ "action": "click", "target": "xpath=//android.widget.TextView[contains(@text, 'Wireless Headphones')]" }},
  {{ "action": "wait", "target": "xpath=//android.widget.TextView[contains(@text, '$')]" }},
  {{ "action": "extract", "query": "find the price of Wireless Headphones" }}
]

IMPORTANT: For extraction steps, use "query" field with natural language instead of "target" with XPath. The extraction will use screenshot analysis with scrolling to find the information.

Valid actions: "click", "type", "wait", "extract"
For extract: use "query" field with natural language description of what to find

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

# === Action Handlers ===
def handle_click_action(d, target):
    """Handle click action with text and xpath support"""
    if not target:
        return False
    
    if target.startswith("text="):
        text_val = target.replace("text=", "").strip("'\"")
        if d(text=text_val).exists(timeout=5):
            d(text=text_val).click()
            return True
    
    elif target.startswith("xpath="):
        xpath_val = target.replace("xpath=", "")
        if d.xpath(xpath_val).exists:
            d.xpath(xpath_val).click()
            return True
        else:
            # Try fallback with text extraction from xpath
            match = re.search(r"'([^']+)'", xpath_val)
            if match:
                fallback_text = match.group(1)
                if d(text=fallback_text).exists(timeout=5):
                    d(text=fallback_text).click()
                    return True
    
    return False

def handle_type_action(d, value):
    """Handle type action"""
    try:
        d.send_keys(value, clear=True)
        return True
    except Exception as e:
        logger.warning(f"⚠️ Type action failed: {e}")
        return False

def handle_wait_action(d, target):
    """Handle wait action"""
    if not target or not target.startswith("xpath="):
        return False
    
    xpath_val = target.replace("xpath=", "")
    return d.xpath(xpath_val).wait(timeout=10)

def handle_extract_action(d, query, user_request, step_index, app_context_file):
    """Handle extract action - always screenshot-based with scrolling"""
    logger.info(f"📸 Starting screenshot-based extraction")
    logger.info(f"   User request: '{user_request}'")
    logger.info(f"   Step query: '{query}'")
    
    # Combine user request and step query for better context
    combined_query = f"User wants: {user_request}. Specifically looking for: {query}"
    
    # Wait 2 seconds before first screenshot to let app render
    logger.info("⏳ Waiting 5 seconds before first screenshot...")
    time.sleep(5)
    
    # Take initial screenshot and use GPT fallback with scrolling
    ss = take_screenshot(d, f"step_{step_index+1}_extract")
    result = gpt_fallback(d, combined_query, app_context_file, ss)
    
    if result:
        logger.info(f"✅ Extracted Value: {result}")
        return result
    else:
        logger.warning(f"⚠️ No answer found for: '{combined_query}' after scrolling")
        return None

def handle_fallback(d, step, step_index, user_request, app_context_file, ui_elements, use_ui_elements, failed_nav_fallbacks):
    """Handle fallback logic for failed actions"""
    if failed_nav_fallbacks >= 2:
        # Switch to extraction fallback after too many navigation failures
        logger.info("🔄 Too many navigation failures, switching to extraction fallback!")
        ss = take_screenshot(d, f"step_{step_index+1}_extract_fallback")
        suggestion = gpt_fallback(d, user_request, app_context_file, ss)
        logger.info(f"🤖 GPT Extracted: {suggestion}")
        if suggestion:
            logger.info(f"✅ Final Result: {suggestion}")
            return suggestion, True  # Return result and indicate early exit
    else:
        # Try action fallback
        ss = take_screenshot(d, f"step_{step_index+1}_{step.get('action', 'unknown')}_fallback")
        
        # Fresh UI extraction for fallback
        fresh_ui_elements = None
        if use_ui_elements:
            from source.filter_ui_elements import extract_ui_elements
            xml_str = d.dump_hierarchy(compressed=True)
            fresh_ui_elements = extract_ui_elements(xml_str)
        
        suggestion = gpt_fallback_action(
            ss, user_request, app_context_file, 
            f"Step {step_index+1}: {step}", fresh_ui_elements, use_ui_elements
        )
        logger.info(f"🤖 GPT Fallback Suggestion: {suggestion}")
        
        if suggestion and isinstance(suggestion, dict):
            return suggestion, False  # Return suggestion to insert into plan
        else:
            logger.warning("⚠️ No valid fallback action from GPT. Skipping.")
    
    return None, False

def get_fresh_ui_elements(d, use_ui_elements):
    """Get fresh UI elements if enabled"""
    if not use_ui_elements:
        return None
    
    from source.filter_ui_elements import extract_ui_elements
    xml_str = d.dump_hierarchy(compressed=True)
    return extract_ui_elements(xml_str)

# === Main Executor ===
def execute_plan(d, plan, user_request, app_context_file, ui_elements=None, use_ui_elements=True):
    """Execute the automation plan with fallback handling"""
    i = 0
    failed_nav_fallbacks = 0  # Track consecutive failed click/type fallbacks
    
    while i < len(plan):
        step = plan[i]
        logger.info(f"\n➡️ Step {i+1}: {step}")
        
        action = step.get("action")
        target = step.get("target")
        value = step.get("value")
        
        success = False
        
        # Handle different action types
        if action == "click":
            success = handle_click_action(d, target)
            
        elif action == "type":
            success = handle_type_action(d, value)
            
        elif action == "wait":
            success = handle_wait_action(d, target)
            if not success:
                logger.warning("⚠️ Step failed: Wait failed: XPath not visible")
            
        elif action == "extract":
            query = step.get("query")
            result = handle_extract_action(d, query, user_request, i, app_context_file)
            if result is not None:
                return result  # Early exit with extracted value
            success = True  # Consider extract as "successful" even if it falls back to GPT
            
        else:
            logger.warning(f"⚠️ Step failed: Unknown action '{action}' in plan. Skipping.")
            success = True  # Skip unknown actions without counting as failure
        
        # Handle failures with fallback logic
        if not success:
            failed_nav_fallbacks += 1
            fallback_result, should_exit = handle_fallback(
                d, step, i, user_request, app_context_file, 
                ui_elements, use_ui_elements, failed_nav_fallbacks
            )
            
            if should_exit:
                return fallback_result  # Early exit
            
            if fallback_result:
                plan.insert(i+1, fallback_result)  # Insert suggestion for next iteration
            
            i += 1
            continue
        else:
            failed_nav_fallbacks = 0  # Reset on success
        
        i += 1
    
    return None  # No result found

# === Main ===
def main():
    from source.filter_ui_elements import extract_ui_elements
    app_choice = ""
    while app_choice not in APP_CONTEXT_FILES:
        app_choice = input("Which app do you want to automate? (uber/zomato): ").strip().lower()
        if app_choice not in APP_CONTEXT_FILES:
            print("Invalid choice. Please enter 'uber' or 'zomato'.")
    package_name, app_context_file = APP_CONTEXT_FILES[app_choice]
    # Set USE_UI_ELEMENTS per app
    if app_choice == "zomato":
        use_ui_elements = True
    else:
        use_ui_elements = False
    user_prompt = input(f"📝 What do you want to do in {app_choice.title()}?\n> ").strip()
    d = connect_to_device()
    launch_app(d, package_name)

    time.sleep(3)
    
    # Extract UI elements if flag is enabled
    ui_elements = None
    if use_ui_elements:
        xml_str = d.dump_hierarchy(compressed=True)
        ui_elements = extract_ui_elements(xml_str)
        logger.info(f"📱 Extracted {len(ui_elements)} UI elements")
        print("UI Elements:")
        print(json.dumps(ui_elements, indent=2))
    else:
        logger.info("📱 UI elements extraction disabled")

    # Generate raw plan
    raw_plan = generate_plan(user_prompt, app_context_file, ui_elements, use_ui_elements)
    
    if raw_plan:
        # Store raw plan in memory state
        global current_plan
        current_plan = raw_plan
        
        # Log raw plan
        logger.info("📋 Raw Plan Generated:")
        logger.info(json.dumps(raw_plan, indent=2))
        
        # Parse and remove unnecessary wait actions
        parsed_plan = parse_plan(raw_plan)
        
        # Log parsed plan
        logger.info("🔧 Parsed Plan (after removing wait before extract):")
        logger.info(json.dumps(parsed_plan, indent=2))
        
        # Execute the parsed plan
        result = execute_plan(d, parsed_plan, user_prompt, app_context_file, ui_elements, use_ui_elements)
        if result is not None:
            logger.info(f"✅ Final Result: {result}")
            return  # Stop further execution after extraction

if __name__ == "__main__":
    main()
