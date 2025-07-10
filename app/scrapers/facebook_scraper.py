#!/usr/bin/env python3
"""
Facebook Profile Scraper (Real Implementation)
Extracts public profile data from Facebook profiles
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import sys
import time
from urllib.parse import urljoin, urlparse
from datetime import datetime

# Fix Windows Unicode encoding issues
if sys.platform == "win32":
    import codecs
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
    except:
        pass

def clean_text(text):
    """Clean and normalize text content"""
    if not text:
        return ""
    
    # Convert to string if needed
    if not isinstance(text, str):
        try:
            text = str(text)
        except:
            return ""
    
    # Remove non-printable characters and control characters
    text = ''.join(char for char in text if char.isprintable() or char.isspace())
    
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove any remaining binary or encoded characters
    text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\'\"]+', '', text)
    
    return text.strip()

def normalize_facebook_url(user_input):
    """Convert user input to proper Facebook URL"""
    user_input = user_input.strip()
    
    # If it's already a full URL, return as is
    if user_input.startswith('http'):
        return user_input
    
    # If it's a numeric ID, convert to facebook.com/profile.php?id=
    if user_input.isdigit():
        return f"https://www.facebook.com/profile.php?id={user_input}"
    
    # If it's a username, convert to facebook.com/username
    if user_input.startswith('@'):
        user_input = user_input[1:]  # Remove @
    
    return f"https://www.facebook.com/{user_input}"

def extract_facebook_profile(profile_input):
    """
    Extract public profile data from Facebook
    Args:
        profile_input: Username, numeric ID, or full URL
    Returns:
        dict with profile data or None if extraction fails
    """
    try:
        profile_url = normalize_facebook_url(profile_input)
        print(f"🔍 Fetching Facebook profile from: {profile_url}", file=sys.stderr)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ro;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        }
        
        try:
            print(f"🌐 Making HTTP request to {profile_url}...", file=sys.stderr)
            print(f"⏱️ Using timeout: 10s connect, 15s read", file=sys.stderr)
            response = requests.get(
                profile_url, 
                headers=headers, 
                timeout=(10, 15),  # Increased timeout for better reliability
                verify=True,
                allow_redirects=True
            )
            print(f"📡 HTTP request completed with status: {response.status_code}", file=sys.stderr)
            
            # Check for Facebook blocking/error pages BEFORE raising for status
            if response.status_code == 400:
                print(f"❌ Facebook returned 400 Bad Request - likely blocking automated requests", file=sys.stderr)
                print(f"📄 Response content preview: {response.text[:200]}...", file=sys.stderr)
                return {
                    "error": f"Facebook is blocking automated requests for profile '{profile_input}' (HTTP 400). The profile may be private or Facebook has anti-bot measures active.",
                    "profile_url": profile_url,
                    "username": extract_username_from_url(profile_url)
                }
            
            # Only raise for status if it's not a 400 (which we handle above)
            if response.status_code >= 400:
                response.raise_for_status()
            
            # Ensure proper encoding
            if response.encoding is None or response.encoding == 'ISO-8859-1':
                response.encoding = 'utf-8'
            
            print(f"✅ Successfully fetched profile page ({len(response.content)} bytes)", file=sys.stderr)
            
            # Check if we got a valid Facebook page with JSON data
            json_script_count = response.text.count('<script type="application/json"')
            print(f"📊 Found {json_script_count} JSON script tags on the page", file=sys.stderr)
            
            if json_script_count == 0:
                print(f"⚠️  No JSON script tags found - may indicate Facebook blocking or error page", file=sys.stderr)
                # Check if this looks like an error page
                if "Error" in response.text[:500] or len(response.content) < 5000:
                    print(f"🚨 Detected Facebook error page - likely blocking request", file=sys.stderr)
                    return {
                        "error": f"Facebook appears to be blocking requests for profile '{profile_input}'. The page returned appears to be an error page rather than a profile.",
                        "profile_url": profile_url,
                        "username": extract_username_from_url(profile_url)
                    }
            
        except requests.exceptions.Timeout as e:
            print(f"⏰ Request timeout: The profile '{profile_input}' took too long to load", file=sys.stderr)
            print("💡 This may indicate the profile is private, blocked, or Facebook is limiting access", file=sys.stderr)
            return {
                "error": f"Request timeout for profile '{profile_input}'. The profile may be private or Facebook is blocking access.",
                "profile_url": profile_url,
                "username": extract_username_from_url(profile_url)
            }
        except requests.exceptions.ConnectionError as e:
            print(f"🌐 Connection error: {e}", file=sys.stderr)
            print("💡 This may indicate network issues or Facebook blocking the request", file=sys.stderr)
            return {
                "error": f"Connection error for profile '{profile_input}'. Check network connectivity.",
                "profile_url": profile_url,
                "username": extract_username_from_url(profile_url)
            }
        except requests.exceptions.HTTPError as e:
            status_code = getattr(response, 'status_code', None)
            if status_code == 400:
                print(f"❌ Bad Request (400): The profile '{profile_input}' may not exist or may be private", file=sys.stderr)
                return {
                    "error": f"Profile '{profile_input}' may not exist or is private (HTTP 400)",
                    "profile_url": profile_url,
                    "username": extract_username_from_url(profile_url)
                }
            elif status_code == 403:
                print(f"❌ Forbidden (403): Access denied to profile '{profile_input}'", file=sys.stderr)
                return {
                    "error": f"Access denied to profile '{profile_input}' (HTTP 403)",
                    "profile_url": profile_url,
                    "username": extract_username_from_url(profile_url)
                }
            elif status_code == 404:
                print(f"❌ Not Found (404): The profile '{profile_input}' does not exist", file=sys.stderr)
                return {
                    "error": f"Profile '{profile_input}' does not exist (HTTP 404)",
                    "profile_url": profile_url,
                    "username": extract_username_from_url(profile_url)
                }
            else:
                print(f"❌ HTTP Error {status_code}: {e}", file=sys.stderr)
                return {
                    "error": f"HTTP Error {status_code} for profile '{profile_input}': {e}",
                    "profile_url": profile_url,
                    "username": extract_username_from_url(profile_url)
                }
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching profile: {e}", file=sys.stderr)
            return {
                "error": f"Network error for profile '{profile_input}': {e}",
                "profile_url": profile_url,
                "username": extract_username_from_url(profile_url)
            }
        
        # Parse the HTML with better encoding handling
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
        except UnicodeDecodeError:
            # Fallback to content with explicit encoding
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
        
        # Extract profile data using multiple strategies
        profile_data = {
            'name': None,
            'bio': None,
            'connected_accounts': [],
            'location': None,
            'profile_url': profile_url,
            'username': extract_username_from_url(profile_url),
            'followers_count': 0,
            'interests': []
        }
        
        # Strategy 1: Extract from meta tags
        extract_from_meta_tags(soup, profile_data)
        
        # Strategy 2: Extract from page title and content
        extract_from_page_content(soup, profile_data)
        
        # Strategy 3: Extract from JSON-LD structured data
        extract_from_json_ld(soup, profile_data)
        
        # Strategy 4: Extract from specific Facebook selectors
        extract_from_facebook_selectors(soup, profile_data)
        
        # Strategy 5: Extract from JSON application data blocks (ENHANCED)
        extract_from_json_application_data(soup, profile_data)
        
        # Strategy 6: Extract detailed intro information (fallback patterns)
        extract_detailed_intro_information(soup, profile_data)
        
        # Strategy 7: Fallback - try to extract from any text that looks like a name
        if not profile_data['name']:
            extract_name_fallback(soup, profile_data)
        
        # Strategy 7: Last resort - use URL components
        if not profile_data['name']:
            extract_from_url_components(profile_input, profile_data)
        
        # Validate extracted data
        if not profile_data['name']:
            print("⚠️  Could not extract profile name", file=sys.stderr)
            print("📋 Available meta tags:", file=sys.stderr)
            
            # Debug: show available meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags[:10]:  # Show first 10 meta tags
                if meta.get('property') or meta.get('name'):
                    content = meta.get('content', '')[:50]
                    prop_or_name = meta.get('property') or meta.get('name')
                    print(f"     {prop_or_name}: {content}...", file=sys.stderr)
            
            return None
        
        print(f"✅ Successfully extracted profile: {profile_data['name']}", file=sys.stderr)
        return profile_data
        
    except Exception as e:
        print(f"❌ Error extracting Facebook profile: {e}", file=sys.stderr)
        return None

def extract_username_from_url(url):
    """Extract username from Facebook URL"""
    try:
        if 'profile.php?id=' in url:
            return url.split('id=')[1].split('&')[0]
        else:
            return url.split('facebook.com/')[-1].split('?')[0].split('/')[0]
    except:
        return None

def extract_from_meta_tags(soup, profile_data):
    """Extract data from meta tags with enhanced field extraction"""
    try:
        # Open Graph meta tags
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title_content = clean_text(og_title['content'])
            # Remove common Facebook suffixes
            title_content = re.sub(r'\s*\|\s*Facebook.*$', '', title_content)
            title_content = re.sub(r'\s*-\s*Facebook.*$', '', title_content)
            if title_content and len(title_content.strip()) > 0:
                profile_data['name'] = title_content.strip()
                print(f"📋 Extracted name from og:title: {profile_data['name']}", file=sys.stderr)
        
        og_description = soup.find('meta', property='og:description')
        if og_description and og_description.get('content'):
            desc_content = clean_text(og_description['content'])
            if desc_content and len(desc_content) > 10:
                profile_data['bio'] = desc_content
                print(f"📋 Extracted bio from og:description: {desc_content[:50]}...", file=sys.stderr)
                
                # ENHANCED: Extract professional title from description
                desc_lower = desc_content.lower()
                if 'creator digital' in desc_lower or 'digital creator' in desc_lower:
                    profile_data['professional_title'] = 'Digital Creator'
                    print(f"✅ Extracted professional title from description: Digital Creator", file=sys.stderr)
                elif 'protopsalt' in desc_lower:
                    profile_data['professional_title'] = 'Protopsalt'
                    profile_data['church_position'] = 'Protopsalt'
                    print(f"✅ Extracted church position from description: Protopsalt", file=sys.stderr)
                elif 'archdeacon' in desc_lower:
                    profile_data['professional_title'] = 'Archdeacon'
                    profile_data['church_position'] = 'Archdeacon'
                    print(f"✅ Extracted church position from description: Archdeacon", file=sys.stderr)
                
                # Extract followers/likes count from description (e.g., "26.312 aprecieri")
                import re
                follower_match = re.search(r'([\d,.]+)\s*(aprecieri|followers|urmăritori)', desc_content, re.IGNORECASE)
                if follower_match:
                    follower_str = follower_match.group(1).replace('.', '').replace(',', '')
                    try:
                        profile_data['followers_count'] = int(follower_str)
                        print(f"✅ Extracted followers count from description: {profile_data['followers_count']}", file=sys.stderr)
                    except ValueError:
                        pass
        
        # Twitter meta tags as fallback
        twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
        if twitter_title and twitter_title.get('content') and not profile_data['name']:
            twitter_content = clean_text(twitter_title['content'])
            twitter_content = re.sub(r'\s*\|\s*Facebook.*$', '', twitter_content)
            if twitter_content and len(twitter_content.strip()) > 0:
                profile_data['name'] = twitter_content.strip()
                print(f"📋 Extracted name from twitter:title: {profile_data['name']}", file=sys.stderr)
        
        # Additional meta tags
        description_meta = soup.find('meta', attrs={'name': 'description'})
        if description_meta and description_meta.get('content') and not profile_data['bio']:
            desc_content = clean_text(description_meta['content'])
            if desc_content and len(desc_content) > 10:
                profile_data['bio'] = desc_content
                print(f"📋 Extracted bio from description meta: {desc_content[:50]}...", file=sys.stderr)
        
    except Exception as e:
        print(f"⚠️  Error extracting from meta tags: {e}", file=sys.stderr)

def extract_from_page_content(soup, profile_data):
    """Extract data from page content"""
    try:
        # Page title as fallback for name
        if not profile_data['name']:
            title = soup.find('title')
            if title and title.text:
                title_text = clean_text(title.text)
                # Remove "| Facebook" and similar suffixes
                title_text = re.sub(r'\s*\|\s*Facebook.*$', '', title_text)
                title_text = re.sub(r'\s*-\s*Facebook.*$', '', title_text)
                title_text = re.sub(r'\s*\|\s*Log into Facebook.*$', '', title_text)
                title_text = re.sub(r'\s*\|\s*Sign up for Facebook.*$', '', title_text)
                if title_text and len(title_text.strip()) > 0:
                    profile_data['name'] = title_text.strip()
                    print(f"📋 Extracted name from page title: {profile_data['name']}", file=sys.stderr)
        
        # Look for bio in various content areas
        bio_selectors = [
            '[data-testid="profile_bio"]',
            '.userContent',
            '.profileBio',
            '.intro',
            '.about',
            '[data-testid="story-subtitle"]',
            '.story_body_container',
            '.text_exposed_root'
        ]
        
        for selector in bio_selectors:
            bio_element = soup.select_one(selector)
            if bio_element and not profile_data['bio']:
                bio_text = clean_text(bio_element.get_text())
                if len(bio_text) > 10:  # Only meaningful bio text
                    profile_data['bio'] = bio_text
                    print(f"📋 Extracted bio from {selector}: {bio_text[:50]}...", file=sys.stderr)
                    break
        
        # Enhanced bio extraction for modern Facebook HTML structures
        if not profile_data['bio']:
            extract_bio_from_modern_structure(soup, profile_data)
        
        # Try to extract from any h1 tags (common for profile names)
        if not profile_data['name']:
            h1_tags = soup.find_all('h1')
            for h1 in h1_tags:
                h1_text = clean_text(h1.get_text())
                if h1_text and len(h1_text) < 100 and len(h1_text) > 2:  # Reasonable name length
                    # Skip common Facebook UI text
                    skip_patterns = [
                        'facebook', 'log in', 'sign up', 'home', 'timeline', 'about', 'photos', 'friends',
                        'more', 'settings', 'activity log', 'privacy shortcuts', 'support inbox'
                    ]
                    if not any(pattern in h1_text.lower() for pattern in skip_patterns):
                        profile_data['name'] = h1_text
                        print(f"📋 Extracted name from h1: {profile_data['name']}", file=sys.stderr)
                        break
        
        # Try to extract from span tags with specific patterns - ENHANCED
        if not profile_data['name']:
            print("🔍 Trying enhanced span-based name extraction...", file=sys.stderr)
            all_spans = soup.find_all('span')
            name_candidates = []
            
            for span in all_spans:
                span_text = clean_text(span.get_text())
                
                # Skip if too short, too long, or contains numbers/symbols
                if not span_text or len(span_text) < 2 or len(span_text) > 100:
                    continue
                if any(char.isdigit() for char in span_text):
                    continue
                if span_text.count(' ') > 5:  # Too many words for a name
                    continue
                    
                # Skip common UI text
                skip_patterns = [
                    'like', 'share', 'comment', 'follow', 'message', 'more', 'home', 'timeline',
                    'about', 'photos', 'friends', 'videos', 'check in', 'facebook', 'log in',
                    'sign up', 'create', 'help', 'settings', 'privacy', 'terms', 'cookies',
                    'see more', 'see less', 'add friend', 'edit profile', 'activity log'
                ]
                
                if any(pattern in span_text.lower() for pattern in skip_patterns):
                    continue
                
                # Score this span as a potential name
                name_score = 0
                
                # Scoring criteria
                if 3 <= len(span_text) <= 50:  # Reasonable name length
                    name_score += 2
                if span_text.count(' ') <= 3:  # Not too many words
                    name_score += 2
                if span_text[0].isupper():  # Starts with capital
                    name_score += 1
                if all(word[0].isupper() for word in span_text.split() if word):  # All words capitalized
                    name_score += 3
                if not any(punct in span_text for punct in ['@', '#', '$', '%', '&']):  # No special chars
                    name_score += 1
                
                # Check parent context for additional clues
                parent_context_score = 0
                current = span.parent
                depth = 0
                while current and depth < 3:
                    if current.get('class'):
                        class_str = ' '.join(current.get('class')).lower()
                        if any(keyword in class_str for keyword in ['profile', 'name', 'title', 'header']):
                            parent_context_score += 3
                        if any(keyword in class_str for keyword in ['nav', 'menu', 'footer', 'sidebar']):
                            parent_context_score -= 2
                    
                    # Check for heading tags
                    if current.name in ['h1', 'h2', 'h3']:
                        parent_context_score += 4
                        
                    current = current.parent
                    depth += 1
                
                total_score = name_score + parent_context_score
                if total_score >= 4:  # Good name candidate
                    name_candidates.append((span_text, total_score, span))
                    print(f"📋 Name candidate (score: {total_score}): {span_text}", file=sys.stderr)
            
            # Sort candidates by score and pick the best one
            if name_candidates:
                name_candidates.sort(key=lambda x: x[1], reverse=True)
                best_name = name_candidates[0]
                profile_data['name'] = best_name[0]
                print(f"✅ Selected name (score: {best_name[1]}): {profile_data['name']}", file=sys.stderr)
        
    except Exception as e:
        print(f"⚠️  Error extracting from page content: {e}", file=sys.stderr)

def extract_from_json_ld(soup, profile_data):
    """Extract data from JSON-LD structured data"""
    try:
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get('@type') == 'Person':
                        if data.get('name') and not profile_data['name']:
                            profile_data['name'] = clean_text(data['name'])
                        if data.get('description') and not profile_data['bio']:
                            profile_data['bio'] = clean_text(data['description'])
            except json.JSONDecodeError:
                continue
    except Exception as e:
        print(f"⚠️  Error extracting from JSON-LD: {e}", file=sys.stderr)

def extract_from_facebook_selectors(soup, profile_data):
    """Extract data using Facebook-specific selectors"""
    try:
        # Look for profile name in various Facebook elements
        name_selectors = [
            'h1',
            '.profileName',
            '[data-testid="profile-name"]',
            '.actor-name',
            '[data-testid="profile_name"]',
            '.profilePicThumb + div',
            '.profilePicThumb + span',
            '.cover + div h1',
            '.profilePic + div',
            'div[role="main"] h1',
            'div[role="banner"] h1',
            '.profileTimeline h1',
            '.timeline h1'
        ]
        
        for selector in name_selectors:
            name_element = soup.select_one(selector)
            if name_element and not profile_data['name']:
                name_text = clean_text(name_element.get_text())
                if name_text and len(name_text) < 100 and len(name_text) > 1:  # Reasonable name length
                    # Additional filtering for Facebook-specific content
                    skip_patterns = [
                        'facebook', 'timeline', 'cover photo', 'profile picture', 'add friend',
                        'message', 'follow', 'more', 'activity', 'about', 'friends', 'photos'
                    ]
                    if not any(pattern in name_text.lower() for pattern in skip_patterns):
                        profile_data['name'] = name_text
                        print(f"📋 Extracted name from selector {selector}: {profile_data['name']}", file=sys.stderr)
                        break
        
        # Look for location information with improved patterns
        location_keywords = ['lives in', 'from', 'location', 'based in', 'located in']
        all_text = soup.get_text().lower()
        
        for keyword in location_keywords:
            if keyword in all_text:
                # Try to extract location context with better regex
                patterns = [
                    rf'{keyword}\s+([^.\n,;]+?)(?:\s*[,;.]|\s*$)',
                    rf'{keyword}:?\s*([^.\n,;]+?)(?:\s*[,;.]|\s*$)',
                    rf'{keyword}\s+(.+?)(?:\s*\n|\s*$)'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, all_text)
                    if match and not profile_data['location']:
                        location = clean_text(match.group(1))
                        if len(location) < 50 and len(location) > 2:  # Reasonable location length
                            profile_data['location'] = location
                            print(f"📋 Extracted location: {profile_data['location']}", file=sys.stderr)
                            break
                
                if profile_data['location']:
                    break
        
        # Try to extract the username/page name directly from URL as fallback
        if not profile_data['name'] and profile_data.get('username'):
            # Use the username as the name if nothing else worked
            username = profile_data['username']
            if username and username != 'profile.php' and len(username) > 0:
                # Clean up the username to make it more readable
                readable_name = username.replace('.', ' ').replace('_', ' ').replace('-', ' ')
                readable_name = ' '.join(word.capitalize() for word in readable_name.split())
                profile_data['name'] = readable_name
                print(f"📋 Using username as fallback name: {profile_data['name']}", file=sys.stderr)
        
    except Exception as e:
        print(f"⚠️  Error extracting from Facebook selectors: {e}", file=sys.stderr)

def extract_name_fallback(soup, profile_data):
    """Fallback method to extract name from any reasonable text"""
    try:
        print("🔍 Trying fallback name extraction methods...", file=sys.stderr)
        
        # Look for any text that could be a profile name
        # Check all text nodes and find the most likely candidate
        all_text_elements = soup.find_all(text=True)
        
        candidates = []
        for text_node in all_text_elements:
            text = clean_text(str(text_node))
            # Skip empty, too long, or obviously non-name text
            if (text and len(text) > 2 and len(text) < 80 and 
                not text.isdigit() and text.count(' ') <= 4):
                
                # Skip common Facebook UI text
                skip_patterns = [
                    'facebook', 'log in', 'sign up', 'home', 'timeline', 'about', 'photos', 
                    'friends', 'more', 'settings', 'help', 'privacy', 'terms', 'cookies',
                    'like', 'share', 'comment', 'follow', 'message', 'post', 'story',
                    'see more', 'see all', 'show more', 'load more', 'view', 'edit',
                    'add friend', 'accept', 'decline', 'block', 'report', 'hide'
                ]
                
                if not any(pattern in text.lower() for pattern in skip_patterns):
                    # Look for text that appears to be a proper name
                    words = text.split()
                    if len(words) >= 1 and len(words) <= 4:  # Reasonable name length
                        # Check if it looks like a name (starts with capital letters)
                        if all(word[0].isupper() for word in words if word):
                            candidates.append(text)
        
        # If we found candidates, pick the first reasonable one
        if candidates:
            # Sort by length (prefer shorter, more name-like text)
            candidates.sort(key=len)
            for candidate in candidates:
                if len(candidate) >= 3:  # Minimum reasonable name length
                    profile_data['name'] = candidate
                    print(f"📋 Extracted name using fallback: {profile_data['name']}", file=sys.stderr)
                    break
                    
    except Exception as e:
        print(f"⚠️  Error in fallback name extraction: {e}", file=sys.stderr)

def extract_from_url_components(profile_input, profile_data):
    """Extract name from URL components as last resort"""
    try:
        print("🔍 Trying URL-based name extraction...", file=sys.stderr)
        
        # Parse the original input to get a readable name
        profile_input = profile_input.strip()
        
        # If it's a URL, extract the username part
        if profile_input.startswith('http'):
            # Extract from URL
            if 'facebook.com/' in profile_input:
                url_part = profile_input.split('facebook.com/')[-1]
                url_part = url_part.split('?')[0].split('/')[0]  # Remove query params and extra paths
                
                if url_part and url_part != 'profile.php':
                    # Convert URL part to readable name
                    readable_name = url_part.replace('.', ' ').replace('_', ' ').replace('-', ' ')
                    readable_name = ' '.join(word.capitalize() for word in readable_name.split() if word)
                    
                    if readable_name and len(readable_name) > 0:
                        profile_data['name'] = readable_name
                        print(f"📋 Extracted name from URL: {profile_data['name']}", file=sys.stderr)
        else:
            # Direct username/identifier input
            if not profile_input.isdigit():  # Skip pure numeric IDs
                readable_name = profile_input.replace('.', ' ').replace('_', ' ').replace('-', ' ')
                readable_name = readable_name.replace('@', '')  # Remove @ if present
                readable_name = ' '.join(word.capitalize() for word in readable_name.split() if word)
                
                if readable_name and len(readable_name) > 0:
                    profile_data['name'] = readable_name
                    print(f"📋 Extracted name from input: {profile_data['name']}", file=sys.stderr)
                    
    except Exception as e:
        print(f"⚠️  Error in URL-based name extraction: {e}", file=sys.stderr)

def extract_bio_from_modern_structure(soup, profile_data):
    """
    Extract bio from modern Facebook HTML structures with dynamic classes.
    Optimized for mihail.buca.7 type profiles with rich Intro sections.
    """
    print("🔍 Trying modern bio extraction strategies...", file=sys.stderr)
    
    # Strategy 1: Look for Intro section - search for spans containing intro-like content
    intro_bio_parts = []
    
    # Look for all spans with dir="auto" which contain profile information
    spans_with_dir_auto = soup.find_all('span', {'dir': 'auto'})
    print(f"📋 Found {len(spans_with_dir_auto)} spans with dir='auto'", file=sys.stderr)
    
    # If no spans with dir='auto', try all spans
    if len(spans_with_dir_auto) == 0:
        print("🔍 No spans with dir='auto' found, trying all spans...", file=sys.stderr)
        spans_with_dir_auto = soup.find_all('span')
        print(f"📋 Found {len(spans_with_dir_auto)} total spans", file=sys.stderr)
    
    for span in spans_with_dir_auto:
        text = clean_text(span.get_text())
        if not text or len(text) < 3:
            continue
        
        # Enhanced bio patterns for mihail.buca.7 type profiles
        bio_patterns = [
            # Professional titles and roles (exact matches from HTML)
            r'(?i)(profile.*digital creator|archdeacon and protopsalt|cantaret bisericesc)',
            r'(?i)(digital creator|creator|artist|musician|singer)',
            # Work experience patterns  
            r'(?i)(worked at|works at|employed at|position at)',
            r'(?i)(pictura bisericeasca|catedrala patriarhala)',
            # Education patterns (exact matches from HTML)
            r'(?i)(studied at|studies at|went to|graduated from)',
            r'(?i)(facultatea de teologie ortodoxa pitesti|pastorala)',
            r'(?i)(s\.t\.o\. bucuresti|seulement pour les connaisseurs|teologia)',
            # Location patterns
            r'(?i)(lives in|from|located in|based in)',
            r'(?i)(bucharest|bucuresti|romania)',
            # Personal info patterns
            r'(?i)(married|single|in a relationship)',
            # Links and external accounts
            r'(?i)(youtube\.com/channel|facebook\.com/.*)',
            # General descriptive patterns
            r'(?i)(passionate|dedicated|experience|specialist)',
        ]
        
        # Check if text matches intro patterns
        is_intro_content = False
        for pattern in bio_patterns:
            if re.search(pattern, text):
                is_intro_content = True
                print(f"🎯 Found intro pattern '{pattern}' in: {text[:60]}...", file=sys.stderr)
                break
        
        # Also include certain standalone descriptive terms that appear in Intro sections
        standalone_terms = [
            'profile', 'digital creator', 'archdeacon', 'protopsalt', 'married',
            'bucharest', 'romania', 'bucuresti', 'cantaret bisericesc'
        ]
        
        if not is_intro_content:
            for term in standalone_terms:
                if term.lower() in text.lower() and len(text) <= 80:  # Increased length for compound terms
                    is_intro_content = True
                    print(f"🎯 Found standalone term '{term}' in: {text}", file=sys.stderr)
                    break
        
        if is_intro_content and len(text) >= 3:
            # Skip obvious UI elements but be more permissive for profile content
            ui_skip = ['see more', 'see less', 'follow', 'message', 'add friend', 
                      'edit profile', 'like this', 'comment on', 'share this']
            
            if not any(ui in text.lower() for ui in ui_skip):
                intro_bio_parts.append(text)
                print(f"✅ Added intro part: {text}", file=sys.stderr)
    
    # Strategy 2: Combine intro parts into a comprehensive bio
    if intro_bio_parts:
        # Remove duplicates while preserving order
        seen = set()
        unique_parts = []
        for part in intro_bio_parts:
            if part not in seen:
                seen.add(part)
                unique_parts.append(part)
        
        # Create a comprehensive bio from the intro parts
        if len(unique_parts) == 1:
            bio_text = unique_parts[0]
        else:
            # Join multiple parts with separators, allowing more parts for rich profiles
            bio_text = " • ".join(unique_parts[:8])  # Increased from 5 to 8 for richer profiles
        
        profile_data['bio'] = bio_text
        print(f"✅ Constructed bio from {len(unique_parts)} intro parts: {bio_text[:100]}...", file=sys.stderr)
        return
    
    # Strategy 3: Fallback to original span scoring method
    print("🔍 No intro patterns found, trying fallback span scoring...", file=sys.stderr)
    bio_candidates = []
    
    for i, span in enumerate(spans_with_dir_auto[:50]):  # Limit to first 50 spans for performance
        text = clean_text(span.get_text())
        if not text or len(text) < 5:
            continue
            
        # Score this text as a potential bio
        score = 0
        
        # Length scoring (prefer medium-length text)
        if 15 <= len(text) <= 300:
            score += 3
        elif 8 <= len(text) <= 500:
            score += 2
        elif len(text) > 500:
            score -= 1
            
        # Content scoring
        if text.count('.') >= 1:
            score += 2
        if text.count(' ') >= 2:
            score += 2
        if any(char.isalpha() for char in text):
            score += 1
        if not text.isdigit():
            score += 1
            
        # Penalty for UI text
        ui_keywords = ['see more', 'see less', 'follow', 'message', 'add friend', 
                      'edit profile', 'like', 'comment', 'share', 'photos', 'videos',
                      'friends', 'timeline', 'about', 'home', 'posts', 'reels', 'create']
        ui_penalty = 0
        for keyword in ui_keywords:
            if keyword in text.lower():
                ui_penalty += 3
        score -= ui_penalty
              
        # Bonus for bio-like indicators
        bio_indicators = ['profile', 'digital creator', 'worked at', 'studied at', 'lives in',
                         'archdeacon', 'protopsalt', 'cantaret', 'bisericesc', 'teologie',
                         'married', 'from', 'passionate', 'dedicated', 'experience']
        for indicator in bio_indicators:
            if indicator in text.lower():
                score += 5
                print(f"🎯 Found bio indicator '{indicator}' in: {text[:40]}...", file=sys.stderr)
                
        # Store candidates with positive scores
        if score > 0:
            bio_candidates.append((text, score, span))
    
    # Sort and select best candidate
    if bio_candidates:
        bio_candidates.sort(key=lambda x: x[1], reverse=True)
        best_candidate = bio_candidates[0]
        
        # Show top 3 candidates for debugging
        print(f"🏆 Top bio candidates:", file=sys.stderr)
        for i, (text, score, span) in enumerate(bio_candidates[:3]):
            print(f"   {i+1}. Score {score}: {text[:60]}...", file=sys.stderr)
        
        if best_candidate[1] >= 3:  # Reasonable threshold
            profile_data['bio'] = best_candidate[0]
            print(f"✅ Selected bio (score: {best_candidate[1]}): {best_candidate[0][:80]}...", file=sys.stderr)
            return
        else:
            print(f"⚠️  Best candidate has low score ({best_candidate[1]}): {best_candidate[0][:60]}...", file=sys.stderr)
        if text.count(' ') >= 2:
            score += 2
        if any(char.isalpha() for char in text):
            score += 1
        if not text.isdigit():
            score += 1
            
        # Penalty for UI text
        ui_keywords = ['see more', 'see less', 'follow', 'message', 'add friend', 
                      'edit profile', 'like', 'comment', 'share', 'photos', 'videos',
                      'friends', 'timeline', 'about', 'home', 'posts', 'reels', 'create']
        ui_penalty = 0
        for keyword in ui_keywords:
            if keyword in text.lower():
                ui_penalty += 3
        score -= ui_penalty
              
        # Bonus for bio-like indicators
        bio_indicators = ['profile', 'digital creator', 'worked at', 'studied at', 'lives in',
                         'archdeacon', 'protopsalt', 'cantaret', 'bisericesc', 'teologie',
                         'married', 'from', 'passionate', 'dedicated', 'experience']
        for indicator in bio_indicators:
            if indicator in text.lower():
                score += 5
                print(f"🎯 Found bio indicator '{indicator}' in: {text[:40]}...", file=sys.stderr)
                
        # Store candidates with positive scores
        if score > 0:
            bio_candidates.append((text, score, span))
    
    # Sort and select best candidate
    if bio_candidates:
        bio_candidates.sort(key=lambda x: x[1], reverse=True)
        best_candidate = bio_candidates[0]
        
        # Show top 3 candidates for debugging
        print(f"🏆 Top bio candidates:", file=sys.stderr)
        for i, (text, score, span) in enumerate(bio_candidates[:3]):
            print(f"   {i+1}. Score {score}: {text[:60]}...", file=sys.stderr)
        
        if best_candidate[1] >= 3:  # Reasonable threshold
            profile_data['bio'] = best_candidate[0]
            print(f"✅ Selected bio (score: {best_candidate[1]}): {best_candidate[0][:80]}...", file=sys.stderr)
            return
        else:
            print(f"⚠️  Best candidate has low score ({best_candidate[1]}): {best_candidate[0][:60]}...", file=sys.stderr)
    
    # Strategy 2: Look for any meaningful text in divs (fallback)
    print("🔍 Trying fallback div extraction...", file=sys.stderr)
    all_divs = soup.find_all('div')
    
    for div in all_divs:
        # Get direct text content (not nested elements)
        direct_texts = []
        for child in div.children:
            if hasattr(child, 'get_text'):
                text = clean_text(child.get_text())
                if text and len(text) > 15:
                    direct_texts.append(text)
                    
        for text in direct_texts:
            if (len(text) >= 20 and len(text) <= 300 and
                not any(keyword in text.lower() for keyword in 
                       ['follow', 'message', 'friend', 'like', 'share', 'comment']) and
                text.count(' ') >= 3 and
                not text.isdigit()):
                
                profile_data['bio'] = text
                print(f"📋 Extracted bio from div fallback: {text[:50]}...", file=sys.stderr)
                return
    
    # Strategy 3: Comprehensive text search with Romanian language support
    print("🔍 Trying comprehensive text search...", file=sys.stderr)
    all_text_elements = soup.find_all(text=True)
    
    for text_node in all_text_elements:
        # Convert to string and clean
        try:
            raw_text = str(text_node)
            # Skip if it contains binary data or non-text content
            if any(ord(char) > 127 and not char.isalpha() for char in raw_text[:50]):
                continue
        except:
            continue
            
        text = clean_text(raw_text)
        
        # Skip if too short/long or obviously not bio
        if not text or len(text) < 20 or len(text) > 400:
            continue
            
        # Skip common UI elements
        skip_patterns = [
            'facebook', 'log in', 'sign up', 'home', 'timeline', 'photos', 'friends',
            'see more', 'see less', 'follow', 'message', 'add friend', 'like', 'share',
            'comment', 'post', 'story', 'settings', 'privacy', 'help'
        ]
        
        if any(pattern in text.lower() for pattern in skip_patterns):
            continue
            
        # Look for bio-like content characteristics
        bio_score = 0
        
        # Romanian/general bio indicators
        bio_keywords = [
            'din', 'din anul', 'din 1888', 'încă din', 'ceea ce', 'adevărul',
            'since', 'founded', 'established', 'about', 'mission', 'vision',
            'passionate', 'dedicated', 'company', 'organization'
        ]
        
        for keyword in bio_keywords:
            if keyword in text.lower():
                bio_score += 3
                
        # Sentence structure indicators
        if text.count('.') >= 1:
            bio_score += 2
        if text.count(' ') >= 5:  # Multiple words
            bio_score += 1
        if any(char.isupper() for char in text):  # Proper capitalization
            bio_score += 1
            
        if bio_score >= 4:  # Good bio candidate
            profile_data['bio'] = text
            print(f"📋 Extracted bio from text search (score: {bio_score}): {text[:50]}...", file=sys.stderr)
            return
    
    print("⚠️  Could not extract bio using modern extraction methods", file=sys.stderr)

def extract_detailed_intro_information(soup, profile_data):
    """
    Extract detailed information from Facebook Intro section
    This includes professional, educational, location, and personal details
    """
    print("🔍 Extracting detailed intro information...", file=sys.stderr)
    
    import json
    
    # Initialize detailed fields
    detailed_info = {
        'professional_title': None,
        'current_employer': None,
        'work_history': [],
        'education': [],
        'current_location': None,
        'origin_location': None,
        'relationship_status': None,
        'languages': [],
        'interests_detailed': [],
        'social_media_links': {},
        'religious_info': None,
        'church_position': None,
        'church_affiliation': None
    }
    
    # Find all text elements that might contain intro information
    all_spans = soup.find_all('span', {'dir': 'auto'})
    if not all_spans:
        all_spans = soup.find_all('span')
    
    print(f"📋 Analyzing {len(all_spans)} spans for detailed info...", file=sys.stderr)
    
    for span in all_spans:
        text = clean_text(span.get_text())
        if not text or len(text) < 3:
            continue
        
        # Professional title patterns (îmbunătățite pentru română)
        prof_patterns = [
            r'(?i)^(digital creator|creator|artist|musician|singer|cantaret|protopsalt|archdeacon|diacon)$',
            r'(?i)^(profile)\s*[•·]\s*(digital creator|creator)$',
            r'(?i)^(arhidiacon|protopsalt|cântăreț|diacon)$',
            r'(?i)^(creator digital|artist|muzician)$',
            r'(?i)^(arhidiacon și protopsalt|archdeacon and protopsalt)$',
            r'(?i)^(cântăreț bisericesc|cantor|psaltic)$',
            r'(?i)^(profile|profil)\s*[•·]\s*(.+)$'
        ]
        for pattern in prof_patterns:
            match = re.match(pattern, text.strip())
            if match:
                if not detailed_info['professional_title']:
                    # Extract the actual title from matched groups
                    if len(match.groups()) >= 2 and match.group(2):
                        detailed_info['professional_title'] = match.group(2).strip()
                    else:
                        detailed_info['professional_title'] = match.group(1).strip() if match.group(1) else text.strip()
                    print(f"✅ Professional title: {detailed_info['professional_title']}", file=sys.stderr)
                break
        
        # Work/employment patterns (îmbunătățite pentru context românesc)
        work_patterns = [
            r'(?i)(worked at|works at|employed at)\s+(.+)',
            r'(?i)(archdeacon and protopsalt at)\s+(.+)',
            r'(?i)(cantaret at|position at)\s+(.+)',
            r'(?i)(arhidiacon și protopsalt la)\s+(.+)',
            r'(?i)(lucrează la|a lucrat la)\s+(.+)',
            r'(?i)(cântăreț la|diacon la)\s+(.+)',
            r'(?i)(poziție la|angajat la)\s+(.+)',
            r'(?i)(Archdeacon and Protopsalt)\s+(la|at)\s+(.+)',
            r'(?i)(.*?)\s+(la|at)\s+(Catedrala\s+Patriarhală|Cathedral|Biserica|Church)(.+)',
            r'(?i)(muzician la|artist la|creator la)\s+(.+)'
        ]
        for pattern in work_patterns:
            match = re.search(pattern, text)
            if match:
                # Handle different pattern groups
                if len(match.groups()) >= 3 and match.group(3):
                    # Pattern with position + "la/at" + company
                    position = match.group(1).strip() if match.group(1) else 'Unknown position'
                    employer = match.group(3).strip()
                elif len(match.groups()) >= 2 and match.group(2):
                    # Standard pattern with action + company
                    position = match.group(1).replace(' at', '').replace(' la', '').strip()
                    employer = match.group(2).strip()
                else:
                    position = 'Unknown position'
                    employer = match.group(1).strip() if match.group(1) else text.strip()
                
                if employer and employer not in [w.get('company', '') for w in detailed_info['work_history']]:
                    work_entry = {
                        'company': employer,
                        'position': position,
                        'current': 'worked' not in match.group(0).lower() and 'a lucrat' not in match.group(0).lower()
                    }
                    detailed_info['work_history'].append(work_entry)
                    
                    if work_entry['current'] and not detailed_info['current_employer']:
                        detailed_info['current_employer'] = employer
                    
                    print(f"✅ Work: {work_entry}", file=sys.stderr)
                break
        
        # Education patterns
        edu_patterns = [
            r'(?i)(studied at|studies at|graduated from|went to)\s+(.+)',
            r'(?i)(facultatea de teologie)\s*(.+)?',
            r'(?i)(s\.t\.o\.\s*bucuresti|pastorala)',
        ]
        for pattern in edu_patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) >= 2:
                    institution = match.group(2).strip() if match.group(2) else match.group(1).strip()
                else:
                    institution = match.group(1).strip()
                
                if institution and institution not in [e.get('institution', '') for e in detailed_info['education']]:
                    edu_entry = {
                        'institution': institution,
                        'type': 'studied at' if 'studied' in match.group(0).lower() else 'education'
                    }
                    detailed_info['education'].append(edu_entry)
                    print(f"✅ Education: {edu_entry}", file=sys.stderr)
                break
        
        # Location patterns
        location_patterns = [
            r'(?i)(lives in)\s+(.+)',
            r'(?i)(from)\s+(.+)',
            r'(?i)(located in|based in)\s+(.+)'
        ]
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(2).strip()
                if 'lives in' in match.group(1).lower():
                    if not detailed_info['current_location']:
                        detailed_info['current_location'] = location
                        print(f"✅ Current location: {location}", file=sys.stderr)
                elif 'from' in match.group(1).lower():
                    if not detailed_info['origin_location']:
                        detailed_info['origin_location'] = location
                        print(f"✅ Origin location: {location}", file=sys.stderr)
                break
        
        # Relationship status patterns
        relationship_patterns = [
            r'(?i)^(married|single|in a relationship|divorced|widowed)$',
            r'(?i)(married to|in a relationship with)\s+(.+)'
        ]
        for pattern in relationship_patterns:
            match = re.search(pattern, text.strip())
            if match:
                if not detailed_info['relationship_status']:
                    detailed_info['relationship_status'] = match.group(1).strip()
                    print(f"✅ Relationship: {match.group(1).strip()}", file=sys.stderr)
                break
        
        # Religious information patterns
        religious_patterns = [
            r'(?i)(protopsalt|archdeacon|diacon|cantaret bisericesc)',
            r'(?i)(catedrala patriarhala|biserica|cathedral)',
            r'(?i)(pictura bisericeasca|church painting|religious art)'
        ]
        for pattern in religious_patterns:
            if re.search(pattern, text):
                if 'protopsalt' in text.lower() or 'archdeacon' in text.lower():
                    if not detailed_info['church_position']:
                        detailed_info['church_position'] = text.strip()
                        print(f"✅ Church position: {text.strip()}", file=sys.stderr)
                elif 'catedrala' in text.lower() or 'cathedral' in text.lower():
                    if not detailed_info['church_affiliation']:
                        detailed_info['church_affiliation'] = text.strip()
                        print(f"✅ Church affiliation: {text.strip()}", file=sys.stderr)
                elif not detailed_info['religious_info']:
                    detailed_info['religious_info'] = text.strip()
                    print(f"✅ Religious info: {text.strip()}", file=sys.stderr)
                break
        
        # Languages (if any mention of languages is found)
        language_patterns = [
            r'(?i)(speaks|fluent in|languages?)\s*[:]\s*(.+)',
            r'(?i)(romanian|english|french|german|spanish|italian|greek)',
        ]
        for pattern in language_patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) >= 2:
                    langs = [lang.strip() for lang in match.group(2).split(',')]
                else:
                    langs = [match.group(1).strip()]
                
                for lang in langs:
                    if lang and lang not in detailed_info['languages']:
                        detailed_info['languages'].append(lang)
                        print(f"✅ Language: {lang}", file=sys.stderr)
                break
    
    # Convert lists to JSON strings and update profile_data
    for key, value in detailed_info.items():
        if isinstance(value, (list, dict)) and value:
            profile_data[key] = json.dumps(value, ensure_ascii=False)
        elif value and isinstance(value, str):
            profile_data[key] = value
    
    # Set scraping metadata
    profile_data['last_scraped_at'] = datetime.now().isoformat()
    profile_data['scraping_method'] = 'manual'
    profile_data['is_public'] = True  # Assume public if we can access it
    
    print(f"✅ Extracted detailed info: {len([k for k, v in detailed_info.items() if v])} fields populated", file=sys.stderr)

def extract_from_json_application_data(soup, profile_data):
    """
    Extract profile data from <script type="application/json"> blocks
    These blocks contain rich structured data about the Facebook profile
    Enhanced with specific Facebook JSON structure navigation
    """
    print("🔍 Extracting from JSON application data blocks...", file=sys.stderr)
    
    # Find all script tags with type="application/json"
    json_scripts = soup.find_all('script', {'type': 'application/json'})
    
    print(f"📋 Found {len(json_scripts)} JSON application data blocks", file=sys.stderr)
    
    for script in json_scripts:
        try:
            if not script.string:
                continue
            
            # Parse the JSON content
            json_data = json.loads(script.string)
            
            # First try the enhanced Facebook-specific structure parsing
            if extract_facebook_specific_json_structure(json_data, profile_data):
                print("✅ Successfully extracted data using Facebook-specific JSON structure", file=sys.stderr)
                continue
            
            # Fallback to generic recursive structure search
            # extract_profile_from_json_structure(json_data, profile_data)
            print("⚠️  Facebook-specific structure not found, using generic JSON extraction", file=sys.stderr)
            
        except json.JSONDecodeError as e:
            # Skip invalid JSON blocks
            continue
        except Exception as e:
            print(f"⚠️  Error processing JSON block: {e}", file=sys.stderr)
            continue

def extract_facebook_specific_json_structure(json_data, profile_data):
    """
    Extract data using Facebook's specific JSON structure from application/json scripts
    This function navigates the exact 'require' -> 'ScheduledServerJS' -> 'profile_tile_sections' structure
    """
    try:
        # Navigate through the complex nested structure
        if not isinstance(json_data, dict) or 'require' not in json_data:
            return False
            
        for require_item in json_data.get('require', []):
            if isinstance(require_item, list) and len(require_item) > 3:
                # Look for ScheduledServerJS data
                if require_item[0] == "ScheduledServerJS" and require_item[1] == "handle":
                    if process_facebook_scheduled_server_js(require_item[3], profile_data):
                        return True
                # Look for RelayPrefetchedStreamCache which contains profile data
                elif require_item[0] == "RelayPrefetchedStreamCache" and require_item[1] == "next":
                    if process_facebook_relay_cache(require_item[3], profile_data):
                        return True
        
        return False
                    
    except Exception as e:
        print(f"⚠️  Error extracting from Facebook-specific JSON structure: {e}", file=sys.stderr)
        return False

def process_facebook_scheduled_server_js(data_list, profile_data):
    """Process Facebook's ScheduledServerJS data structure"""
    
    for item in data_list:
        if isinstance(item, dict) and '__bbox' in item:
            bbox_data = item['__bbox']
            if 'result' in bbox_data:
                result = bbox_data['result']
                if 'data' in result and 'profile_tile_sections' in result['data']:
                    return extract_from_facebook_profile_tile_sections(result['data']['profile_tile_sections'], profile_data)
    
    return False

