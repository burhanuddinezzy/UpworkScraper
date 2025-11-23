import csv
from gpt import query_gpt, init_browser, close_browser
import re

main_file = "upwork_jobs.csv"

rows = []

# Read file including header
with open(main_file, "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)  # store existing header
    rows = list(reader)

init_browser()
# Process each row (assuming columns: Title, Description, URL)
updated_rows = []
for row in rows:
    title, description, url = row[:3]  # safe even if future rows have more columns

    prompt = f"""
    This is an upwork job posting titled '{title}'. The description is as follows: {description}. 
    Create one concise sentence of the task.
    Create a list of specific named entities in the posting.
    Format:
    Task: <sentence>
    Entities: <comma separated list>
    """

    response = query_gpt(prompt)

    task_match = re.search(r'Task:\s*(.+?)(?=Entities:)', response, re.DOTALL)
    entities_match = re.search(r'Entities:\s*(.+?)$', response, re.DOTALL)

    task_text = task_match.group(1).strip() if task_match else ""
    entities_text = entities_match.group(1).strip() if entities_match else ""

    updated_rows.append([title, description, url, task_text, entities_text])

# Write file back with new columns
with open(main_file, "w", encoding="utf-8", newline="") as w:
    writer = csv.writer(w)
    writer.writerow(["Title", "Description", "URL", "Task", "Entities"])
    writer.writerows(updated_rows)

close_browser()