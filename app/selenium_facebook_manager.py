#!/usr/bin/env python3
"""
Enhanced Selenium WebDriver Manager for Facebook Authentication and Scraping
Handles login at startup and maintains session for comprehensive profile scraping
"""

import sys
import os
import time
import json
import re
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FacebookSeleniumManager:
    """Manages Facebook login session and comprehensive profile scraping using Selenium"""
    
    def __init__(self, headless=True):
        self.driver = None
        self.logged_in = False
        self.headless = headless
        self.wait_time = 15
        self.session_start_time = None
    
    def clean_text(self, text):
        """Clean extracted text to remove JavaScript, excessive whitespace, and irrelevant content"""
        if not text:
            return ""
        
        # Convert to string and strip
        text = str(text).strip()
        
        # Early return for empty or very short text
        if len(text) < 3:
            return ""
        
        # Remove common JavaScript keywords and patterns (more comprehensive)
        js_keywords = [
            'require', '__bbox', 'define', 'ScheduledServerJS', 'qplTimingsServerJS',
            'adp_WebWorkerV2', 'FDSStopFilled16PNGIcon', 'CometResourceScheduler',
            'RunWWW', 'cr:', '__rc', 'function(', 'window.', 'document.',
            '{"require"', '"__bbox"', 'null,null', 'FBReelsMediaContent',
            'CometResourceScheduler', 'registerHighPriHashes', 'qplTimingsServerJS',
            'FBReelsMediaContentContainer', 'WebWorkerV2HasteResponsePreloader'
        ]
        
        # Check if text contains JavaScript patterns - stricter filtering
        for keyword in js_keywords:
            if keyword in text:
                return ""
        
        # More aggressive JavaScript detection
        js_patterns = [
            r'function\s*\(',  # function declarations
            r'var\s+\w+\s*=',  # variable declarations
            r'const\s+\w+\s*=',  # const declarations
            r'let\s+\w+\s*=',  # let declarations
            r'return\s+\w+',  # return statements
            r'onclick\s*=',  # onclick handlers
            r'href\s*=',  # href attributes (can be JavaScript)
            r'^\s*\{\s*"',  # JSON objects starting with {"
            r'^\s*\[\s*"',  # JSON arrays starting with ["
            r'null\s*,\s*null',  # null,null patterns
            r'undefined\s*,',  # undefined patterns
            r'console\.\w+',  # console methods
            r'window\.\w+',  # window object access
            r'document\.\w+',  # document object access
        ]
        
        # Check for JavaScript patterns
        for pattern in js_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return ""
        
        # Check for JSON-like patterns that indicate JavaScript code
        if text.startswith('{') and ('require' in text or '__bbox' in text or 'define' in text):
            return ""
        
        # Check for excessive brackets, quotes, or special characters (JavaScript indicators)
        if text.count('{') > 2 or text.count('[') > 2 or text.count('"') > 4:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean whitespace and normalize
        text = ' '.join(text.split())
        
        # Filter out very short text after cleaning
        if len(text) < 3:
            return ""
        
        # Don't over-filter long text - just limit to reasonable length
        if len(text) > 1000:  # Increased max length for bios
            text = text[:1000]
        
        # Remove strings that are mostly numbers, symbols, or look like IDs
        if re.match(r'^[0-9a-fA-F\-_/\\:]+$', text):
            return ""
        
        # Remove strings with excessive special characters
        special_char_count = sum(1 for c in text if not c.isalnum() and c not in ' .,!?-\'')
        if special_char_count > len(text) * 0.4:  # More than 40% special chars
            return ""
        
        # Additional validation for obvious non-user content
        non_user_patterns = [
            r'^\s*\d+\s*$',  # Just numbers
            r'^\s*[A-Z0-9_]+\s*$',  # All caps identifiers
            r'^\s*\w+\.\w+\s*$',  # Simple object notation
            r'^\s*null\s*$',  # null values
            r'^\s*undefined\s*$',  # undefined values
            r'^\s*true\s*$',  # boolean values
            r'^\s*false\s*$',  # boolean values
        ]
        
        # Filter out browser notifications and UI messages
        ui_message_patterns = [
            r'(?i)to allow or block.*notifications',
            r'(?i)go to your browser settings',
            r'(?i)browser notifications from facebook',
            r'(?i)current city',
            r'(?i)works at',
            r'(?i)studied at',
            r'(?i)attended from',
            r'(?i)favorite quotes',
            r'(?i)no favorite',
            r'(?i)add a bio',
            r'(?i)add your bio',
            r'(?i)edit details',
            r'(?i)see all',
            r'(?i)show more',
            r'(?i)hide',
            r'(?i)learn more',
            r'(?i)get started',
            r'(?i)continue',
            r'(?i)skip',
            r'(?i)close',
            r'(?i)facebook\.com',
            r'(?i)messenger\.com',
            r'(?i)instagram\.com',
            r'(?i)click here',
            r'(?i)tap here',
            r'(?i)loading\.\.\.',
            r'(?i)please wait',
            r'(?i)error occurred',
            r'(?i)try again',
            r'(?i)refresh',
            r'(?i)reload'
        ]
        
        for pattern in non_user_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return ""
        
        # Check for UI messages and browser notifications
        for pattern in ui_message_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return ""
        
        return text.strip()
    
    def extract_clean_text_from_elements(self, soup, selectors, limit=10):
        """Extract clean text from elements matching given selectors"""
        extracted_items = set()
        
        for selector in selectors:
            try:
                if selector.startswith('//'):
                    # This is an XPath selector, skip for BeautifulSoup
                    continue
                    
                elements = soup.select(selector)
                for element in elements[:limit]:
                    text = self.clean_text(element.get_text())
                    if text and len(text) > 5:
                        extracted_items.add(text)
                        
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        return list(extracted_items)[:limit]
    
    def setup_driver(self):
        """Initialize Chrome WebDriver with optimal settings for Facebook"""
        try:
            chrome_options = Options()
            
            # Always run in headless mode for backend operation
            chrome_options.add_argument('--headless=new')  # Updated headless parameter
            logger.info("🖥️ Running in optimized headless mode for backend operation")
            
            # Performance optimizations for faster loading
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-gpu-sandbox')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            chrome_options.add_argument('--window-size=1366,768')  # Smaller window for performance
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')  # Disable images for faster loading
            chrome_options.add_argument('--disable-javascript-harmony-shipping')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--disable-background-networking')
            
            # Stealth options to avoid detection
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Optimize resource loading for speed
            chrome_options.add_experimental_option('prefs', {
                'intl.accept_languages': 'en-US,en',
                'profile.managed_default_content_settings.images': 2,  # Block images
                'profile.managed_default_content_settings.stylesheets': 2,  # Block CSS for faster loading
                'profile.managed_default_content_settings.plugins': 2,  # Block plugins
                'profile.managed_default_content_settings.popups': 2,  # Block popups
                'profile.managed_default_content_settings.geolocation': 2,  # Block location requests
                'profile.managed_default_content_settings.notifications': 2,  # Block notifications
                'profile.managed_default_content_settings.media_stream': 2,  # Block media
            })
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Execute script to hide webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set aggressive timeouts for faster operation
            self.driver.implicitly_wait(5)  # Reduced from 10
            self.driver.set_page_load_timeout(15)  # Reduced from 30
            
            logger.info("✅ Chrome WebDriver initialized successfully with performance optimizations")
            return True
            
        except WebDriverException as e:
            logger.error(f"❌ Failed to initialize WebDriver: {e}")
            logger.error("💡 Make sure Chrome and ChromeDriver are installed and in PATH")
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
        
        # Try login with retries
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔐 Starting Facebook login process... (Attempt {attempt}/{max_retries})")
                self.session_start_time = datetime.now()
                
                # Navigate to Facebook login page
                self.driver.get("https://www.facebook.com/login")
                time.sleep(5)  # Increased wait time
                
                logger.info("📄 Facebook login page loaded")
                
                # Handle cookies/consent dialogs first
                self.handle_cookie_consent_dialogs()
                
                # Wait for login form to load with increased timeout
                wait = WebDriverWait(self.driver, self.wait_time * 2)
                
                # Find and fill email field
                logger.info("📧 Looking for email field...")
                email_field = wait.until(EC.presence_of_element_located((By.ID, "email")))
                email_field.clear()
                time.sleep(1)
                email_field.send_keys(email)
                logger.info("✅ Email entered successfully")
                
                # Find and fill password field
                logger.info("🔑 Looking for password field...")
                password_field = wait.until(EC.presence_of_element_located((By.ID, "pass")))
                password_field.clear()
                time.sleep(1)
                password_field.send_keys(password)
                logger.info("✅ Password entered successfully")
                
                # Click login button using JavaScript (more reliable than standard click)
                logger.info("🖱️ Clicking login button using JavaScript...")
                try:
                    login_button = wait.until(EC.element_to_be_clickable((By.NAME, "login")))
                    self.driver.execute_script("arguments[0].click();", login_button)
                except Exception as e:
                    logger.warning(f"Standard login button not clickable, trying alternative method: {e}")
                    # Try alternative login button selectors
                    login_selectors = [
                        "button[name='login']", 
                        "#loginbutton", 
                        "input[value='Log In']",
                        "button[type='submit']"
                    ]
                    for selector in login_selectors:
                        try:
                            buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if buttons:
                                logger.info(f"Found alternative login button using {selector}")
                                self.driver.execute_script("arguments[0].click();", buttons[0])
                                break
                        except:
                            pass
                
                # Wait for login to complete with increased timeout
                logger.info("⏳ Waiting for login to complete...")
                time.sleep(10)  # Increased wait time
                
                # Check if login was successful
                if self.check_login_success():
                    self.logged_in = True
                    logger.info("✅ Facebook login successful!")
                    logger.info("🎯 Session established and ready for profile scraping")
                    return True
                else:
                    logger.error(f"❌ Facebook login failed (Attempt {attempt}/{max_retries})")
                    # Check for common error indicators
                    self.check_login_errors()
                    
                    if attempt < max_retries:
                        logger.info(f"⏳ Waiting before retry {attempt + 1}...")
                        time.sleep(5)  # Wait before retrying
                    else:
                        logger.error("❌ All login attempts failed")
                        return False
            
            except TimeoutException:
                logger.error(f"❌ Login timeout - page elements not found (Attempt {attempt}/{max_retries})")
                logger.error("💡 This may indicate Facebook is blocking automated login")
                
                if attempt < max_retries:
                    logger.info(f"⏳ Waiting before retry {attempt + 1}...")
                    time.sleep(5)
                else:
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Login error: {e}")
                
                if attempt < max_retries:
                    logger.info(f"⏳ Waiting before retry {attempt + 1}...")
                    time.sleep(5)
                else:
                    return False
                    
        # If we get here, all attempts failed
        return False
    
    def check_login_success(self):
        """Check if login was successful by looking for logged-in indicators"""
        try:
            logger.info("🔍 Checking login success...")
            
            # Check for common indicators of successful login
            success_indicators = [
                "//div[@role='navigation']",                  # Main navigation
                "//a[@aria-label='Home']",                   # Home link
                "//div[contains(@aria-label, 'Account')]",   # Account menu
                "//div[@data-testid='royal_login_button']",  # User menu
                "//div[contains(@data-testid, 'left_nav')]", # Left navigation
            ]
            
            for indicator in success_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements:
                        logger.info(f"✅ Found login success indicator: {indicator}")
                        return True
                except NoSuchElementException:
                    continue
            
            # Check URL change (successful login usually redirects away from login page)
            current_url = self.driver.current_url
            logger.info(f"🌐 Current URL: {current_url}")
            
            if "login" not in current_url.lower() and "facebook.com" in current_url:
                logger.info("✅ URL indicates successful login")
                return True
            
            # Check page title
            page_title = self.driver.title
            if "log in" not in page_title.lower() and "facebook" in page_title.lower():
                logger.info("✅ Page title indicates successful login")
                return True
            
            logger.warning("⚠️ No clear login success indicators found")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking login status: {e}")
            return False
    
    def handle_cookie_consent_dialogs(self):
        """Handle cookie consent and other dialogs that might interfere with login"""
        try:
            logger.info("🍪 Checking for cookie consent dialogs...")
            # Common selectors for cookie consent buttons
            cookie_button_selectors = [
                "button[data-cookiebanner='accept_button']",
                "button[data-testid='cookie-policy-dialog-accept-button']",
                "button[title='Accept All']",
                "button[title='Allow']",
                "button[title='Accept']",
                "button[value='Accept']",
                "button:contains('Accept')",
                "button:contains('Allow')",
                "[aria-label='Allow all cookies']",
                "[aria-label='Accept all cookies']"
            ]
            
            for selector in cookie_button_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if buttons:
                        logger.info(f"🍪 Found cookie consent dialog, accepting...")
                        self.driver.execute_script("arguments[0].click();", buttons[0])
                        time.sleep(2)
                        return True
                except Exception as cookie_error:
                    continue
                    
            # Check for "Only allow essential cookies" button
            try:
                buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'essential')]")
                if buttons:
                    logger.info("🍪 Found cookie consent dialog with essential option...")
                    self.driver.execute_script("arguments[0].click();", buttons[0])
                    time.sleep(2)
                    return True
            except:
                pass
                
            logger.info("✅ No blocking dialogs detected")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Error handling cookie dialogs: {e}")
            return False

    def check_login_errors(self):
        """Check for common login error messages"""
        try:
            error_indicators = [
                "//div[contains(text(), 'Wrong credentials')]",
                "//div[contains(text(), 'Incorrect password')]",
                "//div[contains(text(), 'Email address')]",
                "//div[contains(text(), 'Try again')]",
                "//div[contains(@id, 'error')]"
            ]
            
            for indicator in error_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements:
                        error_text = elements[0].text
                        logger.error(f"🚨 Facebook login error: {error_text}")
                        return
                except:
                    continue
                    
            logger.warning("⚠️ Login failed but no specific error message found")
            
        except Exception as e:
            logger.error(f"Error checking login errors: {e}")
    
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
            time.sleep(4)
            
            logger.info("📄 Profile page loaded, looking for About section...")
            
            # Check if we're on the right profile page
            current_url = self.driver.current_url
            logger.info(f"📍 Current URL: {current_url}")
            
            # Try direct About URL first (more reliable)
            about_url = f"{profile_url.rstrip('/')}/about"
            logger.info(f"🔗 Trying direct About URL: {about_url}")
            
            self.driver.get(about_url)
            time.sleep(3)
            
            # Check if About page loaded
            current_url = self.driver.current_url
            logger.info(f"📍 About page URL: {current_url}")
            
            if '/about' in current_url:
                logger.info("✅ Successfully navigated to About section")
                
                # Wait for content to load
                time.sleep(5)
                
                # Check for About section content
                page_source = self.driver.page_source
                if 'about' in page_source.lower() or 'overview' in page_source.lower():
                    logger.info("✅ About section content detected")
                    return True
                else:
                    logger.warning("⚠️ About section may not have loaded properly")
                    return True  # Still try to extract
            else:
                logger.warning("⚠️ About URL redirect occurred, trying alternative approach")
                
                # Fallback: try clicking About tab
                about_selectors = [
                    "//a[contains(@href, '/about')]",
                    "//a[contains(text(), 'About')]",
                    "//div[contains(text(), 'About')]",
                    "//span[contains(text(), 'About')]",
                    "//div[@role='tab'][contains(text(), 'About')]",
                    "//div[@role='tab']//span[contains(text(), 'About')]"
                ]
                
                about_clicked = False
                wait = WebDriverWait(self.driver, 10)
                
                for selector in about_selectors:
                    try:
                        logger.info(f"🔍 Trying selector: {selector}")
                        about_element = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        about_element.click()
                        about_clicked = True
                        logger.info("✅ Successfully clicked About section")
                        break
                    except TimeoutException:
                        logger.warning(f"⏰ Timeout waiting for selector: {selector}")
                        continue
                    except Exception as e:
                        logger.warning(f"⚠️ Error with selector {selector}: {e}")
                        continue
                
                if not about_clicked:
                    logger.warning("⚠️ Could not click About section, but will try to extract anyway")
                
                time.sleep(5)  # Wait for About section to load
            
            logger.info("✅ About section navigation completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error navigating to profile About: {e}")
            return False
    
    def navigate_to_about_subsection(self, profile_url, subsection):
        """
        Navigate to a specific About sub-section
        Args:
            profile_url: Base Facebook profile URL
            subsection: Specific sub-section to navigate to
        Returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            # Define sub-section URLs
            subsection_urls = {
                'overview': f"{profile_url.rstrip('/')}/about_overview",
                'work_and_education': f"{profile_url.rstrip('/')}/about_work_and_education", 
                'places': f"{profile_url.rstrip('/')}/about_places",
                'contact_and_basic_info': f"{profile_url.rstrip('/')}/about_contact_and_basic_info",
                'family_and_relationships': f"{profile_url.rstrip('/')}/about_family_and_relationships",
                'details': f"{profile_url.rstrip('/')}/about_details",
                'life_events': f"{profile_url.rstrip('/')}/about_life_events"
            }
            
            target_url = subsection_urls.get(subsection)
            if not target_url:
                logger.warning(f"⚠️ Unknown subsection: {subsection}")
                return False
            
            logger.info(f"🔍 Navigating to {subsection} section: {target_url}")
            
            # Navigate to the specific sub-section
            self.driver.get(target_url)
            time.sleep(4)  # Allow page to load
            
            # Check if we successfully navigated to the sub-section
            current_url = self.driver.current_url
            logger.info(f"📍 Current URL: {current_url}")
            
            # Wait for content to load
            time.sleep(3)
            
            # Verify the sub-section loaded by checking for specific indicators
            page_source = self.driver.page_source
            subsection_indicators = {
                'overview': ['overview', 'intro', 'basic'],
                'work_and_education': ['work', 'education', 'employment', 'school'],
                'places': ['places', 'location', 'hometown', 'current city'],
                'contact_and_basic_info': ['contact', 'basic info', 'email', 'phone'],
                'family_and_relationships': ['family', 'relationship', 'married', 'single'],
                'details': ['details', 'about', 'quotes', 'interests'],
                'life_events': ['life events', 'events', 'timeline']
            }
            
            indicators = subsection_indicators.get(subsection, [])
            indicators_found = [indicator for indicator in indicators if indicator in page_source.lower()]
            
            if indicators_found:
                logger.info(f"✅ Successfully loaded {subsection} section (indicators: {indicators_found})")
                return True
            else:
                logger.warning(f"⚠️ {subsection} section may not have loaded properly")
                # Still return True to try extraction
                return True
                
        except Exception as e:
            logger.error(f"❌ Error navigating to {subsection} section: {e}")
            return False

    def extract_comprehensive_about_data(self, profile_url):
        """
        Extract data from all About sub-sections by navigating to each one
        Args:
            profile_url: Facebook profile URL
        Returns:
            dict: Comprehensive profile data from all sub-sections
        """
        try:
            logger.info("🚀 Starting comprehensive About data extraction from all sub-sections...")
            
            # Initialize comprehensive data structure
            comprehensive_data = {
                'basic_info': {},
                'overview': {},
                'work_education': {},
                'places_lived': {},
                'contact_basic_info': {},
                'family_relationships': {},
                'details_about': {},
                'life_events': {},
                'extraction_metadata': {
                    'scraped_at': datetime.now().isoformat(),
                    'method': 'selenium_comprehensive_navigation',
                    'subsections_visited': [],
                    'subsections_extracted': []
                }
            }
            
            # Define sub-sections to visit in order
            subsections = [
                'overview',
                'work_and_education', 
                'places',
                'contact_and_basic_info',
                'family_and_relationships',
                'details',
                'life_events'
            ]
            
            # Visit each sub-section and extract data
            for subsection in subsections:
                try:
                    logger.info(f"🔍 Processing {subsection} sub-section...")
                    
                    # Navigate to the sub-section
                    if self.navigate_to_about_subsection(profile_url, subsection):
                        comprehensive_data['extraction_metadata']['subsections_visited'].append(subsection)
                        
                        # Get page source for this sub-section
                        page_source = self.driver.page_source
                        soup = BeautifulSoup(page_source, 'html.parser')
                        
                        # Remove script tags and other non-content elements
                        for script in soup(["script", "style", "noscript", "meta", "link"]):
                            script.decompose()
                        
                        # Extract data based on sub-section type
                        if subsection == 'overview':
                            self.extract_overview_section(soup, comprehensive_data)
                            if any(comprehensive_data['overview'].values()):
                                comprehensive_data['extraction_metadata']['subsections_extracted'].append(subsection)
                                logger.info(f"✅ {subsection}: Data extracted successfully")
                            else:
                                logger.warning(f"⚠️ {subsection}: No data extracted")
                        
                        elif subsection == 'work_and_education':
                            self.extract_work_education_section(soup, comprehensive_data)
                            if any(v for v in comprehensive_data['work_education'].values() if v and (isinstance(v, str) or len(v) > 0)):
                                comprehensive_data['extraction_metadata']['subsections_extracted'].append(subsection)
                                logger.info(f"✅ {subsection}: Data extracted successfully")
                            else:
                                logger.warning(f"⚠️ {subsection}: No data extracted")
                        
                        elif subsection == 'places':
                            self.extract_places_lived_section(soup, comprehensive_data)
                            if any(v for v in comprehensive_data['places_lived'].values() if v and (isinstance(v, str) or len(v) > 0)):
                                comprehensive_data['extraction_metadata']['subsections_extracted'].append(subsection)
                                logger.info(f"✅ {subsection}: Data extracted successfully")
                            else:
                                logger.warning(f"⚠️ {subsection}: No data extracted")
                        
                        elif subsection == 'contact_and_basic_info':
                            self.extract_contact_basic_info_section(soup, comprehensive_data)
                            if any(v for v in comprehensive_data['contact_basic_info'].values() if v and (isinstance(v, str) or len(v) > 0)):
                                comprehensive_data['extraction_metadata']['subsections_extracted'].append(subsection)
                                logger.info(f"✅ {subsection}: Data extracted successfully")
                            else:
                                logger.warning(f"⚠️ {subsection}: No data extracted")
                        
                        elif subsection == 'family_and_relationships':
                            self.extract_family_relationships_section(soup, comprehensive_data)
                            if any(v for v in comprehensive_data['family_relationships'].values() if v and (isinstance(v, str) or len(v) > 0)):
                                comprehensive_data['extraction_metadata']['subsections_extracted'].append(subsection)
                                logger.info(f"✅ {subsection}: Data extracted successfully")
                            else:
                                logger.warning(f"⚠️ {subsection}: No data extracted")
                        
                        elif subsection == 'details':
                            self.extract_details_about_section(soup, comprehensive_data)
                            if any(v for v in comprehensive_data['details_about'].values() if v and (isinstance(v, str) or len(v) > 0)):
                                comprehensive_data['extraction_metadata']['subsections_extracted'].append(subsection)
                                logger.info(f"✅ {subsection}: Data extracted successfully")
                            else:
                                logger.warning(f"⚠️ {subsection}: No data extracted")
                        
                        elif subsection == 'life_events':
                            self.extract_life_events_section(soup, comprehensive_data)
                            if comprehensive_data['life_events']:
                                comprehensive_data['extraction_metadata']['subsections_extracted'].append(subsection)
                                logger.info(f"✅ {subsection}: Data extracted successfully")
                            else:
                                logger.warning(f"⚠️ {subsection}: No data extracted")
                        
                        # Small delay between sub-sections to avoid rate limiting
                        time.sleep(2)
                        
                    else:
                        logger.warning(f"⚠️ Failed to navigate to {subsection} sub-section")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing {subsection} sub-section: {e}")
                    continue
            
            # Also extract basic info from main profile page
            try:
                logger.info("👤 Extracting basic profile info from main page...")
                main_about_url = f"{profile_url.rstrip('/')}/about"
                self.driver.get(main_about_url)
                time.sleep(3)
                
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Remove script tags
                for script in soup(["script", "style", "noscript", "meta", "link"]):
                    script.decompose()
                
                self.extract_basic_profile_info(soup, comprehensive_data)
                
            except Exception as e:
                logger.error(f"❌ Error extracting basic profile info: {e}")
            
            # Log extraction summary
            visited_count = len(comprehensive_data['extraction_metadata']['subsections_visited'])
            extracted_count = len(comprehensive_data['extraction_metadata']['subsections_extracted'])
            
            logger.info(f"📊 Comprehensive extraction completed:")
            logger.info(f"   - Sub-sections visited: {visited_count}/{len(subsections)}")
            logger.info(f"   - Sub-sections with data: {extracted_count}/{len(subsections)}")
            logger.info(f"   - Visited: {comprehensive_data['extraction_metadata']['subsections_visited']}")
            logger.info(f"   - Extracted: {comprehensive_data['extraction_metadata']['subsections_extracted']}")
            
            # Count total extracted fields
            total_fields = 0
            for section_name, section_data in comprehensive_data.items():
                if section_name != 'extraction_metadata' and isinstance(section_data, dict):
                    total_fields += len([v for v in section_data.values() if v and (isinstance(v, str) or len(v) > 0)])
            
            logger.info(f"📊 Total fields extracted: {total_fields}")
            
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"❌ Error in comprehensive About data extraction: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def extract_about_sections(self):
        """
        Extract all information from Facebook About sections
        Returns:
            dict: Extracted profile information organized by categories
        """
        try:
            logger.info("📊 Starting comprehensive About section extraction...")
            
            # Get page source and analyze it
            page_source = self.driver.page_source
            logger.info(f"📄 Page source length: {len(page_source)} characters")
            
            # Check for About section indicators
            about_indicators = ['about', 'overview', 'work', 'education', 'places', 'contact', 'family', 'details', 'life events']
            indicators_found = []
            
            for indicator in about_indicators:
                if indicator in page_source.lower():
                    indicators_found.append(indicator)
            
            logger.info(f"🔍 About section indicators found: {indicators_found}")
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Remove script tags and other non-content elements
            scripts_removed = 0
            for script in soup(["script", "style", "noscript", "meta", "link"]):
                script.decompose()
                scripts_removed += 1
            
            logger.info(f"🧹 Removed {scripts_removed} script/style elements")
            
            # Count remaining text elements
            all_text_elements = soup.find_all(text=True)
            clean_text_elements = [elem.strip() for elem in all_text_elements if elem.strip()]
            logger.info(f"📊 Total clean text elements: {len(clean_text_elements)}")
            
            # Show sample text elements for debugging
            sample_texts = clean_text_elements[:10]
            logger.info(f"📋 Sample text elements: {sample_texts}")
            
            # Initialize profile data structure
            profile_data = {
                'basic_info': {},
                'overview': {},
                'work_education': {},
                'places_lived': {},
                'contact_basic_info': {},
                'family_relationships': {},
                'details_about': {},
                'life_events': {},
                'extraction_metadata': {
                    'scraped_at': datetime.now().isoformat(),
                    'method': 'selenium_comprehensive',
                    'page_source_length': len(page_source),
                    'text_elements_count': len(clean_text_elements),
                    'indicators_found': indicators_found
                }
            }
            
            # Extract each section comprehensively with detailed logging
            logger.info("👤 Extracting basic profile info...")
            self.extract_basic_profile_info(soup, profile_data)
            basic_extracted = len([v for v in profile_data['basic_info'].values() if v])
            logger.info(f"👤 Basic info extraction: {basic_extracted} fields extracted")
            
            logger.info("📋 Extracting overview section...")
            self.extract_overview_section(soup, profile_data)
            overview_extracted = len([v for v in profile_data['overview'].values() if v])
            logger.info(f"📋 Overview extraction: {overview_extracted} fields extracted")
            
            logger.info("💼 Extracting work education section...")
            self.extract_work_education_section(soup, profile_data)
            work_edu_extracted = len([v for v in profile_data['work_education'].values() if v and (isinstance(v, str) or len(v) > 0)])
            logger.info(f"💼 Work education extraction: {work_edu_extracted} fields extracted")
            
            logger.info("🏠 Extracting places lived section...")
            self.extract_places_lived_section(soup, profile_data)
            places_extracted = len([v for v in profile_data['places_lived'].values() if v and (isinstance(v, str) or len(v) > 0)])
            logger.info(f"🏠 Places lived extraction: {places_extracted} fields extracted")
            
            logger.info("📞 Extracting contact basic info section...")
            self.extract_contact_basic_info_section(soup, profile_data)
            contact_extracted = len([v for v in profile_data['contact_basic_info'].values() if v and (isinstance(v, str) or len(v) > 0)])
            logger.info(f"📞 Contact info extraction: {contact_extracted} fields extracted")
            
            logger.info("👨‍👩‍👧‍👦 Extracting family relationships section...")
            self.extract_family_relationships_section(soup, profile_data)
            family_extracted = len([v for v in profile_data['family_relationships'].values() if v and (isinstance(v, str) or len(v) > 0)])
            logger.info(f"👨‍👩‍👧‍👦 Family relationships extraction: {family_extracted} fields extracted")
            
            logger.info("📝 Extracting details about section...")
            self.extract_details_about_section(soup, profile_data)
            details_extracted = len([v for v in profile_data['details_about'].values() if v and (isinstance(v, str) or len(v) > 0)])
            logger.info(f"📝 Details about extraction: {details_extracted} fields extracted")
            
            logger.info("🎯 Extracting life events section...")
            self.extract_life_events_section(soup, profile_data)
            events_extracted = len(profile_data['life_events']) if isinstance(profile_data['life_events'], list) else 0
            logger.info(f"🎯 Life events extraction: {events_extracted} events extracted")
            
            logger.info("✅ Comprehensive About section extraction completed")
            
            # Log detailed extraction summary
            total_extracted = basic_extracted + overview_extracted + work_edu_extracted + places_extracted + contact_extracted + family_extracted + details_extracted + events_extracted
            logger.info(f"📊 Total extraction summary: {total_extracted} items extracted across all sections")
            
            # Log section-by-section summary
            section_summary = {
                'basic_info': basic_extracted,
                'overview': overview_extracted, 
                'work_education': work_edu_extracted,
                'places_lived': places_extracted,
                'contact_basic_info': contact_extracted,
                'family_relationships': family_extracted,
                'details_about': details_extracted,
                'life_events': events_extracted
            }
            
            logger.info(f"� Section extraction summary: {section_summary}")
            
            return profile_data
            
        except Exception as e:
            logger.error(f"❌ Error extracting About sections: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def extract_basic_profile_info(self, soup, profile_data):
        """Extract basic profile information (name, profile photo, etc.) with improved validation"""
        try:
            basic = {}
            
            # Extract profile name with validation
            name_selectors = [
                'h1[data-testid="profile_name"]',
                'h1.x1heor9g',
                'h1 span',
                'h1',
                '[data-testid="profile_name"]',
                '.profile-name',
                '.name'
            ]
            
            for selector in name_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        name_text = self.clean_text(element.get_text())
                        if name_text and len(name_text) > 1 and len(name_text) < 100:
                            # Ensure it's not JavaScript or technical content
                            if not any(js_indicator in name_text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined', 'onclick', 'href']):
                                # Additional validation for name content
                                if not any(fake_indicator in name_text.lower() for fake_indicator in ['facebook', 'loading', 'error', 'undefined', 'null', 'test']):
                                    basic['name'] = name_text
                                    break
                except Exception as e:
                    continue
            
            # If no name found in selectors, try title tag
            if not basic.get('name'):
                try:
                    title_element = soup.find('title')
                    if title_element:
                        title_text = self.clean_text(title_element.get_text())
                        if title_text and '|' in title_text:
                            # Facebook titles are usually "Name | Facebook"
                            name_part = title_text.split('|')[0].strip()
                            if name_part and len(name_part) > 1 and len(name_part) < 100:
                                if not any(fake_indicator in name_part.lower() for fake_indicator in ['facebook', 'loading', 'error', 'undefined', 'null', 'test']):
                                    basic['name'] = name_part
                except Exception as e:
                    pass
            
            # Extract username from URL with validation
            try:
                current_url = self.driver.current_url
                if current_url:
                    if '/profile.php?id=' in current_url:
                        user_id = current_url.split('id=')[1].split('&')[0]
                        if user_id and user_id.isdigit():
                            basic['username'] = user_id
                    elif 'facebook.com/' in current_url:
                        username = current_url.split('facebook.com/')[-1].split('/')[0]
                        if username and len(username) > 1 and len(username) < 50:
                            # Ensure it's not a generic path
                            if username not in ['www', 'web', 'mobile', 'login', 'home', 'profile', 'about']:
                                basic['username'] = username
            except Exception as e:
                logger.warning(f"Error extracting username: {e}")
            
            # Extract profile photo URL (if available)
            try:
                photo_selectors = [
                    'img[data-testid="profile_photo"]',
                    '.profile-photo img',
                    '.profilePic img',
                    'img[alt*="profile"]'
                ]
                
                for selector in photo_selectors:
                    element = soup.select_one(selector)
                    if element and element.get('src'):
                        photo_url = element.get('src')
                        if photo_url and 'http' in photo_url:
                            basic['profile_photo_url'] = photo_url
                            break
            except Exception as e:
                pass
            
            profile_data['basic_info'] = basic
            logger.info(f"👤 Basic info extracted: {basic.get('name', 'Unknown')} (username: {basic.get('username', 'N/A')})")
            
        except Exception as e:
            logger.error(f"Error extracting basic info: {e}")
            profile_data['basic_info'] = {}
    
    def extract_overview_section(self, soup, profile_data):
        """Extract Overview section information with improved text filtering"""
        try:
            logger.info("📋 Starting overview section extraction...")
            
            overview = {
                'current_work': None,
                'education': None,
                'current_location': None,
                'hometown': None,
                'relationship_status': None,
                'bio': None
            }
            
            # Get all clean text elements
            all_text_elements = soup.find_all(text=True)
            cleaned_texts = []
            
            for element in all_text_elements:
                clean_text = self.clean_text(element)
                if clean_text and len(clean_text) > 3:  # Only meaningful text
                    cleaned_texts.append(clean_text)
            
            logger.info(f"📊 Overview: Processing {len(cleaned_texts)} clean text elements")
            
            # Look for work information with better filtering
            work_patterns = [
                'works at', 'work at', 'employed at', 'working at', 'job at', 'position at',
                'lucrează la', 'angajat la', 'poziție la', 'lucrez la',
                'digital creator', 'protopsalt', 'diacon', 'archdeacon', 'cântăreț',
                'cantaret', 'psaltic', 'biserica', 'catedrala', 'church', 'cathedral'
            ]
            work_matches = []
            
            for pattern in work_patterns:
                for text in cleaned_texts:
                    if pattern in text.lower() and len(text) > len(pattern) + 5:
                        # Additional validation to ensure it's real work info
                        if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined']):
                            work_matches.append(text)
                            logger.info(f"🔍 Found work match: {text}")
                            if not overview['current_work']:
                                overview['current_work'] = text
                                logger.info(f"✅ Set current_work: {text}")
                            break
                if overview['current_work']:
                    break
            
            logger.info(f"💼 Work patterns found: {len(work_matches)} matches")
            
            # Look for education information with better filtering
            education_patterns = [
                'studied at', 'student at', 'graduated from', 'studies at', 'degree from', 'university', 'college',
                'a studiat la', 'student la', 'absolvent de la', 'studiez la', 'diplomă de la', 'universitate', 'facultate',
                'facultatea', 'universitatea', 'institutul', 'teologie', 'seminar'
            ]
            education_matches = []
            
            for pattern in education_patterns:
                for text in cleaned_texts:
                    if pattern in text.lower() and len(text) > len(pattern) + 5:
                        # Additional validation to ensure it's real education info
                        if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined']):
                            education_matches.append(text)
                            logger.info(f"🔍 Found education match: {text}")
                            if not overview['education']:
                                overview['education'] = text
                                logger.info(f"✅ Set education: {text}")
                            break
                if overview['education']:
                    break
            
            logger.info(f"🎓 Education patterns found: {len(education_matches)} matches")
            
            # Look for location information with better filtering
            location_patterns = [
                'lives in', 'from', 'based in', 'located in', 'current city', 'hometown',
                'locuiește în', 'din', 'originar din', 'provine din', 'orașul natal', 'orașul curent',
                'bucuresti', 'bucharest', 'românia', 'romania'
            ]
            location_matches = []
            
            for pattern in location_patterns:
                for text in cleaned_texts:
                    if pattern in text.lower() and len(text) > len(pattern) + 3:
                        # Additional validation to ensure it's real location info
                        if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined']):
                            location_matches.append(text)
                            logger.info(f"🔍 Found location match: {text}")
                            if 'lives in' in text.lower() or 'locuiește în' in text.lower() or 'current' in text.lower():
                                if not overview['current_location']:
                                    overview['current_location'] = text
                                    logger.info(f"✅ Set current_location: {text}")
                            elif 'from' in text.lower() or 'din' in text.lower() or 'hometown' in text.lower() or 'natal' in text.lower():
                                if not overview['hometown']:
                                    overview['hometown'] = text
                                    logger.info(f"✅ Set hometown: {text}")
                            break
            
            logger.info(f"🏠 Location patterns found: {len(location_matches)} matches")
            
            # Look for relationship status
            relationship_patterns = [
                'married', 'single', 'in a relationship', 'engaged', 'divorced', 'widowed', 'it\'s complicated',
                'căsătorit', 'căsătorită', 'necăsătorit', 'necăsătorită', 'într-o relație', 'logodnic', 'logodit', 'divorțat', 'divorțată', 'văduv', 'văduvă'
            ]
            relationship_matches = []
            
            for pattern in relationship_patterns:
                for text in cleaned_texts:
                    if pattern in text.lower() and len(text) < 50:  # Relationship status should be short
                        # Additional validation to ensure it's real relationship info
                        if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined']):
                            relationship_matches.append(text)
                            logger.info(f"🔍 Found relationship match: {text}")
                            if not overview['relationship_status']:
                                overview['relationship_status'] = text
                                logger.info(f"✅ Set relationship_status: {text}")
                            break
                if overview['relationship_status']:
                    break
            
            logger.info(f"💑 Relationship patterns found: {len(relationship_matches)} matches")
            
            # Look for bio/about text with improved filtering
            bio_selectors = [
                '[data-testid="profile_bio"]',
                '.userContent',
                '.about-section',
                'div[dir="auto"]',
                '.profile-intro',
                '.bio-section'
            ]
            
            bio_matches = []
            for selector in bio_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = self.clean_text(element.get_text())
                    if text and len(text) > 20 and len(text) < 500:
                        # Ensure it's not JavaScript or technical content
                        if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined', 'onclick', 'href']):
                            bio_matches.append(text)
                            logger.info(f"🔍 Found bio match: {text[:50]}...")
                            if not overview['bio']:
                                overview['bio'] = text
                                logger.info(f"✅ Set bio: {text[:50]}...")
                            break
                if overview['bio']:
                    break
            
            # If no bio found in selectors, look in cleaned text
            if not overview['bio']:
                for text in cleaned_texts:
                    if len(text) > 50 and len(text) < 500:
                        # Check if it looks like a personal bio (contains personal pronouns)
                        if any(pronoun in text.lower() for pronoun in ['i am', 'i\'m', 'i love', 'i work', 'i study', 'my ', 'about me']):
                            if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined']):
                                bio_matches.append(text)
                                logger.info(f"🔍 Found bio match in text: {text[:50]}...")
                                overview['bio'] = text
                                logger.info(f"✅ Set bio from text: {text[:50]}...")
                                break
            
            logger.info(f"📝 Bio patterns found: {len(bio_matches)} matches")
            
            profile_data['overview'] = overview
            extracted_count = len([v for v in overview.values() if v])
            logger.info(f"📋 Overview extraction completed: {extracted_count} fields populated")
            
            # Log final overview results
            for key, value in overview.items():
                if value:
                    logger.info(f"✅ {key}: {str(value)[:100]}...")
                else:
                    logger.info(f"❌ {key}: Not found")
            
        except Exception as e:
            logger.error(f"❌ Error extracting overview: {e}")
            import traceback
            traceback.print_exc()
    
    def extract_work_education_section(self, soup, profile_data):
        """Extract Work and Education section information with comprehensive patterns"""
        try:
            logger.info("💼 Starting comprehensive work education section extraction...")
            
            work_education = {
                'work_history': [],
                'education_history': [],
                'skills': [],
                'certifications': []
            }
            
            # Get all clean text elements
            work_text_elements = soup.find_all(text=True)
            all_clean_texts = []
            
            for text_element in work_text_elements:
                text = self.clean_text(text_element)
                if text and len(text) >= 3:
                    all_clean_texts.append(text)
            
            logger.info(f"📊 Work education: Processing {len(all_clean_texts)} text elements")
            
            work_items = set()
            education_items = set()
            
            # Enhanced regex patterns for work detection
            work_patterns = [
                r'(?i)(works?\s+at|employed\s+at|job\s+at|position\s+at)\s+([^{}\n]+)',
                r'(?i)(lucreaz[ăa]\s+la|angajat\s+la|poziti[ea]\s+la)\s+([^{}\n]+)',
                r'(?i)(archdeacon|protopsalt|di[ao]con|cântăreț|cantaret|digital\s+creator)\s+(at|la)?\s*([^{}\n]*)',
                r'(?i)(manager|director|engineer|developer|consultant|specialist)\s+(at|la)\s+([^{}\n]+)',
                r'(?i)(pastor|priest|preot|profesor|teacher|instructor)\s+(at|la)?\s*([^{}\n]*)',
                r'(?i)works?\s+as\s+(a\s+)?([^{}\n]+)\s+at\s+([^{}\n]+)',
                r'(?i)(current\s+position|current\s+job|currently\s+working)\s*:?\s*([^{}\n]+)'
            ]
            
            # Enhanced regex patterns for education detection
            education_patterns = [
                r'(?i)(studied\s+at|studies\s+at|graduated\s+from|went\s+to|attended)\s+([^{}\n]+)',
                r'(?i)(a\s+studiat\s+la|absolvent\s+de\s+la|a\s+mers\s+la)\s+([^{}\n]+)',
                r'(?i)(bachelor|master|phd|doctorate|diploma|licen[țt][ăa]|masterat|doctorat)\s+(in|of|în|de)?\s*([^{}\n]+)',
                r'(?i)(facultatea\s+de|university\s+of|college\s+of|institute\s+of)\s+([^{}\n]+)',
                r'(?i)(class\s+of\s+\d{4}|promocia\s+\d{4})',
                r'(?i)(theology|teologie|pastorala|music|muzica|byzantine|bizantină)\s+(at|la)?\s*([^{}\n]*)',
                r'(?i)(degree\s+in|diplomă\s+în|studied\s+[a-zA-Z\s]+\s+at)\s+([^{}\n]+)'
            ]
            
            # Apply work patterns
            all_text = ' '.join(all_clean_texts)
            
            for pattern in work_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        work_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        work_text = str(match).strip()
                    
                    if work_text and len(work_text) > 5 and len(work_text) < 300:
                        # Clean up the work text
                        cleaned_work = self.clean_text(work_text)
                        if cleaned_work and not any(invalid in cleaned_work.lower() for invalid in ['javascript', 'function', 'undefined', 'null']):
                            work_items.add(cleaned_work)
                            logger.info(f"✅ Work pattern match: {cleaned_work}")
            
            # Apply education patterns
            for pattern in education_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if isinstance(match, tuple):
                        edu_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        edu_text = str(match).strip()
                    
                    if edu_text and len(edu_text) > 5 and len(edu_text) < 300:
                        # Clean up the education text
                        cleaned_edu = self.clean_text(edu_text)
                        if cleaned_edu and not any(invalid in cleaned_edu.lower() for invalid in ['javascript', 'function', 'undefined', 'null']):
                            education_items.add(cleaned_edu)
                            logger.info(f"✅ Education pattern match: {cleaned_edu}")
            
            # Enhanced keyword-based extraction
            work_keywords = [
                'work', 'job', 'employed', 'position', 'company', 'works at', 'work at', 'worked at',
                'angajat', 'poziție', 'companie', 'lucrează la', 'angajat la', 'a lucrat la',
                'manager', 'director', 'engineer', 'developer', 'consultant',
                'protopsalt', 'diacon', 'cântăreț', 'archdeacon', 'digital creator',
                'cantaret', 'pictura', 'biserica', 'catedrala', 'church', 'cathedral',
                'pastor', 'priest', 'preot', 'profesor', 'teacher', 'instructor'
            ]
            
            education_keywords = [
                'school', 'university', 'college', 'studied', 'degree', 'graduated', 'education', 'went to',
                'școală', 'universitate', 'facultate', 'studiat', 'absolvent', 'diplomă', 'a mers la',
                'bachelor', 'master', 'phd', 'diploma', 'licență', 'masterat', 'doctorat',
                'teologie', 'facultatea', 'universitatea', 'institutul', 'class of', 'theology'
            ]
            
            # Process each text element for keywords
            for text in all_clean_texts:
                if len(text) < 10:
                    continue
                
                # Extract work history with better validation
                is_work_related = any(keyword in text.lower() for keyword in work_keywords)
                
                if is_work_related and len(text) < 200:
                    if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined', 'onclick', 'href']):
                        # Additional validation for work-related content
                        is_valid_work = (
                            any(work_indicator in text.lower() for work_indicator in ['at ', 'la ', 'company', 'companie', 'inc', 'corp', 'ltd', 'llc', 'organization', 'office', 'team', 'biserica', 'church', 'catedrala', 'cathedral', 'worked', 'lucrat', 'position', 'poziție']) or
                            any(profession in text.lower() for profession in ['protopsalt', 'diacon', 'archdeacon', 'cântăreț', 'cantaret', 'pictura', 'digital creator', 'manager', 'director', 'pastor', 'priest', 'preot'])
                        )
                        
                        if is_valid_work:
                            work_items.add(text)
                            logger.info(f"✅ Work keyword match: {text}")
                
                # Extract education history with better validation
                is_education_related = any(keyword in text.lower() for keyword in education_keywords)
                
                if is_education_related and len(text) < 200:
                    if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined', 'onclick', 'href']):
                        # Additional validation for education-related content
                        is_valid_education = (
                            any(edu_indicator in text.lower() for edu_indicator in ['university', 'universitate', 'college', 'facultate', 'school', 'școală', 'institute', 'institut', 'academy', 'academie', 'graduated', 'absolvent', 'degree', 'diplomă', 'studied', 'studiat', 'went to', 'class of']) or
                            any(subject in text.lower() for subject in ['teologie', 'pastorala', 'muzica', 'bizantina', 'theology'])
                        )
                        
                        if is_valid_education:
                            education_items.add(text)
                            logger.info(f"✅ Education keyword match: {text}")
            
            # Look for specific selectors that might contain work/education info
            work_selectors = [
                '[data-overviewsection="work"]',
                '[data-overviewsection="education"]',
                '.profileInfoTable',
                '.workExperience',
                '.educationExperience',
                'div[dir="auto"]'
            ]
            
            for selector in work_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = self.clean_text(element.get_text())
                    if text and len(text) > 10:
                        # Check if it contains work or education info
                        if any(keyword in text.lower() for keyword in work_keywords + education_keywords):
                            if 'work' in text.lower() or 'job' in text.lower() or 'position' in text.lower() or 'angajat' in text.lower():
                                work_items.add(text)
                                logger.info(f"✅ Work selector match: {text}")
                            elif 'university' in text.lower() or 'college' in text.lower() or 'studied' in text.lower() or 'facultate' in text.lower():
                                education_items.add(text)
                                logger.info(f"✅ Education selector match: {text}")
            
            # Look for structured work/education patterns following labels
            work_labels = ['Work', 'Employment', 'Job', 'Position', 'Workplace', 'Lucru', 'Angajare']
            education_labels = ['Education', 'School', 'University', 'College', 'Studies', 'Educație', 'Studii']
            
            for i, text in enumerate(all_clean_texts):
                # Check if this is a section label
                if any(label.lower() in text.lower() for label in work_labels) and len(text) < 30:
                    # Look at the next few elements for work details
                    for j in range(i+1, min(i+10, len(all_clean_texts))):
                        next_text = all_clean_texts[j]
                        if (len(next_text) > 10 and len(next_text) < 200 and
                            not any(js_indicator in next_text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined'])):
                            
                            # Check if it looks like work info
                            if any(work_indicator in next_text.lower() for work_indicator in ['at ', 'company', 'inc', 'corp', 'office', 'team', 'biserica', 'church', 'catedrala']):
                                work_items.add(next_text)
                                logger.info(f"✅ Work label follow-up: {next_text}")
                
                if any(label.lower() in text.lower() for label in education_labels) and len(text) < 30:
                    # Look at the next few elements for education details
                    for j in range(i+1, min(i+10, len(all_clean_texts))):
                        next_text = all_clean_texts[j]
                        if (len(next_text) > 10 and len(next_text) < 200 and
                            not any(js_indicator in next_text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined'])):
                            
                            # Check if it looks like education info
                            if any(edu_indicator in next_text.lower() for edu_indicator in ['university', 'college', 'school', 'institute', 'facultate', 'studied', 'class of']):
                                education_items.add(next_text)
                                logger.info(f"✅ Education item from label: {next_text}")
            
            # Filter and limit work history
            work_education['work_history'] = [item for item in list(work_items)[:15] if len(item) > 10]  # Increased limit
            
            # Filter and limit education history
            work_education['education_history'] = [item for item in list(education_items)[:15] if len(item) > 10]  # Increased limit
            
            # Extract skills (if present in text)
            skill_keywords = ['skills', 'competențe', 'expertise', 'expertiză', 'proficient', 'priceput', 'experienced', 'experimentat', 'specializes', 'specializat', 'certified', 'certificat']
            skills_found = set()
            
            for text in all_clean_texts:
                if any(keyword in text.lower() for keyword in skill_keywords):
                    if len(text) < 100:  # Skills should be concise
                        if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined']):
                            skills_found.add(text)
                            logger.info(f"✅ Skill found: {text}")
            
            work_education['skills'] = list(skills_found)[:5]  # Limit skills
            
            profile_data['work_education'] = work_education
            
            work_count = len(work_education['work_history'])
            edu_count = len(work_education['education_history'])
            skills_count = len(work_education['skills'])
            
            logger.info(f"💼 Work & Education extraction completed: {work_count} work, {edu_count} education, {skills_count} skills")
            
            # Log details
            if work_education['work_history']:
                logger.info(f"💼 Work history ({work_count} items): {work_education['work_history']}")
            if work_education['education_history']:
                logger.info(f"🎓 Education history ({edu_count} items): {work_education['education_history']}")
            if work_education['skills']:
                logger.info(f"🔧 Skills: {work_education['skills']}")
            
        except Exception as e:
            logger.error(f"❌ Error extracting work/education: {e}")
            import traceback
            traceback.print_exc()
            profile_data['work_education'] = {'work_history': [], 'education_history': [], 'skills': [], 'certifications': []}
    
    def extract_places_lived_section(self, soup, profile_data):
        """Extract Places Lived section information with improved filtering"""
        try:
            places = {
                'current_city': None,
                'hometown': None,
                'other_places': []
            }
            
            # Extract location information using safer text extraction
            text_elements = soup.find_all(text=True)
            all_clean_texts = []
            
            for text_element in text_elements:
                text = self.clean_text(text_element)
                if text and len(text) >= 3:
                    all_clean_texts.append(text)
            
            logger.info(f"🏠 Places: Processing {len(all_clean_texts)} clean text elements")
            
            # Look for explicit location keywords first
            location_keywords = ['lives in', 'from', 'hometown', 'current city', 'moved to', 'based in', 'located in']
            location_items = set()
            
            for text in all_clean_texts:
                if any(keyword in text.lower() for keyword in location_keywords):
                    if len(text) < 100:  # Locations should be reasonably short
                        # Ensure it's not JavaScript or technical content
                        if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined', 'onclick', 'href']):
                            logger.info(f"🔍 Found location with keyword: {text}")
                            if 'lives in' in text.lower() or 'current' in text.lower():
                                if not places['current_city']:
                                    places['current_city'] = text
                                    logger.info(f"✅ Set current_city: {text}")
                            elif 'from' in text.lower() or 'hometown' in text.lower():
                                if not places['hometown']:
                                    places['hometown'] = text
                                    logger.info(f"✅ Set hometown: {text}")
                            else:
                                location_items.add(text)
            
            # Look for standalone location patterns (cities, countries)
            location_patterns = [
                r'\b[A-Z][a-z]+,\s*[A-Z][a-z]+\b',  # City, Country
                r'\b[A-Z][a-z]+,\s*[A-Z]{2,}\b',    # City, STATE/COUNTRY_CODE
                r'\bBucharest\b', r'\bBucurești\b',  # Specific cities
                r'\bRomania\b', r'\bRomânia\b',      # Specific countries
            ]
            
            standalone_locations = set()
            
            for text in all_clean_texts:
                # Check if text matches location patterns
                for pattern in location_patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        # Additional validation
                        if (len(text) < 50 and 
                            not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined']) and
                            not any(non_location in text.lower() for non_location in ['website', 'email', 'phone', 'button', 'click', 'link'])):
                            
                            logger.info(f"🔍 Found standalone location: {text}")
                            standalone_locations.add(text)
                            break
            
            # Process standalone locations
            for location in standalone_locations:
                # Determine if it's current city or hometown based on context or position
                if not places['current_city'] and ('current' not in location.lower()):
                    # First good location becomes current city
                    places['current_city'] = location
                    logger.info(f"✅ Set current_city from standalone: {location}")
                elif not places['hometown'] and location != places['current_city']:
                    # Second good location becomes hometown
                    places['hometown'] = location
                    logger.info(f"✅ Set hometown from standalone: {location}")
                else:
                    location_items.add(location)
            
            # Look for specific Facebook location indicators
            fb_location_indicators = [
                'Current city', 'Hometown', 'Lives in', 'From'
            ]
            
            for i, text in enumerate(all_clean_texts):
                if any(indicator in text for indicator in fb_location_indicators):
                    # Look at the next few text elements for the actual location
                    for j in range(i+1, min(i+4, len(all_clean_texts))):
                        next_text = all_clean_texts[j]
                        if (len(next_text) > 2 and len(next_text) < 50 and
                            not any(js_indicator in next_text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined'])):
                            
                            logger.info(f"🔍 Found location after indicator '{text}': {next_text}")
                            
                            if 'current' in text.lower() and not places['current_city']:
                                places['current_city'] = next_text
                                logger.info(f"✅ Set current_city from indicator: {next_text}")
                            elif ('hometown' in text.lower() or 'from' in text.lower()) and not places['hometown']:
                                places['hometown'] = next_text
                                logger.info(f"✅ Set hometown from indicator: {next_text}")
                            else:
                                location_items.add(next_text)
                            break
            
            # Filter and limit other places
            places['other_places'] = [item for item in list(location_items)[:5] if len(item) > 3]
            
            profile_data['places_lived'] = places
            location_count = len([p for p in places.values() if p and (isinstance(p, str) or len(p) > 0)])
            logger.info(f"🏠 Places lived extracted: {location_count} locations")
            
            # Log what was found
            if places['current_city']:
                logger.info(f"✅ Current city: {places['current_city']}")
            else:
                logger.info("❌ Current city: Not found")
            if places['hometown']:
                logger.info(f"✅ Hometown: {places['hometown']}")
            else:
                logger.info("❌ Hometown: Not found")
            if places['other_places']:
                logger.info(f"✅ Other places: {places['other_places']}")
            
        except Exception as e:
            logger.error(f"Error extracting places lived: {e}")
            profile_data['places_lived'] = {'current_city': None, 'hometown': None, 'other_places': []}
    
    def extract_contact_basic_info_section(self, soup, profile_data):
        """Extract Contact and Basic Info section with comprehensive patterns"""
        try:
            logger.info("📞 Starting comprehensive contact basic info extraction...")
            
            contact_info = {
                'email': None,
                'phone': None,
                'website': None,
                'websites': [],
                'birthday': None,
                'gender': None,
                'languages': [],
                'address': None,
                'social_media': {},
                'messenger': None,
                'instagram': None,
                'religious_views': None,
                'political_views': None,
                'interested_in': None,
                'relationship_status': None
            }
            
            # Get all clean text elements and page text
            contact_text_elements = soup.find_all(text=True)
            all_clean_texts = []
            
            for text_element in contact_text_elements:
                text = self.clean_text(text_element)
                if text and len(text) >= 3:
                    all_clean_texts.append(text)
            
            page_text = ' '.join(all_clean_texts)
            logger.info(f"📊 Contact info: Processing {len(all_clean_texts)} text elements")
            
            # Enhanced email extraction with multiple patterns
            import re
            email_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                r'(?i)email:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                r'(?i)e-mail:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                r'(?i)contact:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
            ]
            
            found_emails = set()
            for pattern in email_patterns:
                emails = re.findall(pattern, page_text)
                for email in emails:
                    email = email.strip() if isinstance(email, str) else email
                    # Filter out fake/JavaScript emails (but allow example.com for testing)
                    if not any(fake_indicator in email.lower() for fake_indicator in ['test@test', 'fake@fake', 'null', 'undefined', 'noreply', 'javascript', 'localhost']):
                        if '@' in email and '.' in email.split('@')[1] and len(email) > 5:
                            found_emails.add(email)
                            logger.info(f"✅ Found email: {email}")
            
            if found_emails:
                contact_info['email'] = list(found_emails)[0]
            
            # Enhanced phone number extraction
            phone_patterns = [
                r'(?i)phone:\s*([\+]?[0-9\s\-\(\)]{8,})',
                r'(?i)tel:\s*([\+]?[0-9\s\-\(\)]{8,})',
                r'(?i)telefon:\s*([\+]?[0-9\s\-\(\)]{8,})',
                r'(?i)mobile:\s*([\+]?[0-9\s\-\(\)]{8,})',
                r'(?i)cell:\s*([\+]?[0-9\s\-\(\)]{8,})',
                r'\+\d{1,4}[\s\-]?\d{1,4}[\s\-]?\d{1,4}[\s\-]?\d{1,4}[\s\-]?\d{0,4}',
                r'\b\d{3,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4}\b'
            ]
            
            found_phones = set()
            for pattern in phone_patterns:
                phones = re.findall(pattern, page_text)
                for phone in phones:
                    phone = phone.strip() if isinstance(phone, str) else phone
                    clean_phone = re.sub(r'[^\d+]', '', phone)
                    if len(clean_phone) >= 8 and len(clean_phone) <= 15:
                        # Additional validation - shouldn't be obviously fake
                        if not any(fake_number in clean_phone for fake_number in ['0000000000', '1111111111', '1234567890', '9999999999']):
                            found_phones.add(phone)
                            logger.info(f"✅ Found phone: {phone}")
            
            if found_phones:
                contact_info['phone'] = list(found_phones)[0]
            
            # Enhanced website URL extraction
            url_patterns = [
                r'(?i)website:\s*(https?://[^\s]+)',
                r'(?i)site:\s*(https?://[^\s]+)',
                r'(?i)blog:\s*(https?://[^\s]+)',
                r'(?i)website:\s*([^\s]+\.[a-zA-Z]{2,})',
                r'(?i)site:\s*([^\s]+\.[a-zA-Z]{2,})',
                r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),])+\.[a-zA-Z]{2,}',
                r'(?i)(youtube\.com/[^\s]+)',
                r'(?i)(instagram\.com/[^\s]+)',
                r'(?i)(twitter\.com/[^\s]+)',
                r'(?i)(linkedin\.com/[^\s]+)'
            ]
            
            found_websites = set()
            social_media_found = {}
            
            for pattern in url_patterns:
                urls = re.findall(pattern, page_text)
                for url in urls:
                    url = url.strip() if isinstance(url, str) else url
                    # Clean up the URL
                    if not url.startswith('http') and '.' in url:
                        url = 'https://' + url
                    
                    # Filter out obviously fake URLs (but allow example.com for testing)
                    if not any(fake_indicator in url.lower() for fake_indicator in ['javascript', 'test.com', 'localhost', 'undefined']):
                        # Categorize social media vs regular websites
                        if 'youtube.com' in url.lower():
                            social_media_found['youtube'] = url
                            logger.info(f"✅ Found YouTube: {url}")
                        elif 'instagram.com' in url.lower():
                            social_media_found['instagram'] = url
                            contact_info['instagram'] = url
                            logger.info(f"✅ Found Instagram: {url}")
                        elif 'twitter.com' in url.lower():
                            social_media_found['twitter'] = url
                            logger.info(f"✅ Found Twitter: {url}")
                        elif 'linkedin.com' in url.lower():
                            social_media_found['linkedin'] = url
                            logger.info(f"✅ Found LinkedIn: {url}")
                        elif 'facebook.com' in url.lower():
                            # Only specific Facebook pages, not main profile
                            if '/pages/' in url.lower() or len(url.split('/')[-1]) > 10:
                                found_websites.add(url)
                                logger.info(f"✅ Found Facebook page: {url}")
                        else:
                            found_websites.add(url)
                            logger.info(f"✅ Found website: {url}")
                            logger.info(f"✅ Found website: {url}")
            
            websites_list = list(found_websites)
            contact_info['websites'] = websites_list
            contact_info['social_media'] = social_media_found
            if websites_list:
                contact_info['website'] = websites_list[0]  # Primary website
            
            # Enhanced birthday/age extraction
            birthday_patterns = [
                r'(?i)(born|birthday|birth\s+date|date\s+of\s+birth):\s*([^{}\n]+)',
                r'(?i)(născut|ziua\s+de\s+naștere):\s*([^{}\n]+)',
                r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
                r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
                r'(?i)age:\s*(\d{1,3})',
                r'(?i)born\s+in\s+(\d{4})',
                r'(?i)(age\s+\d{1,3}|years\s+old|\d{1,3}\s+ani)'
            ]
            
            for pattern in birthday_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    birthday_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if birthday_text and len(birthday_text.strip()) > 2:
                        contact_info['birthday'] = birthday_text.strip()
                        logger.info(f"✅ Found birthday/age: {birthday_text}")
                        break
                if contact_info['birthday']:
                    break
            
            # Enhanced gender detection
            gender_patterns = [
                r'(?i)gender:\s*(male|female|man|woman|bărbat|femeie)',
                r'(?i)(male|female|man|woman|bărbat|femeie)(?:\s|$)',
                r'(?i)he/him|she/her|el/lui|ea/ei'
            ]
            
            for pattern in gender_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    gender_text = match.strip() if isinstance(match, str) else match
                    if gender_text and len(gender_text) < 20:
                        contact_info['gender'] = gender_text
                        logger.info(f"✅ Found gender: {gender_text}")
                        break
                if contact_info['gender']:
                    break
            
            # Enhanced languages extraction
            language_patterns = [
                r'(?i)(speaks|language|languages|fluent|native|bilingual):\s*([^{}\n]+)',
                r'(?i)(vorbește|limbi|limbile):\s*([^{}\n]+)',
                r'(?i)speaks\s+([^{}\n]+)',
                r'(?i)languages?\s*[:]?\s*([^{}\n]+)',
                r'(?i)(english|romanian|french|spanish|german|italian|greek|russian|hungarian|bulgarian)(?:\s+language)?',
                r'(?i)(română|engleză|franceză|spaniolă|germană|italiană|greacă|rusă|maghiară|bulgară)'
            ]
            
            languages_found = set()
            for pattern in language_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    lang_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if lang_text and len(lang_text) < 100:
                        # Clean up language text and split multiple languages
                        cleaned_lang = self.clean_text(lang_text)
                        if cleaned_lang:
                            # Split by common separators
                            lang_parts = re.split(r'[,;&]+', cleaned_lang)
                            for lang_part in lang_parts:
                                lang_part = lang_part.strip()
                                if lang_part and len(lang_part) > 1:
                                    languages_found.add(lang_part)
                                    logger.info(f"✅ Found language: {lang_part}")
            
            contact_info['languages'] = list(languages_found)[:10]  # Limit languages
            
            # Enhanced relationship status extraction
            relationship_patterns = [
                r'(?i)(relationship\s+status|civil\s+status|stare\s+civilă):\s*([^{}\n]+)',
                r'(?i)(married|single|divorced|widowed|engaged|in\s+a\s+relationship|it\'s\s+complicated)',
                r'(?i)(căsătorit|necăsătorit|divorțat|văduv|logodit|într-o\s+relație|e\s+complicat)'
            ]
            
            for pattern in relationship_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    rel_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if rel_text and len(rel_text.strip()) < 50:
                        contact_info['relationship_status'] = rel_text.strip()
                        logger.info(f"✅ Found relationship: {rel_text}")
                        break
                if contact_info['relationship_status']:
                    break
            
            # Religious and political views
            religious_patterns = [
                r'(?i)(religious\s+views|religion|religie):\s*([^{}\n]+)',
                r'(?i)(christian|orthodox|catholic|protestant|muslim|jewish|buddhist|hindu)',
                r'(?i)(creștin|ortodox|catolic|protestant|musulman|evreu|budist|hindus)'
            ]
            
            for pattern in religious_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    rel_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if rel_text and len(rel_text.strip()) < 100:
                        contact_info['religious_views'] = rel_text.strip()
                        logger.info(f"✅ Found religious views: {rel_text}")
                        break
                if contact_info['religious_views']:
                    break
            
            # Political views extraction
            political_patterns = [
                r'(?i)(political\s+views|politics|politică):\s*([^{}\n]+)',
                r'(?i)(conservative|liberal|progressive|independent|democrat|republican|socialist)',
                r'(?i)(conservator|liberal|progresist|independent|democrat|republican|socialist)'
            ]
            
            for pattern in political_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    pol_text = match if isinstance(match, str) else (match[1] if len(match) > 1 else match[0])
                    if pol_text and len(pol_text.strip()) < 100:
                        contact_info['political_views'] = pol_text.strip()
                        logger.info(f"✅ Found political views: {pol_text}")
                        break
                if contact_info['political_views']:
                    break
            
            profile_data['contact_basic_info'] = contact_info
            
            # Count extracted fields
            populated_fields = len([v for v in contact_info.values() if v and (isinstance(v, str) or (isinstance(v, list) and len(v) > 0) or (isinstance(v, dict) and len(v) > 0))])
            logger.info(f"📞 Contact & Basic Info extraction completed: {populated_fields} fields populated")
            
            # Log details
            for key, value in contact_info.items():
                if value:
                    if isinstance(value, list):
                        logger.info(f"✅ {key}: {len(value)} items - {value}")
                    elif isinstance(value, dict):
                        logger.info(f"✅ {key}: {len(value)} items - {value}")
                    else:
                        logger.info(f"✅ {key}: {str(value)[:100]}...")
                else:
                    logger.info(f"❌ {key}: Not found")
            
        except Exception as e:
            logger.error(f"❌ Error extracting contact info: {e}")
            import traceback
            traceback.print_exc()
            profile_data['contact_basic_info'] = {}

    def extract_family_relationships_section(self, soup, profile_data):
        """Extract Family and Relationships section with comprehensive patterns"""
        try:
            logger.info("👨‍👩‍👧‍👦 Starting comprehensive family and relationships extraction...")
            
            family_relationships = {
                'relationship_status': None,
                'spouse': None,
                'family_members': [],
                'relationship_history': []
            }
            
            # Get all clean text elements
            text_elements = soup.find_all(text=True)
            all_clean_texts = []
            
            for text_element in text_elements:
                clean_text = self.clean_text(str(text_element))
                if clean_text and len(clean_text) > 2:
                    all_clean_texts.append(clean_text)
            
            logger.info(f"📊 Found {len(all_clean_texts)} clean text elements for family extraction")
            
            # Relationship status patterns
            relationship_patterns = [
                r'(?i)relationship status[:\s]*([^.\n]+)',
                r'(?i)married to\s+([^.\n]+)',
                r'(?i)in a relationship with\s+([^.\n]+)',
                r'(?i)engaged to\s+([^.\n]+)',
                r'(?i)single',
                r'(?i)it\'s complicated',
                r'(?i)divorced',
                r'(?i)widowed',
                r'(?i)separated'
            ]
            
            # Family member patterns
            family_patterns = [
                r'(?i)father[:\s]*([^.\n]+)',
                r'(?i)mother[:\s]*([^.\n]+)',
                r'(?i)son[:\s]*([^.\n]+)',
                r'(?i)daughter[:\s]*([^.\n]+)',
                r'(?i)brother[:\s]*([^.\n]+)',
                r'(?i)sister[:\s]*([^.\n]+)',
                r'(?i)wife[:\s]*([^.\n]+)',
                r'(?i)husband[:\s]*([^.\n]+)',
                r'(?i)spouse[:\s]*([^.\n]+)'
            ]
            
            # Search for relationship information
            for text in all_clean_texts:
                # Check for relationship status
                for pattern in relationship_patterns:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if isinstance(match, str) and len(match.strip()) > 1:
                            status = match.strip()
                            if not family_relationships['relationship_status']:
                                family_relationships['relationship_status'] = status
                                logger.info(f"✅ Found relationship status: {status}")
                
                # Check for family members
                for pattern in family_patterns:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if isinstance(match, str) and len(match.strip()) > 1:
                            member_name = match.strip()
                            relationship_type = pattern.split(r'[:\s]')[0].replace('(?i)', '')
                            
                            family_member = {
                                'relationship': relationship_type,
                                'name': member_name,
                                'profile_url': None
                            }
                            
                            family_relationships['family_members'].append(family_member)
                            logger.info(f"✅ Found family member: {relationship_type} - {member_name}")
            
            # Look for spouse information specifically
            spouse_patterns = [
                r'(?i)married to\s+([^.\n]+)',
                r'(?i)spouse[:\s]*([^.\n]+)',
                r'(?i)wife[:\s]*([^.\n]+)',
                r'(?i)husband[:\s]*([^.\n]+)'
            ]
            
            for text in all_clean_texts:
                for pattern in spouse_patterns:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if isinstance(match, str) and len(match.strip()) > 1:
                            spouse_name = match.strip()
                            if not family_relationships['spouse']:
                                family_relationships['spouse'] = spouse_name
                                logger.info(f"✅ Found spouse: {spouse_name}")
            
            # Remove duplicates from family members
            unique_family_members = []
            seen_members = set()
            for member in family_relationships['family_members']:
                member_key = f"{member['relationship']}:{member['name']}"
                if member_key not in seen_members:
                    unique_family_members.append(member)
                    seen_members.add(member_key)
            
            family_relationships['family_members'] = unique_family_members
            
            # Store in profile data
            profile_data['family_relationships'] = family_relationships
            
            # Log summary
            logger.info(f"👨‍👩‍👧‍👦 Family and relationships extraction completed:")
            logger.info(f"   - Relationship status: {family_relationships['relationship_status']}")
            logger.info(f"   - Spouse: {family_relationships['spouse']}")
            logger.info(f"   - Family members: {len(family_relationships['family_members'])}")
            
            # Log details
            for key, value in family_relationships.items():
                if value:
                    if isinstance(value, list):
                        logger.info(f"✅ {key}: {len(value)} items - {value}")
                    elif isinstance(value, dict):
                        logger.info(f"✅ {key}: {len(value)} items - {value}")
                    else:
                        logger.info(f"✅ {key}: {str(value)[:100]}...")
                else:
                    logger.info(f"❌ {key}: Not found")
            
        except Exception as e:
            logger.error(f"❌ Error extracting family and relationships: {e}")
            import traceback
            traceback.print_exc()
            profile_data['family_relationships'] = {}

    def extract_details_about_section(self, soup, profile_data):
        """Extract Details About section with comprehensive patterns"""
        try:
            logger.info("📝 Starting comprehensive details about extraction...")
            
            details_about = {
                'about_text': None,
                'quotes': [],
                'interests': [],
                'personal_info': [],
                'other_names': [],
                'religious_views': None,
                'political_views': None,
                'blood_type': None,
                'other_details': []
            }
            
            # Get all clean text elements
            text_elements = soup.find_all(text=True)
            all_clean_texts = []
            
            for text_element in text_elements:
                clean_text = self.clean_text(str(text_element))
                if clean_text and len(clean_text) > 2:
                    all_clean_texts.append(clean_text)
            
            logger.info(f"📊 Found {len(all_clean_texts)} clean text elements for details extraction")
            
            # About text patterns (bio/description)
            about_patterns = [
                r'(?i)about[:\s]*([^.\n]{10,200})',
                r'(?i)bio[:\s]*([^.\n]{10,200})',
                r'(?i)description[:\s]*([^.\n]{10,200})',
                r'(?i)intro[:\s]*([^.\n]{10,200})'
            ]
            
            # Quotes patterns
            quotes_patterns = [
                r'(?i)favorite quote[s]?[:\s]*([^.\n]+)',
                r'(?i)quote[s]?[:\s]*([^.\n]+)',
                r'"([^"]{10,200})"',
                r"'([^']{10,200})'"
            ]
            
            # Interests patterns
            interests_patterns = [
                r'(?i)interests[:\s]*([^.\n]+)',
                r'(?i)hobbies[:\s]*([^.\n]+)',
                r'(?i)likes[:\s]*([^.\n]+)',
                r'(?i)activities[:\s]*([^.\n]+)',
                r'(?i)favorite[:\s]*([^.\n]+)'
            ]
            
            # Personal info patterns
            personal_patterns = [
                r'(?i)other names[:\s]*([^.\n]+)',
                r'(?i)nickname[:\s]*([^.\n]+)',
                r'(?i)maiden name[:\s]*([^.\n]+)',
                r'(?i)religious views[:\s]*([^.\n]+)',
                r'(?i)political views[:\s]*([^.\n]+)',
                r'(?i)blood type[:\s]*([^.\n]+)'
            ]
            
            # Search for details information
            for text in all_clean_texts:
                # Check for about text
                for pattern in about_patterns:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if isinstance(match, str) and len(match.strip()) > 10:
                            about_text = match.strip()
                            if not details_about['about_text'] and len(about_text) > 20:
                                details_about['about_text'] = about_text
                                logger.info(f"✅ Found about text: {about_text[:100]}...")
                
                # Check for quotes
                for pattern in quotes_patterns:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if isinstance(match, str) and len(match.strip()) > 10:
                            quote = match.strip()
                            if quote not in details_about['quotes']:
                                details_about['quotes'].append(quote)
                                logger.info(f"✅ Found quote: {quote[:100]}...")
                
                # Check for interests
                for pattern in interests_patterns:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if isinstance(match, str) and len(match.strip()) > 3:
                            interest = match.strip()
                            if interest not in details_about['interests']:
                                details_about['interests'].append(interest)
                                logger.info(f"✅ Found interest: {interest}")
                
                # Check for personal info
                for pattern in personal_patterns:
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if isinstance(match, str) and len(match.strip()) > 1:
                            info = match.strip()
                            
                            # Categorize the info
                            if 'religious' in pattern.lower():
                                details_about['religious_views'] = info
                                logger.info(f"✅ Found religious views: {info}")
                            elif 'political' in pattern.lower():
                                details_about['political_views'] = info
                                logger.info(f"✅ Found political views: {info}")
                            elif 'blood' in pattern.lower():
                                details_about['blood_type'] = info
                                logger.info(f"✅ Found blood type: {info}")
                            elif 'name' in pattern.lower():
                                if info not in details_about['other_names']:
                                    details_about['other_names'].append(info)
                                    logger.info(f"✅ Found other name: {info}")
                            else:
                                if info not in details_about['personal_info']:
                                    details_about['personal_info'].append(info)
                                    logger.info(f"✅ Found personal info: {info}")
            
            # Look for longer biographical text
            for text in all_clean_texts:
                if len(text) > 50 and not details_about['about_text']:
                    # Check if it looks like a bio (contains personal pronouns, etc.)
                    bio_indicators = ['i am', 'i\'m', 'i love', 'i work', 'i study', 'my', 'me', 'myself']
                    text_lower = text.lower()
                    
                    indicator_count = sum(1 for indicator in bio_indicators if indicator in text_lower)
                    if indicator_count >= 2:
                        details_about['about_text'] = text
                        logger.info(f"✅ Found biographical text: {text[:100]}...")
                        break
            
            # Store in profile data
            profile_data['details_about'] = details_about
            
            # Log summary
            logger.info(f"📝 Details about extraction completed:")
            logger.info(f"   - About text: {'Yes' if details_about['about_text'] else 'No'}")
            logger.info(f"   - Quotes: {len(details_about['quotes'])}")
            logger.info(f"   - Interests: {len(details_about['interests'])}")
            logger.info(f"   - Other names: {len(details_about['other_names'])}")
            logger.info(f"   - Religious views: {'Yes' if details_about['religious_views'] else 'No'}")
            logger.info(f"   - Political views: {'Yes' if details_about['political_views'] else 'No'}")
            
            # Log details
            for key, value in details_about.items():
                if value:
                    if isinstance(value, list):
                        logger.info(f"✅ {key}: {len(value)} items - {value}")
                    elif isinstance(value, dict):
                        logger.info(f"✅ {key}: {len(value)} items - {value}")
                    else:
                        logger.info(f"✅ {key}: {str(value)[:100]}...")
                else:
                    logger.info(f"❌ {key}: Not found")
            
        except Exception as e:
            logger.error(f"❌ Error extracting details about: {e}")
            import traceback
            traceback.print_exc()
            profile_data['details_about'] = {}

    def extract_life_events_section(self, soup, profile_data):
        """Extract Life Events section with comprehensive patterns"""
        try:
            logger.info("🎯 Starting comprehensive life events extraction...")
            
            life_events = []
            life_events_found = set()
            
            # Get all clean text elements
            text_elements = soup.find_all(text=True)
            all_clean_texts = []
            
            for text_element in text_elements:
                text = self.clean_text(text_element)
                if text and len(text) >= 5:
                    all_clean_texts.append(text)
            
            page_text = ' '.join(all_clean_texts)
            logger.info(f"📊 Life events: Processing {len(all_clean_texts)} text elements")
            
            # Enhanced regex patterns for life events
            import re
            life_event_patterns = [
                # Birth events
                r'(?i)(born|născut)\s+(in|în|on|pe)?\s*([^{}\n]+)',
                r'(?i)(birth|naștere):\s*([^{}\n]+)',
                
                # Education events
                r'(?i)(graduated|absolvent|finished|terminat)\s+(from|de\s+la|în)?\s*([^{}\n]+)',
                r'(?i)(started\s+studying|a\s+început\s+să\s+studieze)\s+(at|la)?\s*([^{}\n]+)',
                r'(?i)(received\s+degree|a\s+primit\s+diploma)\s+(from|de\s+la)?\s*([^{}\n]+)',
                r'(?i)(class\s+of\s+\d{4}|promocia\s+\d{4})',
                
                # Career events
                r'(?i)(started\s+working|began\s+career|a\s+început\s+să\s+lucreze)\s+(at|la)?\s*([^{}\n]+)',
                r'(?i)(joined|s-a\s+alăturat|became|a\s+devenit)\s+([^{}\n]+)',
                r'(?i)(promoted\s+to|promovat\s+ca|appointed\s+as|numit\s+ca)\s+([^{}\n]+)',
                r'(?i)(ordained|hirotonit|consecrated|consacrat)\s+(as|ca)?\s*([^{}\n]+)',
                
                # Relationship events
                r'(?i)(married|căsătorit|wedding|nuntă)\s+(to|cu|on|în)?\s*([^{}\n]+)',
                r'(?i)(engaged|logodit|engagement|logodnă)\s+(to|cu|on|în)?\s*([^{}\n]+)',
                r'(?i)(divorced|divorțat|separation|separare)\s+(from|de)?\s*([^{}\n]+)',
                
                # Location events
                r'(?i)(moved\s+to|s-a\s+mutat\s+la|relocated\s+to|relocat\s+la)\s+([^{}\n]+)',
                r'(?i)(lived\s+in|a\s+locuit\s+în|resided\s+in|a\s+stat\s+în)\s+([^{}\n]+)',
                
                # Achievement events
                r'(?i)(won|câștigat|achieved|realizat|received|primit)\s+([^{}\n]+)',
                r'(?i)(founded|fondat|established|înființat|created|creat)\s+([^{}\n]+)',
                r'(?i)(published|publicat|wrote|scris|released|lansat)\s+([^{}\n]+)',
                
                # Other life events
                r'(?i)(retired|pensionat|retirement|pensionare)\s+(from|de\s+la)?\s*([^{}\n]+)',
                r'(?i)(died|decedat|passed\s+away|trecut\s+în\s+neființă)\s+(on|în|at|la)?\s*([^{}\n]+)',
                r'(?i)(celebrated|sărbătorit|commemorated|comemorat)\s+([^{}\n]+)'
            ]
            
            # Apply regex patterns
            for pattern in life_event_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    if isinstance(match, tuple):
                        event_text = ' '.join(str(m) for m in match if m).strip()
                    else:
                        event_text = str(match).strip()
                    
                    if event_text and len(event_text) > 5 and len(event_text) < 300:
                        # Clean up the event text
                        cleaned_event = self.clean_text(event_text)
                        if cleaned_event and not any(invalid in cleaned_event.lower() for invalid in ['javascript', 'function', 'undefined', 'null']):
                            life_events_found.add(cleaned_event)
                            logger.info(f"✅ Life event pattern match: {cleaned_event}")
            
            # Enhanced keyword-based extraction
            event_keywords = [
                'born', 'graduated', 'started', 'joined', 'married', 'moved', 'founded',
                'appointed', 'ordained', 'promoted', 'received', 'achieved', 'celebrated',
                'divorced', 'retired', 'won', 'published', 'created', 'established',
                'născut', 'absolvent', 'a început', 's-a alăturat', 'căsătorit', 's-a mutat',
                'fondat', 'numit', 'hirotonit', 'promovat', 'primit', 'realizat', 'sărbătorit'
            ]
            
            date_keywords = [
                'year', 'date', 'time', 'when', 'during', 'after', 'before', 'age', 'old',
                'since', 'until', 'from', 'in', 'on', 'at',
                'an', 'dată', 'timp', 'când', 'în timpul', 'după', 'înainte', 'vârstă',
                'de la', 'până la', 'din', 'în', 'pe', 'la'
            ]
            
            # Process each text element for events
            for text in all_clean_texts:
                if len(text) < 10 or len(text) > 200:
                    continue
                
                # Check if text contains event keywords
                has_event_keyword = any(keyword in text.lower() for keyword in event_keywords)
                has_date_keyword = any(keyword in text.lower() for keyword in date_keywords)
                
                if has_event_keyword and (has_date_keyword or any(char.isdigit() for char in text)):
                    # Ensure it's not JavaScript or technical content
                    if not any(js_indicator in text.lower() for js_indicator in ['function', 'var ', 'const ', 'let ', 'return', '{', '}', 'null', 'undefined', 'onclick', 'href']):
                        # Additional validation for life event content
                        if any(event_indicator in text.lower() for event_indicator in ['year', 'date', 'time', 'when', 'during', 'after', 'before', 'age', 'old', 'since', 'until']):
                            life_events_found.add(text)
                            logger.info(f"✅ Life event keyword match: {text}")
            
            # Look for specific date patterns that indicate life events
            date_event_patterns = [
                r'\b\d{4}\b.*(?:born|graduated|married|started|joined|moved|founded)',
                r'(?:born|graduated|married|started|joined|moved|founded).*\b\d{4}\b',
                r'(?i)(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}.*(?:born|graduated|married|started)',
                r'(?i)(?:born|graduated|married|started).*(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'
            ]
            
            for pattern in date_event_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    if match and len(match) > 10:
                        cleaned_match = self.clean_text(match)
                        if cleaned_match:
                            life_events_found.add(cleaned_match)
                            logger.info(f"✅ Date event pattern: {cleaned_match}")
            
            # Filter and limit life events
            life_events = [event for event in list(life_events_found)[:25] if len(event) > 10]  # Increased limit
            
            profile_data['life_events'] = life_events
            logger.info(f"🎯 Life events extraction completed: {len(life_events)} events extracted")
            
            # Log details
            if life_events:
                logger.info(f"🎯 Life events ({len(life_events)} items):")
                for i, event in enumerate(life_events[:10], 1):  # Show first 10
                    logger.info(f"   {i}. {event}")
                if len(life_events) > 10:
                    logger.info(f"   ... and {len(life_events) - 10} more events")
            else:
                logger.info("❌ No life events found")
            
        except Exception as e:
            logger.error(f"❌ Error extracting life events: {e}")
            import traceback
            traceback.print_exc()
            profile_data['life_events'] = []
    
    def scrape_facebook_profile(self, profile_url):
        """
        Complete profile scraping process using comprehensive sub-section navigation
        Args:
            profile_url: Facebook profile URL to scrape
        Returns:
            dict: Complete profile data from all About sections

        """
        if not self.logged_in:
            logger.error("❌ Not logged in to Facebook")
            return None
        
        try:
            logger.info(f"🚀 Starting comprehensive profile scraping: {profile_url}")
            
            # Use comprehensive extraction method that visits each sub-section
            profile_data = self.extract_comprehensive_about_data(profile_url)
            
            if not profile_data:
                logger.error("❌ No data extracted from profile")
                
                # Fallback to original method if comprehensive extraction fails
                logger.info("🔄 Falling back to original extraction method...")
                
                # Navigate to profile About section
                if not self.navigate_to_profile_about(profile_url):
                    logger.error("❌ Failed to navigate to About section")
                    return None
                
                # Extract all About section information (original method)
                profile_data = self.extract_about_sections()
                
                if not profile_data:
                    logger.error("❌ No data extracted with fallback method either")
                    return None
            
            # Transform data structure to be compatible with database
            database_compatible_data = self.transform_to_database_format(profile_data, profile_url)
            
            logger.info("✅ Profile scraping completed successfully")
            
            # Log summary
            total_sections = len([section for section in profile_data.values() 
                                if isinstance(section, dict) and section])
            logger.info(f"📊 Scraping summary: {total_sections} sections extracted")
            
            # Log extraction metadata if available
            if 'extraction_metadata' in profile_data:
                metadata = profile_data['extraction_metadata']
                logger.info(f"📋 Extraction details:")
                logger.info(f"   - Method: {metadata.get('method', 'unknown')}")
                logger.info(f"   - Sub-sections visited: {len(metadata.get('subsections_visited', []))}")
                logger.info(f"   - Sub-sections extracted: {len(metadata.get('subsections_extracted', []))}")
            
            return database_compatible_data
            
        except Exception as e:
            logger.error(f"❌ Error scraping profile: {e}")
            return None
    
    def truncate_for_db(self, text, max_length=250):
        """Truncate text to fit database field limits with intelligent cutting"""
        if not text:
            return ""
        
        if isinstance(text, list):
            # For lists, convert to string and truncate
            clean_items = []
            for item in text:
                clean_item = self.clean_text(str(item))
                if clean_item:
                    clean_items.append(clean_item)
            text = ", ".join(clean_items[:5])  # Limit to 5 items
        
        if isinstance(text, dict):
            # For dictionaries, convert to JSON string and truncate
            try:
                text = json.dumps(text, ensure_ascii=False)
            except:
                text = str(text)
        
        text = str(text).strip()
        
        # If text is within limit, return as-is
        if len(text) <= max_length:
            return text
        
        # Smart truncation: try to cut at word boundaries
        if max_length > 10:
            # Find last space before the limit
            truncated = text[:max_length-3]
            last_space = truncated.rfind(' ')
            
            if last_space > max_length * 0.8:  # If we found a space in the last 20%
                return truncated[:last_space] + "..."
            else:
                return truncated + "..."
        else:
            return text[:max_length]
    
    def transform_to_database_format(self, profile_data, profile_url):
        """Transform Selenium extracted data to database compatible format with improved mapping"""
        import json
        
        try:
            # Extract sections with improved access
            basic_info = profile_data.get('basic_info', {})
            overview = profile_data.get('overview', {})
            work_education = profile_data.get('work_education', {})
            places_lived = profile_data.get('places_lived', {})
            contact_info = profile_data.get('contact_basic_info', {})
            family = profile_data.get('family_relationships', {})
            details = profile_data.get('details_about', {})
            life_events = profile_data.get('life_events', [])
            
            logger.info(f"🔍 Transforming data sections: basic_info={bool(basic_info)}, overview={bool(overview)}, work_education={bool(work_education)}, places_lived={bool(places_lived)}")
            
            # Enhanced helper function for better data cleaning and preparation
            def clean_and_prepare(data, max_length=255, field_name="unknown"):
                """Clean data and prepare for database storage with field-specific logic"""
                if not data:
                    return ""
                
                if isinstance(data, list):
                    # Filter out JavaScript content and generic placeholders from lists
                    cleaned_list = []
                    for item in data:
                        cleaned_item = self.clean_text(str(item))
                        # Skip generic placeholders and JS content
                        if (cleaned_item and 
                            len(cleaned_item) > 5 and 
                            not any(placeholder in cleaned_item.lower() for placeholder in 
                                   ['current city', 'works at', 'studied at', 'attended from', 'favorite quotes', 'no favorite', 'unknown', 'undefined', 'null', 'none', 'browser notifications', 'browser settings', 'allow or block', 'go to your browser'])):
                            cleaned_list.append(cleaned_item)
                    
                    # Convert to JSON for complex fields or comma-separated for simple ones
                    if cleaned_list:
                        if field_name in ['work_history', 'education', 'languages', 'interests_detailed', 'life_events']:
                            # Use JSON format for complex structured data
                            return self.truncate_for_db(json.dumps(cleaned_list, ensure_ascii=False), max_length)
                        else:
                            # Use comma-separated for simple lists
                            text = ", ".join(cleaned_list[:5])  # Limit to 5 items max
                            return self.truncate_for_db(text, max_length)
                    return ""
                
                if isinstance(data, dict):
                    # Clean dictionary values and filter out empty/generic ones
                    cleaned_dict = {}
                    for key, value in data.items():
                        cleaned_value = self.clean_text(str(value)) if value else ""
                        if (cleaned_value and 
                            len(cleaned_value) > 3 and
                            not any(placeholder in cleaned_value.lower() for placeholder in 
                                   ['current city', 'works at', 'studied at', 'attended from', 'unknown', 'null', 'none', 'undefined', 'browser notifications', 'browser settings', 'allow or block', 'go to your browser'])):
                            cleaned_dict[key] = cleaned_value
                    
                    if cleaned_dict:
                        return self.truncate_for_db(json.dumps(cleaned_dict, ensure_ascii=False), max_length)
                    return ""
                
                # For strings, clean and validate
                cleaned_text = self.clean_text(str(data))
                # Skip generic placeholders
                if (cleaned_text and 
                    len(cleaned_text) > 3 and
                    not any(placeholder in cleaned_text.lower() for placeholder in 
                           ['current city', 'works at', 'studied at', 'attended from', 'unknown', 'null', 'none', 'favorite quotes', 'no favorite', 'undefined', 'browser notifications', 'browser settings', 'allow or block', 'go to your browser'])):
                    return self.truncate_for_db(cleaned_text, max_length)
                return ""
            
            # Build bio from multiple sources with priority
            bio_sources = [
                details.get('about_text', ''),
                overview.get('bio', ''),
                overview.get('current_work', ''),
                basic_info.get('bio', '')
            ]
            bio = ""
            for source in bio_sources:
                cleaned = clean_and_prepare(source, 500, 'bio')
                if cleaned and len(cleaned) > 20:  # Ensure substantial bio content
                    bio = cleaned
                    break
            
            # Extract professional title with better logic
            professional_title = ""
            work_history = work_education.get('work_history', [])
            
            # Look for current position indicators
            if work_history:
                for work_item in work_history:
                    cleaned_work = self.clean_text(str(work_item))
                    if cleaned_work:
                        # Extract title from work entries
                        if ' at ' in cleaned_work:
                            title_part = cleaned_work.split(' at ')[0].strip()
                            if (title_part and 
                                len(title_part) > 3 and 
                                title_part.lower() not in ['worked', 'works', 'employed', 'position']):
                                professional_title = title_part
                                break
                        elif len(cleaned_work) > 10 and cleaned_work.lower() not in ['worked', 'works']:
                            professional_title = cleaned_work
                            break
            
            # Fallback to overview current work
            if not professional_title:
                current_work = clean_and_prepare(overview.get('current_work', ''), 255, 'professional_title')
                if current_work:
                    professional_title = current_work
            
            # Extract current employer
            current_employer = ""
            if work_history:
                for work_item in work_history:
                    cleaned_work = self.clean_text(str(work_item))
                    if cleaned_work and ' at ' in cleaned_work:
                        employer_part = cleaned_work.split(' at ', 1)[1].strip()
                        if employer_part and len(employer_part) > 3:
                            current_employer = employer_part
                            break
            
            if not current_employer:
                current_employer = clean_and_prepare(overview.get('current_employer', ''), 255, 'current_employer')
            
            # Extract location with validation
            current_location = ""
            location_sources = [
                places_lived.get('current_city', ''),
                overview.get('current_location', ''),
                places_lived.get('location', '')
            ]
            for location in location_sources:
                cleaned_loc = clean_and_prepare(location, 255, 'current_location')
                if cleaned_loc:
                    current_location = cleaned_loc
                    break
            
            # Extract hometown/origin
            origin_location = ""
            origin_sources = [
                places_lived.get('hometown', ''),
                overview.get('hometown', ''),
                places_lived.get('origin', '')
            ]
            for origin in origin_sources:
                cleaned_origin = clean_and_prepare(origin, 255, 'origin_location')
                if cleaned_origin:
                    origin_location = cleaned_origin
                    break
            
            # Extract relationship status
            relationship_status = ""
            relationship_sources = [
                family.get('relationship_status', ''),
                overview.get('relationship_status', '')
            ]
            for status in relationship_sources:
                cleaned_status = clean_and_prepare(status, 255, 'relationship_status')
                if cleaned_status:
                    relationship_status = cleaned_status
                    break
            
            # Build interests from multiple sources
            interests_detailed = []
            if details.get('interests'):
                interests_detailed.extend(details['interests'])
            if details.get('favorite_books'):
                interests_detailed.extend([f"Books: {book}" for book in details['favorite_books']])
            if details.get('favorite_movies'):
                interests_detailed.extend([f"Movies: {movie}" for movie in details['favorite_movies']])
            if details.get('favorite_music'):
                interests_detailed.extend([f"Music: {music}" for music in details['favorite_music']])
            
            # Build social media links
            social_links = {}
            if contact_info.get('website'):
                social_links['website'] = contact_info['website']
            if contact_info.get('email'):
                social_links['email'] = contact_info['email']
            if contact_info.get('websites'):
                social_links['additional_websites'] = contact_info['websites']
            
            # Build connected accounts
            connected_accounts = []
            if contact_info.get('email'):
                email = self.clean_text(str(contact_info['email']))
                if email and '@' in email:
                    connected_accounts.append(f"Email: {email}")
            if contact_info.get('website'):
                website = self.clean_text(str(contact_info['website']))
                if website and ('http' in website or 'www' in website or '.' in website):
                    connected_accounts.append(f"Website: {website}")
            if contact_info.get('phone'):
                phone = self.clean_text(str(contact_info['phone']))
                if phone and len(phone) >= 8:
                    connected_accounts.append(f"Phone: {phone}")
            
            # Build final transformed data with improved mapping
            transformed_data = {
                # Basic information
                'name': clean_and_prepare(basic_info.get('name', ''), 255, 'name'),
                'bio': bio,
                'profile_url': profile_url,
                'username': clean_and_prepare(basic_info.get('username', ''), 100, 'username'),
                
                # Professional information
                'professional_title': self.truncate_for_db(professional_title, 255),
                'current_employer': self.truncate_for_db(current_employer, 255),
                'work_history': clean_and_prepare(work_education.get('work_history', []), 1000, 'work_history'),
                
                # Education
                'education': clean_and_prepare(work_education.get('education_history', []), 1000, 'education'),
                
                # Location details
                'current_location': self.truncate_for_db(current_location, 255),
                'origin_location': self.truncate_for_db(origin_location, 255),
                'location': self.truncate_for_db(current_location, 255),  # Same as current_location for compatibility
                
                # Personal information
                'relationship_status': self.truncate_for_db(relationship_status, 255),
                'languages': clean_and_prepare(contact_info.get('languages', []), 500, 'languages'),
                
                # Interests
                'interests': clean_and_prepare(details.get('interests', [])[:3], 255, 'interests'),  # Top 3 interests for basic field
                'interests_detailed': clean_and_prepare(interests_detailed, 1000, 'interests_detailed'),
                
                # Social media links
                'social_media_links': clean_and_prepare(social_links, 500, 'social_media_links'),
                
                # Religious information
                'religious_info': clean_and_prepare(details.get('religious_info', ''), 500, 'religious_info'),
                'church_position': clean_and_prepare(contact_info.get('church_position', ''), 255, 'church_position'),
                'church_affiliation': clean_and_prepare(contact_info.get('church_affiliation', ''), 255, 'church_affiliation'),
                
                # Contact and accounts
                'connected_accounts': connected_accounts,
                
                # Other details
                'life_events': clean_and_prepare(life_events, 1000, 'life_events'),
                'favorite_quotes': clean_and_prepare(details.get('quotes', []), 500, 'favorite_quotes'),
                
                # Metadata
                'scraped_at': datetime.now().isoformat(),
                'session_duration': str(datetime.now() - self.session_start_time) if self.session_start_time else "Unknown",
                'scraping_method': 'selenium',
                'is_public': True,
                'last_scraped_at': datetime.now().isoformat()
            }
            
            # Log transformation results
            populated_fields = len([v for v in transformed_data.values() if v and str(v).strip()])
            logger.info(f"✅ Data transformed to database format with {populated_fields} populated fields")
            
            # Debug log key fields
            logger.info(f"🔍 Key field mapping:")
            logger.info(f"   - Bio: {bio[:50]}..." if bio else "   - Bio: (empty)")
            logger.info(f"   - Professional Title: {professional_title}")
            logger.info(f"   - Current Employer: {current_employer}")
            logger.info(f"   - Current Location: {current_location}")
            logger.info(f"   - Origin Location: {origin_location}")
            logger.info(f"   - Relationship Status: {relationship_status}")
            
            return transformed_data
            
        except Exception as e:
            logger.error(f"❌ Error transforming data to database format: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def close(self):
        """Close the WebDriver session"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                self.logged_in = False
                self.session_start_time = None
                logger.info("✅ WebDriver session closed successfully")
            except Exception as e:
                logger.error(f"❌ Error closing WebDriver: {e}")
                # Try to force close if normal close fails
                try:
                    if self.driver:
                        self.driver.quit()
                except:
                    pass
                finally:
                    self.driver = None
                    self.logged_in = False
                    self.session_start_time = None