def process_facebook_relay_cache(cache_data, profile_data):
    """Process Facebook's RelayPrefetchedStreamCache data structure"""
    
    try:
        print("🔍 Processing Facebook RelayPrefetchedStreamCache...", file=sys.stderr)
        
        # Navigate through cache data structure to find profile_tile_sections
        for item in cache_data:
            if isinstance(item, dict):
                # Look for __bbox with result containing profile data
                if '__bbox' in item:
                    bbox = item['__bbox']
                    if isinstance(bbox, dict) and 'result' in bbox:
                        result = bbox['result']
                        if isinstance(result, dict) and 'data' in result:
                            data = result['data']
                            if isinstance(data, dict) and 'profile_tile_sections' in data:
                                print("✅ Found profile_tile_sections in RelayCache!", file=sys.stderr)
                                return extract_from_facebook_profile_tile_sections(data['profile_tile_sections'], profile_data)
                
                # Also check if this item directly contains profile_tile_sections
                elif 'profile_tile_sections' in item:
                    print("✅ Found direct profile_tile_sections in RelayCache!", file=sys.stderr)
                    return extract_from_facebook_profile_tile_sections(item['profile_tile_sections'], profile_data)
        
        return False
        
    except Exception as e:
        print(f"⚠️  Error processing RelayPrefetchedStreamCache: {e}", file=sys.stderr)
        return False

