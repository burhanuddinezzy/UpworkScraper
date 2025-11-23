# captcha  class="rc-anchor-center-item rc-anchor-checkbox-label" or id="recaptcha-anchor-label" or id="rc-anchor-container"
'''
& 'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe' --remote-debugging-port=9222 --user-data-dir='C:\ChromeSession'
'''
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import csv
from urllib.parse import quote
import pandas as pd
import traceback
import requests
from bs4 import BeautifulSoup
# Change the search query to filter for recent, so you can actually just get a list of jobs that are being posted recently
# ================= CONFIGURATION =================
REMOTE_DEBUGGING_PORT = 9222
WAIT_FOR_ELEMENT = 10
PAGE_LOAD_DELAY = 3

# CONFIGURE YOUR SEARCH QUERY HERE
locations = [
    "(Ontario OR Canada)"
    ]

date_filter = "after:2025-11-13"
keyword_filter = "automation" # OR intitle: automation OR intitle: process automation OR intitle: Business Process Analysis
#keyword_exclude_filter = "-intitle:senior"

search_queries = [
    "site:myworkdayjobs.com",           # Workday
    "site:boards.greenhouse.io",        # Greenhouse
    "site:jobs.lever.co",               # Lever
    "site:careers.smartrecruiters.com", # SmartRecruiters
    "site:icims.com",                   # iCIMS
    "site:taleo.net",                   # Oracle Taleo
    "site:jobvite.com",                 # Jobvite
    "site:recruiting.ultipro.com",      # UKG (UltiPro)
    "site:dayforcehcm.com",             # Ceridian Dayforce
    "site:successfactors.com",          # SAP SuccessFactors
    "site:adp.com",                     # ADP Workforce Now / Recruiting
    "site:paylocity.com",               # Paylocity
    "site:paycor.com",                  # Paycor
    "site:peoplefluent.com",            # PeopleFluent
    "site:jobscore.com",                # JobScore
    "site:hirevue.com",                 # HireVue
    "site:jobs.ashbyhq.com",            # Ashby
    "site:workable.com",                # Workable
    "site:breezy.hr",                   # Breezy HR
    "inurl:/apply",
    "inurl:/job"
]

# Generate all combinations
all_queries = [
    f"{site} {location} {keyword_filter} {date_filter}"
    for site in search_queries
    for location in locations
]

# Example: print first 10
for q in all_queries[:10]:
    print(q)

print(f"\nTotal queries generated: {len(all_queries)}")
# Random delay between page clicks (in seconds)
MIN_DELAY = 5
MAX_DELAY = 20

# Output file
OUTPUT_CSV = "google_search_urls.csv"

columns = ['query', 'url']
results_df = pd.DataFrame(columns=columns)
# ================= FUNCTIONS =================

def extract_urls_from_page(driver):
    """Extract all search result URLs and titles from current Google search page"""
    results = []
    
    try:
        # Find all search result blocks
        blocks = driver.find_elements(By.XPATH, "//a[.//h3]")
        if not blocks:
            print("  No search result blocks found on page.")
            return []

        for block in blocks:
            try:
                # URL
                href = block.get_attribute('href')
                if not href or 'google.com' in href:
                    continue
                if any(x in href for x in ['/search?', 'google.com/url', 'support.google']):
                    continue

                # Title: text of the <h3> inside this <a>
                try:
                    title_el = block.find_element(By.TAG_NAME, 'h3')
                    title = title_el.text.strip() if title_el else ""
                    if not title:
                        print("  Title element found but empty")
                except:
                    title = ""

                results.append({
                    "url": href,
                    "title": title
                })
                print(f"  Found URL: {href} | Title: {title}")

            except Exception as e:
                print(f"  Skipping block due to error: {e}")
                continue
        # Remove duplicates while preserving order
        seen = set()
        unique_results = []
        for r in results:
            if r['url'] not in seen:
                seen.add(r['url'])
                unique_results.append(r)

        return unique_results

    except Exception as e:
        print(f"  Error extracting URLs: {e}")
        return []


def click_next_page(driver):
    """Try to click the 'Next' button to go to next page"""
    try:
        # Multiple selectors for Next button
        next_selectors = [
            "a#pnnext",  # Standard Next button ID
            "a[aria-label='Next page']",
            "span.SJajHc.NVbCr a",  # Alternative selector
            "a[href*='start=']"  # Links with pagination parameter
        ]
        
        for selector in next_selectors:
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, selector)
                if next_button and next_button.is_displayed():
                    next_button.click()
                    return True
            except:
                continue
        
        return False
    
    except Exception as e:
        print(f"  Error clicking next: {e}")
        return False


def save_dataframe_to_csv(df, filename):
    """Save the global DataFrame to CSV"""
    df.to_csv(filename, index=False, encoding='utf-8')
    print(f"\n[INFO] Saved {len(df)} total URLs to {filename}")

