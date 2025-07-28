import base64
import json
import re
import os
import openai
import time
from source.logger import logger
from source.screenshot_manager import take_screenshot

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
    prompt = f"""This is a screenshot of the mobile app. The user request is: '{user_request}'.\n\nApp Context:\n{app_context}\n\nExtract the most relevant information from the screenshot to fulfill the user's request. \nLook for prices, times, availability or any information that matches what the user is asking for.\n\nIMPORTANT: You must respond with a JSON object in this exact format:\n{{"answer": "extracted value or NOT_FOUND", "found": true/false}}\n\nSet "found" to true only if you found the specific information the user is asking for. Set "found" to false if the information is not visible or not what the user requested."""

    # Scrolling loop: 5 turns maximum
    for scroll_turn in range(5):
        logger.info(f"🔄 GPT Fallback Scroll Turn {scroll_turn + 1}/5")
        
        # Take screenshot for current scroll position
        if scroll_turn == 0 and initial_screenshot_path:
            # Use the initial screenshot if provided
            image_path = initial_screenshot_path
            logger.info(f"📸 Using initial screenshot: {image_path}")
        else:
            # Take new screenshot
            image_path = take_screenshot(d, f"gpt_fallback_scroll_{scroll_turn}")
            logger.info(f"📸 Taking new screenshot: {image_path}")
        
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
            
            # Parse JSON response
            try:
                result = json.loads(raw)
                answer = result.get("answer", "")
                found = result.get("found", False)
                
                if found and answer and answer.lower() != "not_found":
                    logger.info(f"✅ GPT found answer on scroll turn {scroll_turn + 1}: {answer}")
                    return answer
                else:
                    logger.info(f"⚠️ No meaningful answer found on scroll turn {scroll_turn + 1}: {answer}")
                    
            except json.JSONDecodeError:
                # Fallback for non-JSON responses
                logger.warning(f"⚠️ GPT returned non-JSON response: {raw}")
                if raw and raw.lower() not in ["none", "not found", "no information", "n/a", "", "not_found"]:
                    logger.info(f"✅ GPT found answer on scroll turn {scroll_turn + 1}: {raw}")
                    return raw
                else:
                    logger.info(f"⚠️ No meaningful answer found on scroll turn {scroll_turn + 1}: {raw}")
            
        except Exception as e:
            logger.error(f"❌ GPT fallback failed on scroll turn {scroll_turn + 1}: {e}")
        
        # Scroll down for next iteration (except on last turn)
        if scroll_turn < 4:  # Don't scroll on the last turn
            try:
                # Get screen dimensions for scrolling
                screen_width = d.window_size()[0]
                screen_height = d.window_size()[1]
                
                # Scroll up in the ride selection area (bottom half of screen)
                start_x = screen_width // 2
                start_y = int(screen_height * 0.8)  # 80% down 
                end_x = screen_width // 2
                end_y = int(screen_height * 0.4)    # 40% down 
                
                logger.info(f"📱 Scrolling: ({start_x}, {start_y}) → ({end_x}, {end_y})")
                d.swipe(start_x, start_y, end_x, end_y, duration=0.8)
                time.sleep(2)  # Wait longer for scroll animation and content to load
                logger.info(f"✅ Scroll completed for turn {scroll_turn + 1}")
                
            except Exception as e:
                logger.error(f"❌ Scrolling failed on turn {scroll_turn + 1}: {e}")
                break
    
    logger.warning("⚠️ No answer found after 5 scroll attempts")
    return None

def gpt_fallback_action(d, user_request, app_context_file, failed_step=None, ui_elements=None, use_ui_elements=True, initial_screenshot_path=None):
    """
    GPT fallback action with scrolling loop for finding clickable elements
    Args:
        d: uiautomator2 device object
        user_request: user's request for extraction
        app_context_file: path to app context file
        failed_step: information about the failed step
        ui_elements: available UI elements
        use_ui_elements: whether to use UI elements
        initial_screenshot_path: optional initial screenshot path (if already taken)
    """
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