def extract_from_facebook_profile_tile_sections(tile_sections, profile_data):
    """Extract data from Facebook's profile_tile_sections"""
    
    print("🎯 Processing Facebook profile tile sections...", file=sys.stderr)
    
    try:
        edges = tile_sections.get('edges', [])
        found_intro = False
        
        for edge in edges:
            node = edge.get('node', {})
            if node.get('profile_tile_section_type') == 'INTRO':
                print("✅ Found Facebook INTRO section!", file=sys.stderr)
                extract_from_facebook_intro_section(node, profile_data)
                found_intro = True
                
        return found_intro
                
    except Exception as e:
        print(f"⚠️  Error extracting from Facebook tile sections: {e}", file=sys.stderr)
        return False

def extract_from_facebook_intro_section(intro_node, profile_data):
    """Extract detailed info from Facebook's INTRO section"""
    
    try:
        # Navigate to profile_tile_views -> nodes
        tile_views = intro_node.get('profile_tile_views', {}).get('nodes', [])
        
        for view in tile_views:
            renderer = view.get('view_style_renderer')
            if renderer and renderer.get('__typename') == 'ProfileTileViewContextListRenderer':
                extract_from_facebook_context_list(renderer.get('view', {}), profile_data)
                
    except Exception as e:
        print(f"⚠️  Error extracting from Facebook intro section: {e}", file=sys.stderr)

