#!/usr/bin/env python3
"""
Utilități pentru extragerea și gestionarea timestamp-urilor din sursele de știri
La ora României (Europe/Bucharest)
"""

import re
import requests
from datetime import datetime, timezone
import pytz
from dateutil import parser
from bs4 import BeautifulSoup

# Timezone România
ROMANIA_TZ = pytz.timezone('Europe/Bucharest')

def get_romania_now():
    """Returnează timestamp-ul curent la ora României"""
    return datetime.now(ROMANIA_TZ)

def parse_to_romania_time(date_string, source_format=None):
    """
    Convertește un string de dată la timezone România
    
    Args:
        date_string: String cu data (ex: "2025-06-29T15:03:11Z" sau "28.06.2025 11:24")
        source_format: Format opțional pentru parsing specific
    
    Returns:
        datetime cu timezone România sau None dacă parsing-ul eșuează
    """
    if not date_string:
        return None
    
    try:
        # Încearcă să parse date-ul
        if source_format:
            # Folosește format specific
            dt = datetime.strptime(date_string.strip(), source_format)
            # Presupune că e în timezone România dacă nu e specificat altfel
            if dt.tzinfo is None:
                dt = ROMANIA_TZ.localize(dt)
        else:
            # Auto-detect format
            dt = parser.parse(date_string.strip())
            
            # Dacă nu are timezone, presupune România
            if dt.tzinfo is None:
                dt = ROMANIA_TZ.localize(dt)
            else:
                # Convertește la timezone România
                dt = dt.astimezone(ROMANIA_TZ)
        
        return dt
        
    except Exception as e:
        print(f"⚠️  Eroare parsing dată '{date_string}': {e}")
        return None

def extract_adevarul_published_date(article_url):
    """
    Extrage data publicării de pe un articol Adevarul.ro
    
    Caută pattern-uri precum:
    - "Publicat: 28.06.2025 11:24 Ultima actualizare: 28.06.2025 11:35"
    - Meta tags cu data
    - JSON-LD schema
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Strategia 1: Caută pattern "Publicat: DD.MM.YYYY HH:MM"
        published_patterns = [
            r'Publicat:\s*(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})',
            r'Publicat\s*:\s*(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})',
            r'(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})'
        ]
        
        article_text = soup.get_text()
        for pattern in published_patterns:
            match = re.search(pattern, article_text)
            if match:
                date_str = match.group(1)
                # Convertește formatul DD.MM.YYYY HH:MM
                try:
                    dt = datetime.strptime(date_str, '%d.%m.%Y %H:%M')
                    return ROMANIA_TZ.localize(dt)
                except:
                    continue
        
        # Strategia 2: Meta tags
        meta_selectors = [
            'meta[property="article:published_time"]',
            'meta[name="publish-date"]',
            'meta[name="date"]',
            'meta[property="og:published_time"]'
        ]
        
        for selector in meta_selectors:
            meta_tag = soup.select_one(selector)
            if meta_tag:
                content = meta_tag.get('content', '')
                if content:
                    parsed_date = parse_to_romania_time(content)
                    if parsed_date:
                        return parsed_date
        
        # Strategia 3: JSON-LD schema
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # Caută datePublished
                    if 'datePublished' in data:
                        parsed_date = parse_to_romania_time(data['datePublished'])
                        if parsed_date:
                            return parsed_date
                    # Caută în array de obiecte
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and 'datePublished' in item:
                                parsed_date = parse_to_romania_time(item['datePublished'])
                                if parsed_date:
                                    return parsed_date
            except:
                continue
        
        # Strategia 4: Time elements
        time_elements = soup.find_all('time')
        for time_elem in time_elements:
            datetime_attr = time_elem.get('datetime', '')
            if datetime_attr:
                parsed_date = parse_to_romania_time(datetime_attr)
                if parsed_date:
                    return parsed_date
        
        print(f"⚠️  Nu s-a găsit data publicării pentru {article_url}")
        return None
        
    except Exception as e:
        print(f"❌ Eroare extragere dată Adevarul {article_url}: {e}")
        return None

def extract_biziday_published_date(article_url):
    """
    Extrage data publicării de pe un articol Biziday.ro
    
    Caută meta-tag-uri precum:
    - <time class="timeago" datetime="2025-06-29T15:03:11Z" title="2025-06-29 @ 14:56:26">
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Strategia 1: <time class="timeago" datetime="...">
        time_elements = soup.find_all('time', class_='timeago')
        for time_elem in time_elements:
            datetime_attr = time_elem.get('datetime', '')
            if datetime_attr:
                # Format: "2025-06-29T15:03:11Z"
                parsed_date = parse_to_romania_time(datetime_attr)
                if parsed_date:
                    return parsed_date
        
        # Strategia 2: Orice element time cu datetime
        time_elements = soup.find_all('time')
        for time_elem in time_elements:
            datetime_attr = time_elem.get('datetime', '')
            if datetime_attr:
                parsed_date = parse_to_romania_time(datetime_attr)
                if parsed_date:
                    return parsed_date
        
        # Strategia 3: Meta tags
        meta_selectors = [
            'meta[property="article:published_time"]',
            'meta[name="publish-date"]',
            'meta[name="date"]'
        ]
        
        for selector in meta_selectors:
            meta_tag = soup.select_one(selector)
            if meta_tag:
                content = meta_tag.get('content', '')
                if content:
                    parsed_date = parse_to_romania_time(content)
                    if parsed_date:
                        return parsed_date
        
        print(f"⚠️  Nu s-a găsit data publicării pentru {article_url}")
        return None
        
    except Exception as e:
        print(f"❌ Eroare extragere dată Biziday {article_url}: {e}")
        return None