# Global selenium manager instance
_selenium_manager = None

def get_selenium_manager():
    """Get the global selenium manager instance"""
    global _selenium_manager
    if _selenium_manager is None:
        _selenium_manager = FacebookSeleniumManager(headless=True)
    return _selenium_manager

def initialize_facebook_session(email, password, headless=True):
    """Initialize Facebook session at application startup"""
    try:
        logger.info("🚀 Initializing Facebook Selenium session...")
        manager = get_selenium_manager()
        manager.headless = headless
        
        success = manager.login_to_facebook(email, password)
        if success:
            logger.info("✅ Facebook session ready for comprehensive profile scraping")
        else:
            logger.error("❌ Facebook session initialization failed")
        
        return success
    except Exception as e:
        logger.error(f"❌ Error initializing Facebook session: {e}")
        return False

def scrape_facebook_profile_selenium(profile_url):
    """Scrape Facebook profile using existing session"""
    try:
        manager = get_selenium_manager()
        if not manager.logged_in:
            logger.error("❌ Facebook session not available")
            return None
        
        return manager.scrape_facebook_profile(profile_url)
    except Exception as e:
        logger.error(f"❌ Error in profile scraping: {e}")
        return None

def close_selenium_session():
    """Close selenium session at application shutdown"""
    global _selenium_manager
    if _selenium_manager:
        try:
            logger.info("🔄 Closing Facebook Selenium session...")
            _selenium_manager.close()
            _selenium_manager = None
            logger.info("✅ Facebook session closed")
        except Exception as e:
            logger.error(f"❌ Error closing Facebook session: {e}")
            try:
                # Force quit if normal close fails
                if hasattr(_selenium_manager, 'driver') and _selenium_manager.driver:
                    _selenium_manager.driver.quit()
                    logger.info("✅ Driver forcibly quit")
            except:
                pass

def get_session_status():
    """Get current session status"""
    global _selenium_manager
    if _selenium_manager and _selenium_manager.logged_in:
        return {
            'logged_in': True,
            'session_start': _selenium_manager.session_start_time.isoformat() if _selenium_manager.session_start_time else None,
            'headless': _selenium_manager.headless
        }
    else:
        return {
            'logged_in': False,
            'session_start': None,
            'headless': None
        }
