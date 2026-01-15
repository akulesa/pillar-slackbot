import re
import requests
from typing import Optional
from html.parser import HTMLParser


class HTMLTextExtractor(HTMLParser):
    """Extract text content from HTML, ignoring scripts and styles."""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_data = False
        self.skip_tags = {'script', 'style', 'noscript', 'header', 'footer', 'nav'}

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip_data = True

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip_data = False

    def handle_data(self, data):
        if not self.skip_data:
            text = data.strip()
            if text:
                self.text_parts.append(text)

    def get_text(self):
        return ' '.join(self.text_parts)


class WebService:
    """Service for fetching and parsing web content."""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

    def fetch_url(self, url: str) -> Optional[str]:
        """Fetch content from a URL and return the text."""
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()

            if 'text/html' in content_type:
                return self._extract_text_from_html(response.text)
            elif 'text/plain' in content_type:
                return response.text
            elif 'application/json' in content_type:
                return response.text
            else:
                # Try to extract as HTML anyway
                return self._extract_text_from_html(response.text)

        except requests.exceptions.Timeout:
            print(f"Timeout fetching URL: {url}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching URL {url}: {e}")
            return None

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from HTML content."""
        # First try to get the main content
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def extract_urls_from_text(self, text: str) -> list:
        """Extract URLs from text."""
        # Match URLs including those in Slack's format <url|label>
        slack_url_pattern = r'<(https?://[^|>]+)(?:\|[^>]+)?>'
        slack_urls = re.findall(slack_url_pattern, text)

        # Also match plain URLs
        plain_url_pattern = r'(?<!<)(https?://[^\s<>]+)'
        plain_urls = re.findall(plain_url_pattern, text)

        # Combine and deduplicate
        all_urls = list(dict.fromkeys(slack_urls + plain_urls))

        return all_urls

    def get_page_title(self, html: str) -> Optional[str]:
        """Extract page title from HTML."""
        match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