def extract_rss_published_date(rss_entry):
    """
    Extrage data publicării dintr-un entry RSS
    
    Args:
        rss_entry: Entry din feed RSS cu câmpuri published_parsed sau published
    """
    try:
        # Încearcă published_parsed (tuple time)
        if hasattr(rss_entry, 'published_parsed') and rss_entry.published_parsed:
            import time
            timestamp = time.mktime(rss_entry.published_parsed)
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            return dt.astimezone(ROMANIA_TZ)
        
        # Încearcă published (string)
        if hasattr(rss_entry, 'published') and rss_entry.published:
            parsed_date = parse_to_romania_time(rss_entry.published)
            if parsed_date:
                return parsed_date
        
        # Încearcă updated
        if hasattr(rss_entry, 'updated') and rss_entry.updated:
            parsed_date = parse_to_romania_time(rss_entry.updated)
            if parsed_date:
                return parsed_date
        
        return None
        
    except Exception as e:
        print(f"⚠️  Eroare parsing dată RSS: {e}")
        return None

def format_for_database(dt):
    """
    Formatează datetime pentru salvare în PostgreSQL cu timezone
    
    Args:
        dt: datetime object cu timezone
        
    Returns:
        string formatat pentru PostgreSQL sau None
    """
    if not dt:
        return None
    
    # Asigură-te că are timezone
    if dt.tzinfo is None:
        dt = ROMANIA_TZ.localize(dt)
    
    # Convertește la timezone România
    dt_ro = dt.astimezone(ROMANIA_TZ)
    
    # Format PostgreSQL: YYYY-MM-DD HH:MM:SS+TZ
    return dt_ro.isoformat()

def extract_published_date_from_content(url, source_name="unknown"):
    """
    Extrage data publicării dintr-un URL specific în funcție de sursa de știri
    
    Args:
        url: URL-ul articolului
        source_name: Numele sursei ("adevarul", "biziday", etc.)
        
    Returns:
        datetime cu timezone România sau None
    """
    source_name = source_name.lower()
    
    if 'adevarul' in source_name or 'adevarul.ro' in url:
        return extract_adevarul_published_date(url)
    elif 'biziday' in source_name or 'biziday.ro' in url:
        return extract_biziday_published_date(url)
    else:
        # Încercare generică
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Caută meta tags generale
            meta_selectors = [
                'meta[property="article:published_time"]',
                'meta[name="publish-date"]',
                'meta[name="date"]',
                'meta[property="og:published_time"]'
            ]
            
            for selector in meta_selectors:
                meta_tag = soup.select_one(selector)
                if meta_tag:
                    content = meta_tag.get('content', '')
                    if content:
                        parsed_date = parse_to_romania_time(content)
                        if parsed_date:
                            return parsed_date
            
            # Caută time elements
            time_elements = soup.find_all('time')
            for time_elem in time_elements:
                datetime_attr = time_elem.get('datetime', '')
                if datetime_attr:
                    parsed_date = parse_to_romania_time(datetime_attr)
                    if parsed_date:
                        return parsed_date
            
            return None
            
        except Exception as e:
            print(f"❌ Eroare extragere dată generică {url}: {e}")
            return None

