from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os
import logging
from logging.handlers import RotatingFileHandler

from datetime import datetime, timedelta
from sqlalchemy import desc, func

# Initialize database instance
from .models.models import db

def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Configure logging to suppress SQLAlchemy verbose output
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    from app.config import config
    app.config.from_object(config[config_name])
    
    # Import and initialize database
    from .models.models import NewsArticle, FacebookUserProfile
    db.init_app(app)
    
    # Configure application logging (keep our messages)
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/news_scraper.log', 
                                         maxBytes=10240000, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('News Scraper startup')
    else:
        # In development/debug mode, configure clean console output
        logging.basicConfig(
            level=logging.WARNING,  # Only show warnings and errors
            format='%(levelname)s: %(message)s'
        )
        app.logger.setLevel(logging.INFO)
    
    # Register blueprints
    # from app.routes.main import main as main_blueprint
    # app.register_blueprint(main_blueprint)
    
    from app.api.routes import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')
    
    # Create database tables
    with app.app_context():
        try:
            # Import models to ensure they're registered
            from app.models import models
            
            # Create all tables
            db.create_all()
            
            # Initialize default news sources if they don't exist
            from app.models.models import NewsSource
            if NewsSource.query.count() == 0:
                initialize_news_sources()
                
        except Exception as e:
            app.logger.error(f"Database initialization error: {e}")
    
    @app.route('/')
    def index():
        """Homepage"""
        return render_template('index.html')
    
    @app.route('/news')
    def news():
        """Display all news articles (combined from all sources)"""
        try:
            # Get all news articles - no limit to show all sources
            articles = NewsArticle.query.order_by(NewsArticle.published_at.desc().nulls_last(), NewsArticle.created_at.desc()).all()
            
            # Get Facebook profiles and format them as articles for unified display
            facebook_profiles = FacebookUserProfile.query.order_by(desc(FacebookUserProfile.created_at)).limit(20).all()
            
            # Combine articles and profiles for display
            combined_articles = []
            
            # Add regular articles
            for article in articles:
                article_data = {
                    'id': article.id,
                    'title': article.title,
                    'summary': article.summary,
                    'link': article.link,
                    'source': article.source,
                    'published_at': article.published_at or article.created_at,
                    'timestamp': article.published_at or article.created_at,
                    'is_facebook_profile': False
                }
                combined_articles.append(article_data)
            
            # Add Facebook profiles as articles
            for profile in facebook_profiles:
                profile_data = {
                    'id': f"fb_{profile.id}",
                    'title': f"Facebook Profile: {profile.name}",
                    'summary': profile.bio or "Facebook user profile",
                    'link': profile.profile_url or '#',
                    'source': 'Facebook',
                    'published_at': profile.created_at,
                    'timestamp': profile.created_at,
                    'is_facebook_profile': True
                }
                combined_articles.append(profile_data)
            
            # Sort by timestamp
            combined_articles.sort(key=lambda x: x['timestamp'] or datetime.min, reverse=True)
            
            print(f"Displaying {len(combined_articles)} total items ({len(articles)} articles + {len(facebook_profiles)} profiles)")
            
            return render_template('news.html', articles=combined_articles)
            
        except Exception as e:
            print(f"Error in news route: {e}")
            return render_template('news.html', articles=[])
    
    @app.route('/stats')
    def stats():
        """Statistics page"""
        try:
            # Get statistics
            total_articles = NewsArticle.query.count()
            total_profiles = FacebookUserProfile.query.count()
            
            # Count by source
            source_counts = db.session.query(
                NewsArticle.source,
                func.count(NewsArticle.id)
            ).group_by(NewsArticle.source).all()
            
            # Get articles per hour for the last 24 hours
            now = datetime.now()
            hours_ago_24 = now - timedelta(hours=24)
            
            hourly_data = []
            labels = []
            
            for i in range(24):
                hour_start = hours_ago_24 + timedelta(hours=i)
                hour_end = hour_start + timedelta(hours=1)
                
                count = NewsArticle.query.filter(
                    NewsArticle.created_at >= hour_start,
                    NewsArticle.created_at < hour_end
                ).count()
                
                hourly_data.append(count)
                labels.append(hour_start.strftime('%H:00'))
            
            # Calculate average article length
            articles_with_length = NewsArticle.query.all()
            total_words = sum(len(article.summary.split()) if article.summary else 0 
                            for article in articles_with_length)
            avg_length = total_words // max(len(articles_with_length), 1)
            
            context = {
                'total_articles': total_articles,
                'total_profiles': total_profiles,
                'active_sources': len(source_counts),
                'average_length': avg_length,
                'source_counts': dict(source_counts),
                'labels': labels,
                'articles_per_hour': hourly_data
            }
            
            return render_template('stats.html', **context)
            
        except Exception as e:
            print(f"Error in stats route: {e}")
            return render_template('stats.html', 
                                 total_articles=0, 
                                 total_profiles=0,
                                 active_sources=0,
                                 average_length=0,
                                 labels=[],
                                 articles_per_hour=[])
    
    @app.route('/facebook')
    def facebook():
        """Facebook Profile Scraper page"""
        return render_template('facebook.html')

    return app

def initialize_news_sources():
    """Initialize default news sources in database"""
    from .models.models import NewsSource
    from app.config import Config
    
    try:
        for source_key, source_config in Config.NEWS_SOURCES.items():
            existing_source = NewsSource.query.filter_by(name=source_config['name']).first()
            if not existing_source:
                news_source = NewsSource(
                    name=source_config['name'],
                    base_url=source_config['url'],
                    description=f"Automated scraper for {source_config['name']}",
                    scraping_enabled=source_config['enabled'],
                    scraping_frequency=source_config['frequency_minutes']
                )
                db.session.add(news_source)
        
        db.session.commit()
        print("✅ Default news sources initialized successfully")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error initializing news sources: {e}")