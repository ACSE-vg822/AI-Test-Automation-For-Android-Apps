import os
import openai
from dotenv import load_dotenv

# === Setup ===
load_dotenv(override=True)
openai.api_key = os.getenv("OPENAI_API_KEY")

# === App Configuration ===
UBER_PACKAGE = "com.ubercab"
ZOMATO_PACKAGE = "com.application.zomato"

# === App Selection ===
APP_CONTEXT_FILES = {
    "uber": (UBER_PACKAGE, "app_context/uber.txt"),
    "zomato": (ZOMATO_PACKAGE, "app_context/zomato.txt")
}

# === UI Elements Configuration ===
# Apps that should use UI elements extraction
APPS_WITH_UI_ELEMENTS = {
    "zomato": True,
    "uber": False
}

def get_ui_elements_setting(app_choice):
    """Get whether UI elements should be used for a specific app."""
    return APPS_WITH_UI_ELEMENTS.get(app_choice, False) 