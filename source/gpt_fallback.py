import base64
import json
import re
import os
import openai
from source.logger import logger

def gpt_fallback(image_path, user_request, app_context_file):
    """Use GPT to extract information from screenshot when automation fails."""
    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")

    # Read app context for better understanding
    app_context = ""
    try:
        with open(app_context_file, "r", encoding="utf-8") as f:
            app_context = f.read()
    except Exception as e:
        logger.warning(f"⚠️ Could not read {app_context_file} for fallback: {e}")

    # Use a more specific prompt with app context
    prompt = f"""This is a screenshot of the mobile app. The user request is: '{user_request}'.\n\nApp Context:\n{app_context}\n\nExtract the most relevant information from the screenshot to fulfill the user's request. \nLook for prices, times, availability or any information that matches what the user is asking for.\n\nOnly reply with the extracted value. And add concise explantion of your answer."""

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

def gpt_fallback_action(image_path, user_request, app_context_file, failed_step=None, ui_elements=None, use_ui_elements=True):
    """Use GPT to suggest the next action when automation fails."""
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