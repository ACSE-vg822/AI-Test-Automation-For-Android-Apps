# AI-Test-Automation-For-Android-Apps

An intelligent Android test automation framework that uses AI-powered screenshot analysis and UIAutomator2 for automated testing of Android applications.

## 🚀 Features

- **AI-Powered Testing**: Uses GPT to analyze screenshots and generate test plans
- **UIAutomator2 Integration**: Robust Android device automation
- **Screenshot Analysis**: Intelligent UI element detection and interaction
- **Multi-App Support**: Configurable for different Android applications
- **Context-Aware**: App-specific context files for better automation accuracy

## 🎥 Demo Video

Watch the AI Test Automation framework in action:

📥 **[Download Demo Video](https://drive.google.com/file/d/1Y70Th-t7weNaakPZLS9IamXxcrygsgg3/view?usp=sharing)**

_Note: The demo video is available on Google Drive. Click the link above to watch the full demo._

## 📋 Prerequisites

- Python 3.8+
- Android Emulator or physical Android device
- OpenAI API key

## 🛠️ Setup Instructions

### 1. Clone and Install Dependencies

```bash
git clone <repository-url>
cd AI-Test-Automation-For-Android-Apps

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup.py Installation

The project includes a `setup.py` file for easy installation and development:

```bash
# Install the package in development mode
pip install -e .

# This will install all dependencies from requirements.txt
# and make the package importable from anywhere
```

### 3. Android Emulator Setup

#### Option A: Android Studio Emulator

1. **Install Android Studio**

   - Download from [developer.android.com](https://developer.android.com/studio)
   - Install Android SDK during setup

2. **Create Virtual Device**

   ```bash
   # Open Android Studio
   # Go to Tools > AVD Manager
   # Click "Create Virtual Device"
   # Select device (e.g., Pixel 4)
   # Download and select system image (API 30+ recommended)
   # Complete setup
   ```

3. **Start Emulator**

   ```bash
   # From Android Studio AVD Manager
   # Click the play button next to your virtual device

   # Or via command line
   emulator -avd <your_avd_name>
   ```

#### Option B: Command Line Emulator

```bash
# List available AVDs
emulator -list-avds

# Start specific AVD
emulator -avd <avd_name> -no-snapshot-load
```

### 4. UIAutomator2 Setup

#### Install UIAutomator2 on Device

```bash
# Connect to device (emulator or physical)
adb devices

# Install UIAutomator2
pip install uiautomator2
python -m uiautomator2 init
```

#### Verify Connection

```python
import uiautomator2 as u2

# Connect to device
d = u2.connect()

# Test connection
print(d.info)
```

### 5. Environment Configuration

1. **Create .env file**

   ```bash
   # Create .env file in project root
   echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
   ```

## 📱 App Configuration

### Adding New Apps

1. **Create App Context File**

   ```bash
   # Create new context file
   touch app_context/your_app.txt
   ```

2. **Update config.py**

   ```python
   # Add to source/config.py
   YOUR_APP_PACKAGE = "com.your.app.package"

   APP_CONTEXT_FILES = {
       "your_app": (YOUR_APP_PACKAGE, "app_context/your_app.txt"),
       # ... existing apps
   }

   APPS_WITH_UI_ELEMENTS = {
       "your_app": True,  # or False based on your needs
       # ... existing apps
   }
   ```

### App Context File Format

Create a `.txt` file in `app_context/` directory describing your app's flow:

```txt
Region: Your Region

Starting Screen:
- Description of the app's initial screen

Default Behavior:
- What happens when app launches

Flow Overview:
1. Step One:
   - Description of first interaction

2. Step Two:
   - Description of second interaction

# Continue with app-specific flow
```

### Example App Context Files

- `app_context/uber.txt` - Uber ride booking flow
- `app_context/zomato.txt` - Zomato food ordering flow
- `app_context/blinkit.txt` - Blinkit grocery delivery flow

## 🎯 Usage

```python
 python source/executor.py
```

and go from there!

## 📁 Project Structure

```
AI-Test-Automation-For-Android-Apps/
├── app_context/           # App-specific context files
│   ├── uber.txt
│   ├── zomato.txt
│   └── blinkit.txt
├── source/               # Core automation modules
│   ├── config.py        # Configuration settings
│   ├── device_manager.py
│   ├── executor.py
│   ├── plan_generator.py
│   └── ...
├── screenshots/          # Screenshot storage
├── logs/                # Log files
├── developer_playground.py  # experimental script
├── setup.py             # Package installation
├── requirements.txt     # Python dependencies
└── README.md
```

## 🔧 Configuration Options

### config.py Settings

- **APP_CONTEXT_FILES**: Map app names to package names and context files
- **APPS_WITH_UI_ELEMENTS**: Control UI element extraction per app
- **OpenAI API Key**: Set via environment variable

### Environment Variables

```bash
OPENAI_API_KEY=your_api_key_here
```

## 🐛 Troubleshooting

### Common Issues

1. **Device Not Found**

   ```bash
   # Check connected devices
   adb devices

   # Restart ADB
   adb kill-server
   adb start-server
   ```

2. **UIAutomator2 Connection Failed**

   ```bash
   # Reinstall UIAutomator2
   python -m uiautomator2 init --force
   ```

3. **Emulator Not Starting**

   ```bash
   # Check available AVDs
   emulator -list-avds

   # Start with specific options
   emulator -avd <name> -no-snapshot-load -wipe-data
   ```

## 📝 Logging

Logs are stored in the `logs/` directory with timestamps for debugging and analysis.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add your app context file
4. Update configuration
5. Test your changes
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👨‍💻 Author

**Vidushee Geetam** - vidusheegeetam@gmail.com

---

For more detailed information about specific modules, check the individual Python files in the `source/` directory.
