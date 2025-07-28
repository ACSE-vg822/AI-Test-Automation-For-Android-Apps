import time
import re
from source.logger import logger
from source.screenshot_manager import take_screenshot
from source.gpt_fallback import gpt_fallback, gpt_fallback_action

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
            d, user_request, app_context_file, 
            f"Step {step_index+1}: {step}", fresh_ui_elements, use_ui_elements, ss
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
        query = step.get("query")
        
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