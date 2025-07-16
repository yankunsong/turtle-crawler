import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time

class TurtleForumCrawler:
    def __init__(self):
        self.base_url = "https://faunaclassifieds.com"
        self.forum_url = "https://faunaclassifieds.com/forums/forums/turtles-tortoises.54/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def fetch_page(self, url):
        """Fetch a page and return the BeautifulSoup object"""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def parse_thread_list(self, soup):
        """Parse the thread list from the forum page"""
        threads = []
        
        # Find all thread containers - typical XenForo structure
        thread_items = soup.find_all('div', class_='structItem--thread')
        
        for thread in thread_items:
            thread_data = {}
            
            # Get thread title and link
            title_elem = thread.find('a', {'data-tp-primary': 'on'})
            if not title_elem:
                title_elem = thread.find('h3', class_='structItem-title').find('a')
            
            if title_elem:
                thread_data['title'] = title_elem.text.strip()
                thread_data['url'] = self.base_url + title_elem.get('href', '')
            
            # Get thread author
            author_elem = thread.find('a', class_='username')
            if author_elem:
                thread_data['author'] = author_elem.text.strip()
            
            # Get last post info
            last_post_elem = thread.find('div', class_='structItem-cell--latest')
            if last_post_elem:
                last_post_time = last_post_elem.find('time')
                if last_post_time:
                    thread_data['last_post_time'] = last_post_time.get('datetime', '')
                
                last_poster = last_post_elem.find('a', class_='username')
                if last_poster:
                    thread_data['last_poster'] = last_poster.text.strip()
            
            # Get reply and view counts
            meta_elem = thread.find('div', class_='structItem-cell--meta')
            if meta_elem:
                reply_elem = meta_elem.find('dd')
                if reply_elem:
                    thread_data['replies'] = reply_elem.text.strip()
                
                views_elem = meta_elem.find_all('dd')
                if len(views_elem) > 1:
                    thread_data['views'] = views_elem[1].text.strip()
            
            if thread_data:
                threads.append(thread_data)
        
        return threads
    
    def crawl_forum(self, max_pages=1):
        """Crawl the forum and collect thread information"""
        all_threads = []
        
        for page in range(1, max_pages + 1):
            if page == 1:
                url = self.forum_url
            else:
                url = f"{self.forum_url}page-{page}"
            
            print(f"Crawling page {page}...")
            soup = self.fetch_page(url)
            
            if soup:
                threads = self.parse_thread_list(soup)
                all_threads.extend(threads)
                print(f"Found {len(threads)} threads on page {page}")
                
                # Be polite - add a small delay between requests
                if page < max_pages:
                    time.sleep(1)
            else:
                print(f"Failed to fetch page {page}")
                break
        
        return all_threads
    
    def save_results(self, threads, filename='turtle_forum_posts.json'):
        """Save the results to a JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(threads, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(threads)} threads to {filename}")
    
    def display_results(self, threads):
        """Display the results in a formatted way"""
        print(f"\nFound {len(threads)} threads:\n")
        for i, thread in enumerate(threads, 1):
            print(f"{i}. {thread.get('title', 'No title')}")
            print(f"   Author: {thread.get('author', 'Unknown')}")
            print(f"   Replies: {thread.get('replies', '0')}, Views: {thread.get('views', '0')}")
            print(f"   Last post by: {thread.get('last_poster', 'Unknown')}")
            print(f"   URL: {thread.get('url', 'No URL')}")
            print()

def main():
    # Create crawler instance
    crawler = TurtleForumCrawler()
    
    # Crawl the forum (you can increase max_pages to get more threads)
    print("Starting to crawl the Turtle & Tortoise forum...")
    threads = crawler.crawl_forum(max_pages=2)
    
    # Display results
    crawler.display_results(threads)
    
    # Save results to JSON file
    crawler.save_results(threads)
    
    print("\nCrawling completed!")

if __name__ == "__main__":
    main()