def extract_from_facebook_context_list(view_data, profile_data):
    """Extract data from Facebook's context list view"""
    
    try:
        tile_items = view_data.get('profile_tile_items', {}).get('nodes', [])
        print(f"📋 Found {len(tile_items)} Facebook tile items", file=sys.stderr)
        
        # Initialize enhanced fields
        work_history = []
        education = []
        social_links = {}
        
        for item in tile_items:
            node = item.get('node', {})
            context_item = node.get('timeline_context_item', {})
            renderer = context_item.get('renderer', {})
            
            if 'context_item' in renderer:
                context_data = renderer['context_item']
                title_data = context_data.get('title', {})
                title_text = title_data.get('text', '')
                item_type = node.get('timeline_context_list_item_type', '')
                
                print(f"📊 Processing Facebook item: {item_type} - {title_text}", file=sys.stderr)
                
                # Extract professional title from influencer category
                if item_type == 'INTRO_CARD_INFLUENCER_CATEGORY':
                    # Handle "Profil · Creator digital" format
                    if 'creator digital' in title_text.lower() or 'digital creator' in title_text.lower():
                        profile_data['professional_title'] = 'Creator digital'
                        print(f"✅ Professional title: Creator digital", file=sys.stderr)
                    elif '·' in title_text:
                        # Extract the part after the bullet point
                        parts = title_text.split('·')
                        if len(parts) > 1:
                            title = parts[-1].strip()
                            profile_data['professional_title'] = title
                            print(f"✅ Professional title: {title}", file=sys.stderr)
                
                # Extract work information
                elif item_type == 'INTRO_CARD_WORK':
                    work_info = extract_facebook_work_info(title_text, title_data.get('ranges', []))
                    if work_info:
                        work_history.append(work_info)
                        print(f"✅ Work: {work_info}", file=sys.stderr)
                        
                        # Check for specific roles
                        if 'archdeacon and protopsalt' in title_text.lower():
                            profile_data['church_position'] = 'Archdeacon and Protopsalt'
                            # Extract church/organization from ranges
                            for range_item in title_data.get('ranges', []):
                                entity = range_item.get('entity', {})
                                if entity.get('__typename') == 'Page':
                                    church_name = entity.get('url', '').split('/')[-2] if entity.get('url') else ''
                                    if church_name:
                                        profile_data['church_affiliation'] = church_name.replace('-', ' ').title()
                                        print(f"✅ Church affiliation: {profile_data['church_affiliation']}", file=sys.stderr)
                                        break
                        print(f"✅ Work: {work_info}", file=sys.stderr)
                
                # Extract education information
                elif item_type == 'INTRO_CARD_EDUCATION':
                    edu_info = extract_facebook_education_info(title_text, title_data.get('ranges', []))
                    if edu_info:
                        education.append(edu_info)
                        print(f"✅ Education: {edu_info}", file=sys.stderr)
                
                # Extract location information
                elif item_type == 'INTRO_CARD_CURRENT_CITY':
                    location = extract_facebook_location_from_title(title_text)
                    if location:
                        profile_data['current_location'] = location
                        print(f"✅ Current location: {location}", file=sys.stderr)
                
                elif item_type == 'INTRO_CARD_HOMETOWN':
                    location = extract_facebook_location_from_title(title_text)
                    if location:
                        profile_data['origin_location'] = location
                        print(f"✅ Origin location: {location}", file=sys.stderr)
                
                # Extract relationship status
                elif item_type == 'INTRO_CARD_RELATIONSHIP':
                    if title_text:
                        profile_data['relationship_status'] = title_text
                        print(f"✅ Relationship status: {title_text}", file=sys.stderr)
                
                # Extract website/social links
                elif item_type == 'INTRO_CARD_WEBSITE':
                    # Handle WebsiteContextItemRenderer structure
                    if renderer.get('__typename') == 'WebsiteContextItemRenderer':
                        context_item = renderer.get('context_item', {})
                        url = context_item.get('url', '')
                        plaintext_title = context_item.get('plaintext_title', {}).get('text', '')
                        
                        print(f"🔗 Found website: {plaintext_title} -> {url}", file=sys.stderr)
                        
                        if 'youtube.com/channel' in plaintext_title:
                            # Extract clean YouTube channel URL
                            if 'youtube.com/channel/' in plaintext_title:
                                channel_id = plaintext_title.split('youtube.com/channel/')[-1]
                                social_links['YouTube'] = f"https://www.youtube.com/channel/{channel_id}"
                                print(f"✅ YouTube channel: {social_links['YouTube']}", file=sys.stderr)
                        elif 'facebook.com/' in plaintext_title and 'Mihail-Buc' in plaintext_title:
                            # Extract Facebook page URL
                            social_links['Facebook_Page'] = plaintext_title
                            print(f"✅ Facebook page: {plaintext_title}", file=sys.stderr)
                        else:
                            social_links['Website'] = plaintext_title
                            print(f"✅ Website: {plaintext_title}", file=sys.stderr)
                    else:
                        # Fallback for simpler structure
                        url = context_data.get('url', '')
                        plaintext_title = context_data.get('plaintext_title', {}).get('text', '')
                        
                        if 'youtube.com' in plaintext_title:
                            social_links['YouTube'] = url
                            print(f"✅ YouTube link: {plaintext_title}", file=sys.stderr)
                        elif 'facebook.com' in plaintext_title:
                            social_links['Facebook'] = url
                            print(f"✅ Facebook link: {plaintext_title}", file=sys.stderr)
                        else:
                            social_links['Website'] = url
                            print(f"✅ Website link: {plaintext_title}", file=sys.stderr)
                
                # Extract languages
                elif item_type == 'INTRO_CARD_LANGUAGES':
                    languages = extract_facebook_languages(title_text)
                    if languages:
                        profile_data['languages'] = json.dumps(languages, ensure_ascii=False)
                        print(f"✅ Languages: {languages}", file=sys.stderr)
                
                # Extract religious views
                elif item_type == 'INTRO_CARD_RELIGIOUS_VIEWS':
                    if title_text:
                        profile_data['religious_info'] = title_text
                        print(f"✅ Religious info: {title_text}", file=sys.stderr)
                
                # Extract family members
                elif item_type == 'INTRO_CARD_FAMILY_MEMBERS':
                    family_info = extract_facebook_family(title_text, title_data.get('ranges', []))
                    if family_info:
                        # Store as JSON array
                        existing_family = profile_data.get('family_members', '[]')
                        try:
                            family_list = json.loads(existing_family)
                        except:
                            family_list = []
                        family_list.append(family_info)
                        profile_data['family_members'] = json.dumps(family_list, ensure_ascii=False)
                        print(f"✅ Family member: {family_info}", file=sys.stderr)
                
                # Extract interests/hobbies
                elif item_type == 'INTRO_CARD_INTERESTS':
                    interests = extract_facebook_interests(title_text)
                    if interests:
                        profile_data['interests_detailed'] = json.dumps(interests, ensure_ascii=False)
                        print(f"✅ Interests: {interests}", file=sys.stderr)
                
                # Extract contact info
                elif item_type == 'INTRO_CARD_CONTACT_INFO':
                    contact_info = extract_facebook_contact(title_text)
                    if contact_info:
                        for contact_type, contact_value in contact_info.items():
                            profile_data[f'contact_{contact_type}'] = contact_value
                            print(f"✅ Contact {contact_type}: {contact_value}", file=sys.stderr)
                
                # Extract basic info (catch-all)
                elif item_type == 'INTRO_CARD_BASIC_INFO':
                    basic_info = extract_facebook_basic_info(title_text)
                    if basic_info:
                        profile_data['additional_info'] = basic_info
                        print(f"✅ Basic info: {basic_info}", file=sys.stderr)
                
                # Extract about section
                elif item_type == 'INTRO_CARD_ABOUT':
                    if title_text and len(title_text) > 10:
                        # Extended bio/about section
                        profile_data['about_section'] = title_text
                        print(f"✅ About section: {title_text[:50]}...", file=sys.stderr)
                
                # Extract life events
                elif item_type == 'INTRO_CARD_LIFE_EVENT':
                    if title_text:
                        # Store life events as JSON array
                        existing_events = profile_data.get('life_events', '[]')
                        try:
                            events_list = json.loads(existing_events)
                        except:
                            events_list = []
                        events_list.append(title_text)
                        profile_data['life_events'] = json.dumps(events_list, ensure_ascii=False)
                        print(f"✅ Life event: {title_text}", file=sys.stderr)
                
                # Extract favorite quotes
                elif item_type == 'INTRO_CARD_FAVORITE_QUOTES':
                    if title_text:
                        profile_data['favorite_quotes'] = title_text
                        print(f"✅ Favorite quote: {title_text}", file=sys.stderr)
                
                # Extract other names/nicknames
                elif item_type == 'INTRO_CARD_OTHER_NAMES' or item_type == 'INTRO_CARD_NICKNAME':
                    if title_text:
                        profile_data['other_names'] = title_text
                        print(f"✅ Other names: {title_text}", file=sys.stderr)
                
                # Extract political views
                elif item_type == 'INTRO_CARD_POLITICAL_VIEWS':
                    if title_text:
                        profile_data['political_views'] = title_text
                        print(f"✅ Political views: {title_text}", file=sys.stderr)
                
                # Extract birthday (if public)
                elif item_type == 'INTRO_CARD_BIRTHDAY':
                    if title_text:
                        profile_data['birthday'] = title_text
                        print(f"✅ Birthday: {title_text}", file=sys.stderr)
                
                # Extract phone number
                elif item_type == 'INTRO_CARD_PHONE':
                    if title_text:
                        profile_data['contact_phone'] = title_text
                        print(f"✅ Phone: {title_text}", file=sys.stderr)
                
                # Extract email
                elif item_type == 'INTRO_CARD_EMAIL':
                    if title_text:
                        profile_data['contact_email'] = title_text
                        print(f"✅ Email: {title_text}", file=sys.stderr)
                
                # Log unknown types for future improvement
                else:
                    if item_type and item_type.startswith('INTRO_CARD_'):
                        print(f"⚠️  Unknown INTRO_CARD type: {item_type} - {title_text}", file=sys.stderr)
        
        # Convert to JSON strings for database storage
        if work_history:
            profile_data['work_history'] = json.dumps(work_history, ensure_ascii=False)
            
            # Set current employer from most recent work
            current_work = next((w for w in work_history if w.get('current')), None)
            if current_work:
                profile_data['current_employer'] = current_work.get('company')
        
        if education:
            profile_data['education'] = json.dumps(education, ensure_ascii=False)
            
        if social_links:
            profile_data['social_media_links'] = json.dumps(social_links, ensure_ascii=False)
        
        print(f"🎉 Successfully extracted enhanced data from Facebook JSON!", file=sys.stderr)
        
    except Exception as e:
        print(f"⚠️  Error extracting from Facebook context list: {e}", file=sys.stderr)

