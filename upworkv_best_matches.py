import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import requests
from selectolax.parser import HTMLParser

# ================= CONFIGURATION =================
SEARCH_URL = "https://www.upwork.com/nx/find-work/best-matches"
REMOTE_DEBUGGING_PORT = 9222
PAGE_LOAD_DELAY = 15
CSV_FILE = "upwork_jobs.csv"

# ================= ATTACH TO EXISTING CHROME =================
chrome_options = Options()

def remote_debugging_available(port=REMOTE_DEBUGGING_PORT, timeout=1.0):
    try:
        resp = requests.get(f"http://127.0.0.1:{port}/json", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False

if remote_debugging_available():
    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{REMOTE_DEBUGGING_PORT}")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    print(f"[INFO] Attached to existing Chrome at 127.0.0.1:{REMOTE_DEBUGGING_PORT}")
else:
    print(f"[INFO] No remote-debugging Chrome detected. Launching new Chrome.")
    chrome_options.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# ================= OPEN NEW TAB AND FETCH HTML =================
driver.execute_script(f"window.open('{SEARCH_URL}', '_blank');")
driver.switch_to.window(driver.window_handles[-1])
time.sleep(PAGE_LOAD_DELAY)  # Wait for page to load

html = driver.page_source
doc = HTMLParser(html)

# ================= EXTRACT DATA =================
job_cards = doc.css('[data-test="job-tile-list"] section')

# Open CSV file for writing
with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["title", "description", "url"])  # Header row

    for card in job_cards:
        title_node = card.css_first(".air3-link.text-decoration-none")
        desc_node = card.css_first('[data-test="job-description-text"]')

        if not title_node or not desc_node:
            continue

        title = title_node.text(strip=True)
        description = desc_node.text(strip=True)

        # Extract job URL from <a> tag inside title_node
        a_tag = title_node.css_first("a")
        url = a_tag.attributes.get("href") if a_tag else SEARCH_URL

        writer.writerow([title, description, url])
        print(f"[INFO] Saved job: {title}")

# ================= CLEANUP =================
driver.quit()