def extract_adevarul_updated_date(article_url):
    """
    Extrage data actualizării de pe un articol Adevarul.ro (OPTIMIZATĂ)
    
    Caută pattern-uri precum:
    - "Ultima actualizare: 28.06.2025 11:35"
    - JSON-LD cu "dateModified"
    - Meta tags cu data modificării
    
    Returns:
        datetime cu timezone România sau None dacă nu e disponibilă
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(article_url, headers=headers, timeout=5)  # Timeout redus la 5s
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Strategia 1: JSON-LD schema cu dateModified (cea mai rapidă)
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts[:3]:  # Limitez la primele 3 script-uri
            try:
                import json
                data = json.loads(script.string)
                
                # Funcție helper pentru a căuta în structuri nested
                def find_date_modified(obj, depth=0):
                    if depth > 3:  # Limitez depth-ul pentru performanță
                        return None
                    if isinstance(obj, dict):
                        if 'dateModified' in obj:
                            return obj['dateModified']
                        # Caută doar în câmpurile importante
                        for key in ['@graph', 'mainEntity', 'article']:
                            if key in obj:
                                result = find_date_modified(obj[key], depth + 1)
                                if result:
                                    return result
                    elif isinstance(obj, list) and len(obj) < 10:  # Limitez list-urile mari
                        for item in obj:
                            result = find_date_modified(item, depth + 1)
                            if result:
                                return result
                    return None
                
                date_modified = find_date_modified(data)
                if date_modified:
                    parsed_date = parse_to_romania_time(date_modified)
                    if parsed_date:
                        return parsed_date
                        
            except:
                continue
        
        # Strategia 2: Caută pattern "Ultima actualizare" doar în primele 500 caractere
        article_text = soup.get_text()[:500]  # Limitez textul pentru căutare rapidă
        updated_patterns = [
            r'Ultima actualizare:\s*(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})',
            r'Actualizat:\s*(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})'
        ]
        
        for pattern in updated_patterns:
            match = re.search(pattern, article_text)
            if match:
                date_str = match.group(1)
                try:
                    dt = datetime.strptime(date_str, '%d.%m.%Y %H:%M')
                    return ROMANIA_TZ.localize(dt)
                except:
                    continue
        
        # Strategia 3: Meta tags (rapid)
        meta_tag = soup.select_one('meta[property="article:modified_time"]')
        if meta_tag:
            content = meta_tag.get('content', '')
            if content:
                parsed_date = parse_to_romania_time(content)
                if parsed_date:
                    return parsed_date
        
        return None  # Nu s-a găsit data actualizării
        
    except Exception as e:
        # Timeout sau eroare de rețea - returnează None rapid
        return None
    """
    Extrage data actualizării de pe un articol Adevarul.ro
    
    Caută pattern-uri precum:
    - JSON-LD cu "dateModified" (prioritate)
    - "Ultima actualizare: 28.06.2025 11:35"
    - Meta tags cu data modificării
    
    Returns:
        datetime cu timezone România sau None dacă nu e disponibilă
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Strategia 1 (PRIORITATE): JSON-LD schema cu dateModified
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                import json
                data = json.loads(script.string)
                
                # Funcție helper pentru a căuta în structuri nested
                def find_date_modified(obj):
                    if isinstance(obj, dict):
                        if 'dateModified' in obj:
                            return obj['dateModified']
                        for value in obj.values():
                            result = find_date_modified(value)
                            if result:
                                return result
                    elif isinstance(obj, list):
                        for item in obj:
                            result = find_date_modified(item)
                            if result:
                                return result
                    return None
                
                date_modified = find_date_modified(data)
                if date_modified:
                    parsed_date = parse_to_romania_time(date_modified)
                    if parsed_date:
                        return parsed_date
                        
            except:
                continue
        
        # Strategia 2: Caută pattern "Ultima actualizare: DD.MM.YYYY HH:MM"
        updated_patterns = [
            r'Ultima actualizare:\s*(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})',
            r'Ultima\s+actualizare\s*:\s*(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})',
            r'Actualizat:\s*(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})'
        ]
        
        article_text = soup.get_text()
        for pattern in updated_patterns:
            match = re.search(pattern, article_text)
            if match:
                date_str = match.group(1)
                # Convertește formatul DD.MM.YYYY HH:MM
                try:
                    dt = datetime.strptime(date_str, '%d.%m.%Y %H:%M')
                    return ROMANIA_TZ.localize(dt)
                except:
                    continue
        
        # Strategia 3: Meta tags pentru dată modificare
        meta_selectors = [
            'meta[property="article:modified_time"]',
            'meta[name="last-modified"]',
            'meta[name="modified-date"]',
            'meta[property="og:updated_time"]'
        ]
        
        for selector in meta_selectors:
            meta_tag = soup.select_one(selector)
            if meta_tag:
                content = meta_tag.get('content', '')
                if content:
                    parsed_date = parse_to_romania_time(content)
                    if parsed_date:
                        return parsed_date
        
        # Nu s-a găsit nicio dată de actualizare - returnează None
        print(f"⚠️  Nu s-a găsit data actualizării pentru {article_url}")
        return None
        
    except Exception as e:
        print(f"❌ Eroare extragere dată actualizare Adevarul {article_url}: {e}")
        return None

