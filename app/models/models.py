from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import pytz

db = SQLAlchemy()

# Configurare timezone România
ROMANIA_TZ = pytz.timezone('Europe/Bucharest')

def ro_now():
    """Returnează timestamp-ul curent la ora României"""
    return datetime.now(ROMANIA_TZ)

def ro_datetime():
    """Wrapper pentru datetime cu timezone România pentru SQLAlchemy"""
    return datetime.now(ROMANIA_TZ)

class NewsArticle(db.Model):
    __tablename__ = 'news_articles'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)  # Măresc size-ul pentru titluri lungi
    summary = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=True)  # Full article content
    link = db.Column(db.String(1000), nullable=False, unique=True)  # Măresc pentru URL-uri lungi
    source = db.Column(db.String(100), nullable=False)
    
    # Timestamp-uri standardizate cu timezone România
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)  # Data publicării pe site
    created_at = db.Column(db.DateTime(timezone=True), default=ro_datetime)  # Data salvării în BD
    updated_at = db.Column(db.DateTime(timezone=True), default=ro_datetime, onupdate=ro_datetime)  # Data actualizării

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'summary': self.summary,
            'link': self.link,
            'source': self.source,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
            # Note: 'content' field is intentionally excluded from API responses
        }

    def __repr__(self):
        return f'<NewsArticle {self.title}>'

