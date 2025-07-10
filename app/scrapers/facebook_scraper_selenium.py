#!/usr/bin/env python3
"""
Enhanced Facebook Profile Scraper using Selenium WebDriver
Extracts complete About section information from Facebook profiles
"""

import sys
import os
import json
import re
from datetime import datetime

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

def extract_username_from_url(url):
    """Extract username from Facebook URL"""
    try:
        if 'profile.php?id=' in url:
            return url.split('id=')[1].split('&')[0]
        else:
            return url.split('facebook.com/')[-1].split('?')[0]
    except:
        return None

def process_extracted_data(raw_data):
    """Process and structure the extracted data for database storage"""
    try:
        profile_data = {
            'name': None,
            'bio': None,
            'connected_accounts': [],
            'profile_url': raw_data.get('profile_url'),
            'username': extract_username_from_url(raw_data.get('profile_url', '')),
            
            # Enhanced fields from About sections
            'professional_title': None,
            'current_employer': None,
            'work_history': None,
            'education': None,
            'current_location': None,
            'origin_location': None,
            'relationship_status': None,
            'social_media_links': None,
            'languages': None,
            'religious_info': None,
            'family_members': None,
            'interests_detailed': None,
            'contact_email': None,
            'contact_phone': None,
            'about_section': None,
            'life_events': None,
            'favorite_quotes': None,
            'other_names': None,
            'birthday': None,
            'political_views': None,
            'followers_count': 0,
            'friends_count': 0
        }
        
        # Extract name from overview or work info
        overview = raw_data.get('overview', {})
        if overview.get('current_work'):
            profile_data['current_employer'] = overview['current_work']
        if overview.get('education'):
            profile_data['education'] = json.dumps([{'institution': overview['education'], 'type': 'education'}])
        if overview.get('location'):
            profile_data['current_location'] = overview['location']
        
        # Process work and education
        work_education = raw_data.get('work_education', {})
        if work_education.get('work_history'):
            work_list = []
            for work in work_education['work_history']:
                work_list.append({
                    'company': work,
                    'position': 'Unknown',
                    'current': True
                })
            profile_data['work_history'] = json.dumps(work_list)
            
            # Set current employer from first work entry
            if work_list:
                profile_data['current_employer'] = work_list[0]['company']
        
        if work_education.get('education_history'):
            edu_list = []
            for edu in work_education['education_history']:
                edu_list.append({
                    'institution': edu,
                    'type': 'education'
                })
            profile_data['education'] = json.dumps(edu_list)
        
        # Process places lived
        places = raw_data.get('places_lived', {})
        if places.get('current_city'):
            profile_data['current_location'] = places['current_city']
        if places.get('hometown'):
            profile_data['origin_location'] = places['hometown']
        
        # Process contact and basic info
        contact_info = raw_data.get('contact_basic_info', {})
        if contact_info.get('email'):
            profile_data['contact_email'] = contact_info['email']
        if contact_info.get('phone'):
            profile_data['contact_phone'] = contact_info['phone']
        if contact_info.get('languages'):
            profile_data['languages'] = json.dumps(contact_info['languages'])
        if contact_info.get('website'):
            profile_data['social_media_links'] = json.dumps({'website': contact_info['website']})
        if contact_info.get('birthday'):
            profile_data['birthday'] = contact_info['birthday']
        
        # Process family and relationships
        family = raw_data.get('family_relationships', {})
        if family.get('relationship_status'):
            profile_data['relationship_status'] = family['relationship_status']
        if family.get('family_members'):
            family_list = []
            for member in family['family_members']:
                family_list.append({
                    'relationship': 'family',
                    'name': member,
                    'profile_url': None
                })
            profile_data['family_members'] = json.dumps(family_list)
        
        # Process details about
        details = raw_data.get('details_about', {})
        if details.get('about_text'):
            profile_data['about_section'] = details['about_text']
            # Use about text as bio if no better option
            if not profile_data['bio']:
                profile_data['bio'] = details['about_text'][:500]  # Limit bio length
        if details.get('quotes'):
            profile_data['favorite_quotes'] = '; '.join(details['quotes'])
        if details.get('interests'):
            profile_data['interests_detailed'] = json.dumps(details['interests'])
        
        # Process life events
        life_events = raw_data.get('life_events', [])
        if life_events:
            profile_data['life_events'] = json.dumps(life_events)
        
        # Extract name from the profile data
        name_candidates = []
        
        # Try to get name from URL
        if profile_data['username']:
            name_from_url = profile_data['username'].replace('.', ' ').replace('_', ' ').title()
            if not name_from_url.isdigit():
                name_candidates.append(name_from_url)
        
        # Use the best name candidate
        if name_candidates:
            profile_data['name'] = name_candidates[0]
        else:
            profile_data['name'] = f"Facebook User {profile_data['username'] or 'Unknown'}"
        
        # Generate bio if not present
        if not profile_data['bio']:
            bio_parts = []
            if profile_data['current_employer']:
                bio_parts.append(f"Works at {profile_data['current_employer']}")
            if profile_data['current_location']:
                bio_parts.append(f"Lives in {profile_data['current_location']}")
            if profile_data['relationship_status']:
                bio_parts.append(profile_data['relationship_status'])
            
            if bio_parts:
                profile_data['bio'] = ' • '.join(bio_parts)
            else:
                profile_data['bio'] = "Facebook user"
        
        return profile_data
        
    except Exception as e:
        print(f"❌ Error processing extracted data: {e}", file=sys.stderr)
        return None