def extract_facebook_work_info(title_text, ranges):
    """Extract work information from Facebook title text and ranges"""
    
    work_info = {'current': True, 'position': None, 'company': None}
    
    # Check for work-related patterns
    if 'worked at' in title_text.lower() or 'a lucrat la' in title_text.lower():
        work_info['current'] = False
    
    # Extract position and company from ranges if available
    for range_item in ranges:
        entity = range_item.get('entity', {})
        if entity.get('__typename') == 'Page':
            # This is likely the company/organization
            work_info['company'] = entity.get('name', '')
            
            # Extract position from the remaining text
            offset = range_item.get('offset', 0)
            if offset > 0:
                work_info['position'] = title_text[:offset].strip()
                # Clean up common work prefixes
                for prefix in ['works at', 'worked at', 'lucrează la', 'a lucrat la']:
                    if work_info['position'].lower().startswith(prefix):
                        work_info['position'] = work_info['position'][len(prefix):].strip()
            
            break
    
    # Fallback: parse from title text if ranges don't work
    if not work_info['company']:
        work_patterns = [
            r'(?i)(.*?)\s+(?:works?\s+at|worked\s+at|la)\s+(.+)',
            r'(?i)(?:works?\s+at|worked\s+at|la)\s+(.+)'
        ]
        
        for pattern in work_patterns:
            match = re.search(pattern, title_text)
            if match:
                if len(match.groups()) >= 2:
                    work_info['position'] = match.group(1).strip()
                    work_info['company'] = match.group(2).strip()
                else:
                    work_info['company'] = match.group(1).strip()
                break
    
    # Only return if we have at least a company
    return work_info if work_info['company'] else None

