import json
import re
import openai
from source.logger import logger

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
    """Generate a step-by-step automation plan using GPT."""
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