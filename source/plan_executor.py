import time
import re
from source.logger import logger
from source.screenshot_manager import take_screenshot
from source.gpt_fallback import gpt_fallback, gpt_fallback_action

def execute_plan(d, plan, user_request, app_context_file, ui_elements=None, use_ui_elements=True):
    """Execute the automation plan step by step."""
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
                    suggestion = gpt_fallback(ss, user_request, app_context_file)
                    logger.info(f"🤖 GPT Extracted: {suggestion}")
                    if suggestion:
                        logger.info(f"✅ Final Result: {suggestion}")
                        return suggestion  # EARLY EXIT
                    # If extraction fails, continue as before
                else:
                    ss = take_screenshot(d, f"step_{i+1}_click_fallback")
                    # Fresh UI extraction for fallback
                    fresh_ui_elements = None
                    if use_ui_elements:
                        from source.filter_ui_elements import extract_ui_elements
                        xml_str = d.dump_hierarchy(compressed=True)
                        fresh_ui_elements = extract_ui_elements(xml_str)
                    else:
                        fresh_ui_elements = None
                    suggestion = gpt_fallback_action(ss, user_request, app_context_file, f"Step {i+1}: {step}", fresh_ui_elements, use_ui_elements)
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
                    suggestion = gpt_fallback(ss, user_request, app_context_file)
                    logger.info(f"🤖 GPT Extracted: {suggestion}")
                    if suggestion:
                        logger.info(f"✅ Final Result: {suggestion}")
                        return suggestion  # EARLY EXIT
                else:
                    ss = take_screenshot(d, f"step_{i+1}_type_fallback")
                    # Fresh UI extraction for fallback
                    fresh_ui_elements = None
                    if use_ui_elements:
                        from source.filter_ui_elements import extract_ui_elements
                        xml_str = d.dump_hierarchy(compressed=True)
                        fresh_ui_elements = extract_ui_elements(xml_str)
                    else:
                        fresh_ui_elements = None
                    suggestion = gpt_fallback_action(ss, user_request, app_context_file, f"Step {i+1}: {step}", fresh_ui_elements, use_ui_elements)
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
                        # Return the first element found (simplified logic)
                        if i_elem == 0:
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
                                # Return the first element found (simplified logic)
                                if i_elem == 0:
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
                    suggestion = gpt_fallback(ss, user_request, app_context_file)
                    logger.info(f"🤖 GPT Extracted: {suggestion}")
                    return suggestion  # EARLY EXIT

        else:
            logger.warning(f"⚠️ Step failed: Unknown action '{action}' in plan. Skipping.")
        i += 1 