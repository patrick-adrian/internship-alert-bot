import os
import json
import smtplib
from time import sleep
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from dotenv import load_dotenv
import requests

# Load environment variables from .env
load_dotenv()

# ========== Config ==========
JOB_TRACK_FILE = "seen_jobs.json"
SENDER = os.getenv("GMAIL_USER")
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECIPIENTS = os.getenv("EMAIL_RECIPIENTS", "").split(",")
# ========== Load Seen Jobs ==========
if os.path.exists(JOB_TRACK_FILE):
    with open(JOB_TRACK_FILE, "r") as f:
        seen_jobs = json.load(f)
else:
    seen_jobs = {"amd": [], "intel": []}

new_jobs = {"amd": [], "intel": []}

# ========== Setup Selenium ==========
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)

# ========== AMD Scraper ==========
def scrape_amd(driver):
    url = "https://careers.amd.com/careers-home/jobs?keywords=intern&location=Markham,%20ON,%20Canada&stretch=10&stretchUnit=MILES&sortBy=relevance&page=1&woe=7&regionCode=CA"
    driver.get(url)
    sleep(10)  # allow JS to render job list

    jobs = driver.find_elements(By.CSS_SELECTOR, 'a.job-title-link')
    results = []

    for job in jobs:
        try:
            title = job.find_element(By.CSS_SELECTOR, 'span[itemprop="title"]').text.strip()
            link = job.get_attribute("href")
            if not link.startswith("http"):
                link = "https://careers.amd.com" + link
            if link not in seen_jobs["amd"]:
                results.append({"title": title, "link": link})
        except:
            continue

    return results

# ========== Intel Scraper ==========
def scrape_intel(driver):
    url = "https://intel.wd1.myworkdayjobs.com/External?q=intern&locations=1e4a4eb3adf1019f4237e975bf81b3ce"
    driver.get(url)
    sleep(10)

    results = []
    job_links = driver.find_elements(By.CSS_SELECTOR, 'a[data-automation-id="jobTitle"]')
    
    for job in job_links:
        title = job.text.strip()
        link = job.get_attribute("href")
        if not link.startswith("http"):
            link = "https://jobs.intel.com" + link
        if link not in seen_jobs["intel"]:
            results.append({"title": title, "link": link})

    return results


# ========== Email Sender ==========
def send_email(jobs_dict):

    # Start body with header
    body = "This is an automated email.\n\n"

    # Add job details (or fallback message)
    for company, jobs in jobs_dict.items():
        body += f"--- {company.upper()} ---\n"
        if jobs:
            subject = "New Internship Roles Update (AMD / Intel)"
            for job in jobs:
                body += f"💼 {job['title']}\n🔗 {job['link']}\n\n"
        else:
            subject = "No New Internship Roles Update (AMD / Intel)"
            body += "No new roles found.\n\n"

    msg = MIMEMultipart()
    msg["From"] = SENDER
    msg["To"] = ", ".join(RECIPIENTS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SENDER, APP_PASSWORD)
        smtp.sendmail(SENDER, RECIPIENTS, msg.as_string())
        print("📧 Email sent to:", ", ".join(RECIPIENTS))

# ========== Telegram Sender ==========

def send_telegram(jobs_dict, bot_token, chat_id):
    if not any(jobs_dict.values()):
        return

    for company, jobs in jobs_dict.items():
        if jobs:
            for job in jobs:
                message = f"🧪 *{company.upper()} Internship Found!*\n💼 {job['title']}\n🔗 [View Job]({job['link']})"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data=payload)

# ========== Main ==========
def main():
    driver = get_driver()

    try:
        new_jobs["amd"] = scrape_amd(driver)
        new_jobs["intel"] = scrape_intel(driver)
    finally:
        driver.quit()

    # Always send email, even if no new jobs found
    send_email(new_jobs)
    send_telegram(new_jobs, os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID"))

    # Still update the seen jobs list to avoid duplicates
    for company in ["amd", "intel"]:
        for job in new_jobs[company]:
            seen_jobs[company].append(job["link"])

    with open(JOB_TRACK_FILE, "w") as f:
        json.dump(seen_jobs, f, indent=2)

if __name__ == "__main__":
    main()
