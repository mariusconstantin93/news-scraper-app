#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import logging

# Configure clean logging FIRST - before any imports
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.orm').setLevel(logging.ERROR)

# Set UTF-8 encoding for Windows
if os.name == 'nt':  # Windows
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from app import create_app
import atexit
import signal

# Global scheduler instance
scheduler = None

# Facebook Selenium session
facebook_session_ready = False

def init_facebook_session_async():
    """Initialize Facebook Selenium session asynchronously"""
    global facebook_session_ready
    
    def facebook_login_worker():
        try:
            print("🔐 Starting Facebook Selenium session initialization (background)...")
            
            # Try to import Facebook config
            try:
                from facebook_config import FACEBOOK_EMAIL, FACEBOOK_PASSWORD, HEADLESS_MODE
                print("📧 Facebook credentials loaded from config")
            except ImportError:
                print("⚠️  Facebook config not found. Please:")
                print("   1. Copy facebook_config_template.py to facebook_config.py")
                print("   2. Add your Facebook email and password to facebook_config.py")
                print("   Facebook scraping will be disabled until configured.")
                return
            
            # Import selenium manager
            from app.selenium_facebook_manager import initialize_facebook_session
            
            # Initialize session with headless mode enabled for performance
            try:
                print(f"💡 Using Facebook credentials for: {FACEBOOK_EMAIL}")
                print(f"💡 Headless mode: Enabled (for performance)")
                
                # Force headless mode for background initialization
                if initialize_facebook_session(FACEBOOK_EMAIL, FACEBOOK_PASSWORD, headless=True):
                    global facebook_session_ready
                    facebook_session_ready = True
                    print("✅ Facebook Selenium session initialized successfully in background!")
                    print("🌐 Ready to scrape Facebook profiles with full About section access")
                else:
                    print("❌ Facebook login failed. Facebook scraping will use fallback HTTP method")
                    print("💡 You can retry by restarting the application")
            except Exception as login_error:
                print(f"❌ Facebook session initialization failed: {login_error}")
                print("� Facebook scraping will use fallback HTTP method")
                
        except Exception as e:
            print(f"❌ Error in Facebook session worker: {e}")
            print("📝 Facebook scraping will use fallback HTTP method")
    
    # Start Facebook login in background thread
    import threading
    facebook_thread = threading.Thread(target=facebook_login_worker, name="FacebookLogin")
    facebook_thread.daemon = True  # Make thread daemon so it doesn't block shutdown
    facebook_thread.start()
    print("🚀 Server starting immediately, Facebook login initializing in background...")

def init_scheduler_delayed(app):
    """Initialize scheduler with proper application context"""
    global scheduler
    
    def start_scheduler_with_context():
        try:
            # 🧪 CONFIGURARE TESTARE/PRODUCȚIE
            # Pentru TESTARE (2 minute): 'true'
            # Pentru PRODUCȚIE (2 ore): 'false'
            import os
            os.environ['SCRAPER_TESTING_MODE'] = 'true'  # 🔧 MODIFICĂ AICI!
            
            # Push application context for the scheduler
            with app.app_context():
                from app.scheduler.tasks import start_scheduler_in_context
                global scheduler
                scheduler = start_scheduler_in_context(app)
                print("✅ Scheduler started successfully with database configuration!")
                
                # Show current mode clearly
                testing_mode = os.getenv('SCRAPER_TESTING_MODE', 'false').lower() == 'true'
                if testing_mode:
                    print("🧪 TESTING MODE: Scrapers run every 2 minutes")
                    print("   Change SCRAPER_TESTING_MODE to 'false' for production (2 hours)")
                    print("⏰ Initial scrapers will run in 30-50 seconds...")
                    print("📊 Watch console for scraper execution messages!")
                else:
                    print("🚀 PRODUCTION MODE: Scrapers run every 2 hours")
                    print("   Change SCRAPER_TESTING_MODE to 'true' for testing (2 minutes)")
                    print("⏰ Initial scrapers will run in 30-50 seconds...")
                    
        except Exception as e:
            print(f"⚠️ Scheduler startup failed: {e}")
            print("📝 The app will continue without automated scraping.")
            print("   You can run scrapers manually with: python test_and_populate.py")
            import traceback
            traceback.print_exc()
    
    # MOMENTUL 0: Scheduler pornește cu întârziere de 5 secunde
    print("⏳ Preparing to start scheduler in 5 seconds...")
    import threading
    timer = threading.Timer(5.0, start_scheduler_with_context)
    timer.daemon = True  # Make thread daemon so it doesn't block shutdown
    timer.start()

def shutdown_scheduler():
    """Clean shutdown of scheduler"""
    global scheduler
    if scheduler:
        try:
            scheduler.shutdown(wait=False)
            print("🔄 Scheduler shutdown completed")
        except Exception as e:
            print(f"⚠️ Error during scheduler shutdown: {e}")

def shutdown_facebook_session():
    """Clean shutdown of Facebook Selenium session"""
    try:
        from app.selenium_facebook_manager import close_selenium_session
        close_selenium_session()
        print("🔄 Facebook Selenium session closed")
    except Exception as e:
        print(f"⚠️ Error closing Facebook session: {e}")

def cleanup_all():
    """Cleanup all resources"""
    shutdown_scheduler()
    shutdown_facebook_session()

# Create Flask app
app = create_app()

if __name__ == "__main__":
    # Register cleanup functions
    atexit.register(cleanup_all)
    signal.signal(signal.SIGTERM, lambda sig, frame: cleanup_all())
    
    print("🚀 Starting News Scraper Application...")
    print("📊 Database initialized successfully")
    
    # Initialize Facebook Selenium session asynchronously (background)
    print("\n" + "="*50)
    init_facebook_session_async()
    print("="*50)
    
    # Initialize scheduler after app is ready
    init_scheduler_delayed(app)
    
    try:
        app.run(debug=True, use_reloader=False)  # Disable reloader to prevent scheduler conflicts
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user")
        cleanup_all()
        sys.exit(0)