def extract_biziday_updated_date(article_url):
    """
    Extrage data actualizării de pe un articol Biziday.ro
    
    Caută meta-tag-uri precum:
    - <meta property="article:modified_time" content="2025-06-29T15:05:11Z"> (PRIORITATE)
    - Alte meta tags cu data modificării
    - JSON-LD cu dateModified
    
    Returns:
        datetime cu timezone România sau None dacă nu e disponibilă
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Strategia 1 (PRIORITATE): Meta tag article:modified_time
        meta_modified = soup.find('meta', property='article:modified_time')
        if meta_modified:
            content = meta_modified.get('content', '')
            if content:
                parsed_date = parse_to_romania_time(content)
                if parsed_date:
                    return parsed_date
        
        # Strategia 2: Alte meta tags pentru dată modificare
        meta_selectors = [
            'meta[name="last-modified"]',
            'meta[name="modified-date"]',
            'meta[property="og:updated_time"]',
            'meta[name="date.updated"]'
        ]
        
        for selector in meta_selectors:
            meta_tag = soup.select_one(selector)
            if meta_tag:
                content = meta_tag.get('content', '')
                if content:
                    parsed_date = parse_to_romania_time(content)
                    if parsed_date:
                        return parsed_date
        
        # Strategia 3: Caută în JSON-LD schema
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                import json
                data = json.loads(script.string)
                
                # Funcție helper pentru a căuta în structuri nested
                def find_date_modified(obj):
                    if isinstance(obj, dict):
                        if 'dateModified' in obj:
                            return obj['dateModified']
                        for value in obj.values():
                            result = find_date_modified(value)
                            if result:
                                return result
                    elif isinstance(obj, list):
                        for item in obj:
                            result = find_date_modified(item)
                            if result:
                                return result
                    return None
                
                date_modified = find_date_modified(data)
                if date_modified:
                    parsed_date = parse_to_romania_time(date_modified)
                    if parsed_date:
                        return parsed_date
                        
            except:
                continue
        
        print(f"⚠️  Nu s-a găsit data actualizării pentru {article_url}")
        return None
        
    except Exception as e:
        print(f"❌ Eroare extragere dată actualizare Biziday {article_url}: {e}")
        return None

def extract_updated_date_from_content(url, source_name="unknown"):
    """
    Extrage data actualizării dintr-un URL specific în funcție de sursa de știri
    
    Args:
        url: URL-ul articolului
        source_name: Numele sursei ("adevarul", "biziday", etc.)
        
    Returns:
        datetime cu timezone România sau None dacă nu e disponibilă
    """
    source_name = source_name.lower()
    
    if 'adevarul' in source_name or 'adevarul.ro' in url:
        return extract_adevarul_updated_date(url)
    elif 'biziday' in source_name or 'biziday.ro' in url:
        return extract_biziday_updated_date(url)
    else:
        # Încercare generică pentru alte surse
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Caută meta tags generale pentru dată modificare
            meta_selectors = [
                'meta[property="article:modified_time"]',
                'meta[name="last-modified"]',
                'meta[name="modified-date"]',
                'meta[property="og:updated_time"]'
            ]
            
            for selector in meta_selectors:
                meta_tag = soup.select_one(selector)
                if meta_tag:
                    content = meta_tag.get('content', '')
                    if content:
                        parsed_date = parse_to_romania_time(content)
                        if parsed_date:
                            return parsed_date
            
            return None
            
        except Exception as e:
            print(f"❌ Eroare extragere dată actualizare generică {url}: {e}")
            return None

# Test functions
if __name__ == "__main__":
    # Test parsing
    test_dates = [
        "2025-06-29T15:03:11Z",
        "28.06.2025 11:24",
        "Sun, 29 Jun 2025 15:05:19 GMT",
        "2025-06-29 17:26:44"
    ]
    
    print("🧪 Test parsing date-uri:")
    for date_str in test_dates:
        result = parse_to_romania_time(date_str)
        formatted = format_for_database(result)
        print(f"   '{date_str}' -> {formatted}")