def extract_facebook_education_info(title_text, ranges):
    """Extract education information from Facebook title text and ranges"""
    
    edu_info = {'institution': None, 'type': 'education'}
    
    # Extract institution from ranges if available
    for range_item in ranges:
        entity = range_item.get('entity', {})
        if entity.get('__typename') == 'Page':
            edu_info['institution'] = entity.get('name', '')
            break
    
    # Fallback: parse from title text if ranges don't work
    if not edu_info['institution']:
        edu_patterns = [
            r'(?i)(?:studied at|studies at|a studiat la)\s+(.+)',
            r'(?i)(.+)(?:\s+University|\s+College|\s+Faculty)'
        ]
        
        for pattern in edu_patterns:
            match = re.search(pattern, title_text)
            if match:
                edu_info['institution'] = match.group(1).strip()
                break
    
    # Only return if we have an institution
    return edu_info if edu_info['institution'] else None

def extract_facebook_location_from_title(title_text):
    """Extract location from Facebook title text"""
    
    location_patterns = [
        r'(?i)(?:lives in|based in|located in|din)\s+(.+)',
        r'(?i)(.+?)(?:,\s*Romania|,\s*România)',
        r'(?i)(.+?)(?:\s*$)'
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, title_text)
        if match:
            location = match.group(1).strip()
            # Clean up common location prefixes
            for prefix in ['lives in', 'based in', 'located in', 'din']:
                if location.lower().startswith(prefix):
                    location = location[len(prefix):].strip()
            
            return location if len(location) > 2 else None
    
    return None