class FacebookUserProfile(db.Model):
    __tablename__ = 'facebook_user_profiles'
    
    # Basic information (existing fields)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    connected_accounts = db.Column(db.Text, nullable=True)
    profile_url = db.Column(db.String(1000), nullable=True, unique=True)
    
    # Additional profile information
    username = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    country = db.Column(db.String(10), nullable=True, default='RO')
    age_range = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    
    # Professional information
    professional_title = db.Column(db.String(255), nullable=True)
    current_employer = db.Column(db.String(255), nullable=True)
    work_history = db.Column(db.Text, nullable=True)  # JSON format
    
    # Education
    education = db.Column(db.Text, nullable=True)  # JSON format
    
    # Location details
    current_location = db.Column(db.String(255), nullable=True)
    origin_location = db.Column(db.String(255), nullable=True)
    
    # Personal information
    relationship_status = db.Column(db.String(50), nullable=True)
    languages = db.Column(db.Text, nullable=True)  # JSON format
    
    # Interests and activities
    interests = db.Column(db.Text, nullable=True)
    interests_detailed = db.Column(db.Text, nullable=True)  # JSON format
    topics_discussed = db.Column(db.Text, nullable=True)
    
    # Social media and external links
    social_media_links = db.Column(db.Text, nullable=True)  # JSON format
    
    # Religious information
    religious_info = db.Column(db.Text, nullable=True)
    church_position = db.Column(db.String(255), nullable=True)
    church_affiliation = db.Column(db.String(255), nullable=True)
    
    # Enhanced fields - Family, events, and additional info
    family_members = db.Column(db.Text, nullable=True)  # JSON array with family relationships
    life_events = db.Column(db.Text, nullable=True)  # JSON array with life events
    about_section = db.Column(db.Text, nullable=True)  # Extended about section
    favorite_quotes = db.Column(db.Text, nullable=True)  # Favorite quotes
    other_names = db.Column(db.Text, nullable=True)  # Other names or nicknames
    
    # Contact details
    contact_email = db.Column(db.String(255), nullable=True)  # Public email address
    contact_phone = db.Column(db.String(100), nullable=True)  # Public phone number
    birthday = db.Column(db.String(50), nullable=True)  # Birthday if public
    political_views = db.Column(db.Text, nullable=True)  # Political views
    
    # Social metrics
    followers_count = db.Column(db.Integer, nullable=True, default=0)
    friends_count = db.Column(db.Integer, nullable=True, default=0)
    posts_count = db.Column(db.Integer, nullable=True, default=0)
    avg_engagement_rate = db.Column(db.Numeric(5, 2), nullable=True, default=0.00)
    last_post_date = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Status and quality
    is_verified = db.Column(db.Boolean, nullable=True, default=False)
    is_public = db.Column(db.Boolean, nullable=True, default=True)
    scraping_method = db.Column(db.String(50), nullable=True, default='automated')
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=ro_datetime)
    updated_at = db.Column(db.DateTime(timezone=True), default=ro_datetime, onupdate=ro_datetime)
    last_scraped_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        """Convert model to dictionary with all fields"""
        import json
        
        # Helper function to parse JSON fields safely
        def safe_json_parse(field_value):
            if field_value is None:
                return None
            if isinstance(field_value, str):
                try:
                    return json.loads(field_value)
                except json.JSONDecodeError:
                    return field_value
            return field_value
        
        return {
            'id': self.id,
            'name': self.name,
            'bio': self.bio,
            'connected_accounts': self.connected_accounts.split(',') if self.connected_accounts else [],
            'profile_url': self.profile_url,
            
            # Additional profile info
            'username': self.username,
            'location': self.location,
            'country': self.country,
            'age_range': self.age_range,
            'gender': self.gender,
            
            # Professional info
            'professional_title': self.professional_title,
            'current_employer': self.current_employer,
            'work_history': safe_json_parse(self.work_history),
            
            # Education
            'education': safe_json_parse(self.education),
            
            # Location details
            'current_location': self.current_location,
            'origin_location': self.origin_location,
            
            # Personal info
            'relationship_status': self.relationship_status,
            'languages': safe_json_parse(self.languages),
            
            # Interests
            'interests': self.interests,
            'interests_detailed': safe_json_parse(self.interests_detailed),
            'topics_discussed': self.topics_discussed,
            
            # Social links
            'social_media_links': safe_json_parse(self.social_media_links),
            
            # Religious info
            'religious_info': self.religious_info,
            'church_position': self.church_position,
            'church_affiliation': self.church_affiliation,
            
            # Enhanced fields - Family, events, and additional info
            'family_members': safe_json_parse(self.family_members),
            'life_events': safe_json_parse(self.life_events),
            'about_section': self.about_section,
            'favorite_quotes': self.favorite_quotes,
            'other_names': self.other_names,
            
            # Contact details
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'birthday': self.birthday,
            'political_views': self.political_views,
            
            # Metrics
            'followers_count': self.followers_count,
            'friends_count': self.friends_count,
            'posts_count': self.posts_count,
            'avg_engagement_rate': float(self.avg_engagement_rate) if self.avg_engagement_rate else 0.0,
            'last_post_date': self.last_post_date.isoformat() if self.last_post_date else None,
            
            # Status
            'is_verified': self.is_verified,
            'is_public': self.is_public,
            'scraping_method': self.scraping_method,
            
            # Timestamps
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_scraped_at': self.last_scraped_at.isoformat() if self.last_scraped_at else None
        }

    def __repr__(self):
        return f'<FacebookUserProfile {self.name}>'

class NewsSource(db.Model):
    __tablename__ = 'news_sources'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    base_url = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Configurare scraping
    scraping_enabled = db.Column(db.Boolean, default=True)
    scraping_frequency = db.Column(db.Integer, default=120)  # minutes
    last_scraped_at = db.Column(db.DateTime, nullable=True)
    
    # Metadata sursă
    country = db.Column(db.String(10), default='RO')
    language = db.Column(db.String(10), default='ro')
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=ro_datetime)
    updated_at = db.Column(db.DateTime(timezone=True), default=ro_datetime, onupdate=ro_datetime)
    last_scraped_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'base_url': self.base_url,
            'description': self.description,
            'scraping_enabled': self.scraping_enabled,
            'scraping_frequency': self.scraping_frequency,
            'last_scraped_at': self.last_scraped_at.isoformat() if self.last_scraped_at else None,
            'country': self.country,
            'language': self.language,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<NewsSource {self.name}>'

# Alias pentru compatibilitate
Article = NewsArticle