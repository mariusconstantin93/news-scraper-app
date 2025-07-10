#!/usr/bin/env python3
"""
Biziday.ro News Scraper
Extracts news articles and outputs JSON format for the scheduler
"""

import requests
from bs4 import BeautifulSoup
import json
import sys
import os
from datetime import datetime
import re
try:
    from .content_extractor import extract_article_content, generate_summary_from_content, extract_article_metadata
    from .timestamp_utils import extract_biziday_published_date, format_for_database, get_romania_now
except ImportError:
    # Fallback for when running as script
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from content_extractor import extract_article_content, generate_summary_from_content, extract_article_metadata
    from timestamp_utils import extract_biziday_published_date, format_for_database, get_romania_now

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
    return text

def extract_article_metadata(url, source_name=""):
    """
    Extract publication and modification dates from article page meta tags
    Returns dict with 'published_at' and 'updated_at' (can be None)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        
        # Enhanced error handling for network requests
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=True)
            response.raise_for_status()
        except requests.exceptions.SSLError as ssl_err:
            print(f"❌ SSL Error for {url}: {ssl_err}")
            return {'published_at': None, 'updated_at': None}
        except requests.exceptions.ConnectTimeout as timeout_err:
            print(f"⏱️ Timeout Error for {url}: {timeout_err}")
            return {'published_at': None, 'updated_at': None}
        except requests.exceptions.RequestException as req_err:
            print(f"🌐 Request Error for {url}: {req_err}")
            return {'published_at': None, 'updated_at': None}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        metadata = {
            'published_at': None,
            'updated_at': None
        }
        
        if 'biziday.ro' in url.lower():
            # Extract published date from article:published_time meta tag
            published_meta = soup.find('meta', {'property': 'article:published_time'})
            if published_meta:
                published_content = published_meta.get('content')
                if published_content:
                    try:
                        published_dt = datetime.fromisoformat(published_content.replace('Z', '+00:00'))
                        metadata['published_at'] = published_dt.isoformat()
                        print(f"📅 Found published date: {published_content}", file=sys.stderr)
                    except:
                        pass
            
            # Extract updated date from article:modified_time meta tag
            modified_meta = soup.find('meta', {'property': 'article:modified_time'})
            if modified_meta:
                modified_content = modified_meta.get('content')
                if modified_content:
                    try:
                        modified_dt = datetime.fromisoformat(modified_content.replace('Z', '+00:00'))
                        metadata['updated_at'] = modified_dt.isoformat()
                        print(f"🔄 Found updated date: {modified_content}", file=sys.stderr)
                    except:
                        pass
            
            # Also try to extract from time elements with datetime attributes
            if not metadata['published_at']:
                time_elements = soup.find_all('time')
                for time_elem in time_elements:
                    datetime_attr = time_elem.get('datetime')
                    if datetime_attr:
                        try:
                            parsed_time = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                            metadata['published_at'] = parsed_time.isoformat()
                            print(f"📅 Found published date from time element: {datetime_attr}", file=sys.stderr)
                            break
                        except:
                            continue
        
        return metadata
        
    except Exception as e:
        print(f"⚠️  Error extracting metadata from {url}: {e}", file=sys.stderr)
        return {'published_at': None, 'updated_at': None}

def extract_biziday_articles():
    """Extract articles from Biziday.ro"""
    articles = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print("🔍 Fetching Biziday.ro homepage...", file=sys.stderr)
        
        # Enhanced error handling for network requests
        try:
            response = requests.get('https://www.biziday.ro', headers=headers, timeout=10, verify=True)
            response.raise_for_status()
        except requests.exceptions.SSLError as ssl_err:
            print(f"❌ SSL Error accessing Biziday homepage: {ssl_err}", file=sys.stderr)
            return []
        except requests.exceptions.ConnectTimeout as timeout_err:
            print(f"⏱️ Timeout Error accessing Biziday homepage: {timeout_err}", file=sys.stderr)
            return []
        except requests.exceptions.RequestException as req_err:
            print(f"🌐 Request Error accessing Biziday homepage: {req_err}", file=sys.stderr)
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find article elements - updated selector based on the HTML structure
        article_elements = soup.find_all('li', class_='article')
        
        print(f"📊 Found {len(article_elements)} articles on page", file=sys.stderr)
        
        if not article_elements:
            print("⚠️  No articles found - trying alternative selectors", file=sys.stderr)
            # Try alternative selectors
            article_elements = soup.find_all('article') or soup.find_all('div', class_='post')
        
        # Remove the limit - extract ALL articles found
        for i, article in enumerate(article_elements):
            try:
                # Skip ad elements
                if article.get('class') and 'is-ad' in article.get('class'):
                    print(f"⏭️  Skipping ad element {i+1}", file=sys.stderr)
                    continue
                
                # Find the main link
                link_element = article.find('a', class_='post-url')
                if not link_element:
                    print(f"⚠️  No link found for article {i+1}", file=sys.stderr)
                    continue
                
                link = link_element.get('href')
                if not link:
                    print(f"⚠️  Empty link for article {i+1}", file=sys.stderr)
                    continue
                
                # Extract title
                title_element = article.find('h2', class_='post-title') or article.find('span', itemprop='headline')
                title = title_element.get_text(strip=True) if title_element else 'No title'
                
                # Extract summary/content
                content_div = article.find('div', class_='news-content')
                summary = ""
                if content_div:
                    # Try to find summary in various ways
                    summary_p = content_div.find('p') or content_div.find('div', class_='summary')
                    if summary_p:
                        summary = summary_p.get_text(strip=True)
                    elif title_element:
                        # Use title as summary if no separate summary found
                        summary = title[:200] + "..." if len(title) > 200 else title
                
                # Extract published date from time element
                time_element = article.find('time', class_='timeago')
                published_at = None
                if time_element:
                    datetime_attr = time_element.get('datetime')
                    if datetime_attr:
                        try:
                            # Parse the datetime - this is the real publication date
                            parsed_time = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                            published_at = parsed_time.isoformat()
                        except:
                            published_at = get_romania_now().isoformat()
                else:
                    published_at = get_romania_now().isoformat()
                
                # Extract full content from the article URL
                full_content = extract_article_content(link, "biziday")
                
                # Extract metadata (published_at and updated_at) from the article page
                metadata = extract_article_metadata(link, "biziday")
                
                # Use published_at from metadata if available, otherwise use time element
                final_published_at = metadata.get('published_at')
                if not final_published_at:
                    final_published_at = published_at
                
                # Get updated_at from metadata (could be None)
                updated_at = metadata.get('updated_at')  # This can be None
                
                # Generate summary from content or use fallback
                if full_content and len(full_content) > 100:
                    final_summary = generate_summary_from_content(full_content, 100)
                    print(f"✅ Generated summary from content: {final_summary[:50]}...", file=sys.stderr)
                else:
                    # Use extracted summary or title as fallback
                    final_summary = summary if summary and len(summary) > 20 else (title[:100] + "..." if len(title) > 100 else title)
                    print(f"⚠️  Using fallback summary: {final_summary[:50]}...", file=sys.stderr)
                
                # Ensure we have minimum required data
                if title and link and final_summary:
                    article_data = {
                        'title': title,
                        'summary': final_summary,
                        'content': full_content,  # Include full content
                        'link': link,
                        'published_at': final_published_at,  # Real publication date from meta tags
                        'updated_at': updated_at  # Real update date or None
                    }
                    articles.append(article_data)
                    print(f"✅ Extracted article {len(articles)}: {title[:50]}... (updated_at: {'Yes' if updated_at else 'None'})", file=sys.stderr)
                else:
                    print(f"⚠️  Skipping incomplete article {i+1}: title={bool(title)}, link={bool(link)}, summary={bool(summary)}", file=sys.stderr)
                    
            except Exception as e:
                print(f"❌ Error processing article {i+1}: {e}", file=sys.stderr)
                continue
        
        print(f"🎉 Successfully extracted {len(articles)} articles from Biziday", file=sys.stderr)
        
        # If no articles found, return mock data for testing
        if not articles:
            print("📝 No articles found, returning mock data for testing", file=sys.stderr)
            articles = [{
                'title': 'Test Article from Biziday - No Real Data Available',
                'summary': 'This is a test article because no real articles could be extracted from Biziday. The website might have anti-scraping measures or the structure has changed.',
                'link': 'https://www.biziday.ro/test-article',
                'timestamp': datetime.now().isoformat(),
                'published_at': datetime.now().isoformat()  # Fallback published date
            }]
        
        return articles
        
    except requests.RequestException as e:
        print(f"❌ Network error accessing Biziday: {e}", file=sys.stderr)
        # Return mock data for testing
        return [{
            'title': 'Network Error - Biziday Unavailable',
            'summary': f'Could not access Biziday.ro due to network error: {str(e)}. This is mock data for testing purposes.',
            'link': 'https://www.biziday.ro/network-error',
            'timestamp': datetime.now().isoformat(),
            'published_at': datetime.now().isoformat()  # Fallback published date
        }]
        
    except Exception as e:
        print(f"❌ Unexpected error in Biziday scraper: {e}", file=sys.stderr)
        # Return mock data for testing
        return [{
            'title': 'Scraper Error - Biziday',
            'summary': f'An unexpected error occurred while scraping Biziday: {str(e)}. This is mock data for testing purposes.',
            'link': 'https://www.biziday.ro/scraper-error',
            'timestamp': datetime.now().isoformat(),
            'published_at': datetime.now().isoformat()  # Fallback published date
        }]

def main():
    """Main function - called when script is run directly"""
    try:
        articles = extract_biziday_articles()
        
        # Output JSON to stdout for the scheduler with proper encoding
        json_output = json.dumps(articles, ensure_ascii=False, indent=2)
        print(json_output)
        
        # Exit with appropriate code
        sys.exit(0 if articles else 1)
        
    except Exception as e:
        print(f"💥 Fatal error in Biziday scraper: {e}", file=sys.stderr)
        # Output empty array to prevent scheduler errors
        print("[]")
        sys.exit(1)

if __name__ == '__main__':
    main()