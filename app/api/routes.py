from flask import Blueprint, jsonify, render_template, request
from app.models.models import NewsArticle, FacebookUserProfile, db
from sqlalchemy import func, or_, desc
from datetime import datetime, timedelta

# Create the API blueprint
api = Blueprint('api', __name__)

# Production sources filter - exclude test and development sources
PRODUCTION_SOURCES = ['Adevarul', 'Biziday', 'Facebook']

def get_production_source_filter():
    """Get a SQLAlchemy filter for production sources only"""
    return NewsArticle.source.in_(PRODUCTION_SOURCES)

def filter_production_sources_only(query):
    """Apply production source filter to a query"""
    return query.filter(get_production_source_filter())

@api.route('/articles')
def get_articles():
    """Get all news articles"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        source = request.args.get('source', None)
        
        query = NewsArticle.query
        
        if source:
            query = query.filter(NewsArticle.source == source)
        
        articles = query.order_by(desc(NewsArticle.published_at)).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'articles': [article.to_dict() for article in articles.items],
            'total': articles.total,
            'pages': articles.pages,
            'current_page': page
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/facebook-profiles')
def get_facebook_profiles():
    """Get all Facebook user profiles"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        profiles = FacebookUserProfile.query.order_by(desc(FacebookUserProfile.created_at)).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'profiles': [profile.to_dict() for profile in profiles.items],
            'total': profiles.total,
            'pages': profiles.pages,
            'current_page': page
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/facebook-users')
def get_facebook_users():
    """Get all Facebook user profiles (alias for compatibility)"""
    try:
        profiles = FacebookUserProfile.query.order_by(desc(FacebookUserProfile.created_at)).all()
        
        # Return direct array for template compatibility
        result = []
        for profile in profiles:
            profile_dict = profile.to_dict()
            # Ensure connected_accounts is an array
            if isinstance(profile_dict.get('connected_accounts'), str):
                profile_dict['connected_accounts'] = [acc.strip() for acc in profile_dict['connected_accounts'].split(',') if acc.strip()]
            result.append(profile_dict)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/stats')
