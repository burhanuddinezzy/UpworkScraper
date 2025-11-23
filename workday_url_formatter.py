import pandas as pd
import re

# Read original CSV
df = pd.read_csv("search_results_1.csv")
df.columns = df.columns.str.strip()

base_urls = {}

for url in df['URL']:
    if pd.isna(url):
        continue

    # Extract company name for deduplication
    match_company = re.match(r'https://([^.]+)\.wd', url)
    if not match_company:
        continue
    company = match_company.group(1)

    # Extract CareerSite from URL
    # Look for the segment after the locale (en-US, zh-CN, fr-CA, etc.) and before /job/
    match_career_site = re.match(r'https://[^/]+/(?:[a-z]{2}-[A-Z]{2})/([^/]+)/job/', url)
    if not match_career_site:
        # fallback: try without locale
        match_career_site = re.match(r'https://[^/]+/([^/]+)/job/', url)
    if match_career_site:
        career_site = match_career_site.group(1)
        # Build canonical URL
        canonical_url = f"https://{company}.wd3.myworkdayjobs.com/wday/cxs/{company}/{career_site}/jobs?$filter=postedOn ge 2025-11-11&$orderby=postedOn desc"
        base_urls[company] = canonical_url  # deduplicate by company

# Save to CSV
formatted_urls = list(base_urls.values())
df_out = pd.DataFrame(formatted_urls, columns=['Formatted_URL'])
df_out.to_csv("formatted_urls_corrected.csv", index=False)

print(f"Formatted URLs saved to formatted_urls_corrected.csv ({len(formatted_urls)} unique URLs).")