{{ "action": "click", "target": "text='Button Text'", "found": true }}
OR
{{ "action": "click", "target": "xpath=//android.widget.TextView[contains(@text, 'Partial Text')]", "found": true }}
OR
{{ "action": "type", "value": "text to type", "found": true }}
OR
{{ "action": "extract", "target": "xpath=//android.widget.TextView[contains(@text, '$')]", "found": true }}

Valid actions: "click", "type", "wait", "extract"
Valid targets: "text='exact text'", "xpath=//path/to/element"
For typing: use "value" field instead of "target"
For extract: use "target" field with xpath to find elements to extract text from

IMPORTANT: Set "found" to true only if you can see a clear, actionable element in the screenshot. Set "found" to false if no suitable element is visible.

Only return the JSON object - no explanations or markdown formatting."""
    
    # Scrolling loop: 5 turns maximum
    for scroll_turn in range(5):
        logger.info(f"🔄 GPT Fallback Action Scroll Turn {scroll_turn + 1}/5")
        
        # Take screenshot for current scroll position
        if scroll_turn == 0 and initial_screenshot_path:
            # Use the initial screenshot if provided
            image_path = initial_screenshot_path
            logger.info(f"📸 Using initial screenshot: {image_path}")
        else:
            # Take new screenshot
            image_path = take_screenshot(d, f"gpt_fallback_action_scroll_{scroll_turn}")
            logger.info(f"📸 Taking new screenshot: {image_path}")
        
        # Process screenshot with GPT
        try:
            with open(image_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a mobile automation assistant. You must return ONLY a valid JSON object with action, target/value, and found fields. No explanations."
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
            try:
                result = json.loads(raw)
                
                # Check if element was found
                found = result.get("found", False)
                
                if found:
                    logger.info(f"✅ GPT found actionable element on scroll turn {scroll_turn + 1}")
                    
                    # Validate required fields
                    if "action" not in result:
                        logger.error("❌ GPT fallback action missing 'action' field")
                        continue
                    
                    if result["action"] == "click" and "target" not in result:
                        logger.error("❌ GPT fallback action missing 'target' field for click action")
                        continue
                    
                    if result["action"] == "type" and "value" not in result:
                        logger.error("❌ GPT fallback action missing 'value' field for type action")
                        continue
                    
                    if result["action"] == "extract" and "target" not in result:
                        logger.error("❌ GPT fallback action missing 'target' field for extract action")
                        continue
                    
                    # Remove the "found" field before returning
                    result.pop("found", None)
                    
                    # Dump hierarchy before clicking to ensure fresh UI state
                    logger.info("📱 Dumping hierarchy before action...")
                    try:
                        d.dump_hierarchy(compressed=True)
                        logger.info("✅ Hierarchy dumped successfully")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to dump hierarchy: {e}")
                    
                    return result
                else:
                    logger.info(f"⚠️ No actionable element found on scroll turn {scroll_turn + 1}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ GPT fallback action JSON parsing failed on scroll turn {scroll_turn + 1}: {e}")
                logger.error(f"Raw response: {raw}")
                continue
            
        except Exception as e:
            logger.error(f"❌ GPT fallback action failed on scroll turn {scroll_turn + 1}: {e}")
            continue
        
        # Scroll down for next iteration (except on last turn)
        if scroll_turn < 4:  # Don't scroll on the last turn
            try:
                # Get screen dimensions for scrolling
                screen_width = d.window_size()[0]
                screen_height = d.window_size()[1]
                
                # Scroll up in the ride selection area (bottom half of screen)
                start_x = screen_width // 2
                start_y = int(screen_height * 0.8)  # 80% down 
                end_x = screen_width // 2
                end_y = int(screen_height * 0.4)    # 40% down 
                
                logger.info(f"📱 Scrolling: ({start_x}, {start_y}) → ({end_x}, {end_y})")
                d.swipe(start_x, start_y, end_x, end_y, duration=0.8)
                time.sleep(2)  # Wait longer for scroll animation and content to load
                logger.info(f"✅ Scroll completed for turn {scroll_turn + 1}")
                
            except Exception as e:
                logger.error(f"❌ Scrolling failed on turn {scroll_turn + 1}: {e}")
                break
    
    logger.warning("⚠️ No actionable element found after 5 scroll attempts")
    return None 