def get_stats():
    """Get statistics (production sources only)"""
    try:
        # Filter all queries to production sources only
        total_articles = NewsArticle.query.filter(get_production_source_filter()).count()
        total_profiles = FacebookUserProfile.query.count()
        
        # Count by source (production only)
        source_counts = db.session.query(
            NewsArticle.source,
            func.count(NewsArticle.id)
        ).filter(get_production_source_filter()).group_by(NewsArticle.source).all()
        
        # Count articles in last 24h (production only)
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_articles_24h = NewsArticle.query.filter(
            NewsArticle.published_at >= last_24h,
            get_production_source_filter()
        ).count()
        
        # Get articles per source distribution (production only)
        articles_per_source = {}
        for source, count in source_counts:
            articles_per_source[source] = count
        
        # Get average content length per source (production only)
        content_lengths = db.session.query(
            NewsArticle.source,
            func.avg(
                func.array_length(
                    func.string_to_array(
                        func.regexp_replace(NewsArticle.content, r'\s+', ' ', 'g'), 
                        ' '
                    ), 
                    1
                )
            ).label('avg_words')
        ).filter(
            NewsArticle.content.isnot(None),
            NewsArticle.content != '',
            get_production_source_filter()  # Filter production sources only
        ).group_by(NewsArticle.source).all()
        
        avg_content_length = {}
        for source, avg_words in content_lengths:
            avg_content_length[source] = round(float(avg_words or 0), 1)
        
        return jsonify({
            'total_articles': total_articles,
            'total_profiles': total_profiles,
            'active_sources': len(source_counts),
            'source_distribution': dict(source_counts),
            'articles_per_source': articles_per_source,
            'recent_articles_24h': recent_articles_24h,
            'avg_content_length': avg_content_length
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@api.route('/news')
def get_news():
    """Get all news articles (alias for /articles endpoint) - for frontend compatibility"""
    try:
        source = request.args.get('source', None)
        
        query = NewsArticle.query
        
        if source:
            query = query.filter(NewsArticle.source == source)
        
        # Return all articles without any limit to show all Biziday articles
        articles = query.order_by(desc(NewsArticle.published_at)).all()
        
        # Convert to list of dictionaries for JSON response
        articles_list = []
        for article in articles:
            articles_list.append({
                'id': article.id,
                'title': article.title,
                'summary': article.summary,
                'link': article.link,
                'source': article.source,
                'timestamp': article.published_at.isoformat() if article.published_at else (article.created_at.isoformat() if article.created_at else None)
            })
        
        return jsonify(articles_list)
    except Exception as e:
        print(f"Error in /api/news endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@api.route('/chart-data')
def get_chart_data():
    """Get chart data for specific date range and sources with optional source and hour filtering"""
    try:
        # Get parameters from request
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        start_hour = request.args.get('start_hour', type=int)  # Optional hour filtering
        end_hour = request.args.get('end_hour', type=int)      # Optional hour filtering
        selected_sources = request.args.getlist('sources')  # Support multiple sources
        show_all_time = request.args.get('show_all_time', 'false').lower() == 'true'
        
        # Handle "Show All Time" mode
        if show_all_time:
            # Get the earliest and latest dates from database
            earliest = db.session.query(func.min(NewsArticle.published_at)).scalar()
            latest = db.session.query(func.max(NewsArticle.published_at)).scalar()
            
            if earliest and latest:
                start_dt = earliest.replace(hour=0, minute=0, second=0)
                end_dt = latest.replace(hour=23, minute=59, second=59)
            else:
                # Fallback to current date if no articles
                start_dt = datetime.now().replace(hour=0, minute=0, second=0)
                end_dt = start_dt.replace(hour=23, minute=59, second=59)
        else:
            # Default to current date if no parameters provided
            if not start_date:
                start_date = datetime.now().strftime('%Y-%m-%d')
            if not end_date:
                end_date = start_date
            
            # Parse dates and set time boundaries
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Apply hour filtering if specified
        if start_hour is not None and end_hour is not None:
            # Validate hour range
            if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
                return jsonify({'error': 'Hours must be between 0 and 23'}), 400
            
            # For single day with hour filtering, adjust the time boundaries
            if start_dt.date() == end_dt.date():
                start_dt = start_dt.replace(hour=start_hour)
                end_dt = end_dt.replace(hour=end_hour, minute=59, second=59)
            # For multi-day ranges, we'll filter in the query instead
        
        # Get available sources in the database (production only)
        all_sources = db.session.query(NewsArticle.source).filter(get_production_source_filter()).distinct().all()
        all_source_names = [source[0] for source in all_sources]
        
        # Filter sources if specific ones are requested (ensure they're production sources)
        if selected_sources:
            # Validate that requested sources exist and are production sources
            source_names = [s for s in selected_sources if s in all_source_names and s in PRODUCTION_SOURCES]
            if not source_names:
                return jsonify({'error': 'No valid production sources specified'}), 400
        else:
            # Use all production sources if none specified
            source_names = all_source_names
        
        # Query articles grouped by hour and source using published_at field (production sources only)
        query = db.session.query(
            func.date_trunc('hour', NewsArticle.published_at).label('hour'),
            NewsArticle.source,
            func.count(NewsArticle.id).label('count')
        ).filter(
            NewsArticle.published_at >= start_dt,
            NewsArticle.published_at <= end_dt,
            NewsArticle.published_at.isnot(None),
            get_production_source_filter()  # Filter production sources only
        )
        
        # Add source filtering if specific sources are requested
        if source_names:
            query = query.filter(NewsArticle.source.in_(source_names))
        
        # Add hour filtering for multi-day ranges if specified
        if start_hour is not None and end_hour is not None and start_dt.date() != end_dt.date():
            query = query.filter(
                func.extract('hour', NewsArticle.published_at) >= start_hour,
                func.extract('hour', NewsArticle.published_at) <= end_hour
            )
        
        articles_per_hour_source_raw = query.group_by(
            func.date_trunc('hour', NewsArticle.published_at),
            NewsArticle.source
        ).order_by('hour', NewsArticle.source).all()
        
        # Create nested dictionary: {hour: {source: count}}
        hour_source_counts = {}
        for hour_obj, source, count in articles_per_hour_source_raw:
            if hour_obj:
                hour_str = hour_obj.strftime('%Y-%m-%d %H:00:00')
                if hour_str not in hour_source_counts:
                    hour_source_counts[hour_str] = {}
                hour_source_counts[hour_str][source] = count
        
        # Determine granularity based on date range
        date_diff = (end_dt.date() - start_dt.date()).days
        
        # Improved granularity logic:
        # - Single day (0 days): Hourly granularity (24 points)
        # - 2-7 days: Enhanced granularity (every 2 hours with better aggregation)  
        # - 8-30 days: Daily granularity with all days shown
        # - 31+ days: Weekly granularity
        
        if date_diff == 0:
            # Single day - hourly granularity
            use_granularity = 'hourly'
            use_daily = False
        elif date_diff <= 7:
            # Up to 7 days - enhanced granularity with improved data aggregation
            use_granularity = 'hourly_detailed'
            use_daily = False
        elif date_diff <= 30:
            # Up to 30 days - daily granularity (show all days)
            use_granularity = 'daily'
            use_daily = True
        else:
            # More than 30 days - weekly granularity
            use_granularity = 'weekly'
            use_daily = True
        
        if use_granularity == 'hourly':
            # Standard hourly granularity for single day
            labels = []
            datasets = {}
            
            # Initialize datasets for each source
            for source in source_names:
                datasets[source] = []
            
            # Generate labels and data for each hour
            for hour in range(24):
                hour_dt = start_dt.replace(hour=hour, minute=0, second=0)
                hour_key = hour_dt.strftime('%Y-%m-%d %H:00:00')
                hour_label = hour_dt.strftime('%H:00')
                
                labels.append(hour_label)
                
                for source in source_names:
                    count = hour_source_counts.get(hour_key, {}).get(source, 0)
                    datasets[source].append(count)
                    
        elif use_granularity == 'hourly_detailed':
            # Enhanced hourly for 2-7 days - show every 2 hours with better data aggregation
            labels = []
            datasets = {}
            
            # Initialize datasets for each source
            for source in source_names:
                datasets[source] = []
            
            # Generate labels and data for every 2 hours across the date range
            current_dt = start_dt.replace(hour=0, minute=0, second=0)
            while current_dt <= end_dt:
                if current_dt.hour % 2 == 0:  # Show every 2 hours (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)
                    hour_key = current_dt.strftime('%Y-%m-%d %H:00:00')
                    if current_dt.date() == start_dt.date() and current_dt.date() == end_dt.date():
                        # Single day range
                        hour_label = current_dt.strftime('%H:00')
                    else:
                        # Multi-day range - show day and hour for better context
                        hour_label = current_dt.strftime('%m/%d %H:00')
                    
                    labels.append(hour_label)
                    
                    # For each source, sum the count for this 2-hour period with improved aggregation
                    for source in source_names:
                        # Sum current hour + next hour for more comprehensive data
                        count = 0
                        for h_offset in [0, 1]:  # Current hour and next hour
                            check_dt = current_dt + timedelta(hours=h_offset)
                            if check_dt <= end_dt:
                                check_key = check_dt.strftime('%Y-%m-%d %H:00:00')
                                count += hour_source_counts.get(check_key, {}).get(source, 0)
                        datasets[source].append(count)
                
                current_dt += timedelta(hours=1)
                
        elif use_granularity == 'weekly':
            # Weekly granularity for longer ranges
            labels = []
            datasets = {}
            
            # Initialize datasets for each source
            for source in source_names:
                datasets[source] = []
            
            # Generate labels and data for each week
            current_date = start_dt.replace(hour=0, minute=0, second=0)
            # Adjust to start of week (Monday)
            current_date = current_date - timedelta(days=current_date.weekday())
            
            while current_date <= end_dt:
                week_end = min(current_date + timedelta(days=6), end_dt)
                week_label = f"{current_date.strftime('%m/%d')}-{week_end.strftime('%m/%d')}"
                labels.append(week_label)
                
                # Sum up all articles in this week for each source
                for source in source_names:
                    weekly_count = 0
                    week_dt = current_date
                    while week_dt <= week_end and week_dt <= end_dt:
                        for hour in range(24):
                            hour_dt = week_dt + timedelta(hours=hour)
                            if hour_dt <= end_dt:
                                hour_key = hour_dt.strftime('%Y-%m-%d %H:00:00')
                                weekly_count += hour_source_counts.get(hour_key, {}).get(source, 0)
                        week_dt += timedelta(days=1)
                    datasets[source].append(weekly_count)
                
                current_date += timedelta(weeks=1)
        
        else:  # use_granularity == 'daily'
            # Daily granularity for multi-day ranges
            labels = []
            datasets = {}
            
            # Initialize datasets for each source
            for source in source_names:
                datasets[source] = []
            
            # Generate labels and data for each day
            current_date = start_dt.replace(hour=0, minute=0, second=0)
            while current_date <= end_dt:
                date_str = current_date.strftime('%Y-%m-%d')
                labels.append(current_date.strftime('%m/%d'))
                
                # Sum up hourly counts for each source for this day
                for source in source_names:
                    daily_count = 0
                    for hour in range(24):
                        hour_dt = current_date + timedelta(hours=hour)
                        hour_key = hour_dt.strftime('%Y-%m-%d %H:00:00')
                        daily_count += hour_source_counts.get(hour_key, {}).get(source, 0)
                    datasets[source].append(daily_count)
                
                current_date += timedelta(days=1)
        
        # Convert datasets to Chart.js format
        chart_datasets = []
        colors = [
            'rgba(255, 99, 132, 0.8)',   # Red
            'rgba(54, 162, 235, 0.8)',   # Blue  
            'rgba(255, 205, 86, 0.8)',   # Yellow
            'rgba(75, 192, 192, 0.8)',   # Teal
            'rgba(153, 102, 255, 0.8)',  # Purple
            'rgba(255, 159, 64, 0.8)'    # Orange
        ]
        
        for i, (source, data) in enumerate(datasets.items()):
            chart_datasets.append({
                'label': source,
                'data': data,
                'backgroundColor': colors[i % len(colors)],
                'borderColor': colors[i % len(colors)].replace('0.8', '1'),
                'borderWidth': 2,
                'fill': False,
                'tension': 0.1
            })
        
        return jsonify({
            'labels': labels,
            'datasets': chart_datasets,
            'granularity': use_granularity,
            'date_range': {
                'start': start_dt.strftime('%Y-%m-%d') if not show_all_time else start_dt.strftime('%Y-%m-%d'),
                'end': end_dt.strftime('%Y-%m-%d') if not show_all_time else end_dt.strftime('%Y-%m-%d')
            },
            'hour_range': {
                'start': start_hour,
                'end': end_hour
            } if start_hour is not None and end_hour is not None else None,
            'show_all_time': show_all_time,
            'available_sources': all_source_names,
            'selected_sources': source_names,
            'total_articles': sum(sum(dataset['data']) for dataset in chart_datasets)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/sources')
def get_sources():
    """Get all available news sources (production only)"""
    try:
        # Filter to production sources only
        sources = db.session.query(NewsArticle.source).filter(get_production_source_filter()).distinct().all()
        source_names = [source[0] for source in sources]
        
        # Get article count per source for additional context (production only)
        source_counts = db.session.query(
            NewsArticle.source,
            func.count(NewsArticle.id).label('count')
        ).filter(get_production_source_filter()).group_by(NewsArticle.source).all()
        
        source_info = {}
        for source, count in source_counts:
            source_info[source] = {
                'name': source,
                'article_count': count
            }
        
        return jsonify({
            'sources': source_names,
            'source_info': source_info
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/hourly-stats')
def get_hourly_stats():
    """Get hourly statistics per source (production sources only)"""
    try:
        # Get parameters
        date_filter = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Parse date
        try:
            target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Query articles grouped by hour and source for the target date (production sources only)
        hourly_stats = db.session.query(
            func.extract('hour', NewsArticle.published_at).label('hour'),
            NewsArticle.source,
            func.count(NewsArticle.id).label('article_count')
        ).filter(
            func.date(NewsArticle.published_at) == target_date,
            NewsArticle.published_at.isnot(None),
            get_production_source_filter()  # Filter production sources only
        ).group_by(
            func.extract('hour', NewsArticle.published_at),
            NewsArticle.source
        ).order_by('hour', NewsArticle.source).all()
        
        # Format data for response
        hourly_data = {}
        sources = set()
        
        for hour, source, count in hourly_stats:
            hour_key = f"{int(hour):02d}:00"
            if hour_key not in hourly_data:
                hourly_data[hour_key] = {}
            hourly_data[hour_key][source] = count
            sources.add(source)
        
        # Fill missing hours with zeros
        complete_hourly_data = {}
        for hour in range(24):
            hour_key = f"{hour:02d}:00"
            complete_hourly_data[hour_key] = {}
            for source in sources:
                complete_hourly_data[hour_key][source] = hourly_data.get(hour_key, {}).get(source, 0)
        
        return jsonify({
            'date': date_filter,
            'hourly_data': complete_hourly_data,
            'sources': list(sources),
            'total_hours': 24
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/content-stats')
def get_content_stats():
    """Get content length statistics per source (production sources only)"""
    try:
        # Query content statistics per source (production sources only)
        content_stats = db.session.query(
            NewsArticle.source,
            func.count(NewsArticle.id).label('total_articles'),
            func.avg(
                func.array_length(
                    func.string_to_array(
                        func.regexp_replace(NewsArticle.content, r'\s+', ' ', 'g'), 
                        ' '
                    ), 
                    1
                )
            ).label('avg_words'),
            func.min(
                func.array_length(
                    func.string_to_array(
                        func.regexp_replace(NewsArticle.content, r'\s+', ' ', 'g'), 
                        ' '
                    ), 
                    1
                )
            ).label('min_words'),
            func.max(
                func.array_length(
                    func.string_to_array(
                        func.regexp_replace(NewsArticle.content, r'\s+', ' ', 'g'), 
                        ' '
                    ), 
                    1
                )
            ).label('max_words'),
            func.avg(func.length(NewsArticle.content)).label('avg_characters')
        ).filter(
            NewsArticle.content.isnot(None),
            NewsArticle.content != '',
            get_production_source_filter()  # Filter production sources only
        ).group_by(NewsArticle.source).all()
        
        # Format response
        stats_data = {}
        for source, total, avg_words, min_words, max_words, avg_chars in content_stats:
            stats_data[source] = {
                'total_articles': total,
                'avg_words': round(float(avg_words or 0), 1),
                'min_words': int(min_words or 0),
                'max_words': int(max_words or 0),
                'avg_characters': round(float(avg_chars or 0), 1)
            }
        
        return jsonify({
            'content_stats': stats_data,
            'sources': list(stats_data.keys())
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

main_bp = Blueprint('main', __name__)

# Template Routes
@main_bp.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@main_bp.route('/news')
def news():
    """News page"""
    # Get all news articles - no limit to show all sources properly
    articles = NewsArticle.query.order_by(NewsArticle.published_at.desc()).all()
    
    # Also get Facebook profiles and convert them to article-like format for display
    facebook_profiles = FacebookUserProfile.query.order_by(FacebookUserProfile.created_at.desc()).limit(20).all()
    
    # Convert Facebook profiles to article-like objects for unified display
    facebook_articles = []
    for profile in facebook_profiles:
        facebook_article = type('FacebookArticle', (), {
            'id': f'fb_{profile.id}',
            'title': f'Facebook Profile: {profile.name}',
            'summary': profile.bio or 'No bio available',
            'source': 'Facebook',
            'timestamp': profile.created_at,
            'link': profile.profile_url or '#',
            'is_facebook_profile': True
        })()
        facebook_articles.append(facebook_article)
    
    # Combine all articles
    all_articles = list(articles) + facebook_articles
    
    # Sort by published_at (with fallback to created_at)
    all_articles.sort(key=lambda x: (x.published_at if hasattr(x, 'published_at') and x.published_at else x.timestamp) or datetime.min, reverse=True)
    
    return render_template('news.html', articles=all_articles)

@main_bp.route('/stats')
def stats():
    """Statistics page with date range support"""
    total_articles = NewsArticle.query.count()
    
    # Get articles per source
    articles_per_source = NewsArticle.query.with_entities(
        NewsArticle.source, func.count(NewsArticle.id)
    ).group_by(NewsArticle.source).all()
    
    # Default to current date for initial load
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Calculate average article length
    avg_length = 150
    try:
        articles_with_summary = NewsArticle.query.filter(
            NewsArticle.summary.isnot(None)
        ).all()
        if articles_with_summary:
            total_length = sum(len(article.summary.split()) for article in articles_with_summary)
            avg_length = int(total_length / len(articles_with_summary))
    except:
        pass
    
    return render_template('stats.html', 
                         total_articles=total_articles,
                         active_sources=len(articles_per_source),
                         average_length=avg_length,
                         current_date=current_date)

@main_bp.route('/debug')
def debug():
    """Debug page to check API data"""
    try:
        # Get ALL articles like the frontend would
        articles = NewsArticle.query.order_by(desc(NewsArticle.published_at)).all()
        
        # Convert to list of dictionaries
        articles_list = []
        for article in articles:
            articles_list.append({
                'id': article.id,
                'title': article.title,
                'summary': article.summary,
                'link': article.link,
                'source': article.source,
                'timestamp': article.published_at.isoformat() if article.published_at else (article.created_at.isoformat() if article.created_at else None)
            })
        
        # Count by source
        from collections import Counter
        source_counts = Counter([a['source'] for a in articles_list])
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>API Debug</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .article {{ border: 1px solid #ccc; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                .source-biziday {{ background-color: #e3f2fd; }}
                .source-adevarul {{ background-color: #fce4ec; }}
                .source-facebook {{ background-color: #e8f5e8; }}
                .stats {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <h1>🔍 API Debug Information</h1>
            
            <div class="stats">
                <h2>📊 Statistics</h2>
                <p><strong>Total articles:</strong> {len(articles_list)}</p>
                <p><strong>Articles by source:</strong></p>
                <ul>
        """
        
        for source, count in source_counts.items():
            html += f"<li>{source}: {count}</li>"
        
        html += """
                </ul>
            </div>
            
            <h2>📄 First 10 Articles</h2>
        """
        
        for i, article in enumerate(articles_list[:10], 1):
            source_class = f"source-{article['source'].lower()}" if article['source'] else ""
            html += f"""
            <div class="article {source_class}">
                <h3>{i}. [{article['source']}] {article['title']}</h3>
                <p><strong>Summary:</strong> {article['summary'][:200] if article['summary'] else 'No summary'}...</p>
                <p><strong>Timestamp:</strong> {article['timestamp']}</p>
                <p><strong>Link:</strong> <a href="{article['link']}" target="_blank">{article['link']}</a></p>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>"

@api.route('/scrape-facebook', methods=['POST'])
def scrape_facebook():
    """Manual Facebook profile scraping endpoint"""
    try:
        # Get profile input from request
        data = request.get_json()
        if not data or 'profile_input' not in data:
            return jsonify({'error': 'Missing profile_input in request body'}), 400
        
        profile_input = data['profile_input'].strip()
        
        if not profile_input:
            return jsonify({'error': 'Profile input cannot be empty'}), 400
        
        # Import the Facebook scraper function
        from app.scheduler.tasks import run_facebook_scraper
        
        # Run the scraper
        result = run_facebook_scraper(profile_input)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500