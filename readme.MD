# ChatGPT Chat Deleter

A Python automation script that uses Selenium WebDriver to automatically delete your ChatGPT conversation history through the Firefox browser.

## Prerequisites

- Python 3.6+
- Firefox Browser installed
- A Firefox profile with existing ChatGPT login credentials
- Git (for cloning the repository)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/chatgpt-chat-deleter.git
cd chatgpt-chat-deleter
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Linux/macOS
# or
.\venv\Scripts\activate  # On Windows
```

3. Install the required packages:
```bash
pip install selenium
```

## Usage

The script uses your existing Firefox profile to access ChatGPT, so make sure you're already logged in to ChatGPT in Firefox.

To run the script with the browser visible (non-headless mode):
```bash
export HEADLESS=0
python Delete.py
```

To run in headless mode (default):
```bash
python Delete.py
```

## How It Works

- The script uses your default Firefox profile to access ChatGPT
- It automatically finds and deletes all chat conversations
- Deleted chat IDs are stored in `deleted_chats.json` to avoid re-processing
- The script handles various edge cases and retries failed deletions

## Notes

- The script requires an existing Firefox profile with ChatGPT login credentials
- ONLY USE THIS, if you want your chats to be deleted in full, if not this program IS NOT for you!
- If you encounter any issues, check the console output for error messages, making it was quite finicky so if they update the UI this is likely to stop working!

## File Structure

```
chatgpt-chat-deleter/
├── Delete.py
├── README.md
├── .gitignore
└── deleted_chats.json (created after first run)
```

