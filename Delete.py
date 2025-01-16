import os
import time
import json
import logging
from pathlib import Path
from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
)

# Configuration
DELETED_LOG_FILE = "deleted_chats.json"
WAIT_TIMEOUT = 10  # seconds
BASE_URL = "https://chat.openai.com/"

# The known text color (font color) for the first Delete in the menu
DELETE_MENU_COLOR = "rgb(169, 53, 51)"
# The known text color for the second Delete in the confirmation dialog
DELETE_CONFIRM_COLOR = "rgb(239, 68, 68)"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_firefox_profile():
    """Get the default Firefox profile path."""
    import platform
    from pathlib import Path
    home = Path.home()
    system = platform.system()

    if system == "Linux":
        base_dir = home / ".mozilla" / "firefox"
    elif system == "Windows":
        base_dir = home / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"
    elif system == "Darwin":  # macOS
        base_dir = home / "Library" / "Application Support" / "Firefox" / "Profiles"
    else:
        return None

    for subdir in base_dir.glob("*"):
        if subdir.is_dir() and ("default" in subdir.name or "release" in subdir.name):
            return str(subdir)
    return None

class ChatGPTDeleter:
    def __init__(self, headless=True):
        self.profile_path = get_firefox_profile()
        if not self.profile_path:
            raise Exception("No Firefox profile found!")

        self.deleted_chat_ids = set()
        self.options = Options()
        if headless:
            self.options.add_argument("--headless")

        self.options.add_argument("-profile")
        self.options.add_argument(self.profile_path)

        # Error tracking
        self.current_error_chat_id = None
        self.dark_mode_error_count = 0

        self._load_deleted_log()

    def _load_deleted_log(self):
        """Load previously deleted chat IDs."""
        if Path(DELETED_LOG_FILE).exists():
            try:
                with open(DELETED_LOG_FILE, 'r') as f:
                    self.deleted_chat_ids = set(json.load(f))
                logging.info(f"Loaded {len(self.deleted_chat_ids)} deleted chat IDs")
            except Exception as e:
                logging.warning(f"Could not load deleted chats log: {e}")

    def _save_deleted_log(self):
        """Save deleted chat IDs."""
        try:
            with open(DELETED_LOG_FILE, 'w') as f:
                json.dump(list(self.deleted_chat_ids), f)
        except Exception as e:
            logging.warning(f"Could not save deleted chats log: {e}")

    def _get_chats(self, driver):
        """Get all chat elements in the sidebar."""
        try:
            # Wait for chat history to load
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href^="/c/"]'))
            )

            chats = []
            elements = driver.find_elements(By.CSS_SELECTOR, 'a[href^="/c/"]')
            for element in elements:
                try:
                    href = element.get_attribute('href')
                    if href and '/c/' in href:
                        chat_id = href.split('/')[-1]
                        if chat_id not in self.deleted_chat_ids:
                            chats.append({
                                'id': chat_id,
                                'element': element
                            })
                except:
                    continue

            return chats

        except Exception as e:
            logging.error(f"Error getting chats: {e}")
            return []

    def _find_delete_button_in_menu(self, driver):
        """
        Find the Delete button in the menu using data-testid.
        """
        try:
            # Wait for menu to be visible and find the delete option
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="delete-chat-menu-item"]'))
            )
            delete_button = driver.find_element(By.CSS_SELECTOR, 'div[data-testid="delete-chat-menu-item"]')
            return delete_button
        except Exception as e:
            logging.warning(f"Error finding menu delete button: {e}")
            return None

    def _find_delete_button_in_confirm(self, driver):
        """
        This method is not used in _delete_chat below, but leaving it here in case
        you want to experiment with a JavaScript-based approach to click the button.
        """
        try:
            # Wait for the dialog first
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="dialog"]'))
            )
            time.sleep(0.5)  # Brief pause to ensure dialog is fully rendered

            script = """
                const deleteBtn = document.evaluate(
                    '/html/body/div[5]/div/div/div/div[2]/div[2]/button[1]/div',
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                ).singleNodeValue;

                if (deleteBtn) {
                    const parentButton = deleteBtn.parentElement;  // Get the actual button
                    parentButton.click();
                    return true;
                }
                return false;
            """

            result = driver.execute_script(script)
            if result:
                logging.info("Successfully clicked delete button via JavaScript using XPath")
                return True

            logging.warning("Could not find or click delete button")
            return None
        except Exception as e:
            logging.warning(f"Error finding confirmation delete button: {e}")
            return None

    def _delete_chat(self, driver, chat):
        """
        Delete a single chat using:
        1. Click the chat link
        2. Hover + click the three-dot (options) button
        3. Click "Delete" in the dropdown
        4. Click the "Delete" confirmation button
        """
        try:
            # Quick cleanup of any overlay before starting
            driver.execute_script("""
                const overlays = document.querySelectorAll('div[class*="z-50"]');
                overlays.forEach(o => o.remove());
            """)

            # Track which chat we're working on
            if self.current_error_chat_id != chat['id']:
                self.current_error_chat_id = chat['id']
                self.dark_mode_error_count = 0

            # 1. Click the chat link itself
            chat['element'].click()
            time.sleep(1)  # Let the chat row fully load

            # 2. Hover over the container (the parent of chat['element'])
            chat_container = chat['element'].find_element(By.XPATH, "..")
            action = webdriver.ActionChains(driver)
            action.move_to_element(chat_container).perform()
            time.sleep(1)  # Let the three-dot button appear

            # 3. Locate the three-dot menu button inside this container
            menu_button = WebDriverWait(chat_container, WAIT_TIMEOUT).until(
                EC.visibility_of_element_located((
                    By.CSS_SELECTOR,
                    'button[data-testid$="-options"][aria-haspopup="menu"]'
                ))
            )
            logging.info(f"Menu button displayed? {menu_button.is_displayed()}, enabled? {menu_button.is_enabled()}")

            # Attempt direct ActionChains click on the three-dot button
            try:
                action.move_to_element(menu_button).pause(0.5).click(menu_button).perform()
                time.sleep(1)  # Wait for the menu to appear
            except ElementClickInterceptedException as e:
                if "because another element <html class=\"dark\">" in str(e):
                    self.dark_mode_error_count += 1
                    logging.warning(f"Dark mode error count for chat {chat['id']}: {self.dark_mode_error_count}")
                    if self.dark_mode_error_count >= 5:
                        logging.warning("Refreshing page due to multiple dark mode errors")
                        driver.refresh()
                        time.sleep(3)  # Wait for the page to reload
                        self.dark_mode_error_count = 0  # Reset counter after refresh
                        return False  # Retry deletion
                else:
                    logging.error(f"Unexpected error: {e}")
                return False

            # 4. Wait for the "Delete" item in that menu
            delete_button = self._find_delete_button_in_menu(driver)
            if not delete_button:
                logging.warning("Delete button not found in menu after waiting")
                return False

            delete_button.click()
            time.sleep(1)  # Let the confirmation dialog appear

            # 5. Look for the confirmation dialog
            dialog_selectors = [
                'div[role="dialog"]',
                'div.relative.flex.flex-col',
                'div[data-state="open"]'
            ]
            dialog_found = False
            for selector in dialog_selectors:
                try:
                    WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    dialog_found = True
                    logging.info(f"Found dialog with selector: {selector}")
                    break
                except TimeoutException:
                    continue

            if not dialog_found:
                logging.warning("Could not find confirmation dialog")
                return False

            # 6. IMPORTANT FIX: Click the correct 'Delete' button by explicit XPath with retries
            success = False
            button_selectors = [
                '/html/body/div[5]/div/div/div/div[2]/div[2]/button[1]',  # Original XPath
                '//button[contains(text(), "Delete")]',  # Text-based selector
                '//div[@role="dialog"]//button[contains(@class, "text-red")]',  # Class-based selector
                '//div[@role="dialog"]//button[last()]'  # Position-based selector (if Delete is last button)
            ]

            for attempt in range(5):
                if attempt > 0:
                    time.sleep(1)  # Wait between attempts

                for selector in button_selectors:
                    try:
                        confirm_button = driver.find_element(
                            By.XPATH,
                            selector
                        )
                        confirm_button.click()
                        success = True
                        break
                    except NoSuchElementException:
                        continue
                    except Exception as e:
                        logging.error(f"Error with selector {selector}: {e}")
                        continue

                if success:
                    break

            if not success:
                logging.warning("All confirmation button click attempts failed")
                driver.refresh()
                time.sleep(5)  # Extended wait after refresh
                self.dark_mode_error_count = 0  # Reset error count since we're refreshing
                return False  # Return to main loop to get fresh elements

            time.sleep(3)  # Wait for the chat to actually disappear

            # 7. Verify the chat is gone
            retries = 0
            while retries < 3:
                try:
                    driver.find_element(By.CSS_SELECTOR, f'a[href*="{chat["id"]}"]')
                    time.sleep(1)
                    retries += 1
                except NoSuchElementException:
                    logging.info(f"Successfully deleted chat {chat['id']}")
                    return True

            logging.warning("Chat still exists after deletion attempt")
            return False

        except Exception as e:
            logging.error(f"Error in deletion process for chat {chat['id']}: {e}")
            if "because another element <html class=\"dark\">" in str(e):
                self.dark_mode_error_count += 1
                logging.warning(f"Dark mode error count for chat {chat['id']}: {self.dark_mode_error_count}")
                if self.dark_mode_error_count >= 5:
                    logging.warning("Refreshing page due to multiple dark mode errors")
                    driver.refresh()
                    time.sleep(3)  # Wait for the page to reload
                    self.dark_mode_error_count = 0  # Reset counter after refresh
                    return False  # Retry deletion
            else:
                logging.error(f"Unexpected error: {e}")
            return False

    def _try_confirm_button_with_retries(self, driver, max_attempts=5):
        """
        Try to find and click the confirm button with retries.
        Returns True if successful, False otherwise.
        """
        for attempt in range(max_attempts):
            try:
                if attempt > 0:  # Don't wait on first attempt
                    time.sleep(1)  # Wait between attempts

                confirm_button = driver.find_element(
                    By.XPATH,
                    '/html/body/div[5]/div/div/div/div[2]/div[2]/button[1]'
                )
                confirm_button.click()
                return True
            except NoSuchElementException:
                logging.warning(f"Could not find confirmation button (Attempt {attempt + 1}/{max_attempts})")
                continue
            except Exception as e:
                logging.error(f"Error clicking confirm button: {e}")
                continue

        # If we get here, all attempts failed
        logging.warning("All confirmation button click attempts failed")
        driver.refresh()
        time.sleep(5)  # Extended wait after refresh
        return False

    def run(self):
        """Main execution loop."""
        driver = None
        try:
            driver = webdriver.Firefox(options=self.options)
            driver.get(BASE_URL)

            # Wait for page to load fully
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            while True:
                chats = self._get_chats(driver)
                if not chats:
                    logging.info("No more chats to delete")
                    break

                for chat in chats:
                    if self._delete_chat(driver, chat):
                        self.deleted_chat_ids.add(chat['id'])
                        self._save_deleted_log()
                        logging.info(f"Deleted chat {chat['id']}")
                    else:
                        logging.warning(f"Failed to delete chat {chat['id']}")

                time.sleep(1)  # Brief pause between batches

        except Exception as e:
            logging.error(f"Error during execution: {e}")

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

if __name__ == "__main__":
    # Set HEADLESS=0 (or HEADLESS="false") in your environment
    # if you want to watch the browser in non-headless mode.
    headless = os.environ.get("HEADLESS", "1") == "1"
    deleter = ChatGPTDeleter(headless=headless)
    deleter.run()
