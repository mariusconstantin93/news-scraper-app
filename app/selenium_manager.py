#!/usr/bin/env python3
"""
Selenium WebDriver Manager for Facebook Authentication and Scraping
Handles login at startup and maintains session for profile scraping
"""

import sys
import os
import time
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FacebookSeleniumManager:
    """Manages Facebook login session and profile scraping using Selenium"""
    
    def __init__(self, headless=True):
        self.driver = None
        self.logged_in = False
        self.headless = headless
        self.wait_time = 10
        
    def setup_driver(self):
        """Initialize Chrome WebDriver with optimal settings"""
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument('--headless')
            
            # Essential Chrome options for stability
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Privacy and security options
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Language preference
            chrome_options.add_argument('--accept-lang=en-US,en;q=0.9')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Chrome WebDriver initialized successfully")
            return True
            
        except WebDriverException as e:
            logger.error(f"❌ Failed to initialize WebDriver: {e}")
            return False
    
    def login_to_facebook(self, email, password):
        """
        Log into Facebook and maintain session
        Args:
            email: Facebook email/username
            password: Facebook password
        Returns:
            bool: True if login successful, False otherwise
        """
        if not self.driver:
            if not self.setup_driver():
                return False
        
        try:
            logger.info("🔐 Starting Facebook login process...")
            
            # Navigate to Facebook login page
            self.driver.get("https://www.facebook.com/login")
            time.sleep(2)
            
            # Wait for login form to load
            wait = WebDriverWait(self.driver, self.wait_time)
            
            # Find and fill email field
            email_field = wait.until(EC.presence_of_element_located((By.ID, "email")))
            email_field.clear()
            email_field.send_keys(email)
            logger.info("📧 Email entered successfully")
            
            # Find and fill password field
            password_field = self.driver.find_element(By.ID, "pass")
            password_field.clear()
            password_field.send_keys(password)
            logger.info("🔑 Password entered successfully")
            
            # Click login button
            login_button = self.driver.find_element(By.NAME, "login")
            login_button.click()
            logger.info("🖱️ Login button clicked")
            
            # Wait for login to complete
            time.sleep(5)
            
            # Check if login was successful
            if self.check_login_success():
                self.logged_in = True
                logger.info("✅ Facebook login successful!")
                return True
            else:
                logger.error("❌ Facebook login failed - credentials may be incorrect")
                return False
                
        except TimeoutException:
            logger.error("❌ Login timeout - page elements not found")
            return False
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False
    
    def check_login_success(self):
        """Check if login was successful by looking for logged-in indicators"""
        try:
            # Check for common indicators of successful login
            indicators = [
                "//div[@data-testid='royal_login_button']",  # Logout button
                "//div[contains(@aria-label, 'Account')]",   # Account menu
                "//a[@aria-label='Home']",                   # Home link
                "//div[@role='navigation']"                  # Main navigation
            ]
            
            for indicator in indicators:
                try:
                    element = self.driver.find_element(By.XPATH, indicator)
                    if element:
                        return True
                except NoSuchElementException:
                    continue
            
            # Check URL change (successful login usually redirects)
            current_url = self.driver.current_url
            if "login" not in current_url and "facebook.com" in current_url:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False
    
    def navigate_to_profile_about(self, profile_url):
        """
        Navigate to a Facebook profile's About section
        Args:
            profile_url: Full Facebook profile URL
        Returns:
            bool: True if navigation successful, False otherwise
        """
        if not self.logged_in:
            logger.error("❌ Not logged in to Facebook")
            return False
        
        try:
            logger.info(f"🔍 Navigating to profile: {profile_url}")
            
            # Navigate to profile
            self.driver.get(profile_url)
            time.sleep(3)
            
            # Look for and click "About" tab
            about_selectors = [
                "//a[contains(@href, '/about')]",
                "//a[contains(text(), 'About')]",
                "//div[contains(text(), 'About')]",
                "//span[contains(text(), 'About')]"
            ]
            
            about_clicked = False
            for selector in about_selectors:
                try:
                    about_element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    about_element.click()
                    about_clicked = True
                    logger.info("📋 Clicked About section")
                    break
                except TimeoutException:
                    continue
            
            if not about_clicked:
                # Try alternative: add /about to URL
                about_url = f"{profile_url.rstrip('/')}/about"
                self.driver.get(about_url)
                logger.info("📋 Navigated to About URL directly")
            
            time.sleep(3)
            return True
            
        except Exception as e:
            logger.error(f"❌ Error navigating to profile About: {e}")
            return False
    
    def extract_about_sections(self):
        """
        Extract all information from Facebook About sections using multiple strategies
        Returns:
            dict: Extracted profile information
        """
        try:
            logger.info("📊 Extracting About section information...")
            
            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            profile_data = {
                'overview': {},
                'work_education': {},
                'places_lived': {},
                'contact_basic_info': {},
                'family_relationships': {},
                'details_about': {},
                'life_events': {}
            }
            
            # Strategy 1: Try Facebook JSON extraction first (most reliable)
            logger.info("🔍 Attempting JSON extraction...")
            try:
                json_data = self.extract_facebook_json_data(page_source)
                if json_data:
                    logger.info("✅ JSON extraction successful")
                    # Merge JSON data into profile_data
                    self.merge_json_data(json_data, profile_data)
            except Exception as e:
                logger.warning(f"JSON extraction failed: {e}")
            
            # Strategy 2: Enhanced HTML extraction (fallback)
            logger.info("🔍 Performing enhanced HTML extraction...")
            self.extract_overview_section(soup, profile_data)
            self.extract_work_education_section(soup, profile_data)
            self.extract_places_lived_section(soup, profile_data)
            self.extract_contact_basic_info_section(soup, profile_data)
            self.extract_family_relationships_section(soup, profile_data)
            self.extract_details_about_section(soup, profile_data)
            self.extract_life_events_section(soup, profile_data)
            
            # Strategy 3: Enhanced meta tag extraction
            logger.info("🔍 Extracting meta tag information...")
            self.extract_meta_information(soup, profile_data)
            
            logger.info("✅ About section extraction completed")
            return profile_data
            
        except Exception as e:
            logger.error(f"❌ Error extracting About sections: {e}")
            return {}
    
    def extract_facebook_json_data(self, page_source):
        """Extract data from Facebook's JSON structures in the page"""
        try:
            import json as json_module
            
            # Find application/json script tags
            soup = BeautifulSoup(page_source, 'html.parser')
            script_tags = soup.find_all('script', {'type': 'application/json'})
            
            extracted_data = {}
            
            for script in script_tags:
                try:
                    json_content = script.string
                    if not json_content:
                        continue
                    
                    data = json_module.loads(json_content)
                    
                    # Look for Facebook-specific structures
                    if 'require' in data:
                        self.process_facebook_require_data(data['require'], extracted_data)
                    
                    # Look for profile tile sections
                    if 'props' in data:
                        self.process_facebook_props_data(data['props'], extracted_data)
                        
                except Exception as e:
                    logger.debug(f"Failed to parse JSON script: {e}")
                    continue
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error extracting Facebook JSON: {e}")
            return {}
    
    def process_facebook_require_data(self, require_data, extracted_data):
        """Process Facebook's require data structure"""
        try:
            for require_item in require_data:
                if isinstance(require_item, list) and len(require_item) > 3:
                    if require_item[0] == "ScheduledServerJS" and require_item[1] == "handle":
                        self.process_scheduled_server_js(require_item[3], extracted_data)
        except Exception as e:
            logger.debug(f"Error processing require data: {e}")
    
    def process_scheduled_server_js(self, data, extracted_data):
        """Process ScheduledServerJS data to find profile information"""
        try:
            if isinstance(data, list) and len(data) > 1:
                js_data = data[1]
                if isinstance(js_data, dict) and '__bbox' in js_data:
                    bbox_data = js_data['__bbox']
                    if 'result' in bbox_data and 'data' in bbox_data['result']:
                        profile_data = bbox_data['result']['data']
                        self.extract_from_profile_data(profile_data, extracted_data)
        except Exception as e:
            logger.debug(f"Error processing ScheduledServerJS: {e}")
    
    def process_facebook_props_data(self, props_data, extracted_data):
        """Process Facebook props data"""
        try:
            # Look for profile-related data in props
            if 'profile' in props_data:
                self.extract_from_profile_data(props_data['profile'], extracted_data)
        except Exception as e:
            logger.debug(f"Error processing props data: {e}")
    
    def extract_from_profile_data(self, profile_data, extracted_data):
        """Extract information from Facebook profile data structure"""
        try:
            # Look for profile tile sections
            if 'profile_tile_sections' in profile_data:
                sections = profile_data['profile_tile_sections']
                if 'edges' in sections:
                    for edge in sections['edges']:
                        node = edge.get('node', {})
                        section_type = node.get('profile_tile_section_type')
                        
                        if section_type == 'INTRO':
                            self.extract_intro_section_data(node, extracted_data)
                        elif section_type == 'WORK':
                            self.extract_work_section_data(node, extracted_data)
                        elif section_type == 'EDUCATION':
                            self.extract_education_section_data(node, extracted_data)
                        elif section_type == 'PLACES':
                            self.extract_places_section_data(node, extracted_data)
                        elif section_type == 'CONTACT':
                            self.extract_contact_section_data(node, extracted_data)
                        elif section_type == 'FAMILY':
                            self.extract_family_section_data(node, extracted_data)
                        elif section_type == 'LIFE_EVENTS':
                            self.extract_life_events_section_data(node, extracted_data)
                            
        except Exception as e:
            logger.debug(f"Error extracting from profile data: {e}")
    
    def extract_intro_section_data(self, intro_node, extracted_data):
        """Extract data from INTRO section"""
        try:
            if 'profile_tile_views' in intro_node:
                views = intro_node['profile_tile_views']
                if 'nodes' in views:
                    for view in views['nodes']:
                        renderer = view.get('view_style_renderer', {})
                        if renderer.get('__typename') == 'ProfileTileViewContextListRenderer':
                            view_data = renderer.get('view', {})
                            self.extract_context_list_data(view_data, extracted_data)
        except Exception as e:
            logger.debug(f"Error extracting intro section: {e}")
    
    def extract_context_list_data(self, view_data, extracted_data):
        """Extract data from context list view"""
        try:
            if 'profile_tile_items' in view_data:
                items = view_data['profile_tile_items']
                if 'nodes' in items:
                    for item in items['nodes']:
                        node = item.get('node', {})
                        context_item = node.get('timeline_context_item', {})
                        renderer = context_item.get('renderer', {})
                        
                        if 'context_item' in renderer:
                            self.process_context_item(renderer['context_item'], node, extracted_data)
        except Exception as e:
            logger.debug(f"Error extracting context list: {e}")
    
    def process_context_item(self, context_data, node, extracted_data):
        """Process individual context item"""
        try:
            title_data = context_data.get('title', {})
            title_text = title_data.get('text', '')
            item_type = node.get('timeline_context_list_item_type', '')
            
            if not title_text or not item_type:
                return
            
            # Process different types of context items
            if item_type == 'INTRO_CARD_WORK':
                self.extract_work_info(title_text, title_data, extracted_data)
            elif item_type == 'INTRO_CARD_EDUCATION':
                self.extract_education_info(title_text, title_data, extracted_data)
            elif item_type == 'INTRO_CARD_CURRENT_CITY':
                extracted_data['current_location'] = title_text
            elif item_type == 'INTRO_CARD_HOMETOWN':
                extracted_data['origin_location'] = title_text
            elif item_type == 'INTRO_CARD_RELATIONSHIP':
                extracted_data['relationship_status'] = title_text
            elif item_type == 'INTRO_CARD_LANGUAGES':
                self.extract_languages_info(title_text, extracted_data)
            elif item_type == 'INTRO_CARD_RELIGIOUS_VIEWS':
                extracted_data['religious_info'] = title_text
            elif item_type == 'INTRO_CARD_FAMILY_MEMBERS':
                self.extract_family_member_info(title_text, title_data, extracted_data)
            elif item_type == 'INTRO_CARD_INTERESTS':
                self.extract_interests_info(title_text, extracted_data)
            elif item_type == 'INTRO_CARD_CONTACT_INFO':
                self.extract_contact_info_from_json(title_text, extracted_data)
            elif item_type == 'INTRO_CARD_WEBSITE':
                self.extract_website_info(context_data, extracted_data)
            elif item_type == 'INTRO_CARD_LIFE_EVENT':
                self.extract_life_event_info(title_text, extracted_data)
            elif item_type == 'INTRO_CARD_FAVORITE_QUOTES':
                extracted_data['favorite_quotes'] = title_text
            elif item_type == 'INTRO_CARD_OTHER_NAMES':
                extracted_data['other_names'] = title_text
            elif item_type == 'INTRO_CARD_ABOUT':
                extracted_data['about_section'] = title_text
            elif item_type == 'INTRO_CARD_EMAIL':
                extracted_data['contact_email'] = title_text
            elif item_type == 'INTRO_CARD_PHONE':
                extracted_data['contact_phone'] = title_text
            elif item_type == 'INTRO_CARD_BIRTHDAY':
                extracted_data['birthday'] = title_text
            elif item_type == 'INTRO_CARD_POLITICAL_VIEWS':
                extracted_data['political_views'] = title_text
            elif item_type.startswith('INTRO_CARD_'):
                logger.info(f"Unknown INTRO_CARD type: {item_type} - {title_text}")
                
        except Exception as e:
            logger.debug(f"Error processing context item: {e}")
    
    def extract_work_info(self, title_text, title_data, extracted_data):
        """Extract work information from JSON"""
        try:
            work_info = {
                'position': '',
                'company': '',
                'current': True
            }
            
            # Parse work text
            if ' at ' in title_text:
                parts = title_text.split(' at ', 1)
                work_info['position'] = parts[0].strip()
                work_info['company'] = parts[1].strip()
            else:
                work_info['company'] = title_text.strip()
            
            # Initialize work history if not exists
            if 'work_history' not in extracted_data:
                extracted_data['work_history'] = []
            
            extracted_data['work_history'].append(work_info)
            
            # Set current employer
            if work_info['current']:
                extracted_data['current_employer'] = work_info['company']
                extracted_data['professional_title'] = work_info['position']
                
        except Exception as e:
            logger.debug(f"Error extracting work info: {e}")
    
    def extract_education_info(self, title_text, title_data, extracted_data):
        """Extract education information from JSON"""
        try:
            edu_info = {
                'institution': title_text.strip(),
                'type': 'education'
            }
            
            # Initialize education if not exists
            if 'education_history' not in extracted_data:
                extracted_data['education_history'] = []
            
            extracted_data['education_history'].append(edu_info)
            
        except Exception as e:
            logger.debug(f"Error extracting education info: {e}")
    
    def extract_languages_info(self, title_text, extracted_data):
        """Extract languages information"""
        try:
            # Parse multiple languages
            languages = []
            separators = [',', ';', ' and ', ' și ', ' si ', '•']
            
            text = title_text
            for sep in separators:
                if sep in text:
                    languages = [lang.strip() for lang in text.split(sep)]
                    break
            
            if not languages:
                languages = [title_text.strip()]
            
            extracted_data['languages'] = languages
            
        except Exception as e:
            logger.debug(f"Error extracting languages: {e}")
    
    def extract_family_member_info(self, title_text, title_data, extracted_data):
        """Extract family member information"""
        try:
            if 'family_members' not in extracted_data:
                extracted_data['family_members'] = []
            
            family_info = {
                'relationship': 'family',
                'name': title_text.strip()
            }
            
            # Determine relationship type
            text_lower = title_text.lower()
            if any(word in text_lower for word in ['married', 'wife', 'husband', 'spouse']):
                family_info['relationship'] = 'spouse'
            elif any(word in text_lower for word in ['son', 'daughter', 'child']):
                family_info['relationship'] = 'child'
            elif any(word in text_lower for word in ['mother', 'father', 'parent']):
                family_info['relationship'] = 'parent'
            elif any(word in text_lower for word in ['sister', 'brother', 'sibling']):
                family_info['relationship'] = 'sibling'
            
            extracted_data['family_members'].append(family_info)
            
        except Exception as e:
            logger.debug(f"Error extracting family member: {e}")
    
    def extract_interests_info(self, title_text, extracted_data):
        """Extract interests information"""
        try:
            interests = []
            separators = [',', ';', ' and ', ' și ', ' si ', '•', '·']
            
            text = title_text
            for sep in separators:
                if sep in text:
                    interests = [interest.strip() for interest in text.split(sep)]
                    break
            
            if not interests:
                interests = [title_text.strip()]
            
            extracted_data['interests_detailed'] = interests
            
        except Exception as e:
            logger.debug(f"Error extracting interests: {e}")
    
    def extract_contact_info_from_json(self, title_text, extracted_data):
        """Extract contact information from JSON"""
        try:
            # Check for email
            if '@' in title_text and '.' in title_text:
                extracted_data['contact_email'] = title_text.strip()
            
            # Check for phone
            import re
            if re.match(r'[\+]?[0-9\s\-\(\)]{8,}', title_text):
                extracted_data['contact_phone'] = title_text.strip()
                
        except Exception as e:
            logger.debug(f"Error extracting contact info: {e}")
    
    def extract_website_info(self, context_data, extracted_data):
        """Extract website information"""
        try:
            url = context_data.get('url', '')
            plaintext_title = context_data.get('plaintext_title', {}).get('text', '')
            
            if url:
                if 'social_media_links' not in extracted_data:
                    extracted_data['social_media_links'] = {}
                
                if 'youtube.com' in url:
                    extracted_data['social_media_links']['YouTube'] = url
                elif 'instagram.com' in url:
                    extracted_data['social_media_links']['Instagram'] = url
                elif 'twitter.com' in url:
                    extracted_data['social_media_links']['Twitter'] = url
                else:
                    extracted_data['website'] = url
                    
        except Exception as e:
            logger.debug(f"Error extracting website info: {e}")
    
    def extract_life_event_info(self, title_text, extracted_data):
        """Extract life event information"""
        try:
            if 'life_events' not in extracted_data:
                extracted_data['life_events'] = []
            
            extracted_data['life_events'].append(title_text.strip())
            
        except Exception as e:
            logger.debug(f"Error extracting life event: {e}")
    
    def extract_meta_information(self, soup, profile_data):
        """Extract information from meta tags"""
        try:
            # Extract from meta tags
            meta_title = soup.find('meta', {'property': 'og:title'})
            if meta_title and not profile_data.get('overview', {}).get('name'):
                title_content = meta_title.get('content', '')
                if title_content and 'Facebook' not in title_content:
                    if 'overview' not in profile_data:
                        profile_data['overview'] = {}
                    profile_data['overview']['name'] = title_content.strip()
            
            meta_description = soup.find('meta', {'property': 'og:description'})
            if meta_description and not profile_data.get('details_about', {}).get('about_text'):
                desc_content = meta_description.get('content', '')
                if desc_content and len(desc_content) > 10:
                    if 'details_about' not in profile_data:
                        profile_data['details_about'] = {}
                    profile_data['details_about']['about_text'] = desc_content.strip()
                    
        except Exception as e:
            logger.debug(f"Error extracting meta information: {e}")
    
    def merge_json_data(self, json_data, profile_data):
        """Merge JSON extracted data into profile_data structure"""
        try:
            # Merge work information
            if json_data.get('work_history'):
                if 'work_education' not in profile_data:
                    profile_data['work_education'] = {}
                profile_data['work_education']['work_history'] = json_data['work_history']
            
            if json_data.get('current_employer'):
                if 'overview' not in profile_data:
                    profile_data['overview'] = {}
                profile_data['overview']['current_work'] = json_data['current_employer']
            
            if json_data.get('professional_title'):
                if 'overview' not in profile_data:
                    profile_data['overview'] = {}
                profile_data['overview']['professional_title'] = json_data['professional_title']
            
            # Merge education information
            if json_data.get('education_history'):
                if 'work_education' not in profile_data:
                    profile_data['work_education'] = {}
                profile_data['work_education']['education_history'] = json_data['education_history']
            
            # Merge location information
            if json_data.get('current_location'):
                if 'places_lived' not in profile_data:
                    profile_data['places_lived'] = {}
                profile_data['places_lived']['current_city'] = json_data['current_location']
            
            if json_data.get('origin_location'):
                if 'places_lived' not in profile_data:
                    profile_data['places_lived'] = {}
                profile_data['places_lived']['hometown'] = json_data['origin_location']
            
            # Merge contact information
            if json_data.get('languages'):
                if 'contact_basic_info' not in profile_data:
                    profile_data['contact_basic_info'] = {}
                profile_data['contact_basic_info']['languages'] = json_data['languages']
            
            if json_data.get('contact_email'):
                if 'contact_basic_info' not in profile_data:
                    profile_data['contact_basic_info'] = {}
                profile_data['contact_basic_info']['email'] = json_data['contact_email']
            
            if json_data.get('contact_phone'):
                if 'contact_basic_info' not in profile_data:
                    profile_data['contact_basic_info'] = {}
                profile_data['contact_basic_info']['phone'] = json_data['contact_phone']
            
            # Merge family information
            if json_data.get('relationship_status'):
                if 'family_relationships' not in profile_data:
                    profile_data['family_relationships'] = {}
                profile_data['family_relationships']['relationship_status'] = json_data['relationship_status']
            
            if json_data.get('family_members'):
                if 'family_relationships' not in profile_data:
                    profile_data['family_relationships'] = {}
                profile_data['family_relationships']['family_members'] = json_data['family_members']
            
            # Merge details information
            if json_data.get('about_section'):
                if 'details_about' not in profile_data:
                    profile_data['details_about'] = {}
                profile_data['details_about']['about_text'] = json_data['about_section']
            
            if json_data.get('interests_detailed'):
                if 'details_about' not in profile_data:
                    profile_data['details_about'] = {}
                profile_data['details_about']['interests'] = json_data['interests_detailed']
            
            if json_data.get('favorite_quotes'):
                if 'details_about' not in profile_data:
                    profile_data['details_about'] = {}
                profile_data['details_about']['quotes'] = [json_data['favorite_quotes']]
            
            # Merge life events
            if json_data.get('life_events'):
                profile_data['life_events'] = json_data['life_events']
            
            # Merge social media links
            if json_data.get('social_media_links'):
                if 'contact_basic_info' not in profile_data:
                    profile_data['contact_basic_info'] = {}
                profile_data['contact_basic_info']['social_links'] = json_data['social_media_links']
            
            logger.info(f"✅ Successfully merged JSON data: {len(json_data)} fields")
            
        except Exception as e:
            logger.error(f"Error merging JSON data: {e}")
    
    def extract_overview_section(self, soup, profile_data):
        """Extract Overview section information with enhanced patterns"""
        try:
            overview = {}
            
            # Remove script tags and other non-content elements
            for script in soup(["script", "style", "noscript", "meta", "link"]):
                script.decompose()
            
            all_text = soup.get_text()
            
            # Enhanced work extraction
            work_indicators = ['works at', 'work at', 'employed at', 'job at', 'position at', 'lucreaza la', 'angajat la']
            for indicator in work_indicators:
                work_pattern = rf'(?i){re.escape(indicator)}\s+([^\n{{}}]+)'
                matches = re.findall(work_pattern, all_text)
                
                for match in matches:
                    work_text = match.strip()
                    if work_text and len(work_text) > 2 and len(work_text) < 200:
                        # Validate it's not JavaScript
                        if not any(js_word in work_text.lower() for js_word in ['function', 'var', 'const', 'null', 'undefined']):
                            overview['current_work'] = f"{indicator} {work_text}"
                            logger.info(f"✅ Work found: {indicator} {work_text}")
                            break
                
                if 'current_work' in overview:
                    break
            
            # Enhanced education extraction
            education_indicators = ['studied at', 'studies at', 'graduated from', 'went to', 'university', 'college', 'faculty', 'facultatea']
            for indicator in education_indicators:
                education_pattern = rf'(?i){re.escape(indicator)}\s+([^\n{{}}]+)'
                matches = re.findall(education_pattern, all_text)
                
                for match in matches:
                    edu_text = match.strip()
                    if edu_text and len(edu_text) > 2 and len(edu_text) < 200:
                        if not any(js_word in edu_text.lower() for js_word in ['function', 'var', 'const', 'null', 'undefined']):
                            overview['education'] = f"{indicator} {edu_text}"
                            logger.info(f"✅ Education found: {indicator} {edu_text}")
                            break
                
                if 'education' in overview:
                    break
            
            # Enhanced location extraction
            location_indicators = ['lives in', 'based in', 'located in', 'from', 'hometown', 'current city', 'traieste in', 'locuieste in']
            for indicator in location_indicators:
                location_pattern = rf'(?i){re.escape(indicator)}\s+([^\n{{}}]+)'
                matches = re.findall(location_pattern, all_text)
                
                for match in matches:
                    location_text = match.strip()
                    if location_text and len(location_text) > 2 and len(location_text) < 100:
                        if not any(js_word in location_text.lower() for js_word in ['function', 'var', 'const', 'null', 'undefined']):
                            overview['location'] = f"{indicator} {location_text}"
                            logger.info(f"✅ Location found: {indicator} {location_text}")
                            break
                
                if 'location' in overview:
                    break
            
            profile_data['overview'] = overview
            logger.info(f"📋 Overview extracted: {len(overview)} items")
            
        except Exception as e:
            logger.error(f"Error extracting overview: {e}")
    
    def extract_work_education_section(self, soup, profile_data):
        """Extract Work and Education section information with enhanced patterns"""
        try:
            work_education = {
                'work_history': [],
                'education_history': []
            }
            
            # Remove script tags and other non-content elements
            for script in soup(["script", "style", "noscript", "meta", "link"]):
                script.decompose()
            
            all_text = soup.get_text()
            
            # Enhanced work extraction with multiple patterns
            work_patterns = [
                r'(?i)(works?\s+at|work\s+at|employed\s+at|job\s+at|position\s+at)\s+([^\n{}]+)',
                r'(?i)(archdeacon|protopsalt|cantaret|diacon)\s*(and\s*)?([^{}\n]+)?',
                r'(?i)(lucreaza\s+la|angajat\s+la|pozitie\s+la)\s+([^\n{}]+)',
                r'(?i)(currently\s+working\s+at|presently\s+at)\s+([^\n{}]+)'
            ]
            
            for pattern in work_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        work_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        work_text = str(match).strip()
                    
                    if work_text and len(work_text) > 5 and len(work_text) < 200:
                        # Validate it's not JavaScript or system text
                        if not any(invalid in work_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined', 'javascript']):
                            work_education['work_history'].append(work_text)
                            logger.info(f"✅ Work found: {work_text}")
            
            # Enhanced education extraction
            education_patterns = [
                r'(?i)(studied\s+at|studies\s+at|graduated\s+from|went\s+to)\s+([^\n{}]+)',
                r'(?i)(facultatea\s+de\s+teologie|university|college|faculty)\s+([^\n{}]+)',
                r'(?i)(bachelor|master|phd|degree)\s+([^\n{}]+)',
                r'(?i)(a\s+studiat\s+la|absolvent\s+de\s+la)\s+([^\n{}]+)'
            ]
            
            for pattern in education_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        edu_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        edu_text = str(match).strip()
                    
                    if edu_text and len(edu_text) > 5 and len(edu_text) < 200:
                        if not any(invalid in edu_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined', 'javascript']):
                            work_education['education_history'].append(edu_text)
                            logger.info(f"✅ Education found: {edu_text}")
            
            # Remove duplicates while preserving order
            work_education['work_history'] = list(dict.fromkeys(work_education['work_history']))
            work_education['education_history'] = list(dict.fromkeys(work_education['education_history']))
            
            profile_data['work_education'] = work_education
            logger.info(f"💼 Work & Education extracted: {len(work_education['work_history'])} work, {len(work_education['education_history'])} education")
            
        except Exception as e:
            logger.error(f"Error extracting work/education: {e}")
    
    def extract_places_lived_section(self, soup, profile_data):
        """Extract Places Lived section information with enhanced patterns"""
        try:
            places = {
                'current_city': None,
                'hometown': None,
                'other_places': []
            }
            
            # Remove script tags and other non-content elements
            for script in soup(["script", "style", "noscript", "meta", "link"]):
                script.decompose()
            
            all_text = soup.get_text()
            
            # Enhanced current location extraction
            current_location_patterns = [
                r'(?i)(lives\s+in|based\s+in|located\s+in|current\s+city)\s+([^\n{}]+)',
                r'(?i)(traieste\s+in|locuieste\s+in|localizat\s+in)\s+([^\n{}]+)'
            ]
            
            for pattern in current_location_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        location_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        location_text = str(match).strip()
                    
                    if location_text and len(location_text) > 2 and len(location_text) < 100:
                        if not any(invalid in location_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            places['current_city'] = location_text
                            logger.info(f"✅ Current city found: {location_text}")
                            break
                
                if places['current_city']:
                    break
            
            # Enhanced hometown extraction
            hometown_patterns = [
                r'(?i)(from|hometown|born\s+in|originar\s+din)\s+([^\n{}]+)',
                r'(?i)(provine\s+din|nascut\s+in|orasul\s+natal)\s+([^\n{}]+)'
            ]
            
            for pattern in hometown_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        hometown_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        hometown_text = str(match).strip()
                    
                    if hometown_text and len(hometown_text) > 2 and len(hometown_text) < 100:
                        if not any(invalid in hometown_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            places['hometown'] = hometown_text
                            logger.info(f"✅ Hometown found: {hometown_text}")
                            break
                
                if places['hometown']:
                    break
            
            # Enhanced other places extraction
            other_places_patterns = [
                r'(?i)(moved\s+to|lived\s+in|stayed\s+in|resided\s+in)\s+([^\n{}]+)',
                r'(?i)(s-a\s+mutat\s+la|a\s+locuit\s+in|a\s+stat\s+in)\s+([^\n{}]+)'
            ]
            
            for pattern in other_places_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        place_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        place_text = str(match).strip()
                    
                    if place_text and len(place_text) > 2 and len(place_text) < 100:
                        if not any(invalid in place_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            if place_text not in places['other_places']:
                                places['other_places'].append(place_text)
                                logger.info(f"✅ Other place found: {place_text}")
            
            profile_data['places_lived'] = places
            logger.info(f"🏠 Places lived extracted: {len([p for p in places.values() if p])} locations")
            
        except Exception as e:
            logger.error(f"Error extracting places lived: {e}")
    
    def extract_contact_basic_info_section(self, soup, profile_data):
        """Extract Contact and Basic Info section with enhanced patterns"""
        try:
            contact_info = {
                'email': None,
                'phone': None,
                'website': None,
                'birthday': None,
                'gender': None,
                'languages': []
            }
            
            # Remove script tags and other non-content elements
            for script in soup(["script", "style", "noscript", "meta", "link"]):
                script.decompose()
            
            all_text = soup.get_text()
            
            # Enhanced email extraction
            email_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                r'(?i)(email|e-mail|contact):\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
            ]
            
            for pattern in email_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    email = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    # Validate email and filter out fake/test emails
                    if email and '@' in email and '.' in email:
                        if not any(fake in email.lower() for fake in ['example.com', 'test.com', 'fake.com', 'dummy.com']):
                            contact_info['email'] = email
                            logger.info(f"✅ Email found: {email}")
                            break
                
                if contact_info['email']:
                    break
            
            # Enhanced phone extraction
            phone_patterns = [
                r'(?i)(phone|tel|mobile|telefon):\s*([+]?[0-9\s\-\(\)]{8,})',
                r'[+]?[0-9\s\-\(\)]{8,}',
                r'(?i)(contact|call):\s*([+]?[0-9\s\-\(\)]{8,})'
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    phone = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    clean_phone = re.sub(r'[^\d+]', '', phone)
                    if len(clean_phone) >= 8 and len(clean_phone) <= 15:
                        contact_info['phone'] = phone
                        logger.info(f"✅ Phone found: {phone}")
                        break
                
                if contact_info['phone']:
                    break
            
            # Enhanced website extraction
            website_patterns = [
                r'(?i)(website|site|url):\s*(https?://[^\s]+)',
                r'(https?://[^\s]+)',
                r'(?i)(link|vezi):\s*(https?://[^\s]+)'
            ]
            
            for pattern in website_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    url = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if url and url.startswith(('http://', 'https://')):
                        # Filter out Facebook URLs and other social media
                        if not any(social in url.lower() for social in ['facebook.com', 'instagram.com', 'twitter.com']):
                            contact_info['website'] = url
                            logger.info(f"✅ Website found: {url}")
                            break
                
                if contact_info['website']:
                    break
            
            # Enhanced language extraction
            language_patterns = [
                r'(?i)(speaks|language|fluent|native|vorbeste|limba):\s*([^\n{}]+)',
                r'(?i)(limbi|languages):\s*([^\n{}]+)',
                r'(?i)(romanian|english|french|german|italian|spanish|greek)',
                r'(?i)(romana|engleza|franceza|germana|italiana|spaniola|greaca)'
            ]
            
            for pattern in language_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    lang_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if lang_text and len(lang_text) > 1 and len(lang_text) < 50:
                        if not any(invalid in lang_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            contact_info['languages'].append(lang_text)
                            logger.info(f"✅ Language found: {lang_text}")
            
            # Remove duplicates from languages
            contact_info['languages'] = list(dict.fromkeys(contact_info['languages']))
            
            profile_data['contact_basic_info'] = contact_info
            logger.info(f"📞 Contact info extracted: {len([v for v in contact_info.values() if v])} items")
            
        except Exception as e:
            logger.error(f"Error extracting contact info: {e}")
    
    def extract_family_relationships_section(self, soup, profile_data):
        """Extract Family and Relationships section with enhanced patterns"""
        try:
            family = {
                'relationship_status': None,
                'family_members': [],
                'partner': None,
                'children': [],
                'parents': [],
                'siblings': []
            }
            
            # Remove script tags and other non-content elements
            for script in soup(["script", "style", "noscript", "meta", "link"]):
                script.decompose()
            
            all_text = soup.get_text()
            
            # Enhanced relationship status extraction
            relationship_patterns = [
                r'(?i)(married|single|in\s+a\s+relationship|engaged|divorced|widowed)\s*([^\n{}]*)',
                r'(?i)(casatorit|necasatorit|intr-o\s+relatie|logodit|divortat)\s*([^\n{}]*)',
                r'(?i)(relationship\s+status|status\s+relatie):\s*([^\n{}]+)',
                r'(?i)(married\s+to|casatorit\s+cu|sotie|sot)\s+([^\n{}]+)'
            ]
            
            for pattern in relationship_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        status_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        status_text = str(match).strip()
                    
                    if status_text and len(status_text) > 3 and len(status_text) < 100:
                        if not any(invalid in status_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            family['relationship_status'] = status_text
                            logger.info(f"✅ Relationship status found: {status_text}")
                            break
                
                if family['relationship_status']:
                    break
            
            # Enhanced family members extraction
            family_patterns = [
                r'(?i)(mother|father|mama|tata|parent):\s*([^\n{}]+)',
                r'(?i)(sister|brother|sora|frate|sibling):\s*([^\n{}]+)',
                r'(?i)(son|daughter|fiu|fiica|child):\s*([^\n{}]+)',
                r'(?i)(wife|husband|sotie|sot|spouse):\s*([^\n{}]+)',
                r'(?i)(family\s+member|membru\s+familie):\s*([^\n{}]+)'
            ]
            
            for pattern in family_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        member_text = ' '.join(str(m) for m in match if m).strip()
                        relationship_type = match[0].lower()
                    else:
                        member_text = str(match).strip()
                        relationship_type = 'family'
                    
                    if member_text and len(member_text) > 2 and len(member_text) < 100:
                        if not any(invalid in member_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            family['family_members'].append(member_text)
                            
                            # Categorize by relationship type
                            if any(rel in relationship_type for rel in ['mother', 'father', 'mama', 'tata', 'parent']):
                                family['parents'].append(member_text)
                            elif any(rel in relationship_type for rel in ['sister', 'brother', 'sora', 'frate', 'sibling']):
                                family['siblings'].append(member_text)
                            elif any(rel in relationship_type for rel in ['son', 'daughter', 'fiu', 'fiica', 'child']):
                                family['children'].append(member_text)
                            elif any(rel in relationship_type for rel in ['wife', 'husband', 'sotie', 'sot', 'spouse']):
                                family['partner'] = member_text
                            
                            logger.info(f"✅ Family member found: {member_text} ({relationship_type})")
            
            # Remove duplicates
            family['family_members'] = list(dict.fromkeys(family['family_members']))
            family['children'] = list(dict.fromkeys(family['children']))
            family['parents'] = list(dict.fromkeys(family['parents']))
            family['siblings'] = list(dict.fromkeys(family['siblings']))
            
            profile_data['family_relationships'] = family
            logger.info(f"👨‍👩‍👧‍👦 Family info extracted: {len(family['family_members'])} members")
            
        except Exception as e:
            logger.error(f"Error extracting family info: {e}")
    
    def extract_details_about_section(self, soup, profile_data):
        """Extract Details About section with enhanced patterns"""
        try:
            details = {
                'about_text': None,
                'quotes': [],
                'interests': [],
                'favorite_books': [],
                'favorite_movies': [],
                'favorite_music': [],
                'other_info': []
            }
            
            # Remove script tags and other non-content elements
            for script in soup(["script", "style", "noscript", "meta", "link"]):
                script.decompose()
            
            all_text = soup.get_text()
            
            # Enhanced about/bio text extraction
            bio_patterns = [
                r'(?i)(about|bio|description|despre|descriere):\s*([^\n{}]{20,500})',
                r'(?s)(about\s+me|despre\s+mine):\s*([^\n{}]{20,500})',
                r'(?i)(personal\s+info|informatii\s+personale):\s*([^\n{}]{20,500})'
            ]
            
            for pattern in bio_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    bio_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if bio_text and len(bio_text) > 20 and len(bio_text) < 500:
                        if not any(invalid in bio_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined', 'javascript']):
                            details['about_text'] = bio_text.strip()
                            logger.info(f"✅ About text found: {bio_text[:100]}...")
                            break
                
                if details['about_text']:
                    break
            
            # Enhanced quotes extraction
            quote_patterns = [
                r'(?i)(favorite\s+quote|quote|saying|motto|citat):\s*([^\n{}]{10,200})',
                r'(?i)(proverb|proverbe|zicala):\s*([^\n{}]{10,200})',
                r'"([^"]{10,200})"',
                r"'([^']{10,200})'"
            ]
            
            for pattern in quote_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    quote_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if quote_text and len(quote_text) > 10 and len(quote_text) < 200:
                        if not any(invalid in quote_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            details['quotes'].append(quote_text.strip())
                            logger.info(f"✅ Quote found: {quote_text[:50]}...")
            
            # Enhanced interests extraction
            interest_patterns = [
                r'(?i)(interests|hobbies|pasiuni|hobby):\s*([^\n{}]{5,200})',
                r'(?i)(likes|enjoy|place|imi\s+place):\s*([^\n{}]{5,200})',
                r'(?i)(favorite\s+activities|activitati\s+preferate):\s*([^\n{}]{5,200})'
            ]
            
            for pattern in interest_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    interest_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if interest_text and len(interest_text) > 5 and len(interest_text) < 200:
                        if not any(invalid in interest_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            details['interests'].append(interest_text.strip())
                            logger.info(f"✅ Interest found: {interest_text[:50]}...")
            
            # Enhanced favorite books extraction
            book_patterns = [
                r'(?i)(favorite\s+book|books|carti\s+preferate):\s*([^\n{}]{5,200})',
                r'(?i)(reading|citeste|lectura):\s*([^\n{}]{5,200})'
            ]
            
            for pattern in book_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    book_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if book_text and len(book_text) > 5 and len(book_text) < 200:
                        if not any(invalid in book_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            details['favorite_books'].append(book_text.strip())
                            logger.info(f"✅ Favorite book found: {book_text[:50]}...")
            
            # Enhanced favorite movies extraction
            movie_patterns = [
                r'(?i)(favorite\s+movie|movies|filme\s+preferate):\s*([^\n{}]{5,200})',
                r'(?i)(cinema|film):\s*([^\n{}]{5,200})'
            ]
            
            for pattern in movie_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    movie_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if movie_text and len(movie_text) > 5 and len(movie_text) < 200:
                        if not any(invalid in movie_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            details['favorite_movies'].append(movie_text.strip())
                            logger.info(f"✅ Favorite movie found: {movie_text[:50]}...")
            
            # Enhanced favorite music extraction
            music_patterns = [
                r'(?i)(favorite\s+music|music|muzica\s+preferata):\s*([^\n{}]{5,200})',
                r'(?i)(listening\s+to|asculta|artist):\s*([^\n{}]{5,200})'
            ]
            
            for pattern in music_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    music_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if music_text and len(music_text) > 5 and len(music_text) < 200:
                        if not any(invalid in music_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            details['favorite_music'].append(music_text.strip())
                            logger.info(f"✅ Favorite music found: {music_text[:50]}...")
            
            # Remove duplicates
            details['quotes'] = list(dict.fromkeys(details['quotes']))
            details['interests'] = list(dict.fromkeys(details['interests']))
            details['favorite_books'] = list(dict.fromkeys(details['favorite_books']))
            details['favorite_movies'] = list(dict.fromkeys(details['favorite_movies']))
            details['favorite_music'] = list(dict.fromkeys(details['favorite_music']))
            
            profile_data['details_about'] = details
            logger.info(f"📝 Details extracted: {len([v for v in details.values() if v])} items")
            
        except Exception as e:
            logger.error(f"Error extracting details: {e}")
    
    def extract_life_events_section(self, soup, profile_data):
        """Extract Life Events section with enhanced patterns"""
        try:
            life_events = []
            
            # Remove script tags and other non-content elements
            for script in soup(["script", "style", "noscript", "meta", "link"]):
                script.decompose()
            
            all_text = soup.get_text()
            
            # Enhanced life events extraction
            life_event_patterns = [
                r'(?i)(born|nascut|birth)\s+([^\n{}]{5,100})',
                r'(?i)(graduated|absolvit|graduation)\s+([^\n{}]{5,100})',
                r'(?i)(started|began|inceput)\s+([^\n{}]{5,100})',
                r'(?i)(joined|became|devenir)\s+([^\n{}]{5,100})',
                r'(?i)(moved|se\s+muta|relocat)\s+([^\n{}]{5,100})',
                r'(?i)(married|casatorit|marriage)\s+([^\n{}]{5,100})',
                r'(?i)(divorced|divortat|separation)\s+([^\n{}]{5,100})',
                r'(?i)(retired|pensionat|retirement)\s+([^\n{}]{5,100})',
                r'(?i)(promoted|promovat|promotion)\s+([^\n{}]{5,100})',
                r'(?i)(founded|infiintat|started)\s+([^\n{}]{5,100})',
                r'(?i)(launched|lansat|created)\s+([^\n{}]{5,100})',
                r'(?i)(achieved|realizat|accomplished)\s+([^\n{}]{5,100})',
                r'(?i)(ordained|hirotonit|appointment)\s+([^\n{}]{5,100})',
                r'(?i)(received|primit|awarded)\s+([^\n{}]{5,100})'
            ]
            
            for pattern in life_event_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        event_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        event_text = str(match).strip()
                    
                    if event_text and len(event_text) > 10 and len(event_text) < 200:
                        # Validate it's not JavaScript or system text
                        if not any(invalid in event_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined', 'javascript']):
                            life_events.append(event_text)
                            logger.info(f"✅ Life event found: {event_text[:50]}...")
            
            # Look for date-based life events
            date_event_patterns = [
                r'(?i)(in\s+\d{4}|on\s+\w+\s+\d{1,2}|since\s+\d{4})\s+([^\n{}]{10,150})',
                r'(?i)(din\s+\d{4}|pe\s+\d{1,2}\s+\w+|de\s+la\s+\d{4})\s+([^\n{}]{10,150})'
            ]
            
            for pattern in date_event_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        event_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        event_text = str(match).strip()
                    
                    if event_text and len(event_text) > 10 and len(event_text) < 200:
                        if not any(invalid in event_text.lower() for invalid in ['function', 'var', 'const', 'null', 'undefined']):
                            life_events.append(event_text)
                            logger.info(f"✅ Date-based life event found: {event_text[:50]}...")
            
            # Remove duplicates while preserving order
            life_events = list(dict.fromkeys(life_events))
            
            profile_data['life_events'] = life_events
            logger.info(f"🎯 Life events extracted: {len(life_events)} events")
            
        except Exception as e:
            logger.error(f"Error extracting life events: {e}")
    
    def scrape_facebook_profile(self, profile_url):
        """
        Complete profile scraping process with enhanced extraction
        Args:
            profile_url: Facebook profile URL to scrape
        Returns:
            dict: Complete profile data in database format
        """
        if not self.logged_in:
            logger.error("❌ Not logged in to Facebook")
            return None
        
        try:
            # Navigate to profile About section
            if not self.navigate_to_profile_about(profile_url):
                return None
            
            # Extract all About section information
            raw_profile_data = self.extract_about_sections()
            
            # Add metadata
            raw_profile_data['profile_url'] = profile_url
            raw_profile_data['scraped_at'] = time.time()
            
            # Transform to database format
            transformed_data = self.transform_to_database_format(raw_profile_data)
            
            # Set basic info if available
            if not transformed_data.get('name'):
                # Try to extract name from page title or other sources
                try:
                    page_title = self.driver.title
                    if page_title and 'Facebook' in page_title:
                        name_part = page_title.replace('Facebook', '').strip()
                        if name_part and len(name_part) > 1:
                            transformed_data['name'] = name_part
                except:
                    pass
            
            logger.info("✅ Profile scraping completed successfully")
            return transformed_data
            
        except Exception as e:
            logger.error(f"❌ Error scraping profile: {e}")
            return None
    
    def close(self):
        """Close the WebDriver session"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("🔄 WebDriver session closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None
                self.logged_in = False
    
    def transform_to_database_format(self, profile_data):
        """Transform extracted About section data to database format"""
        try:
            # Initialize database-compatible format
            transformed_data = {
                'name': None,
                'bio': None,
                'profile_url': profile_data.get('profile_url', ''),
                'username': None,
                'professional_title': None,
                'current_employer': None,
                'work_history': None,
                'education': None,
                'current_location': None,
                'origin_location': None,
                'location': None,
                'relationship_status': None,
                'languages': None,
                'connected_accounts': [],
                'interests': None,
                'interests_detailed': None,
                'social_media_links': None,
                'family_members': None,
                'life_events': None,
                'favorite_quotes': None,
                'about_section': None,
                'scraped_at': profile_data.get('scraped_at', time.time()),
                'session_duration': None,
                'scraping_method': 'selenium',
                'is_public': True,
                'last_scraped_at': time.time()
            }
            
            # Extract name from profile URL or other sources
            if profile_data.get('profile_url'):
                url_parts = profile_data['profile_url'].split('/')
                if 'profile.php' in profile_data['profile_url']:
                    transformed_data['username'] = url_parts[-1] if url_parts else None
                else:
                    transformed_data['username'] = url_parts[-1] if url_parts else None
            
            # Transform overview data
            overview = profile_data.get('overview', {})
            if overview.get('current_work'):
                transformed_data['professional_title'] = overview['current_work']
            if overview.get('education'):
                transformed_data['education'] = overview['education']
            if overview.get('location'):
                transformed_data['current_location'] = overview['location']
            
            # Transform work and education data
            work_education = profile_data.get('work_education', {})
            if work_education.get('work_history'):
                transformed_data['work_history'] = json.dumps(work_education['work_history'], ensure_ascii=False)
                # Set current employer from first work entry
                if work_education['work_history']:
                    transformed_data['current_employer'] = work_education['work_history'][0]
            if work_education.get('education_history'):
                transformed_data['education'] = json.dumps(work_education['education_history'], ensure_ascii=False)
            
            # Transform places lived data
            places_lived = profile_data.get('places_lived', {})
            if places_lived.get('current_city'):
                transformed_data['current_location'] = places_lived['current_city']
            if places_lived.get('hometown'):
                transformed_data['origin_location'] = places_lived['hometown']
            if places_lived.get('other_places'):
                transformed_data['location'] = json.dumps(places_lived['other_places'], ensure_ascii=False)
            
            # Transform contact and basic info
            contact_info = profile_data.get('contact_basic_info', {})
            if contact_info.get('languages'):
                transformed_data['languages'] = json.dumps(contact_info['languages'], ensure_ascii=False)
            
            # Transform family relationships
            family = profile_data.get('family_relationships', {})
            if family.get('relationship_status'):
                transformed_data['relationship_status'] = family['relationship_status']
            if family.get('family_members'):
                transformed_data['family_members'] = json.dumps(family['family_members'], ensure_ascii=False)
            
            # Transform details about
            details = profile_data.get('details_about', {})
            if details.get('about_text'):
                transformed_data['about_section'] = details['about_text']
            if details.get('interests'):
                transformed_data['interests'] = json.dumps(details['interests'], ensure_ascii=False)
            if details.get('quotes'):
                transformed_data['favorite_quotes'] = json.dumps(details['quotes'], ensure_ascii=False)
            
            # Transform life events
            if profile_data.get('life_events'):
                transformed_data['life_events'] = json.dumps(profile_data['life_events'], ensure_ascii=False)
            
            # Clean and truncate all text fields
            self.clean_and_truncate_data(transformed_data)
            
            logger.info("✅ Data transformation completed")
            return transformed_data
            
        except Exception as e:
            logger.error(f"Error transforming data: {e}")
            return {}
    
    def clean_and_truncate_data(self, data):
        """Clean and truncate data to fit database constraints"""
        try:
            # Define max lengths for database fields
            max_lengths = {
                'name': 255,
                'bio': 500,
                'profile_url': 500,
                'username': 100,
                'professional_title': 255,
                'current_employer': 255,
                'current_location': 255,
                'origin_location': 255,
                'location': 255,
                'relationship_status': 255,
                'about_section': 1000
            }
            
            for field, max_length in max_lengths.items():
                if data.get(field) and isinstance(data[field], str):
                    # Clean the text
                    cleaned_text = self.clean_text(data[field])
                    # Truncate if necessary
                    if len(cleaned_text) > max_length:
                        data[field] = cleaned_text[:max_length-3] + '...'
                    else:
                        data[field] = cleaned_text
            
            logger.info("✅ Data cleaning and truncation completed")
            
        except Exception as e:
            logger.error(f"Error cleaning data: {e}")
    
    def clean_text(self, text):
        """Clean text content from JavaScript and unwanted characters"""
        if not text:
            return ""
        
        # Convert to string if needed
        if not isinstance(text, str):
            try:
                text = str(text)
            except:
                return ""
        
        # Remove JavaScript patterns
        js_patterns = [
            r'function\s*\([^)]*\)\s*\{[^}]*\}',
            r'var\s+\w+\s*=\s*[^;]+;',
            r'const\s+\w+\s*=\s*[^;]+;',
            r'let\s+\w+\s*=\s*[^;]+;',
            r'\{[^}]*\}',
            r'\[[^\]]*\]',
            r'null|undefined|true|false'
        ]
        
        for pattern in js_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove non-printable characters
        text = ''.join(char for char in text if char.isprintable() or char.isspace())
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        return text.strip()
        
        # Global selenium manager instance
_selenium_manager = None

def get_selenium_manager():
    """Get the global selenium manager instance"""
    global _selenium_manager
    if _selenium_manager is None:
        _selenium_manager = FacebookSeleniumManager(headless=True)
    return _selenium_manager

def initialize_facebook_session(email, password):
    """Initialize Facebook session at application startup"""
    manager = get_selenium_manager()
    return manager.login_to_facebook(email, password)

def scrape_facebook_profile_selenium(profile_url):
    """Scrape Facebook profile using existing session"""
    manager = get_selenium_manager()
    return manager.scrape_facebook_profile(profile_url)

def close_selenium_session():
    """Close selenium session at application shutdown"""
    global _selenium_manager
    if _selenium_manager:
        _selenium_manager.close()
        _selenium_manager = None
