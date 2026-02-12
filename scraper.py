#!/usr/env/bin python3

import requests
from bs4 import BeautifulSoup
import json
import os
import sys
import time
import re
import csv
from datetime import datetime

''' SETUP SOME VARIABLES HERE '''
BASE_URL = "https://firstmonday.org/ojs/index.php/fm/issue/archive"
NUMBER_OF_PAGES = 8
ARTICLES_OUTPUT_FILE = "articles.csv"
ISSUES_OUTPUT_FILE = "issues.csv"


def request_with_retry(url, retries=3, backoff_factor=1):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}. Attempt {attempt + 1} of {retries}.")
            if attempt < retries - 1:
                sleep_time = backoff_factor * (2 ** attempt)  # Exponential backoff
                print(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
    print("All retry attempts failed.")
    return None

def setup_csv():
    with open(ARTICLES_OUTPUT_FILE, "w") as f:
        f.write("title,authors,keywords,publication_date,abstract,url,pdf_url,doi,status\n")
        
    with open(ISSUES_OUTPUT_FILE, "w") as f:
        f.write("volume,number,publication_date,url, articles, status\n")

def save_article(article_url):
    response = request_with_retry(article_url)
    if response is None:
        print(f"Failed to fetch article: {article_url}")
        # We can write a row to the CSV with status "failed" here if we want to keep track of failures
        with open(ARTICLES_OUTPUT_FILE, "a") as f:
            f.write(f'"N/A","N/A","N/A","N/A","N/A","{article_url}","N/A","N/A","failed"\n')
        return
    soup = BeautifulSoup(response.text, "html.parser")
    
    article_title = soup.find("h1", class_="page_title").text.strip()
    authors = soup.find("section", class_=['item', 'authors'])
    authors = authors.find("ul").find_all("li") if authors else []
    authors_list = []
    for author in authors:
        name = author.find("span", class_="name").text.strip()
        affiliation = author.find("span", class_="affiliation").text.strip() if author.find("span", class_="affiliation") else "N/A"
        authors_list.append({"name": name, "affiliation": affiliation})
    publication_date = soup.select_one("div.item.published span").text.strip() if soup.select_one("div.item.published span") else "N/A"
    abstract = soup.select_one("div.item.abstract").text.strip() if soup.select_one("div.item.abstract") else "N/A"
    doi = soup.select_one("div.item.doi a").text.strip() if soup.select_one("div.item.doi a") else "N/A"
    try:
        keywords = soup.find("div", class_=["item", "keywords"]).find("span").text.strip() if soup.find("div", class_=["item", "keywords"]) else "N/A"
    except AttributeError:
        keywords = "N/A"
    pdf_link = soup.select_one("a.obj_galley_link.pdf")["href"] if soup.select_one("a.obj_galley_link.pdf") else "N/A"
    
    # Try to download a copy of the PDF file
    try:
        if pdf_link != "N/A":
            pdf_response = request_with_retry(pdf_link)
            if pdf_response is not None:
                pdf_filename = f"{doi.replace('/', '_')}.pdf" if doi != "N/A" else f"{article_title[:50].replace(' ', '_')}.pdf"
                
                # Need to make sure the "pdfs" directory exists before trying to save files there
                os.makedirs("pdfs", exist_ok=True)
                
                # Need to sanitize the filename because there's a very real chance that the titles will have special characters in them
                pdf_filename = re.sub(r'[\\/*?:"<>|]', "", pdf_filename)
                
                with open(os.path.join("pdfs", pdf_filename), "wb") as f:
                    f.write(pdf_response.content)
    except Exception as e:
        print(f"Failed to download PDF: {e}")
        with open(ARTICLES_OUTPUT_FILE, "a") as f:
            f.write(f'"{article_title}","{json.dumps(authors_list)}","{keywords}","{publication_date}","{abstract}","{article_url}","N/A","{doi}","pdf_download_failed"\n')
        return

    
    # Write this all into the CSV file
    with open(ARTICLES_OUTPUT_FILE, "a") as f:
        f.write(f'"{article_title}","{json.dumps(authors_list)}","{keywords}","{publication_date}","{abstract}","{article_url}","{pdf_link}","{doi}","success"\n')

def scrape_issue(issue_url):
    response = requests.get(issue_url, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code != 200:
        print(f"Failed to fetch issue: {issue_url}")
        return
    soup = BeautifulSoup(response.text, "html.parser")
    
    articles = soup.find_all("div", class_="obj_article_summary")
    count = len(articles)
    print(f"Found {count} articles in issue")
    
    for article in articles:
        url = article.find("h3", class_="title").find("a")["href"]
        title = article.find("h3", class_="title").text.strip()
        print(f"Scraping article: {title} - {url}")
        save_article(url)
        
    return count

def scrape_archive_page(page_number):
    url = f"{BASE_URL}/{page_number}"
    print(f"Scraping URL: {url}")
    
    # TO-DO: add a delay here to avoid overwhelming the server, including some back-off logic if we get rate limited
    response = request_with_retry(url)
    if response is None:
        print(f"Failed to fetch page {page_number}")
        return
    soup = BeautifulSoup(response.text, "html.parser")

    issues = soup.find_all("div", class_="obj_issue_summary")
    
    print(f"Found {len(issues)} issues on page {page_number}")

    for issue in issues:
        issue_url = issue.find("a", class_="title")["href"]
         
        # Parse the title to get volume number and publication date as separate values
        title = issue.find("a", class_="title").text.strip()
        volume_match = re.search(r"Volume\s+(\d+)", title)
        issue_match = re.search(r"Number\s+(\d+)", title)
        # match date in format like: 2 February 2026
        date_match = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", title)
        
        print(f"Volume: {volume_match.group(1) if volume_match else 'N/A'}, Issue: {issue_match.group(1) if issue_match else 'N/A'}, Date: {date_match.group(1) if date_match else 'N/A'}")
        
        print(f"Scraping issue: {issue_url}")
        article_count = scrape_issue(issue_url)
        
        with open(ISSUES_OUTPUT_FILE, "a") as f:
            f.write(f'"{volume_match.group(1) if volume_match else "N/A"}","{issue_match.group(1) if issue_match else "N/A"}","{date_match.group(1) if date_match else "N/A"}","{issue_url}","{article_count}","success"\n')
        
def main():
    
    setup_csv()
    for page in range(1, NUMBER_OF_PAGES + 1):
        print(f"Scraping archive page {page}")
        scrape_archive_page(page)


if __name__ == "__main__":
    main()