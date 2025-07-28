import time
import json
from source.logger import logger
from source.config import APP_CONTEXT_FILES, get_ui_elements_setting
from source.device_manager import connect_to_device, launch_app
from source.plan_generator import generate_plan, parse_plan
from source.plan_executor import execute_plan
from source.filter_ui_elements import extract_ui_elements

# === Memory State ===
# Store the generated plan for logging and modification
current_plan = None

def main():
    """Main executor function that orchestrates the entire automation flow."""
    global current_plan
    
    app_choice = ""
    while app_choice not in APP_CONTEXT_FILES:
        app_choice = input("Which app do you want to automate? (uber/zomato): ").strip().lower()
        if app_choice not in APP_CONTEXT_FILES:
            print("Invalid choice. Please enter 'uber' or 'zomato'.")
    
    package_name, app_context_file = APP_CONTEXT_FILES[app_choice]
    
    # Get UI elements setting from configuration
    use_ui_elements = get_ui_elements_setting(app_choice)
    
    user_prompt = input(f"📝 What do you want to do in {app_choice.title()}?\n> ").strip()
    
    # Connect to device and launch app
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