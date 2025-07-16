# Turtle Forum Crawler

A web crawler for extracting posts from the Fauna Classifieds Turtle & Tortoise forum.

## Features

- Fetches thread listings from the forum
- Extracts thread metadata including:
  - Title
  - Author
  - URL
  - Reply count
  - View count
  - Last post information
- Saves results to JSON format
- Supports multi-page crawling
- Implements polite crawling with delays

## Installation

1. Clone this repository:

```bash
git clone <repository-url>
cd turtle-crawler
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the crawler with default settings (crawls first page only):

```bash
python main.py
```

The crawler will:

1. Fetch the forum page
2. Parse all thread information
3. Display results in the console
4. Save results to `turtle_forum_posts.json`

## Customization

To crawl multiple pages, modify the `max_pages` parameter in `main.py`:

```python
threads = crawler.crawl_forum(max_pages=5)  # Crawls first 5 pages
```

## Output Format

The crawler saves data in JSON format with the following structure:

```json
{
  "title": "Thread Title",
  "url": "https://faunaclassifieds.com/forums/threads/...",
  "author": "Username",
  "last_post_time": "2025-07-16T07:15:28-0400",
  "last_poster": "LastPosterName",
  "replies": "5",
  "views": "100"
}
```

## Notes

- The crawler includes a User-Agent header to identify itself properly
- A 1-second delay is added between page requests to be respectful to the server
- The forum appears to use XenForo forum software
