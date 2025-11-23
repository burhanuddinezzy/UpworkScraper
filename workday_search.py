import requests
import json
import time
import pandas as pd
from datetime import datetime

def scrape_workday_jobs(base_urls, search_text="", max_jobs=None):
    """
    Scrape job listings from multiple Workday careers portals.

    Args:
        base_urls: List of Workday jobs URLs (with query filter)
        search_text: Optional search keyword
        max_jobs: Maximum number of jobs to fetch (None = all jobs)
    """
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    all_jobs = []
    
    for base_url in base_urls:
        print(f"\nScraping jobs from: {base_url}")
        offset = 0
        limit = 20
        x = 0

        while x < 2:
            x += 1
            payload = {
                "appliedFacets": {},
                "limit": limit,
                "offset": offset,
                "searchText": search_text
            }
            
            try:
                response = requests.post(base_url, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                jobs = data.get('jobPostings', [])
                
                if not jobs:
                    print("No more jobs found for this company.")
                    break
                
                all_jobs.extend(jobs)
                print(f"Retrieved {len(jobs)} jobs. Total so far: {len(all_jobs)}")
                
                # Check if we've reached max_jobs
                if max_jobs and len(all_jobs) >= max_jobs:
                    all_jobs = all_jobs[:max_jobs]
                    print(f"Reached maximum job limit ({max_jobs})")
                    return all_jobs
                
                if len(jobs) < limit:
                    print("Retrieved all available jobs for this company.")
                    break
                
                offset += limit
                time.sleep(0.5)  # Rate limiting
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching jobs from {base_url}: {e}")
                break
    
    return all_jobs


def save_jobs_to_file(jobs, filename="workday_jobs.txt"):
    """Save jobs to a formatted text file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"Workday Job Listings\n")
        f.write(f"Scraped on: {timestamp}\n")
        f.write(f"Total jobs: {len(jobs)}\n")
        f.write("=" * 80 + "\n\n")
        
        for idx, job in enumerate(jobs, 1):
            title = job.get('title', 'N/A')
            location = job.get('locationsText', 'N/A')
            posted_date = job.get('postedOn', 'N/A')
            
            bullet_fields = job.get('bulletFields', [])
            if bullet_fields:
                if isinstance(bullet_fields[0], dict):
                    job_id = bullet_fields[0].get('value', 'N/A')
                else:
                    job_id = bullet_fields[0]
            else:
                job_id = 'N/A'
            
            external_path = job.get('externalPath', '')
            full_url = f"{external_path}" if external_path else 'N/A'
            
            f.write(f"Job #{idx}\n")
            f.write(f"Title: {title}\n")
            f.write(f"Location: {location}\n")
            f.write(f"Posted: {posted_date}\n")
            f.write(f"Job ID: {job_id}\n")
            f.write(f"URL: {full_url}\n")
            f.write("-" * 80 + "\n\n")
    
    print(f"\nJobs saved to {filename}")


def save_jobs_to_json(jobs, filename="workday_jobs.json"):
    """Save raw JSON data"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    print(f"Raw JSON saved to {filename}")


if __name__ == "__main__":
    # Load formatted URLs from CSV
    df_urls = pd.read_csv("formatted_urls.csv")
    df_urls.columns = df_urls.columns.str.strip()
    base_urls = df_urls['Formatted_URL'].dropna().tolist()
    print(f"Loaded {len(base_urls)} Workday job URLs to scrape.")
    
    # Configuration
    SEARCH_TEXT = ""  # optional search term
    MAX_JOBS = None   # set to limit, or None for all jobs
    
    # Scrape jobs
    jobs = scrape_workday_jobs(base_urls, search_text=SEARCH_TEXT, max_jobs=MAX_JOBS)
    
    if jobs:
        save_jobs_to_file(jobs, "workday_jobs.txt")
        save_jobs_to_json(jobs, "workday_jobs.json")
        print(f"\nTotal jobs scraped: {len(jobs)}")
    else:
        print("No jobs found.")
