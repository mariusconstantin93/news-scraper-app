from apscheduler.schedulers.background import BackgroundScheduler
import subprocess
import json
from datetime import datetime, timedelta
import os
import sys
import threading

# Global locks to prevent concurrent execution of same scraper
_scraper_locks = {
    'biziday': threading.Lock(),
    'adevarul': threading.Lock(), 
    'facebook': threading.Lock()
}

def run_biziday_scraper():
    """Runs the Biziday scraper and saves data to database"""
    # Prevent concurrent execution
    if not _scraper_locks['biziday'].acquire(blocking=False):
        print(f"⏸️  [{datetime.now().strftime('%H:%M:%S')}] Biziday scraper already running - skipping this execution")
        return
    
    try:
        print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] Starting Biziday scraper...")
        # Use same path calculation as other scrapers
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scrapers', 'biziday_scraper.py')
        script_path = os.path.abspath(script_path)  # Normalize the path
        print(f"📂 Script path: {script_path}")
        
        if not os.path.exists(script_path):
            print(f"❌ Script not found: {script_path}")
            print(f"🔍 Current dir: {os.path.dirname(__file__)}")
            return
        
        # Fix encoding issue by explicitly setting UTF-8
        result = subprocess.run(
            [sys.executable, script_path], 
            capture_output=True, 
            text=True, 
            timeout=60,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode == 0:
            try:
                if result.stdout and result.stdout.strip():
                    articles_data = json.loads(result.stdout)
                    if isinstance(articles_data, list):
                        save_articles(articles_data, 'Biziday')
                        print(f"✅ Biziday: Processed {len(articles_data)} articles")
                    else:
                        print(f"⚠️  Biziday: Unexpected data format: {type(articles_data)}")
                else:
                    print("⚠️  Biziday: No output received from scraper")
            except json.JSONDecodeError as e:
                print(f"❌ Biziday JSON decode error: {e}")
                print(f"📝 Raw output (first 200 chars): {result.stdout[:200]}...")
        else:
            print(f"❌ Biziday scraper failed (exit code {result.returncode})")
            print(f"📝 Error: {result.stderr}")
            if result.stdout:
                print(f"📝 Output: {result.stdout}")
    except subprocess.TimeoutExpired:
        print("⏰ Biziday scraper timeout (60s)")
    except Exception as e:
        print(f"💥 Biziday scraper exception: {e}")
    finally:
        # Always release the lock
        _scraper_locks['biziday'].release()

def run_adevarul_scraper():
    """Runs the Adevarul scraper and saves data to database"""
    # Prevent concurrent execution
    if not _scraper_locks['adevarul'].acquire(blocking=False):
        print(f"⏸️  [{datetime.now().strftime('%H:%M:%S')}] Adevarul scraper already running - skipping this execution")
        return
    
    try:
        print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] Starting Adevarul scraper...")
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scrapers', 'adevarul_scraper.py')
        script_path = os.path.abspath(script_path)  # Normalize the path
        print(f"📂 Script path: {script_path}")
        
        if not os.path.exists(script_path):
            print(f"❌ Script not found: {script_path}")
            return
        
        # Fix encoding issue by explicitly setting UTF-8
        result = subprocess.run(
            [sys.executable, script_path], 
            capture_output=True, 
            text=True, 
            timeout=600,  # Increased timeout for Adevarul scraper (content extraction takes time)
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode == 0:
            try:
                if result.stdout and result.stdout.strip():
                    articles_data = json.loads(result.stdout)
                    if isinstance(articles_data, list):
                        save_articles(articles_data, 'Adevarul')
                        print(f"✅ Adevarul: Processed {len(articles_data)} articles")
                    else:
                        print(f"⚠️  Adevarul: Unexpected data format: {type(articles_data)}")
                else:
                    print("⚠️  Adevarul: No output received from scraper")
            except json.JSONDecodeError as e:
                print(f"❌ Adevarul JSON decode error: {e}")
                print(f"📝 Raw output (first 200 chars): {result.stdout[:200]}...")
        else:
            print(f"❌ Adevarul scraper failed (exit code {result.returncode})")
            print(f"📝 Error: {result.stderr}")
            if result.stdout:
                print(f"📝 Output: {result.stdout}")
    except subprocess.TimeoutExpired:
        print("⏰ Adevarul scraper timeout (600s)")
    except Exception as e:
        print(f"💥 Adevarul scraper exception: {e}")
    finally:
        # Always release the lock
        _scraper_locks['adevarul'].release()

def run_facebook_scraper(profile_input=None):
    """
    Runs the Facebook scraper for a specific profile and saves data to database
    Uses Selenium WebDriver for enhanced extraction
    Args:
        profile_input: Facebook username, numeric ID, or full URL to scrape
    """
    # Prevent concurrent execution
    if not _scraper_locks['facebook'].acquire(blocking=False):
        print(f"⏸️  [{datetime.now().strftime('%H:%M:%S')}] Facebook scraper already running - skipping this execution")
        return {'error': 'Facebook scraper is already running'}
    
    try:
        if not profile_input:
            print("❌ No profile input provided for Facebook scraper")
            return {'error': 'No profile input provided'}
        
        print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] Starting Facebook scraper (Selenium) for: {profile_input}")
        
        # Try using Selenium scraper first
        try:
            from app.selenium_facebook_manager import scrape_facebook_profile_selenium
            
            # Convert profile input to full URL 
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
            
            profile_url = normalize_facebook_url(profile_input)
            profile_data = scrape_facebook_profile_selenium(profile_url)
            
            if profile_data and 'error' not in profile_data:
                # Check for existing profile and update/save accordingly
                from app.models.models import FacebookUserProfile
                existing = FacebookUserProfile.query.filter_by(profile_url=profile_data['profile_url']).first()
                
                if existing:
                    # ALWAYS UPDATE existing profile with fresh data 
                    print(f"🔄 Facebook: Found existing profile, updating with fresh data: {profile_data['name']}")
                    result = update_facebook_profile(existing, profile_data)
                    # Return success regardless of whether fields changed
                    return {
                        'success': True,
                        'message': f"Successfully refreshed profile: {profile_data['name']} (method: Selenium) (updated: {result.get('updated', False)})",
                        'profile_data': profile_data,
                        'action': 'updated' if result.get('updated') else 'refreshed',
                        'method': 'selenium'
                    }
                else:
                    # CREATE new profile
                    save_facebook_profile(profile_data, profile_data['profile_url'])
                    print(f"✅ Facebook: Successfully created new profile: {profile_data['name']} (method: Selenium)")
                    return {
                        'success': True,
                        'message': f"Successfully extracted and saved new profile: {profile_data['name']} (method: Selenium)",
                        'profile_data': profile_data,
                        'action': 'created',
                        'method': 'selenium'
                    }
            else:
                error_msg = profile_data.get('error', 'Unknown error from Selenium scraper') if profile_data else 'Selenium scraper returned no data'
                print(f"❌ Facebook Selenium scraper error: {error_msg}")
                return {'error': f'Selenium scraper failed: {error_msg}', 'method': 'selenium'}
                
        except ImportError:
            print("⚠️ Selenium scraper not available, trying fallback script method")
        except Exception as e:
            print(f"❌ Selenium scraper exception: {e}")
        
        # Fallback to script method if Selenium fails
        print("🔄 Falling back to script-based Facebook scraper")
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scrapers', 'facebook_scraper.py')
        script_path = os.path.abspath(script_path)  # Normalize the path
        print(f"📂 Script path: {script_path}")
        
        if not os.path.exists(script_path):
            error_msg = f"Script not found: {script_path}"
            print(f"❌ {error_msg}")
            return {'error': error_msg}
        
        try:
            # Run the scraper with the specific profile input
            result = subprocess.run(
                [sys.executable, script_path, profile_input], 
                capture_output=True, 
                text=True, 
                timeout=60,  # Timeout for Facebook scraper
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                if result.stdout and result.stdout.strip():
                    try:
                        profile_data = json.loads(result.stdout)
                        if 'error' not in profile_data:
                            # Check for existing profile and update/save accordingly
                            from app.models.models import FacebookUserProfile
                            existing = FacebookUserProfile.query.filter_by(profile_url=profile_data['profile_url']).first()
                            
                            if existing:
                                # ALWAYS UPDATE existing profile with fresh data 
                                print(f"🔄 Facebook: Found existing profile, updating with fresh data: {profile_data['name']}")
                                result = update_facebook_profile(existing, profile_data)
                                # Return success regardless of whether fields changed
                                return {
                                    'success': True,
                                    'message': f"Successfully refreshed profile: {profile_data['name']} (method: HTTP fallback) (updated: {result.get('updated', False)})",
                                    'profile_data': profile_data,
                                    'action': 'updated' if result.get('updated') else 'refreshed',
                                    'method': 'http_fallback'
                                }
                            else:
                                # CREATE new profile
                                save_facebook_profile(profile_data, profile_data['profile_url'])
                                print(f"✅ Facebook: Successfully created new profile: {profile_data['name']} (method: HTTP fallback)")
                                return {
                                    'success': True,
                                    'message': f"Successfully extracted and saved new profile: {profile_data['name']} (method: HTTP fallback)",
                                    'profile_data': profile_data,
                                    'action': 'created',
                                    'method': 'http_fallback'
                                }
                        else:
                            error_msg = profile_data.get('error', 'Unknown error from scraper')
                            print(f"❌ Facebook scraper returned error: {error_msg}")
                            return {'error': error_msg, 'method': 'http_fallback'}
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON response from scraper: {e}"
                        print(f"❌ {error_msg}")
                        print(f"📝 Raw output: {result.stdout[:200]}...")
                        return {'error': error_msg}
                else:
                    error_msg = "No output received from Facebook scraper"
                    print(f"⚠️  {error_msg}")
                    return {'error': error_msg}
            else:
                error_msg = f"Facebook scraper failed (exit code {result.returncode}): {result.stderr}"
                print(f"❌ {error_msg}")
                if result.stdout:
                    print(f"📝 Output: {result.stdout}")
                return {'error': error_msg}
                
        except subprocess.TimeoutExpired:
            error_msg = "Facebook scraper timeout (60s)"
            print(f"⏰ {error_msg}")
            return {'error': error_msg}
        except Exception as e:
            error_msg = f"Facebook scraper exception: {e}"
            print(f"💥 {error_msg}")
            return {'error': error_msg}
            
    except Exception as e:
        error_msg = f"Facebook scraper wrapper exception: {e}"
        print(f"💥 {error_msg}")
        return {'error': error_msg}
    finally:
        # Always release the lock
        _scraper_locks['facebook'].release()

def get_scraper_status():
    """Get current status of all scrapers (running or idle)"""
    status = {}
    for scraper_name, lock in _scraper_locks.items():
        # Try to acquire lock non-blocking to check if scraper is running
        if lock.acquire(blocking=False):
            # Lock acquired - scraper is idle
            lock.release()
            status[scraper_name] = 'idle'
        else:
            # Lock not acquired - scraper is running
            status[scraper_name] = 'running'
    return status

def log_scraper_status():
    """Log current status of all scrapers"""
    status = get_scraper_status()
    running_scrapers = [name for name, state in status.items() if state == 'running']
    
    if running_scrapers:
        print(f"🔄 Currently running: {', '.join(running_scrapers)}")
    else:
        print("💤 All scrapers idle")

def save_articles(articles_data, source):
    """Save articles to database with duplicate checking and smart update detection"""
    # Import models inside the function to ensure proper app context
    from app.models.models import db, NewsArticle
    import hashlib
    
    try:
        saved_count = 0
        updated_count = 0
        checked_count = 0  # Track how many updates we've checked
        
        for article_data in articles_data:
            # Check for duplicates by link
            existing = NewsArticle.query.filter_by(link=article_data['link']).first()
            
            if not existing:
                # NEW ARTICLE - Parse and save normally
                published_at = None
                if article_data.get('published_at'):
                    try:
                        published_at = datetime.fromisoformat(article_data['published_at'].replace('Z', '+00:00'))
                    except:
                        published_at = None
                
                # Legacy: also check for timestamp field for backward compatibility
                if not published_at and article_data.get('timestamp'):
                    try:
                        published_at = datetime.fromisoformat(article_data['timestamp'].replace('Z', '+00:00'))
                    except:
                        published_at = None
                
                # Parse updated date from article data (can be None)
                updated_at = None
                if article_data.get('updated_at'):
                    try:
                        updated_at = datetime.fromisoformat(article_data['updated_at'].replace('Z', '+00:00'))
                    except:
                        updated_at = None
                
                article = NewsArticle(
                    title=article_data['title'],
                    summary=article_data['summary'],
                    content=article_data.get('content'),  # Include full content
                    link=article_data['link'],
                    source=source,
                    published_at=published_at,  # Use the real publication date
                    updated_at=updated_at  # Use the real update date (can be None)
                )
                db.session.add(article)
                saved_count += 1
                
            else:
                # DUPLICATE FOUND - Check if we should verify for updates
                # Respect the session limit for update checks
                if (checked_count < UPDATE_CHECK_CONFIG['max_checks_per_session'] and 
                    should_check_article_for_updates(existing, article_data)):
                    
                    checked_count += 1
                    print(f"🔍 Checking for updates ({checked_count}/{UPDATE_CHECK_CONFIG['max_checks_per_session']}): {existing.title[:50]}...")
                    # Parse the new updated_at from scraped data
                    new_updated_at = None
                    if article_data.get('updated_at'):
                        try:
                            new_updated_at = datetime.fromisoformat(article_data['updated_at'].replace('Z', '+00:00'))
                        except:
                            new_updated_at = None
                    
                    # Check if the article was actually updated
                    if article_needs_update(existing, article_data, new_updated_at):
                        # ENHANCED UPDATE: Re-extract content when updated_at changed
                        if new_updated_at and existing.updated_at:
                            # Ensure both datetimes are timezone-aware for comparison
                            new_updated_tz = ensure_romania_timezone(new_updated_at)
                            existing_updated_tz = ensure_romania_timezone(existing.updated_at)
                            if new_updated_tz > existing_updated_tz:
                                # Check if content refresh is enabled
                                if UPDATE_CHECK_CONFIG.get('enable_content_refresh', True):
                                    print(f"🔄 Article has newer updated_at - re-extracting full content: {existing.title[:50]}...")
                                    
                                    # Re-extract full content from the source with timeout protection
                                    try:
                                        import time
                                        import threading
                                        from app.scrapers.content_extractor import extract_article_content, extract_article_metadata, generate_summary_from_content
                                        
                                        # Ultra-robust timeout wrapper that prevents all hanging
                                        def extract_with_guaranteed_timeout(url, source_name, timeout_seconds=30):
                                            """
                                            Guaranteed timeout mechanism that will NEVER hang.
                                            Uses multiple layers of protection.
                                            """
                                            result = {'content': None, 'metadata': None, 'error': None}
                                            extraction_complete = threading.Event()
                                            extraction_started = threading.Event()
                                            
                                            def extraction_thread():
                                                try:
                                                    extraction_started.set()
                                                    print(f"   🌐 Starting content extraction (max: {timeout_seconds}s)...")
                                                    
                                                    # Use the improved extract_article_content which has internal timeouts
                                                    result['content'] = extract_article_content(url, source_name)
                                                    
                                                    if result['content']:
                                                        print(f"   🌐 Starting metadata extraction...")
                                                        result['metadata'] = extract_article_metadata(url, source_name)
                                                    
                                                except Exception as e:
                                                    result['error'] = f"Extraction error: {str(e)}"
                                                finally:
                                                    extraction_complete.set()
                                            
                                            # Start extraction in daemon thread (will be killed when main thread ends)
                                            thread = threading.Thread(target=extraction_thread, daemon=True)
                                            thread.start()
                                            
                                            # Wait for thread to start
                                            if not extraction_started.wait(timeout=5):
                                                result['error'] = "Extraction thread failed to start within 5s"
                                                return result
                                            
                                            # Robust polling-based timeout with early exit conditions
                                            start_time = time.time()
                                            poll_interval = 0.5  # Check every 0.5 seconds
                                            
                                            while True:
                                                elapsed = time.time() - start_time
                                                
                                                # Check if extraction completed
                                                if extraction_complete.wait(timeout=poll_interval):
                                                    print(f"   ✅ Extraction completed in {elapsed:.1f}s")
                                                    break
                                                
                                                # Check for timeout
                                                if elapsed >= timeout_seconds:
                                                    result = {
                                                        'content': None,
                                                        'metadata': None,
                                                        'error': f"Extraction timeout after {elapsed:.1f}s (limit: {timeout_seconds}s)"
                                                    }
                                                    print(f"   ⏱️  TIMEOUT: {result['error']}")
                                                    break
                                                
                                                # Progress indicator
                                                if int(elapsed) % 5 == 0 and elapsed > 0:
                                                    print(f"   ⏳ Still extracting... ({elapsed:.0f}s/{timeout_seconds}s)")
                                            
                                            return result
                                        
                                        # Use guaranteed timeout protection
                                        timeout_seconds = min(UPDATE_CHECK_CONFIG.get('content_extraction_timeout', 20), 30)  # Cap at 30s
                                        print(f"   🛡️  Using guaranteed timeout: {timeout_seconds}s")
                                        extraction_result = extract_with_guaranteed_timeout(existing.link, source.lower(), timeout_seconds=timeout_seconds)
                                        
                                        if extraction_result['error']:
                                            print(f"   ⏱️  Content extraction failed: {extraction_result['error']}")
                                            print(f"   ⚠️  Using basic update without content re-extraction")
                                            # Fallback to basic update
                                            existing.updated_at = new_updated_at
                                            existing.summary = article_data.get('summary', existing.summary)
                                            existing.content = article_data.get('content', existing.content)
                                        else:
                                            fresh_content = extraction_result['content']
                                            fresh_metadata = extraction_result['metadata'] or {}
                                            
                                            if fresh_content:
                                                existing.content = fresh_content
                                                print(f"   ✅ Updated content ({len(fresh_content)} chars)")
                                                
                                                # Regenerate summary from new content
                                                if len(fresh_content) > 100:
                                                    fresh_summary = generate_summary_from_content(fresh_content, 200)
                                                    existing.summary = fresh_summary
                                                    print(f"   ✅ Updated summary from fresh content")
                                                
                                            else:
                                                # Fallback: use scraped summary if content extraction failed
                                                existing.summary = article_data.get('summary', existing.summary)
                                                existing.content = article_data.get('content', existing.content)
                                                print(f"   ⚠️  Content re-extraction failed, using scraped data")
                                            
                                            # Use fresh metadata if available
                                            if fresh_metadata.get('updated_at'):
                                                try:
                                                    fresh_updated_at = datetime.fromisoformat(fresh_metadata['updated_at'].replace('Z', '+00:00'))
                                                    existing.updated_at = fresh_updated_at
                                                    print(f"   ✅ Updated with fresh metadata updated_at: {fresh_updated_at}")
                                                except:
                                                    existing.updated_at = new_updated_at
                                            else:
                                                existing.updated_at = new_updated_at
                                        
                                    except Exception as content_error:
                                        print(f"   ❌ Error re-extracting content: {content_error}")
                                        # Fallback to basic update
                                        existing.updated_at = new_updated_at
                                        existing.summary = article_data.get('summary', existing.summary)
                                        existing.content = article_data.get('content', existing.content)
                                else:
                                    # Content refresh disabled - do basic update
                                    print(f"🔄 Article has newer updated_at - content refresh disabled, doing basic update: {existing.title[:50]}...")
                                    existing.updated_at = new_updated_at
                                    existing.summary = article_data.get('summary', existing.summary)
                                    existing.content = article_data.get('content', existing.content)
                        else:
                            # Normal update without content re-extraction
                            existing.updated_at = new_updated_at
                            existing.summary = article_data.get('summary', existing.summary)
                            existing.content = article_data.get('content', existing.content)
                        
                        updated_count += 1
                        print(f"🔄 Updated article: {existing.title[:50]}... (new updated_at: {existing.updated_at})")
                    # else: Article is duplicate but no update needed - skip silently
        
        db.session.commit()
        
        if updated_count > 0:
            print(f"💾 {source}: Saved {saved_count} new, updated {updated_count} existing, checked {checked_count} for updates (total processed: {len(articles_data)})")
        else:
            print(f"💾 Saved {saved_count} new articles from {source} (total processed: {len(articles_data)})")
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error saving articles from {source}: {e}")

# Enhanced duplicate checking with smart updated_at verification
UPDATE_CHECK_CONFIG = {
    'check_frequency_hours': {'Adevarul': 24, 'Biziday': 24, 'default': 72},
    'max_article_age_days': 7,
    'max_checks_per_session': 50,
    'enable_update_checks': True,
    'enable_content_refresh': True,  # Re-extract content when updated_at changes
    'content_extraction_timeout': 20,  # Timeout for content extraction (seconds)
    'skip_content_refresh_on_timeout': True  # Skip content refresh if it times out
}

def ensure_romania_timezone(dt):
    """Helper function to ensure datetime is in Romania timezone"""
    import pytz
    ROMANIA_TZ = pytz.timezone('Europe/Bucharest')
    
    if dt is None:
        return None
        
    if dt.tzinfo is None:
        # Naive datetime - assume it's already in Romania timezone
        return ROMANIA_TZ.localize(dt)
    else:
        # Timezone-aware datetime - convert to Romania timezone
        return dt.astimezone(ROMANIA_TZ)

def should_check_article_for_updates(existing_article, new_article_data):
    """
    Determine if a duplicate article should be checked for updates
    Uses selective criteria to avoid performance impact
    """
    from datetime import datetime, timedelta
    import pytz
    
    if not UPDATE_CHECK_CONFIG['enable_update_checks']:
        return False
    
    # Use timezone-aware datetime for Romania
    ROMANIA_TZ = pytz.timezone('Europe/Bucharest')
    now = datetime.now(ROMANIA_TZ)
    
    # Always check if existing article has no updated_at
    if not existing_article.updated_at:
        return True
    
    # Only check recent articles (configurable age limit)
    if existing_article.published_at:
        published_at = ensure_romania_timezone(existing_article.published_at)
        days_since_published = (now - published_at).days
        if days_since_published > UPDATE_CHECK_CONFIG['max_article_age_days']:
            return False  # Article too old, skip checking
    
    # Check frequency limits based on source importance
    updated_at = ensure_romania_timezone(existing_article.updated_at)
    hours_since_last_update = (now - updated_at).total_seconds() / 3600
    source_frequency = UPDATE_CHECK_CONFIG['check_frequency_hours'].get(
        existing_article.source, 
        UPDATE_CHECK_CONFIG['check_frequency_hours']['default']
    )
    
    if hours_since_last_update < source_frequency:
        return False  # Too soon to check again
    
    # Check if scraped data suggests changes
    if new_article_data.get('updated_at'):
        try:
            new_updated_at = datetime.fromisoformat(new_article_data['updated_at'].replace('Z', '+00:00'))
            new_updated_at = ensure_romania_timezone(new_updated_at)
            
            if new_updated_at and existing_article.updated_at:
                existing_updated_at = ensure_romania_timezone(existing_article.updated_at)
                if new_updated_at > existing_updated_at:
                    return True  # Scraped data shows newer update date
        except Exception as e:
            print(f"   ⚠️  Error parsing new updated_at: {e}")
    
    return True  # Default: check for updates

def article_needs_update(existing_article, new_article_data, new_updated_at):
    """
    Determine if an article actually needs to be updated in the database
    Enhanced logic to detect real content changes
    """
    import pytz
    
    # Use Romania timezone for comparisons
    ROMANIA_TZ = pytz.timezone('Europe/Bucharest')
    
    # Priority 1: If updated_at changed, it definitely needs update
    if new_updated_at and existing_article.updated_at:
        # Ensure both datetimes are timezone-aware and in Romania timezone
        new_updated_at = ensure_romania_timezone(new_updated_at)
        existing_updated_at = ensure_romania_timezone(existing_article.updated_at)
        
        if new_updated_at > existing_updated_at:
            print(f"   📅 updated_at changed: {existing_updated_at} → {new_updated_at}")
            return True
    elif new_updated_at and not existing_article.updated_at:
        # Article has no updated_at but new data has one
        new_updated_at = ensure_romania_timezone(new_updated_at)
        print(f"   📅 First time updated_at detected: {new_updated_at}")
        return True
    
    # Priority 2: Content length changes significantly (indicates real changes)
    if new_article_data.get('content') and existing_article.content:
        old_length = len(existing_article.content)
        new_length = len(new_article_data['content'])
        length_diff_percent = abs(new_length - old_length) / old_length * 100 if old_length > 0 else 0
        
        if length_diff_percent > 5:  # More than 5% change in content length
            print(f"   📝 Content length changed significantly: {old_length} → {new_length} chars ({length_diff_percent:.1f}%)")
            return True
    
    # Priority 3: Summary changes significantly
    if new_article_data.get('summary') and existing_article.summary:
        old_summary = existing_article.summary.strip()
        new_summary = new_article_data['summary'].strip()
        
        # Check if summary is completely different
        if new_summary != old_summary:
            # Allow minor differences (whitespace, punctuation)
            import difflib
            similarity = difflib.SequenceMatcher(None, old_summary.lower(), new_summary.lower()).ratio()
            
            if similarity < 0.8:  # Less than 80% similar
                print(f"   📋 Summary changed significantly (similarity: {similarity:.2f})")
                return True
    
    # Priority 4: Title changes (rare but important)
    if new_article_data.get('title') and existing_article.title:
        if new_article_data['title'].strip() != existing_article.title.strip():
            print(f"   📰 Title changed: {existing_article.title[:30]}... → {new_article_data['title'][:30]}...")
            return True
    
    return False

def save_facebook_profile(profile_data, profile_url):
    """Save Facebook profile to database with duplicate checking and ALL enhanced fields"""
    # Import models inside the function to ensure proper app context
    from app.models.models import db, FacebookUserProfile
    from datetime import datetime
    
    try:
        # Check for duplicates by profile_url
        existing = FacebookUserProfile.query.filter_by(profile_url=profile_url).first()
        if not existing:
            connected_accounts = ','.join(profile_data.get('connected_accounts', []))
            
            # Helper function to safely get and clean string values
            def safe_get_string(data, key, default=''):
                value = data.get(key, default)
                if isinstance(value, str):
                    return value.strip()
                return default
            
            # Helper function to safely get integer values
            def safe_get_int(data, key, default=0):
                value = data.get(key, default)
                if isinstance(value, (int, str)) and str(value).isdigit():
                    return int(value)
                return default
            
            # Helper function to safely get boolean values  
            def safe_get_bool(data, key, default=False):
                value = data.get(key, default)
                if isinstance(value, bool):
                    return value
                return default
            
            profile = FacebookUserProfile(
                # Basic information
                name=profile_data['name'],
                bio=safe_get_string(profile_data, 'bio'),
                connected_accounts=connected_accounts,
                profile_url=profile_url,
                username=safe_get_string(profile_data, 'username'),
                location=safe_get_string(profile_data, 'location'),
                country=safe_get_string(profile_data, 'country', 'RO'),
                age_range=safe_get_string(profile_data, 'age_range'),
                gender=safe_get_string(profile_data, 'gender'),
                
                # Professional information
                professional_title=safe_get_string(profile_data, 'professional_title'),
                current_employer=safe_get_string(profile_data, 'current_employer'),
                work_history=safe_get_string(profile_data, 'work_history'),
                
                # Education
                education=safe_get_string(profile_data, 'education'),
                
                # Location details
                current_location=safe_get_string(profile_data, 'current_location'),
                origin_location=safe_get_string(profile_data, 'origin_location'),
                
                # Personal information
                relationship_status=safe_get_string(profile_data, 'relationship_status'),
                languages=safe_get_string(profile_data, 'languages'),
                
                # Interests
                interests=safe_get_string(profile_data, 'interests'),
                interests_detailed=safe_get_string(profile_data, 'interests_detailed'),
                topics_discussed=safe_get_string(profile_data, 'topics_discussed'),
                
                # Social media links
                social_media_links=safe_get_string(profile_data, 'social_media_links'),
                
                # Religious information
                religious_info=safe_get_string(profile_data, 'religious_info'),
                church_position=safe_get_string(profile_data, 'church_position'),
                church_affiliation=safe_get_string(profile_data, 'church_affiliation'),
                
                # Enhanced fields - Family, events, and additional info
                family_members=safe_get_string(profile_data, 'family_members'),
                life_events=safe_get_string(profile_data, 'life_events'),
                about_section=safe_get_string(profile_data, 'about_section'),
                favorite_quotes=safe_get_string(profile_data, 'favorite_quotes'),
                other_names=safe_get_string(profile_data, 'other_names'),
                
                # Contact details
                contact_email=safe_get_string(profile_data, 'contact_email'),
                contact_phone=safe_get_string(profile_data, 'contact_phone'),
                birthday=safe_get_string(profile_data, 'birthday'),
                political_views=safe_get_string(profile_data, 'political_views'),
                
                # Social metrics
                followers_count=safe_get_int(profile_data, 'followers_count'),
                friends_count=safe_get_int(profile_data, 'friends_count'),
                posts_count=safe_get_int(profile_data, 'posts_count'),
                
                # Status fields
                is_verified=safe_get_bool(profile_data, 'is_verified'),
                is_public=safe_get_bool(profile_data, 'is_public', True),
                scraping_method=safe_get_string(profile_data, 'scraping_method', 'manual'),
                
                # Timestamps
                last_scraped_at=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            db.session.add(profile)
            db.session.commit()
            
            # Count populated enhanced fields for reporting
            enhanced_fields = [
                'professional_title', 'current_employer', 'work_history', 'education',
                'current_location', 'origin_location', 'relationship_status', 'languages',
                'interests_detailed', 'social_media_links', 'religious_info', 
                'church_position', 'church_affiliation',
                'family_members', 'life_events', 'about_section', 'favorite_quotes',
                'other_names', 'contact_email', 'contact_phone', 'birthday', 'political_views'
            ]
            populated_count = sum(1 for field in enhanced_fields if getattr(profile, field))
            
            print(f"✅ Saved NEW Facebook profile: {profile_data['name']} ({populated_count}/{len(enhanced_fields)} enhanced fields populated)")
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error saving Facebook profile: {e}")
        import traceback
        traceback.print_exc()

def update_facebook_profile(existing_profile, new_profile_data):
    """Update existing Facebook profile with fresh data"""
    from app.models.models import db
    import json
    
    try:
        updated = False
        
        # Helper function to safely get and clean string values
        def safe_get_string(data, key, default=''):
            value = data.get(key, default)
            if isinstance(value, str):
                return value.strip()
            return default
        
        # Helper function to update field if different
        def update_field_if_different(field_name, new_value):
            nonlocal updated
            current_value = getattr(existing_profile, field_name, None)
            
            # Handle None values
            if new_value is None:
                new_value = ''
            if current_value is None:
                current_value = ''
            
            if str(new_value) != str(current_value):
                if new_value:
                    print(f"   📝 Updating {field_name}: '{str(current_value)[:30]}...' → '{str(new_value)[:30]}...'")
                else:
                    print(f"   📝 Clearing {field_name}")
                setattr(existing_profile, field_name, new_value)
                updated = True
        
        # Update basic fields
        update_field_if_different('name', safe_get_string(new_profile_data, 'name'))
        update_field_if_different('bio', safe_get_string(new_profile_data, 'bio'))
        
        # Update connected accounts
        new_accounts = new_profile_data.get('connected_accounts', [])
        new_accounts_str = ','.join(new_accounts) if new_accounts else ''
        update_field_if_different('connected_accounts', new_accounts_str)
        
        # Update additional profile information
        update_field_if_different('username', safe_get_string(new_profile_data, 'username'))
        update_field_if_different('location', safe_get_string(new_profile_data, 'location'))
        update_field_if_different('country', safe_get_string(new_profile_data, 'country', 'RO'))
        update_field_if_different('age_range', safe_get_string(new_profile_data, 'age_range'))
        update_field_if_different('gender', safe_get_string(new_profile_data, 'gender'))
        
        # Update professional information
        update_field_if_different('professional_title', safe_get_string(new_profile_data, 'professional_title'))
        update_field_if_different('current_employer', safe_get_string(new_profile_data, 'current_employer'))
        update_field_if_different('work_history', safe_get_string(new_profile_data, 'work_history'))
        
        # Update education
        update_field_if_different('education', safe_get_string(new_profile_data, 'education'))
        
        # Update location details
        update_field_if_different('current_location', safe_get_string(new_profile_data, 'current_location'))
        update_field_if_different('origin_location', safe_get_string(new_profile_data, 'origin_location'))
        
        # Update personal information
        update_field_if_different('relationship_status', safe_get_string(new_profile_data, 'relationship_status'))
        update_field_if_different('languages', safe_get_string(new_profile_data, 'languages'))
        
        # Update interests
        update_field_if_different('interests', safe_get_string(new_profile_data, 'interests'))
        update_field_if_different('interests_detailed', safe_get_string(new_profile_data, 'interests_detailed'))
        update_field_if_different('topics_discussed', safe_get_string(new_profile_data, 'topics_discussed'))
        
        # Update social media links
        update_field_if_different('social_media_links', safe_get_string(new_profile_data, 'social_media_links'))
        
        # Update religious information
        update_field_if_different('religious_info', safe_get_string(new_profile_data, 'religious_info'))
        update_field_if_different('church_position', safe_get_string(new_profile_data, 'church_position'))
        update_field_if_different('church_affiliation', safe_get_string(new_profile_data, 'church_affiliation'))
        
        # Update enhanced fields - Family, events, and additional info
        update_field_if_different('family_members', safe_get_string(new_profile_data, 'family_members'))
        update_field_if_different('life_events', safe_get_string(new_profile_data, 'life_events'))
        update_field_if_different('about_section', safe_get_string(new_profile_data, 'about_section'))
        update_field_if_different('favorite_quotes', safe_get_string(new_profile_data, 'favorite_quotes'))
        update_field_if_different('other_names', safe_get_string(new_profile_data, 'other_names'))
        
        # Update contact details
        update_field_if_different('contact_email', safe_get_string(new_profile_data, 'contact_email'))
        update_field_if_different('contact_phone', safe_get_string(new_profile_data, 'contact_phone'))
        update_field_if_different('birthday', safe_get_string(new_profile_data, 'birthday'))
        update_field_if_different('political_views', safe_get_string(new_profile_data, 'political_views'))
        
        # Update social metrics
        followers_count = new_profile_data.get('followers_count', 0)
        if isinstance(followers_count, (int, str)) and str(followers_count).isdigit():
            update_field_if_different('followers_count', int(followers_count))
        
        friends_count = new_profile_data.get('friends_count', 0)
        if isinstance(friends_count, (int, str)) and str(friends_count).isdigit():
            update_field_if_different('friends_count', int(friends_count))
        
        posts_count = new_profile_data.get('posts_count', 0)
        if isinstance(posts_count, (int, str)) and str(posts_count).isdigit():
            update_field_if_different('posts_count', int(posts_count))
        
        # Update status fields
        is_verified = new_profile_data.get('is_verified', False)
        if isinstance(is_verified, bool):
            update_field_if_different('is_verified', is_verified)
        
        is_public = new_profile_data.get('is_public', True)
        if isinstance(is_public, bool):
            update_field_if_different('is_public', is_public)
        
        update_field_if_different('scraping_method', safe_get_string(new_profile_data, 'scraping_method', 'manual'))
        
        # Update timestamps
        last_scraped_str = new_profile_data.get('last_scraped_at')
        if last_scraped_str:
            try:
                from datetime import datetime
                if isinstance(last_scraped_str, str):
                    # Try to parse ISO format
                    last_scraped = datetime.fromisoformat(last_scraped_str.replace('Z', '+00:00'))
                    update_field_if_different('last_scraped_at', last_scraped)
            except ValueError:
                # If parsing fails, use current time
                update_field_if_different('last_scraped_at', datetime.now())
        
        # Update the updated_at timestamp if any changes were made
        if updated:
            from datetime import datetime
            existing_profile.updated_at = datetime.now()
            db.session.commit()
            print(f"   ✅ Successfully updated profile in database with {sum(1 for k, v in new_profile_data.items() if v)} fields")
        else:
            print(f"   ℹ️  No changes detected - profile already up to date")
        
        return {'updated': updated}
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating Facebook profile: {e}")
        return {'updated': False, 'error': str(e)}

def get_scraping_config():
    """Get scraping configuration from database with fallback strategy"""
    try:
        # Import here to avoid circular imports
        from app.models.models import NewsSource
        import unicodedata
        
        def normalize_source_name(name):
            """Normalize source name by removing diacritics and converting to lowercase"""
            # Remove diacritics
            normalized = unicodedata.normalize('NFD', name)
            ascii_name = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
            return ascii_name.lower()
        
        sources_config = {}
        
        # Try to get from database first
        try:
            sources = NewsSource.query.filter_by(scraping_enabled=True).all()
            
            for source in sources:
                # Normalize source name to handle diacritics
                normalized_name = normalize_source_name(source.name)
                sources_config[normalized_name] = {
                    'frequency_minutes': source.scraping_frequency,
                    'enabled': source.scraping_enabled,
                    'source_id': source.id,
                    'original_name': source.name  # Keep original for logging
                }
            
            if sources_config:
                print("📊 Using database configuration for scraping")
                return sources_config
                
        except Exception as db_error:
            print(f"⚠️  Database config unavailable: {db_error}")
        
        # Fallback to hardcoded values if DB not available
        print("🔧 Using fallback configuration")
        sources_config = {
            'biziday': {'frequency_minutes': 120, 'enabled': True, 'source_id': None, 'original_name': 'Biziday'},
            'adevarul': {'frequency_minutes': 120, 'enabled': True, 'source_id': None, 'original_name': 'Adevarul'},
            'facebook': {'frequency_minutes': 180, 'enabled': True, 'source_id': None, 'original_name': 'Facebook'}
        }
        
        return sources_config
        
    except Exception as e:
        print(f"❌ Error getting scraping config: {e}")
        # Ultimate fallback
        return {
            'biziday': {'frequency_minutes': 120, 'enabled': True, 'source_id': None, 'original_name': 'Biziday'},
            'adevarul': {'frequency_minutes': 120, 'enabled': True, 'source_id': None, 'original_name': 'Adevarul'},
            'facebook': {'frequency_minutes': 180, 'enabled': True, 'source_id': None, 'original_name': 'Facebook'}
        }

def start_scheduler_in_context(app):
    """Start the background scheduler with progressive enhancement strategy"""
    def run_with_context(func):
        """Wrapper to run scheduler jobs with application context"""
        def wrapper():
            try:
                with app.app_context():
                    return func()
            except Exception as e:
                print(f"💥 Scheduler job failed: {e}")
                import traceback
                traceback.print_exc()
        return wrapper
    
    scheduler = BackgroundScheduler()
    
    # Get configuration with fallback strategy
    with app.app_context():
        config = get_scraping_config()
        
        # 🧪 CONFIGURARE TESTARE/PRODUCȚIE
        testing_mode = os.getenv('SCRAPER_TESTING_MODE', 'false').lower() == 'true'
        
        # Define intervals based on mode
        if testing_mode:
            print("🧪 TESTING MODE ACTIVE: Using 2-minute intervals for all scrapers")
            test_interval_minutes = 2
        else:
            print("🚀 PRODUCTION MODE ACTIVE: Using database/fallback intervals")
        
        # Add jobs based on configuration (database or fallback)
        jobs_added = 0
        for source_name, source_config in config.items():
            if not source_config['enabled']:
                print(f"⏸️  Skipping {source_name} - disabled")
                continue
            
            # Use testing interval or production interval
            if testing_mode:
                interval_minutes = test_interval_minutes
                mode_label = "TESTING"
            else:
                interval_minutes = source_config['frequency_minutes']
                mode_label = "PRODUCTION"
            
            # Log configuration source
            original_name = source_config.get('original_name', source_name)
            config_source = "database" if source_config['source_id'] else "fallback"
            print(f"📅 {original_name}: {interval_minutes}min ({mode_label} - {config_source})")
            
            if source_name == 'biziday':
                scheduler.add_job(
                    run_with_context(run_biziday_scraper), 
                    'interval', 
                    minutes=interval_minutes, 
                    id='biziday_scraper'
                )
                jobs_added += 1
            elif source_name == 'adevarul':
                scheduler.add_job(
                    run_with_context(run_adevarul_scraper), 
                    'interval', 
                    minutes=interval_minutes, 
                    id='adevarul_scraper'
                )
                jobs_added += 1
            elif source_name == 'facebook':
                # MODIFICARE: Facebook scraper nu se programează automat
                # Va fi executat doar la cererea utilizatorului prin interfața web
                print(f"📋 {original_name}: Manual execution only (not scheduled automatically)")
                # Nu adăugăm job automat pentru Facebook
                pass
    
    # Add initial jobs with proper datetime calculation (exclude Facebook - manual only)
    print(f"⏰ Scheduling initial runs in 30-40 seconds...")
    now = datetime.now()
    
    # Schedule initial runs with proper datetime handling (Facebook excluded)
    scheduler.add_job(
        run_with_context(run_biziday_scraper), 
        'date', 
        run_date=now + timedelta(seconds=30),
        id='biziday_initial'
    )
    scheduler.add_job(
        run_with_context(run_adevarul_scraper), 
        'date', 
        run_date=now + timedelta(seconds=40),
        id='adevarul_initial'
    )
    # MODIFICARE: Facebook nu se programează automat - doar la cererea utilizatorului
    
    scheduler.start()
    
    # Final status message
    print(f"🔄 Scheduler started with {jobs_added} recurring jobs + 2 initial jobs")
    print(f"📋 Facebook scraper: Manual execution only (available through web interface)")
    if testing_mode:
        print("⚠️  TESTING MODE: Change SCRAPER_TESTING_MODE='false' for production")
        print("   Current: 2 minutes | Production: 2 hours")
    else:
        print("✅ PRODUCTION MODE: Scrapers using configured intervals")
        print("   Change SCRAPER_TESTING_MODE='true' for testing (2 minutes)")
    
    return scheduler

# Keep the old function for backwards compatibility
def start_scheduler():
    """Legacy function - use start_scheduler_in_context instead"""
    print("⚠️  Warning: start_scheduler called without application context")
    print("   Use start_scheduler_in_context(app) instead")
    return None