def extract_facebook_profile_selenium(profile_input):
    """
    Extract Facebook profile using Selenium WebDriver
    Args:
        profile_input: Username, numeric ID, or full URL
    Returns:
        dict with profile data or error information
    """
    try:
        # Import selenium manager
        from app.selenium_manager import scrape_facebook_profile_selenium
        
        # Normalize profile URL
        profile_url = normalize_facebook_url(profile_input)
        print(f"🔍 Scraping Facebook profile with Selenium: {profile_url}", file=sys.stderr)
        
        # Scrape profile using existing Selenium session
        raw_data = scrape_facebook_profile_selenium(profile_url)
        
        if raw_data is None:
            return {
                'error': 'Failed to scrape profile with Selenium. Session may not be initialized or profile may be inaccessible.',
                'method': 'selenium'
            }
        
        # Process the extracted data
        profile_data = process_extracted_data(raw_data)
        
        if profile_data is None:
            return {
                'error': 'Failed to process extracted profile data',
                'method': 'selenium'
            }
        
        print(f"✅ Successfully extracted Facebook profile: {profile_data['name']}", file=sys.stderr)
        print(f"📊 Extracted {len([k for k, v in profile_data.items() if v])} fields", file=sys.stderr)
        
        return profile_data
        
    except ImportError:
        return {
            'error': 'Selenium WebDriver not available. Please ensure Chrome and ChromeDriver are installed.',
            'method': 'selenium'
        }
    except Exception as e:
        print(f"❌ Error in Selenium Facebook scraper: {e}", file=sys.stderr)
        return {
            'error': f'Selenium scraping failed: {str(e)}',
            'method': 'selenium'
        }

def extract_facebook_profile_fallback(profile_input):
    """
    Fallback to HTTP-based scraping if Selenium fails
    """
    try:
        from app.scrapers.facebook_scraper import extract_facebook_profile
        print("🔄 Falling back to HTTP-based scraping", file=sys.stderr)
        return extract_facebook_profile(profile_input)
    except Exception as e:
        print(f"❌ Fallback scraper also failed: {e}", file=sys.stderr)
        return {
            'error': f'Both Selenium and HTTP scraping failed: {str(e)}',
            'method': 'fallback'
        }

def extract_facebook_profile(profile_input):
    """
    Main Facebook profile extraction function
    Tries Selenium first, falls back to HTTP if needed
    """
    try:
        # Check if Selenium session is available
        from app.selenium_manager import get_selenium_manager
        selenium_manager = get_selenium_manager()
        
        if selenium_manager and selenium_manager.logged_in:
            print("🌐 Using Selenium WebDriver for enhanced Facebook scraping", file=sys.stderr)
            result = extract_facebook_profile_selenium(profile_input)
            
            # If Selenium failed, try fallback
            if 'error' in result:
                print("⚠️ Selenium scraping failed, trying fallback method", file=sys.stderr)
                fallback_result = extract_facebook_profile_fallback(profile_input)
                if 'error' not in fallback_result:
                    return fallback_result
            
            return result
        else:
            print("⚠️ Selenium session not available, using HTTP fallback", file=sys.stderr)
            return extract_facebook_profile_fallback(profile_input)
            
    except ImportError:
        print("⚠️ Selenium not available, using HTTP fallback", file=sys.stderr)
        return extract_facebook_profile_fallback(profile_input)
    except Exception as e:
        print(f"❌ Error in main Facebook extractor: {e}", file=sys.stderr)
        return extract_facebook_profile_fallback(profile_input)

def main():
    """Main function - called when script is run directly"""
    try:
        # Get profile input from command line argument
        if len(sys.argv) < 2:
            print("❌ Usage: python facebook_scraper_selenium.py <username_or_id_or_url>", file=sys.stderr)
            sys.exit(1)
        
        profile_input = sys.argv[1]
        
        print(f"🔍 Processing Facebook profile: {profile_input}", file=sys.stderr)
        
        # Extract profile data
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