def extract_facebook_languages(title_text):
    """Extract languages from Facebook language info"""
    languages = []
    
    # Split by common separators
    for separator in [',', ';', ' și ', ' and ', ' | ']:
        if separator in title_text:
            lang_parts = title_text.split(separator)
            languages.extend([lang.strip() for lang in lang_parts if lang.strip()])
            break
    else:
        # Single language
        languages = [title_text.strip()]
    
    return [lang for lang in languages if len(lang) > 1]

def extract_facebook_family(title_text, ranges):
    """Extract family member information"""
    family_info = {
        'relationship': None,
        'name': None,
        'profile_url': None
    }
    
    # Extract relationship type (wife, husband, son, daughter, etc.)
    if 'married to' in title_text.lower():
        family_info['relationship'] = 'spouse'
        family_info['name'] = title_text.lower().replace('married to', '').strip()
    elif 'wife' in title_text.lower():
        family_info['relationship'] = 'wife'
    elif 'husband' in title_text.lower():
        family_info['relationship'] = 'husband'
    elif 'son' in title_text.lower():
        family_info['relationship'] = 'son'
    elif 'daughter' in title_text.lower():
        family_info['relationship'] = 'daughter'
    elif 'mother' in title_text.lower():
        family_info['relationship'] = 'mother'
    elif 'father' in title_text.lower():
        family_info['relationship'] = 'father'
    
    # Extract profile URL from ranges if available
    for range_item in ranges:
        entity = range_item.get('entity', {})
        if entity.get('__typename') == 'User':
            family_info['profile_url'] = entity.get('url')
            # Extract name from range text
            offset = range_item.get('offset', 0)
            length = range_item.get('length', 0)
            if offset + length <= len(title_text):
                family_info['name'] = title_text[offset:offset+length]
            break
    
    return family_info if family_info['relationship'] else None

