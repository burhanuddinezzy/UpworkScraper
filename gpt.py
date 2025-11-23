"""
run this before using gpt.py
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebug"

# Initialize browser once
init_browser()

# Query multiple times in same session
response1 = query_gpt("What is AI?")
response2 = query_gpt("Explain machine learning")

# Close when done
close_browser()
"""

from playwright.sync_api import sync_playwright
import time
import random

browser = None
page = None
request_count = 0
playwright_instance = None

REMOTE_DEBUGGING_URL = "http://127.0.0.1:9222"
CHAT_URL = "https://chat.openai.com"

def init_browser():
    global browser, page, request_count, playwright_instance
    
    playwright_instance = sync_playwright().start()
    
    # Attach to the running Chrome
    browser = playwright_instance.chromium.connect_over_cdp(REMOTE_DEBUGGING_URL)

    # If Chrome has multiple tabs, pick one or open a new one
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()

    page.goto(CHAT_URL)
    time.sleep(3)
    request_count = 0

def query_gpt(input_text):
    time.sleep(random.uniform(4, 9))  # Small delay to mimic human behavior
    global page, request_count

    if page is None:
        init_browser()

    try:
        page.fill("#prompt-textarea", input_text)
        time.sleep(0.5)
        page.click("#composer-submit-button")
        time.sleep(1)

        request_count += 1
        response_turn = request_count * 2

        page.wait_for_selector(f'[data-testid="conversation-turn-{response_turn}"]', timeout=120000)
        time.sleep(2)

        response_elem = page.query_selector(f'[data-testid="conversation-turn-{response_turn}"]')
        text = response_elem.inner_text()
        print(f"paragraphs:\n{text}")

        return text

    except Exception as e:
        print(f"Error: {e}")
        raise

def close_browser():
    global browser, page, playwright_instance
    if browser:
        browser.close()
    if playwright_instance:
        playwright_instance.stop()
    browser = None
    page = None