def is_captcha_in_html(html):
    """Return True if any known captcha markers exist in the provided html string."""
    # exact markers you provided
    markers = [
        'id="recaptcha-anchor-label"',
    ]
    # some additional common signals to increase detection reliability
    extra_signals = [
        'g-recaptcha',        # common attribute for reCAPTCHA
        'recaptcha',          # generic string
        'class="grecaptcha"', # other naming
        'data-sitekey'        # reCAPTCHA sitekey attribute
    ]
    for m in markers:
        if m in html:
            return True
    for s in extra_signals:
        if s in html:
            return True
    return False

def check_for_captcha(driver, poll_interval=20, save_on_detect=True):
    try:
        html = driver.page_source or ""
    except Exception as e:
        print(f"[WARN] Could not get page source to check captcha: {e}")
        # Be conservative: treat as no captcha to avoid blocking unnecessarily
        return

    if not is_captcha_in_html(html):
        # No captcha immediately present
        return

    # Captcha detected — persist progress and wait for manual resolution
    print("\n[CAPTCHA DETECTED] reCAPTCHA or similar marker found on page.")
    if save_on_detect:
        try:
            # Save immediate progress to the main CSV
            save_dataframe_to_csv(results_df, OUTPUT_CSV)
        except Exception as e:
            print(f"[WARN] Failed to save progress on captcha detection: {e}")

    print(f"[ACTION REQUIRED] Please solve the captcha in the browser. Script will poll every {poll_interval}s and resume automatically after captcha is cleared.")

    # Poll loop: check page HTML every poll_interval seconds until captcha removed
    while True:
        time.sleep(poll_interval)
        try:
            html = driver.page_source or ""
        except Exception as e:
            print(f"[WARN] Could not refresh page source while waiting for captcha bypass: {e}")
            # continue polling even if page_source fails briefly
            continue

        if not is_captcha_in_html(html):
            print("[CAPTCHA CLEARED] Captcha no longer detected. Resuming scraping.")
            # short pause to let page settle
            time.sleep(1)
            return
        else:
            print(f"[STILL BLOCKED] Captcha still present — will check again in {poll_interval}s.")


def main():
    global results_df  # use the global DataFrame
    print("=" * 60)
    print("Google Search URL Scraper")
    print("=" * 60)
    print(f"Delay between pages: {MIN_DELAY}-{MAX_DELAY} seconds")
    print("=" * 60)
    
    try:
        print("\nConnecting to existing Chrome session...")
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{REMOTE_DEBUGGING_PORT}")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        wait = WebDriverWait(driver, WAIT_FOR_ELEMENT)
        print("Connected successfully!")

        # Open a single new tab at the start
        driver.execute_script("window.open('about:blank', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])

        for search_query in all_queries:
            page_count = 0
            query_urls = []

            search_url = f"https://www.google.com/search?q={quote(search_query)}&lr=lang_en"
            print(f"\nOpening search in tab for query: {search_query}")

            # Navigate to the search URL in the same tab
            driver.get(search_url)
            time.sleep(PAGE_LOAD_DELAY)

            # CHECK FOR CAPTCHA BEFORE EXTRACTING URLS
            check_for_captcha(driver, poll_interval=20, save_on_detect=True)

            while True:
                page_count += 1
                print(f"\n[Page {page_count}] Extracting URLs...")

                page_results = extract_urls_from_page(driver)

                if not page_results:
                    print("  No URLs found on this page. Stopping.")
                    break

                # Filter out URLs that have already been seen
                new_results = [r for r in page_results if r['url'] not in query_urls]
                query_urls.extend([r['url'] for r in new_results])
                print(f"  Added {len(new_results)} new URLs (Total: {len(query_urls)})")

                # Add to global DataFrame
                new_rows = pd.DataFrame({
                    'query': [search_query]*len(new_results),
                    'url': [r['url'] for r in new_results],
                    'title': [r['title'] for r in new_results]
                })
                results_df = pd.concat([results_df, new_rows], ignore_index=True)

                if not click_next_page(driver):
                    print("  Could not find 'Next' button. End of results.")
                    break

                delay = random.randint(MIN_DELAY, MAX_DELAY)
                print(f"  Waiting {delay} seconds before next page...")
                time.sleep(delay)

            print(f"\nCompleted query: {search_query}, collected {len(query_urls)} URLs.")
            save_dataframe_to_csv(results_df, OUTPUT_CSV)

    except Exception as e:
        print("\n[ERROR] An exception occurred during scraping.")
        traceback.print_exc()
        save_dataframe_to_csv(results_df, OUTPUT_CSV)

    finally:
        print("\nScript finished.")
        save_dataframe_to_csv(results_df, OUTPUT_CSV)
        print("Browser tab will remain open for manual review.")


if __name__ == "__main__":
    main()
