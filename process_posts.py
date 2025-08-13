import requests
from bs4 import BeautifulSoup
import json
import os
import time
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# --- Configuration ---
# The file containing keywords to search for. This file should be in the same
# directory as the script in the Lambda deployment package.
KEYWORDS_FILE = 'keywords.json'

# Environment variables that must be set in the Lambda function configuration.
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')
BRIGHTDATA_API_TOKEN = os.environ.get('BRIGHTDATA_API_TOKEN', "14f155bfe51a4c4255093e8bd64a1cdf5c380bb7144099a2a909a64a8d4deb75")

# Gmail API settings
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']
# --- End Configuration ---


class TurtleForumCrawler:
    """
    Crawls the FaunaClassifieds forum for turtle and tortoise posts.
    """
    def __init__(self):
        self.base_url = "https://faunaclassifieds.com"
        self.forum_url = "https://faunaclassifieds.com/forums/forums/turtles-tortoises.54/"
        # Headers are now managed by the proxy service.
        self.brightdata_token = BRIGHTDATA_API_TOKEN

    def fetch_page(self, url):
        """Fetch a page through the Bright Data proxy and return a BeautifulSoup object."""
        if not self.brightdata_token:
            print("Error: BRIGHTDATA_API_TOKEN environment variable not set. Cannot use proxy.")
            return None

        proxy_api_url = "https://api.brightdata.com/request"
        
        headers = {
            "Authorization": f"Bearer {self.brightdata_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "zone": "web_unlocker1",
            "url": url,
            "format": "raw"
        }

        try:
            print(f"Fetching {url} via proxy...")
            response = requests.post(proxy_api_url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            
            # A 200 OK from the proxy API means the request was successful.
            # The body will contain the raw HTML from the target URL.
            return BeautifulSoup(response.text, 'html.parser')

        except requests.RequestException as e:
            print(f"Error fetching {url} via proxy: {e}")
            if e.response is not None:
                # It's useful to log the proxy's response if something goes wrong.
                print(f"Proxy API Response Status: {e.response.status_code}")
                print(f"Proxy API Response Body: {e.response.text}")
            return None

    def parse_thread_list(self, soup):
        """Parse the thread list from the forum page."""
        threads = []
        thread_items = soup.find_all('div', class_='structItem--thread')

        for thread in thread_items:
            thread_data = {}
            title_elem = thread.find('a', {'data-tp-primary': 'on'})
            if not title_elem:
                title_elem = thread.find('h3', class_='structItem-title').find('a')
            
            if title_elem:
                thread_data['title'] = title_elem.text.strip()
                thread_data['url'] = self.base_url + title_elem.get('href', '')
            
            author_elem = thread.find('a', class_='username')
            if author_elem:
                thread_data['author'] = author_elem.text.strip()

            meta_elem = thread.find('div', class_='structItem-cell--meta')
            if meta_elem:
                counts = meta_elem.find_all('dd')
                if len(counts) > 0:
                    thread_data['replies'] = counts[0].text.strip()
                if len(counts) > 1:
                    thread_data['views'] = counts[1].text.strip()
            
            if thread_data:
                threads.append(thread_data)
        
        return threads

    def crawl_forum(self, max_pages=2):
        """Crawl the forum and return a list of all found threads."""
        all_threads = []
        for page in range(1, max_pages + 1):
            url = f"{self.forum_url}page-{page}" if page > 1 else self.forum_url
            print(f"Crawling page {page}...")
            soup = self.fetch_page(url)
            if soup:
                threads = self.parse_thread_list(soup)
                all_threads.extend(threads)
                print(f"Found {len(threads)} threads on page {page}")
                if page < max_pages:
                    time.sleep(1) # Be polite
            else:
                print(f"Failed to fetch page {page}")
                break
        return all_threads


def load_keywords(filename):
    """Loads keywords from the JSON file included in the package."""
    try:
        # The script and keywords.json are in the same directory in the Lambda package
        script_dir = os.path.dirname(__file__)
        keywords_path = os.path.join(script_dir, filename)
        with open(keywords_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {filename} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filename}.")
        return []

def filter_posts_by_keywords(posts, keywords):
    """Filters posts based on keywords in the title (case-insensitive)."""
    filtered_posts = []
    for post in posts:
        title = post.get('title', '').lower()
        if any(keyword.lower() in title for keyword in keywords):
            filtered_posts.append(post)
    return filtered_posts

def format_email_body(posts):
    """Formats the list of posts into an HTML email body."""
    if not posts:
        return "No new turtle forum posts matching your keywords found."

    body_html = "<html><head></head><body>"
    body_html += "<h1>New Turtle Forum Posts</h1>"
    body_html += "<p>Here are the latest posts matching your keywords:</p>"
    
    for post in posts:
        title = post.get('title', 'No Title')
        url = post.get('url', '#')
        author = post.get('author', 'Unknown')
        replies = post.get('replies', '0')
        views = post.get('views', '0')
        
        body_html += f"<h2><a href='{url}'>{title}</a></h2>"
        body_html += f"<p><strong>Author:</strong> {author}<br/>"
        body_html += f"<strong>Replies:</strong> {replies} | <strong>Views:</strong> {views}</p>"
        body_html += "<hr/>"
        
    body_html += "</body></html>"
    return body_html


def get_gmail_credentials():
    """
    Authenticates with Google and returns credentials.
    Handles the OAuth 2.0 flow. In a Lambda environment, it relies on a
    packaged token.json and will not attempt to write back the refreshed token.
    """
    creds = None
    # Use the script's directory to build absolute paths to token/credentials files.
    # This is more robust for different execution environments like AWS Lambda.
    script_dir = os.path.dirname(__file__)
    token_path = os.path.join(script_dir, 'token.json')

    # The file token.json stores the user's access and refresh tokens.
    # It's created automatically during the first-time local authorization.
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, GMAIL_SCOPES)
        except (ValueError, json.JSONDecodeError):
            # If token.json is invalid or empty, we'll proceed as if it's not there.
            print("Warning: token.json is invalid or empty. A new one will be created.")
            creds = None
    
    # If there are no (valid) credentials available, attempt to refresh or run local auth.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            
            # Only try to save the refreshed credentials if NOT in a read-only
            # environment like AWS Lambda. We detect Lambda by checking for a common
            # environment variable.
            is_lambda = 'AWS_LAMBDA_FUNCTION_NAME' in os.environ
            if not is_lambda:
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
        else:
            # This part requires user interaction, so it must be done locally
            # before deploying to Lambda. It needs 'credentials.json'.
            credentials_path = os.path.join(script_dir, 'credentials.json')
            if not os.path.exists(credentials_path):
                print("Error: 'credentials.json' not found. This is required for the initial auth flow.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
            
            # Save the newly generated credentials for the next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
    return creds

def send_email_gmail(subject, body_html):
    """Sends an email using the Gmail API."""
    if not RECIPIENT_EMAIL:
        print("Error: RECIPIENT_EMAIL environment variable must be set.")
        return False

    creds = get_gmail_credentials()
    if not creds:
        print("Error: Could not authenticate with Gmail.")
        return False
        
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        message = MIMEText(body_html, 'html')
        message['to'] = RECIPIENT_EMAIL
        message['subject'] = subject
        
        # The 'from' field is automatically set to the authenticated user's email.
        # The 'userId' is 'me', which also refers to the authenticated user.
        encoded_message = {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}
        
        sent_message = service.users().messages().send(userId='me', body=encoded_message).execute()
        print(f"Email sent! Message ID: {sent_message['id']}")
        return True

    except HttpError as error:
        print(f'An error occurred: {error}')
        return False


def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    This function crawls the forum, filters posts, and sends an email via Gmail.
    """
    print("Starting crawler and post processing...")
    
    # 1. Crawl the forum
    crawler = TurtleForumCrawler()
    posts = crawler.crawl_forum(max_pages=2)
    
    # 2. Load keywords
    keywords = load_keywords(KEYWORDS_FILE)
    if not keywords:
        print("Could not load keywords. Exiting.")
        return {'statusCode': 400, 'body': json.dumps('Failed to load keywords.json.')}

    # 3. Filter posts
    filtered_posts = filter_posts_by_keywords(posts, keywords)
    if not filtered_posts:
        print("No new posts matching keywords found.")
        return {'statusCode': 200, 'body': json.dumps('No new posts matching keywords.')}

    print(f"Found {len(filtered_posts)} posts matching keywords.")
    
    # 4. Send email
    email_subject = 'New Turtle Forum Posts Found!'
    email_body = format_email_body(filtered_posts)
    success = send_email_gmail(email_subject, email_body)

    if success:
        return {'statusCode': 200, 'body': json.dumps(f'Email sent with {len(filtered_posts)} posts.')}
    else:
        return {'statusCode': 500, 'body': json.dumps('Failed to send email.')}


if __name__ == '__main__':
    """
    For local testing.
    -   You MUST have a 'credentials.json' file from Google Cloud in this directory.
    -   Run this script once to go through the OAuth flow and create 'token.json'.
    -   Set the RECIPIENT_EMAIL environment variable.
    """
    if not os.path.exists('credentials.json'):
        print("FATAL: 'credentials.json' not found. Please download it from your Google Cloud project.")
    elif not RECIPIENT_EMAIL:
         print("--- Testing without sending email ---")
         print("Set the RECIPIENT_EMAIL environment variable to test email sending.")
         crawler = TurtleForumCrawler()
         posts = crawler.crawl_forum(max_pages=2)
         keywords = load_keywords(KEYWORDS_FILE)
         if keywords:
             filtered_posts = filter_posts_by_keywords(posts, keywords)
             print(f"\nFound {len(filtered_posts)} matching posts:")
             for post in filtered_posts:
                 print(f"- {post.get('title')}")
    else:
        # Run the full Lambda handler for local testing with email
        lambda_handler(None, None)
