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
    
    # Check if the CSV files already exist, if not, create them and write the headers
    if os.path.exists(ARTICLES_OUTPUT_FILE) and os.path.exists(ISSUES_OUTPUT_FILE):
        pass
    else:
        with open(ARTICLES_OUTPUT_FILE, "w") as f:
            f.write("title,authors,keywords,publication_date,abstract,url,download_url,doi,local_filename,status\n")
    
    if os.path.exists(ISSUES_OUTPUT_FILE):
        return
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
    doi = soup.select_one("section.item.doi a").text.strip() if soup.select_one("section.item.doi a") else "N/A"
    print(doi)
    try:
        keywords = soup.select_one("section.item.keywords span.value").text.strip() if soup.select_one("section.item.keywords span.value") else "N/A"
    except AttributeError:
        keywords = "N/A"
    # strip tabs and spaces from keywords
    keywords = re.sub(r"\s+", " ", keywords)
    pdf_link = soup.select_one("a.obj_galley_link.pdf")["href"] if soup.select_one("a.obj_galley_link.pdf") else "N/A"
    
    # Try to download a copy of the PDF file

    
    pdf_filename = ''
    try:
        if pdf_link != "N/A":
            pdf_response = request_with_retry(pdf_link)
            if pdf_response is not None:
                
                    # FM has a funky JS viewer that loads the PDF but with some extra stuff.
                    # The *actual* PDF URL is going to be something like: https://firstmonday.org/ojs/index.php/fm/article/download/14442/12149/93487
                    # The URL that I get through beautifulsoup looks like: https://firstmonday.org/ojs/index.php/fm/article/view/14442/12149
                    
                    # I think we have to get this correct URL from the "Download" link on the new "viewer" page
                    
                viewer_soup = BeautifulSoup(pdf_response.text, "html.parser")
                download_link = viewer_soup.find("a", class_="download")["href"] if viewer_soup.find("a", class_="download") else None
                
                if download_link:
                    pdf_response = request_with_retry(download_link)
                else:
                    raise Exception("Download link not found on viewer page")
                
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
            f.write(f'"{article_title}","{json.dumps(authors_list)}","{keywords}","{publication_date}","{abstract}","{article_url}","N/A","{doi}","{pdf_filename}", "pdf_download_failed"\n')
        return

    # handle cases where there *isn't* a PDF link by writing "N/A" in the pdf_url and pdf_filename fields in the CSV file, but still writing the article metadata
    # TO-DO: make sure that we come back and save copies of the HTML 
    if pdf_link == "N/A":
        pdf_link = "N/A"
        pdf_filename = "N/A"
    
        
    if pdf_link != "N/A":
        file_download_link = pdf_link
        local_file = pdf_filename
    else:
        # No PDF available, try to get the HTML version
        html_link = soup.select_one("a.obj_galley_link.file")["href"] if soup.select_one("a.obj_galley_link.file") else "N/A"
        if html_link != "N/A":
            file_download_link = html_link
            local_file = f"{doi.replace('/', '_')}.html" if doi != "N/A" else f"{article_title[:50].replace(' ', '_')}.html"
            local_file = re.sub(r'[\\/*?:"<>|]', "", local_file)
            
            # HTML link on the article page looks like: https://firstmonday.org/ojs/index.php/fm/article/view/10306/9585
            # But we need to actually load: https://firstmonday.org/ojs/index.php/fm/article/download/10306/9585?inline=1
            
            html_link = html_link.replace("/view/", "/download/") + "?inline=1"
            
            html_response = request_with_retry(html_link)
            if html_response is not None:
                with open(os.path.join("pdfs", local_file), "w", encoding="utf-8") as f:
                    f.write(html_response.text)
        else:
            file_download_link = "N/A"
            local_file = "N/A"
    
    # Write this all into the CSV file
    with open(ARTICLES_OUTPUT_FILE, "a") as f:
        f.write(f'"{article_title}","{json.dumps(authors_list)}","{keywords}","{publication_date}","{abstract}","{article_url}","{file_download_link}","{doi}","{local_file}", "success"\n')

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
        
        # Check if article is already in the CSV file by matching the URL:
        # TO-DO: check if the status is "failed" and if so, try to scrape it again instead of skipping it
        with open(ARTICLES_OUTPUT_FILE, "r") as f:
            if article.find("h3", class_="title").find("a")["href"] in f.read():
                print(f"Article already exists in CSV, skipping: {article.find('h3', class_='title').text.strip()}")
                continue
        
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