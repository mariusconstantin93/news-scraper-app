#!/usr/bin/env python3
"""
Adevarul.ro News Scraper
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
    from .timestamp_utils import extract_published_date_from_content, get_romania_now, format_for_database
except ImportError:
    # Fallback for when running as script
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from content_extractor import extract_article_content, generate_summary_from_content, extract_article_metadata
    from timestamp_utils import extract_published_date_from_content, get_romania_now, format_for_database

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

def extract_adevarul_articles():
    """Extract articles from Adevarul.ro homepage - OPTIMIZED VERSION"""
    articles = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ro-RO,ro;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        print("🔍 Fetching Adevarul homepage with enhanced selectors...", file=sys.stderr)
        
        # Enhanced error handling for network requests
        try:
            response = requests.get('https://adevarul.ro/', headers=headers, timeout=20, verify=True)
            response.raise_for_status()
        except requests.exceptions.SSLError as ssl_err:
            print(f"❌ SSL Error accessing Adevarul homepage: {ssl_err}", file=sys.stderr)
            return []
        except requests.exceptions.ConnectTimeout as timeout_err:
            print(f"⏱️ Timeout Error accessing Adevarul homepage: {timeout_err}", file=sys.stderr)
            return []
        except requests.exceptions.RequestException as req_err:
            print(f"🌐 Request Error accessing Adevarul homepage: {req_err}", file=sys.stderr)
            # Check if it's a blocking issue
            if "403" in str(req_err) or "Forbidden" in str(req_err):
                print("🚫 Detected IP blocking - switching to fallback mode", file=sys.stderr)
                return extract_adevarul_fallback()
            return extract_adevarul_fallback()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("📰 Searching for articles using multiple strategies...", file=sys.stderr)
        
        # STRATEGY 1: Enhanced selectors based on HTML analysis
        enhanced_selectors = [
            # Primary selectors for main articles
            'a.title.titleAndHeadings[href*="adevarul.ro"]',
            'a[data-gtrack*="homepage"][href*="adevarul.ro"]',
            'a[data-gtrack*="box_deschidere"][href*="adevarul.ro"]',
            
            # Secondary selectors for additional articles
            'a.item.svelte-hjtm2f[href*="adevarul.ro"]',
            'a[href*="adevarul.ro"][class*="title"]',
            'a[href*="adevarul.ro"][class*="svelte"]',
            
            # Catch-all for any adevarul.ro links with tracking
            'a[data-gtrack][href*="adevarul.ro"]'
        ]
        
        found_articles = set()
        
        # Collect all potential articles
        for selector in enhanced_selectors:
            try:
                elements = soup.select(selector)
                print(f"   🔗 Selector '{selector}' found {len(elements)} elements", file=sys.stderr)
                
                for element in elements:
                    href = element.get('href', '')
                    if href and href not in found_articles:
                        # Only include actual article URLs
                        if any(section in href for section in [
                            '/stiri-', '/politica/', '/economie/', '/sport/', '/stil-de-viata/', 
                            '/showbiz/', '/tech/', '/istoria-zilei/', '/blogurile-adevarul/',
                            '/stiri-externe/', '/stiri-interne/', '/stiri-locale/'
                        ]):
                            found_articles.add(href)
                            
            except Exception as e:
                print(f"   ⚠️  Selector error: {e}", file=sys.stderr)
                continue
        
        print(f"🎯 Found {len(found_articles)} unique article URLs", file=sys.stderr)
        
        # STRATEGY 2: Process each article URL and extract title/summary
        processed_urls = set()
        
        # Limit to 200 articles for faster processing (avoid timeout)
        max_articles = 200
        print(f"📋 Processing maximum {max_articles} articles to avoid timeout", file=sys.stderr)
        
        for href in list(found_articles)[:max_articles]:
            try:
                # Skip duplicates and invalid URLs
                clean_href = href.split('#')[0].split('?')[0]  # Remove fragments and parameters
                if clean_href in processed_urls:
                    continue
                    
                # Skip non-article links
                if any(skip in href for skip in [
                    '#comments', '/tag/', '/author/', 'facebook.com', 'twitter.com',
                    '.jpg', '.png', '.pdf', '/rss/', '/search', 'mailto:'
                ]):
                    continue
                
                processed_urls.add(clean_href)
                
                # Find the element containing this URL to extract title and summary
                title = ""
                summary = ""
                
                # Method A: Find by exact href match
                link_element = soup.find('a', href=href)
                if not link_element:
                    # Method B: Find by partial href match
                    link_elements = soup.find_all('a', href=lambda x: x and clean_href in x)
                    if link_elements:
                        link_element = link_elements[0]
                
                if link_element:
                    # Extract title from the link text
                    title_text = clean_text(link_element.get_text())
                    
                    # Enhanced title extraction for different structures
                    if not title_text or len(title_text) < 15:
                        # Try to find title in child elements
                        title_elem = link_element.find(class_=lambda x: x and 'title' in str(x))
                        if title_elem:
                            title_text = clean_text(title_elem.get_text())
                    
                    # Clean and validate title
                    if title_text and len(title_text) >= 15:
                        # Remove video indicators and other prefixes
                        title_text = re.sub(r'^(Video\s*)?', '', title_text, flags=re.IGNORECASE)
                        title = title_text.strip()
                    
                    # Extract summary from parent container
                    parent_container = link_element.find_parent()
                    if parent_container:
                        # Look for summary class
                        summary_elem = parent_container.find(class_=lambda x: x and 'summary' in str(x))
                        if summary_elem:
                            summary = clean_text(summary_elem.get_text())
                        
                        # If no summary found, look for any text content nearby
                        if not summary:
                            text_elements = parent_container.find_all(text=True)
                            for text in text_elements:
                                text_content = clean_text(str(text))
                                if text_content and len(text_content) > 50 and text_content != title:
                                    summary = text_content[:300]
                                    break
                
                # Skip if no valid title found
                if not title or len(title) < 15:
                    continue
                
                # Skip navigation and non-article titles
                if any(skip in title.lower() for skip in [
                    'vezi toate', 'citește mai mult', 'mai multe din', 'comentarii',
                    'homepage', 'menu', 'contact', 'despre', 'află mai mult'
                ]):
                    continue
                
                # Use title as summary if no summary found
                if not summary or len(summary) < 20:
                    summary = title[:200] + "..." if len(title) > 200 else title
                
                # Create article object with content extraction (with timeout protection)
                full_content = None
                metadata = {'published_at': None, 'updated_at': None}
                
                try:
                    # Extract content with timeout protection
                    full_content = extract_article_content(clean_href, "adevarul")
                    print(f"✅ Content extracted for: {title[:30]}...", file=sys.stderr)
                except Exception as e:
                    print(f"⚠️  Content extraction failed for {clean_href}: {e}", file=sys.stderr)
                
                try:
                    # Extract metadata (published_at and updated_at) from the article page
                    metadata = extract_article_metadata(clean_href, "adevarul")
                    print(f"📅 Metadata extracted: pub={metadata.get('published_at')}, upd={metadata.get('updated_at')}", file=sys.stderr)
                except Exception as e:
                    print(f"⚠️  Metadata extraction failed for {clean_href}: {e}", file=sys.stderr)
                
                # Use published_at from metadata if available, otherwise from old method
                final_published_at = metadata.get('published_at')
                if not final_published_at:
                    # Extract published date from article (legacy method)
                    published_date = extract_published_date_from_content(clean_href, "adevarul")
                    final_published_at = format_for_database(published_date)
                
                # Get updated_at from metadata (could be None)
                updated_at = metadata.get('updated_at')  # This can be None
                
                # Generate summary from content or use fallback
                if full_content and len(full_content) > 100:
                    final_summary = generate_summary_from_content(full_content, 100)
                    print(f"✅ Generated summary from content: {final_summary[:50]}...", file=sys.stderr)
                else:
                    # Fallback to extracted summary or title
                    final_summary = summary if summary and len(summary) > 20 else (title[:100] + "..." if len(title) > 100 else title)
                    print(f"⚠️  Using fallback summary: {final_summary[:50]}...", file=sys.stderr)
                
                article_data = {
                    'title': title,
                    'summary': final_summary,
                    'content': full_content,  # Include full content
                    'link': clean_href,
                    'published_at': final_published_at,  # Real publication date from metadata
                    'updated_at': updated_at,  # Real update date or None
                    'timestamp': get_romania_now().isoformat()  # Data extragerii (pentru compatibilitate)
                }
                
                articles.append(article_data)
                print(f"✅ Extracted: {title[:70]}... (updated_at: {'Yes' if updated_at else 'None'})", file=sys.stderr)
                
            except Exception as e:
                print(f"⚠️  Error processing article {href}: {e}", file=sys.stderr)
                continue
        
        # Validation - no fallback needed since RSS runs separately
        if len(articles) < 5:
            print(f"⚠️  Only {len(articles)} articles found from homepage scraping", file=sys.stderr)
        
        print(f"🎉 Successfully extracted {len(articles)} articles from Adevarul homepage", file=sys.stderr)
        
    except requests.RequestException as e:
        print(f"❌ Network error fetching Adevarul homepage: {e}", file=sys.stderr)
        print("⚠️  Homepage scraping failed, returning empty list", file=sys.stderr)
        return []
        
    except Exception as e:
        print(f"💥 Unexpected error in homepage scraping: {e}", file=sys.stderr)
        print("⚠️  Homepage scraping failed, returning empty list", file=sys.stderr)
        return []
    
    return articles

def extract_adevarul_rss():
    """Fallback method: Extract articles from Adevarul RSS feed"""
    articles = []
    
    try:
        import xml.etree.ElementTree as ET
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        print("📡 Fetching Adevarul RSS feed...", file=sys.stderr)
        
        # Enhanced error handling for network requests  
        try:
            response = requests.get('https://adevarul.ro/rss/index', headers=headers, timeout=10, verify=True)
            response.raise_for_status()
        except requests.exceptions.SSLError as ssl_err:
            print(f"❌ SSL Error accessing Adevarul RSS: {ssl_err}", file=sys.stderr)
            return []
        except requests.exceptions.ConnectTimeout as timeout_err:
            print(f"⏱️ Timeout Error accessing Adevarul RSS: {timeout_err}", file=sys.stderr)
            return []
        except requests.exceptions.RequestException as req_err:
            print(f"🌐 Request Error accessing Adevarul RSS: {req_err}", file=sys.stderr)
            # Check if it's a blocking issue
            if "403" in str(req_err) or "Forbidden" in str(req_err):
                print("🚫 Detected IP blocking - switching to fallback mode", file=sys.stderr)
                return extract_adevarul_fallback()
            return extract_adevarul_fallback()
        
        # Parse RSS XML
        root = ET.fromstring(response.content)
        
        # Find all items in RSS
        items = root.findall('.//item')
        
        print(f"📰 Found {len(items)} items in RSS feed", file=sys.stderr)
        
        for item in items[:200]:  # Limit to 200 articles
            try:
                title_elem = item.find('title')
                description_elem = item.find('description')
                link_elem = item.find('link')
                pubdate_elem = item.find('pubDate')
                
                title = clean_text(title_elem.text) if title_elem is not None else ""
                description = clean_text(description_elem.text) if description_elem is not None else ""
                link = link_elem.text.strip() if link_elem is not None else ""
                pubdate = pubdate_elem.text.strip() if pubdate_elem is not None else ""
                
                # Skip if essential fields are missing
                if not title or not link or len(title) < 10:
                    continue
                
                # Convert pubDate to ISO format for published_at
                published_at = None
                if pubdate:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pubdate)
                        published_at = dt.isoformat()
                    except:
                        published_at = get_romania_now().isoformat()
                else:
                    published_at = get_romania_now().isoformat()
                
                # Extract full content from the article URL
                full_content = extract_article_content(link, "adevarul")
                
                # Extract metadata (updated_at) from the article page
                metadata = extract_article_metadata(link, "adevarul")
                updated_at = metadata.get('updated_at')  # This can be None
                
                # Use published_at from RSS as primary source, but could also check metadata
                final_published_at = published_at
                if not final_published_at and metadata.get('published_at'):
                    final_published_at = metadata.get('published_at')
                
                # Generate summary from content or use description as fallback
                if full_content and len(full_content) > 100:
                    final_summary = generate_summary_from_content(full_content, 100)
                    print(f"✅ RSS: Generated summary from content", file=sys.stderr)
                else:
                    # Use description as summary, fallback to title
                    final_summary = description if description else (title[:100] + "..." if len(title) > 100 else title)
                    print(f"⚠️  RSS: Using fallback summary", file=sys.stderr)
                
                article_data = {
                    'title': title,
                    'summary': final_summary,
                    'content': full_content,  # Include full content
                    'link': link,
                    'published_at': final_published_at,  # Real publication date from RSS
                    'updated_at': updated_at  # Real update date or None
                }
                
                articles.append(article_data)
                print(f"✅ RSS: {title[:50]}... (updated_at: {'Yes' if updated_at else 'None'})", file=sys.stderr)
                
            except Exception as e:
                print(f"⚠️  Error processing RSS item: {e}", file=sys.stderr)
                continue
        
        print(f"🎉 Successfully extracted {len(articles)} articles from Adevarul RSS", file=sys.stderr)
        
    except Exception as e:
        print(f"❌ Error fetching RSS feed: {e}", file=sys.stderr)
        return extract_adevarul_fallback()
    
    return articles

def extract_adevarul_fallback():
    """Fallback method when Adevarul.ro blocks access"""
    print("🔄 Using fallback method for Adevarul scraping", file=sys.stderr)
    
    # Return minimal data to keep the system running
    fallback_articles = [
        {
            'title': 'Știri Adevarul.ro - Temporar indisponibil',
            'summary': 'Sistemul de extragere a știrilor de pe Adevarul.ro este temporar restricționat. Scraper-ul va încerca din nou la următoarea execuție.',
            'link': 'https://adevarul.ro/',
            'published_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
    ]
    
    print(f"🔄 Fallback method returned {len(fallback_articles)} placeholder articles", file=sys.stderr)
    return fallback_articles

def combine_and_deduplicate_articles(rss_articles, homepage_articles):
    """Combine articles from RSS and homepage, removing duplicates based on title and link"""
    try:
        print("🔄 Combining articles from RSS and homepage...", file=sys.stderr)
        
        all_articles = []
        seen_links = set()
        seen_titles = set()
        
        # Process RSS articles first (they have priority due to real-time updates)
        print("📡 Processing RSS articles (priority)...", file=sys.stderr)
        for article in rss_articles:
            link_key = article.get('link', '').split('?')[0].split('#')[0].lower()  # Clean URL
            title_key = clean_text(article.get('title', '')).lower()
            
            if link_key and link_key not in seen_links and title_key not in seen_titles:
                seen_links.add(link_key)
                seen_titles.add(title_key)
                all_articles.append(article)
                print(f"   ✅ Added RSS: {article.get('title', 'No title')[:50]}...", file=sys.stderr)
            else:
                print(f"   ⏭️  Skipped RSS duplicate: {article.get('title', 'No title')[:30]}...", file=sys.stderr)
        
        # Process homepage articles (additional content not in RSS)
        print("🏠 Processing homepage articles (additional)...", file=sys.stderr)
        for article in homepage_articles:
            link_key = article.get('link', '').split('?')[0].split('#')[0].lower()  # Clean URL
            title_key = clean_text(article.get('title', '')).lower()
            
            if link_key and link_key not in seen_links and title_key not in seen_titles:
                seen_links.add(link_key)
                seen_titles.add(title_key)
                all_articles.append(article)
                print(f"   ✅ Added Homepage: {article.get('title', 'No title')[:50]}...", file=sys.stderr)
            else:
                print(f"   ⏭️  Skipped Homepage duplicate: {article.get('title', 'No title')[:30]}...", file=sys.stderr)
        
        print(f"📊 Deduplication summary:", file=sys.stderr)
        print(f"   📡 RSS articles: {len(rss_articles)}", file=sys.stderr)
        print(f"   🏠 Homepage articles: {len(homepage_articles)}", file=sys.stderr)
        print(f"   🎯 Final unique articles: {len(all_articles)}", file=sys.stderr)
        
        return all_articles
        
    except Exception as e:
        print(f"⚠️  Error in deduplication: {e}", file=sys.stderr)
        # Fallback: return RSS articles if deduplication fails
        return rss_articles if rss_articles else homepage_articles

def main():
    """Main function - called when script is run directly"""
    try:
        print("🎯 Starting Adevarul scraper - Dual method approach", file=sys.stderr)
        
        # STEP 1: RSS Feed method (primary - real-time updates)
        print("📡 STEP 1: Extracting from RSS feed (real-time content)...", file=sys.stderr)
        rss_articles = extract_adevarul_rss()
        print(f"✅ RSS method yielded {len(rss_articles)} articles", file=sys.stderr)
        
        # STEP 2: Homepage scraping method (mandatory - additional content)
        print("� STEP 2: Extracting from homepage (additional content)...", file=sys.stderr)
        homepage_articles = extract_adevarul_articles()
        print(f"✅ Homepage method yielded {len(homepage_articles)} articles", file=sys.stderr)
        
        # STEP 3: Combine and deduplicate articles
        print("🔗 STEP 3: Combining and deduplicating articles...", file=sys.stderr)
        all_articles = combine_and_deduplicate_articles(rss_articles, homepage_articles)
        print(f"🎉 Final result: {len(all_articles)} unique articles", file=sys.stderr)
        
        # Output JSON to stdout for the scheduler with proper encoding
        json_output = json.dumps(all_articles, ensure_ascii=False, indent=2)
        print(json_output)
        
        # Exit with appropriate code
        sys.exit(0 if all_articles else 1)
        
    except Exception as e:
        print(f"💥 Fatal error in Adevarul scraper: {e}", file=sys.stderr)
        # Output empty array to prevent scheduler errors
        print("[]")
        sys.exit(1)

if __name__ == '__main__':
    main()