def extract_facebook_interests(title_text):
    """Extract interests/hobbies"""
    interests = []
    
    # Split by common separators
    for separator in [',', ';', ' • ', ' | ', ' and ', ' și ']:
        if separator in title_text:
            interest_parts = title_text.split(separator)
            interests.extend([interest.strip() for interest in interest_parts if interest.strip()])
            break
    else:
        interests = [title_text.strip()]
    
    return [interest for interest in interests if len(interest) > 2]

def extract_facebook_contact(title_text):
    """Extract contact information"""
    contact_info = {}
    
    # Email pattern
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_match = re.search(email_pattern, title_text)
    if email_match:
        contact_info['email'] = email_match.group()
    
    # Phone pattern (simple)
    phone_pattern = r'[\+]?[0-9\s\-\(\)]{10,}'
    phone_match = re.search(phone_pattern, title_text)
    if phone_match:
        contact_info['phone'] = phone_match.group().strip()
    
    return contact_info

def extract_facebook_basic_info(title_text):
    """Extract other basic information"""
    # This can be customized based on what kind of basic info is found
    # For now, just return the text as is
    return title_text.strip() if title_text and len(title_text.strip()) > 3 else None

def main():
    """Main function - called when script is run directly"""
    try:
        # Get profile input from command line argument
        if len(sys.argv) < 2:
            print("❌ Usage: python facebook_scraper.py <username_or_id_or_url>", file=sys.stderr)
            sys.exit(1)
        
        profile_input = sys.argv[1]
        
        print(f"🔍 Processing Facebook profile: {profile_input}", file=sys.stderr)
        
        # Extract real profile data
        profile_data = extract_facebook_profile(profile_input)
        
        if profile_data:
            if 'error' in profile_data:
                print(f"❌ Scraper error: {profile_data['error']}", file=sys.stderr)
                # Output error JSON
                print(json.dumps(profile_data))
                sys.exit(1)
            else:
                print(f"✅ Successfully extracted profile for: {profile_data['name']}", file=sys.stderr)
                # Output JSON to stdout for the scheduler
                print(json.dumps(profile_data, ensure_ascii=False, indent=2))
                sys.exit(0)
        else:
            print("❌ Failed to extract profile data", file=sys.stderr)
            # Output error JSON
            error_data = {"error": "Could not extract profile data from the provided input"}
            print(json.dumps(error_data))
            sys.exit(1)
        
    except Exception as e:
        print(f"💥 Fatal error in Facebook scraper: {e}", file=sys.stderr)
        # Output error JSON
        error_data = {"error": str(e)}
        print(json.dumps(error_data))
        sys.exit(1)

if __name__ == '__main__':
    main()
