#!/usr/bin/env python3
"""
Content extraction utilities for news scrapers
Fetches full article content from URLs
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin, urlparse
import sys

# Fix Windows Unicode encoding issues
if sys.platform == "win32":
    import codecs
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
    except:
        pass  # Fallback if encoding fix fails

def clean_text(text):
    """Clean and normalize text content"""
    if not text:
        return ""
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    # Remove common unwanted patterns
    text = re.sub(r'(Citește mai mult|Citeste mai mult|Continuă citirea|Vezi mai mult)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(Foto:|Photo:|Video:|FOTO:|VIDEO:)', '', text, flags=re.IGNORECASE)
    return text.strip()

def extract_article_content(url, source_name=""):
    """
    Extract full article content from a given URL with guaranteed timeout protection
    Returns the full text content or None if extraction fails
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ro-RO,ro;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        print(f"🔍 Fetching content from: {url[:80]}...", file=sys.stderr)
        
        # ULTRA-ROBUST error handling with multiple timeout layers
        import time
        start_time = time.time()
        
        try:
            # Use aggressive timeout settings to prevent hanging
            response = requests.get(
                url, 
                headers=headers, 
                timeout=(5, 8),  # (connect_timeout, read_timeout) - very aggressive
                verify=True,
                allow_redirects=True,
                stream=False  # Download all content at once
            )
            response.raise_for_status()
            
            fetch_time = time.time() - start_time
            print(f"🌐 Network fetch completed in {fetch_time:.2f}s", file=sys.stderr)
            
        except requests.exceptions.ConnectTimeout:
            print(f"⏱️ Connect timeout for {url} (>5s)", file=sys.stderr)
            return None
        except requests.exceptions.ReadTimeout:
            print(f"⏱️ Read timeout for {url} (>8s)", file=sys.stderr)
            return None
        except requests.exceptions.Timeout:
            print(f"⏱️ General timeout for {url}", file=sys.stderr)
            return None
        except requests.exceptions.SSLError as ssl_err:
            print(f"❌ SSL Error for {url}: {ssl_err}", file=sys.stderr)
            return None
        except requests.exceptions.RequestException as req_err:
            print(f"🌐 Request Error for {url}: {req_err}", file=sys.stderr)
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'advertisement']):
            tag.decompose()
        
        # Try different extraction strategies based on the source
        content = None
        
        if 'adevarul.ro' in url.lower():
            content = extract_adevarul_content(soup)
        elif 'biziday.ro' in url.lower():
            content = extract_biziday_content(soup)
        else:
            # Generic extraction
            content = extract_generic_content(soup)
        
        if content and len(content) > 100:
            print(f"✅ Extracted {len(content)} characters of content", file=sys.stderr)
            return content
        else:
            print(f"⚠️  Content extraction failed or too short ({len(content or '')} chars)", file=sys.stderr)
            return None
            
    except requests.RequestException as e:
        print(f"❌ Network error fetching {url}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"❌ Error extracting content from {url}: {e}", file=sys.stderr)
        return None

def extract_adevarul_content(soup):
    """Extract content specifically from Adevarul.ro articles"""
    try:
        # Try multiple selectors for Adevarul content
        content_selectors = [
            'div.article-content',
            'div.content-article',
            'div.entry-content',
            'article .content',
            'div.post-content',
            '.articleContent',
            '.article-body'
        ]
        
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Extract all paragraphs
                paragraphs = content_div.find_all(['p', 'div'], recursive=True)
                content_parts = []
                
                for p in paragraphs:
                    text = clean_text(p.get_text())
                    if text and len(text) > 20:  # Only meaningful paragraphs
                        content_parts.append(text)
                
                if content_parts:
                    full_content = ' '.join(content_parts)
                    print(f"✅ Adevarul content extracted with selector: {selector}", file=sys.stderr)
                    return full_content
        
        # Fallback: extract all text from article tag
        article = soup.find('article')
        if article:
            text = clean_text(article.get_text())
            if len(text) > 200:
                return text
        
        return None
        
    except Exception as e:
        print(f"❌ Error in Adevarul content extraction: {e}", file=sys.stderr)
        return None

def extract_biziday_content(soup):
    """Extract content specifically from Biziday.ro articles"""
    try:
        # Try multiple selectors for Biziday content
        content_selectors = [
            'div.post-content',
            'div.entry-content',
            'article .content',
            'div.article-content',
            '.post-body',
            '.content-area'
        ]
        
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Extract all paragraphs
                paragraphs = content_div.find_all(['p', 'div'], recursive=True)
                content_parts = []
                
                for p in paragraphs:
                    text = clean_text(p.get_text())
                    if text and len(text) > 20:  # Only meaningful paragraphs
                        content_parts.append(text)
                
                if content_parts:
                    full_content = ' '.join(content_parts)
                    print(f"✅ Biziday content extracted with selector: {selector}", file=sys.stderr)
                    return full_content
        
        # Fallback: look for main content area
        main_content = soup.find('main') or soup.find('article')
        if main_content:
            text = clean_text(main_content.get_text())
            if len(text) > 200:
                return text
        
        return None
        
    except Exception as e:
        print(f"❌ Error in Biziday content extraction: {e}", file=sys.stderr)
        return None

def extract_generic_content(soup):
    """Generic content extraction for any website"""
    try:
        # Try common content selectors
        content_selectors = [
            'article',
            '[role="main"]',
            'main',
            '.content',
            '.post-content',
            '.entry-content',
            '.article-content',
            '.story-content',
            '.news-content'
        ]
        
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                text = clean_text(content_div.get_text())
                if len(text) > 200:
                    print(f"✅ Generic content extracted with selector: {selector}", file=sys.stderr)
                    return text
        
        # Last resort: get all paragraphs from body
        paragraphs = soup.find_all('p')
        if paragraphs:
            content_parts = []
            for p in paragraphs:
                text = clean_text(p.get_text())
                if text and len(text) > 20:
                    content_parts.append(text)
            
            if content_parts and len(content_parts) >= 3:  # At least 3 meaningful paragraphs
                full_content = ' '.join(content_parts)
                if len(full_content) > 200:
                    return full_content
        
        return None
        
    except Exception as e:
        print(f"❌ Error in generic content extraction: {e}", file=sys.stderr)
        return None

def generate_summary_from_content(content, max_length=100):
    """Generate a summary from full content (first 100 characters)"""
    if not content:
        return ""
    
    # Clean the content
    clean_content = clean_text(content)
    
    # Take first 100 characters and try to end at a word boundary
    if len(clean_content) <= max_length:
        return clean_content
    
    # Find a good breaking point (sentence or word boundary)
    truncated = clean_content[:max_length]
    
    # Try to end at sentence boundary
    sentence_end = truncated.rfind('. ')
    if sentence_end > max_length * 0.7:  # If sentence end is reasonably close
        return truncated[:sentence_end + 1]
    
    # Try to end at word boundary
    word_end = truncated.rfind(' ')
    if word_end > max_length * 0.8:  # If word end is reasonably close
        return truncated[:word_end] + '...'
    
    # Fallback: just truncate and add ellipsis
    return truncated + '...'

def extract_article_metadata(url, source_name=""):
    """
    Extract metadata from an article page including published_at and updated_at
    Returns a dictionary with extracted metadata
    """
    try:
        # Import timestamp utilities
        try:
            from .timestamp_utils import (
                extract_published_date_from_content, 
                extract_updated_date_from_content,
                format_for_database
            )
        except ImportError:
            from timestamp_utils import (
                extract_published_date_from_content, 
                extract_updated_date_from_content,
                format_for_database
            )
        
        metadata = {
            'published_at': None,
            'updated_at': None
        }
        
        # Extract published date
        published_dt = extract_published_date_from_content(url, source_name)
        if published_dt:
            metadata['published_at'] = format_for_database(published_dt)
        
        # Extract updated date
        updated_dt = extract_updated_date_from_content(url, source_name)
        if updated_dt:
            metadata['updated_at'] = format_for_database(updated_dt)
        
        print(f"📅 Metadata for {url[:50]}...: published={metadata['published_at']}, updated={metadata['updated_at']}", file=sys.stderr)
        return metadata
        
    except Exception as e:
        print(f"❌ Error extracting metadata from {url}: {e}", file=sys.stderr)
        return {'published_at': None, 'updated_at': None}

def test_content_extraction():
    """Test the content extraction functions"""
    test_urls = [
        'https://adevarul.ro/stiri-interne/politica/psd-si-pnl-ar-putea-sa-intre-la-guvernare-cu-usr-2425668.html',
        'https://www.biziday.ro/ultima-ora-marile-banci-din-romania-au-inchis-mii-de-conturi/'
    ]
    
    for url in test_urls:
        print(f"\n🧪 Testing content extraction for: {url}")
        content = extract_article_content(url)
        if content:
            summary = generate_summary_from_content(content)
            print(f"📝 Content length: {len(content)} characters")
            print(f"📋 Summary: {summary}")
        else:
            print("❌ Failed to extract content")

if __name__ == '__main__':
    test_content_extraction()
