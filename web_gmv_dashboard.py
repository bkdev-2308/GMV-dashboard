"""
Web GMV Dashboard - Flask App
Hiển thị Top GMV sản phẩm với link Shopee
"""

import os
import psycopg2
import psycopg2.extras
import json
from functools import wraps
from datetime import datetime, timezone, timedelta
import threading
import unicodedata
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import gspread
from google.oauth2.service_account import Credentials
from apscheduler.schedulers.background import BackgroundScheduler

# Multi-session functions from db_helpers
try:
    from db_helpers import (
        get_active_sessions, get_history_timeslots, get_history_data
    )
except ImportError:
    def get_active_sessions(*args, **kwargs):
        return []
    def get_history_timeslots(*args, **kwargs):
        return []
    def get_history_data(*args, **kwargs):
        return []

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database URL (PostgreSQL)
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Admin password from environment
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Google Sheets scope
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

# ============== Auto-Sync Scheduler ==============
# Initialize scheduler (only start if not in Flask reloader subprocess)
scheduler = None
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not os.environ.get('FLASK_DEBUG'):
    scheduler = BackgroundScheduler()
    scheduler.start()
    print("[SCHEDULER] Background scheduler started")

# Auto-sync state (in-memory)
auto_sync_state = {
    'running': False,
    'end_time': None,  # HH:MM format
    'job_id': None,
    'last_auto_sync': None,
    'next_sync': None
}

# ============== Server-Side Cache ==============
import time

# Cache configuration
CACHE_TTL = 60  # 1 minute in seconds

# In-memory cache storage
data_cache = {
    'all_data': None,
    'last_update': 0,
    'shop_ids': None,
    'stats': None
}

def get_cached_data():
    """Get data from cache if still valid, else return None"""
    if data_cache['all_data'] is None:
        return None
    if time.time() - data_cache['last_update'] > CACHE_TTL:
        return None  # Cache expired
    return data_cache['all_data']

def set_cached_data(data, shop_ids, stats):
    """Store data in cache"""
    data_cache['all_data'] = data
    data_cache['shop_ids'] = shop_ids
    data_cache['stats'] = stats
    data_cache['last_update'] = time.time()
    print(f"[CACHE] Cached {len(data)} products")

def invalidate_cache():
    """Clear the cache (call after data sync)"""
    data_cache['all_data'] = None
    data_cache['last_update'] = 0
    data_cache['shop_ids'] = None
    data_cache['stats'] = None
    print("[CACHE] Cache invalidated")

# ============== Helper Functions ==============

def normalize_vietnamese(text):
    """Remove Vietnamese diacritics for easier matching"""
    if not text:
        return ""
    # Normalize to decomposed form, then remove combining marks
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().replace(' ', '')

# ============== Database Functions ==============

def get_db():
    """Get database connection (direct connection)"""
    return psycopg2.connect(DATABASE_URL)

def close_db(conn):
    """Close database connection"""
    if conn:
        try:
            conn.close()
        except Exception:
            pass

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Config table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # GMV data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gmv_data (
            item_id TEXT PRIMARY KEY,
            item_name TEXT,
            revenue INTEGER,
            shop_id TEXT,
            link_sp TEXT,
            datetime TEXT,
            clicks INTEGER,
            ctr TEXT,
            orders INTEGER,
            items_sold INTEGER,
            cluster TEXT,
            add_to_cart INTEGER,
            confirmed_revenue INTEGER
        )
    ''')
    
    # Add new columns if not exists (for existing databases)
    cursor.execute('''
        ALTER TABLE gmv_data ADD COLUMN IF NOT EXISTS confirmed_revenue INTEGER DEFAULT 0
    ''')
    
    # Raw session data table (for monthly analytics)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_session_data (
            id SERIAL PRIMARY KEY,
            item_name TEXT,
            item_id TEXT,
            revenue INTEGER,
            clicks INTEGER,
            file_name TEXT,
            session_name TEXT
        )
    ''')
    
    # Add add_to_cart column to existing gmv_data table if not exists
    try:
        cursor.execute('''
            ALTER TABLE gmv_data ADD COLUMN IF NOT EXISTS add_to_cart INTEGER DEFAULT 0
        ''')
    except Exception:
        pass  # Column might already exist
    
    # Create indexes for faster sorting and filtering
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gmv_revenue ON gmv_data(revenue DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gmv_clicks ON gmv_data(clicks DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gmv_orders ON gmv_data(orders DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gmv_add_to_cart ON gmv_data(add_to_cart DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gmv_shop_id ON gmv_data(shop_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gmv_item_name ON gmv_data(item_name)')
        print("[DB] Indexes created for gmv_data")
    except Exception as e:
        print(f"[DB] Index creation note: {e}")
    
    conn.commit()
    conn.close()

def get_config(key):
    """Get config value by key"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT value FROM config WHERE key = %s', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else None

def set_config(key, value):
    """Set config value"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO config (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    ''', (key, value))
    conn.commit()
    conn.close()

# ============== Google Sheets Functions ==============

def get_gspread_client():
    """Get authenticated gspread client"""
    # Try service account key from env (base64) or file
    service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    
    if service_account_json:
        import base64
        try:
            # Try base64 decode first
            decoded = base64.b64decode(service_account_json).decode('utf-8')
            service_account_info = json.loads(decoded)
        except:
            # If not base64, try direct JSON
            service_account_info = json.loads(service_account_json)
        creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    else:
        # Local: use service-account-key.json file
        key_path = os.path.join(os.path.dirname(__file__), 'service-account-key.json')
        if os.path.exists(key_path):
            creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
        else:
            raise Exception("No Google service account credentials found")
    
    return gspread.authorize(creds)

def get_spreadsheet_sheets(spreadsheet_url):
    """Get list of sheet names from spreadsheet"""
    client = get_gspread_client()
    spreadsheet = client.open_by_url(spreadsheet_url)
    return [sheet.title for sheet in spreadsheet.worksheets()]

def sync_deallist_only(spreadsheet_url, deallist_sheet_name):
    """
    Sync Deal List vào bảng deal_list riêng trong PostgreSQL.
    Data mới từ scraper sẽ tự động được map qua JOIN.
    Returns: (count, spreadsheet_title)
    """
    client = get_gspread_client()
    spreadsheet = client.open_by_url(spreadsheet_url)
    spreadsheet_title = spreadsheet.title  # Lấy tên spreadsheet
    
    # Read Deal list
    deallist_sheet = spreadsheet.worksheet(deallist_sheet_name)
    deallist_values = deallist_sheet.get_all_values()
    
    # Find header row - look for row with actual column names (not just counts)
    header_row_idx = 0
    for idx, row in enumerate(deallist_values):
        row_text = ' '.join(str(cell).lower() for cell in row)
        # Header row should contain "item" AND "id" AND "shop" (not just numbers)
        if 'item' in row_text and 'id' in row_text and 'shop' in row_text:
            header_row_idx = idx
            print(f"[DEALLIST DEBUG] Found header at row {idx}: {row[:5]}...")
            break
    
    # Extract headers and data
    if header_row_idx < len(deallist_values):
        headers = deallist_values[header_row_idx]
        data_rows = deallist_values[header_row_idx + 1:]
    else:
        headers = deallist_values[0] if deallist_values else []
        data_rows = deallist_values[1:] if len(deallist_values) > 1 else []
    
    # Convert to list of dicts
    deallist_data = []
    for row in data_rows:
        if any(cell.strip() for cell in row):
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    row_dict[header] = row[i]
            deallist_data.append(row_dict)
    
    # Find column names
    item_id_col = None
    shop_id_col = None
    cluster_col = None
    
    if deallist_data:
        first_row_keys = list(deallist_data[0].keys())
        # First pass: look for 'finalitemid' specifically (priority)
        for key in first_row_keys:
            key_lower = key.lower().replace(' ', '').replace('_', '')
            if 'finalitemid' in key_lower:
                item_id_col = key
            if 'shopid' in key_lower:
                shop_id_col = key
            if 'cluster' in key_lower:
                cluster_col = key
        # Second pass: fallback to 'itemid' if finalitemid not found
        if not item_id_col:
            for key in first_row_keys:
                key_lower = key.lower().replace(' ', '').replace('_', '')
                if 'itemid' in key_lower:
                    item_id_col = key
                    break
    
    # Debug log: which columns were found
    print(f"[DEALLIST DEBUG] item_id_col='{item_id_col}', shop_id_col='{shop_id_col}', cluster_col='{cluster_col}'")
    
    if not item_id_col or not shop_id_col:
        print(f"[DEALLIST DEBUG] Headers found: {first_row_keys if deallist_data else 'No data'}")
        raise Exception("Không tìm thấy cột Item ID hoặc Shop ID trong Deal List")
    
    # Prepare data for inserting into deal_list table
    deal_list_items = []
    for row in deallist_data:
        item_id = str(row.get(item_id_col, '')).strip()
        shop_id_raw = str(row.get(shop_id_col, '')).strip()
        cluster = str(row.get(cluster_col, '')).strip() if cluster_col else ''
        
        if '+' in shop_id_raw:
            shop_id = shop_id_raw.split('+')[-1]
        else:
            shop_id = shop_id_raw
        shop_id = ''.join(c for c in shop_id if c.isdigit())
        
        if item_id and shop_id:
            deal_list_items.append((item_id, shop_id, cluster))
    
    print(f"[DEALLIST] Preparing to save {len(deal_list_items)} items to deal_list table")
    
    # Debug: count items with cluster
    items_with_cluster = sum(1 for item in deal_list_items if item[2])
    print(f"[DEALLIST DEBUG] Items with cluster: {items_with_cluster}/{len(deal_list_items)}")
    if deal_list_items:
        print(f"[DEALLIST DEBUG] Sample item: {deal_list_items[0]}")
    
    # Save to deal_list table in PostgreSQL
    conn = get_db()
    cursor = conn.cursor()
    
    # Create deal_list table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deal_list (
            item_id TEXT PRIMARY KEY,
            shop_id TEXT,
            cluster TEXT
        )
    ''')
    
    # Clear old data
    cursor.execute("DELETE FROM deal_list")
    
    # Batch insert using executemany
    if deal_list_items:
        insert_sql = '''
            INSERT INTO deal_list (item_id, shop_id, cluster)
            VALUES (%s, %s, %s)
            ON CONFLICT (item_id) DO UPDATE SET
                shop_id = EXCLUDED.shop_id,
                cluster = EXCLUDED.cluster
        '''
        psycopg2.extras.execute_batch(cursor, insert_sql, deal_list_items, page_size=500)
    
    # Also update gmv_data với shop_id/link từ deal_list (JOIN approach)
    cursor.execute('''
        UPDATE gmv_data g
        SET 
            shop_id = d.shop_id,
            cluster = d.cluster,
            link_sp = 'https://shopee.vn/a-i.' || d.shop_id || '.' || g.item_id
        FROM deal_list d
        WHERE g.item_id = d.item_id
    ''')
    updated_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"[DEALLIST] Saved {len(deal_list_items)} items to deal_list table")
    print(f"[DEALLIST] Updated {updated_count} items in gmv_data with shop_id/link/cluster")
    
    # Update last sync time
    set_config('last_sync', datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S'))
    
    return len(deal_list_items), spreadsheet_title


def sync_deallist2_only(spreadsheet_url, deallist_sheet_name):
    """
    Sync Deal List 2 vào bảng deal_list_2 riêng trong PostgreSQL.
    Tương tự sync_deallist_only nhưng cho deal list thứ 2.
    Returns: (count, spreadsheet_title)
    """
    client = get_gspread_client()
    spreadsheet = client.open_by_url(spreadsheet_url)
    spreadsheet_title = spreadsheet.title  # Lấy tên spreadsheet
    
    # Read Deal list
    deallist_sheet = spreadsheet.worksheet(deallist_sheet_name)
    deallist_values = deallist_sheet.get_all_values()
    
    # Find header row
    header_row_idx = 0
    for idx, row in enumerate(deallist_values):
        row_text = ' '.join(str(cell).lower() for cell in row)
        if 'item' in row_text and 'id' in row_text and 'shop' in row_text:
            header_row_idx = idx
            print(f"[DEALLIST2 DEBUG] Found header at row {idx}: {row[:5]}...")
            break
    
    # Extract headers and data
    if header_row_idx < len(deallist_values):
        headers = deallist_values[header_row_idx]
        data_rows = deallist_values[header_row_idx + 1:]
    else:
        headers = deallist_values[0] if deallist_values else []
        data_rows = deallist_values[1:] if len(deallist_values) > 1 else []
    
    # Convert to list of dicts
    deallist_data = []
    for row in data_rows:
        if any(cell.strip() for cell in row):
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    row_dict[header] = row[i]
            deallist_data.append(row_dict)
    
    # Find column names - same logic as sync_deallist_only
    item_id_col = None
    shop_id_col = None
    cluster_col = None
    
    if deallist_data:
        first_row_keys = list(deallist_data[0].keys())
        # First pass: look for 'finalitemid' specifically (priority)
        for key in first_row_keys:
            key_lower = key.lower().replace(' ', '').replace('_', '')
            if 'finalitemid' in key_lower:
                item_id_col = key
            if 'shopid' in key_lower:
                shop_id_col = key
            if 'cluster' in key_lower:
                cluster_col = key
        # Second pass: fallback to 'itemid' if finalitemid not found
        if not item_id_col:
            for key in first_row_keys:
                key_lower = key.lower().replace(' ', '').replace('_', '')
                if 'itemid' in key_lower:
                    item_id_col = key
                    break
    
    # Debug log: which columns were found
    print(f"[DEALLIST2 DEBUG] item_id_col='{item_id_col}', shop_id_col='{shop_id_col}', cluster_col='{cluster_col}'")
    
    if not item_id_col or not shop_id_col:
        print(f"[DEALLIST2 DEBUG] Headers found: {first_row_keys if deallist_data else 'No data'}")
        raise Exception("Không tìm thấy cột Item ID hoặc Shop ID trong Deal List 2")
    
    # Prepare data - same logic as sync_deallist_only
    deal_list_items = []
    for row in deallist_data:
        item_id = str(row.get(item_id_col, '')).strip()
        shop_id_raw = str(row.get(shop_id_col, '')).strip()
        cluster = str(row.get(cluster_col, '')).strip() if cluster_col else ''
        
        if '+' in shop_id_raw:
            shop_id = shop_id_raw.split('+')[-1]
        else:
            shop_id = shop_id_raw
        shop_id = ''.join(c for c in shop_id if c.isdigit())
        
        if item_id and shop_id:
            deal_list_items.append((item_id, shop_id, cluster))
    
    print(f"[DEALLIST2] Preparing to save {len(deal_list_items)} items to deal_list_2 table")
    
    # Save to deal_list_2 table in PostgreSQL
    conn = get_db()
    cursor = conn.cursor()
    
    # Create deal_list_2 table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deal_list_2 (
            item_id TEXT PRIMARY KEY,
            shop_id TEXT,
            cluster TEXT
        )
    ''')
    
    # Clear old data
    cursor.execute("DELETE FROM deal_list_2")
    
    # Batch insert
    if deal_list_items:
        insert_sql = '''
            INSERT INTO deal_list_2 (item_id, shop_id, cluster)
            VALUES (%s, %s, %s)
            ON CONFLICT (item_id) DO UPDATE SET
                shop_id = EXCLUDED.shop_id,
                cluster = EXCLUDED.cluster
        '''
        psycopg2.extras.execute_batch(cursor, insert_sql, deal_list_items, page_size=500)
    
    conn.commit()
    conn.close()
    
    print(f"[DEALLIST2] Saved {len(deal_list_items)} items to deal_list_2 table")
    
    return len(deal_list_items), spreadsheet_title


def get_session_deallist_mapping():
    """Get all session -> deallist mappings"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_deallist_config (
            session_id TEXT PRIMARY KEY,
            deallist_id INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    
    cursor.execute('SELECT session_id, deallist_id FROM session_deallist_config')
    rows = cursor.fetchall()
    conn.close()
    
    return {row['session_id']: row['deallist_id'] for row in rows}


def set_session_deallist_mapping(session_id, deallist_id):
    """Set which deallist a session uses (1 or 2)"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_deallist_config (
            session_id TEXT PRIMARY KEY,
            deallist_id INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        INSERT INTO session_deallist_config (session_id, deallist_id)
        VALUES (%s, %s)
        ON CONFLICT (session_id) DO UPDATE SET deallist_id = EXCLUDED.deallist_id
    ''', (session_id, deallist_id))
    
    conn.commit()
    conn.close()
    
    return True


def get_deallist_for_session(session_id):
    """Get which deallist ID a session uses (1 or 2), default 1"""
    if not session_id:
        return 1
    
    mapping = get_session_deallist_mapping()
    return mapping.get(session_id, 1)


def sync_data_from_sheets(spreadsheet_url, rawdata_sheet_name, deallist_sheet_name):
    """
    Sync data from Google Sheets to SQLite
    1. Đọc GMV data từ rawdata sheet
    2. Đọc Deal list để map Item ID -> Shop ID
    3. Generate link sản phẩm
    4. Lưu vào SQLite
    """
    client = get_gspread_client()
    spreadsheet = client.open_by_url(spreadsheet_url)
    
    # 1. Read Deal list to create item_id -> shop_id mapping
    deallist_sheet = spreadsheet.worksheet(deallist_sheet_name)
    
    # Use get_all_values() to handle sheets with notes row at top
    # Row 1 = notes/colors, Row 2 = actual headers
    deallist_values = deallist_sheet.get_all_values()
    
    # Find header row (skip empty rows and look for row with column names)
    header_row_idx = 0
    for idx, row in enumerate(deallist_values):
        # Check if this row looks like a header (contains "Item" AND "Shop" AND "ID")
        row_text = ' '.join(str(cell).lower() for cell in row)
        if 'item' in row_text and 'id' in row_text and 'shop' in row_text:
            header_row_idx = idx
            break
    
    # Extract headers and data
    if header_row_idx < len(deallist_values):
        headers = deallist_values[header_row_idx]
        data_rows = deallist_values[header_row_idx + 1:]
    else:
        headers = deallist_values[0] if deallist_values else []
        data_rows = deallist_values[1:] if len(deallist_values) > 1 else []
    
    # Convert to list of dicts
    deallist_data = []
    for row in data_rows:
        if any(cell.strip() for cell in row):  # Skip empty rows
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    row_dict[header] = row[i]
            deallist_data.append(row_dict)
    
    # Find the correct column names for item_id, shop_id, and cluster in deal list
    item_id_col = None
    shop_id_col = None
    cluster_col = None
    
    if deallist_data:
        first_row_keys = list(deallist_data[0].keys())
        # First pass: look for 'finalitemid' specifically (priority)
        for key in first_row_keys:
            key_lower = key.lower().replace(' ', '').replace('_', '')
            if 'finalitemid' in key_lower:
                item_id_col = key
            if 'shopid' in key_lower:
                shop_id_col = key
            if 'cluster' in key_lower:
                cluster_col = key
        # Second pass: fallback to 'itemid' if finalitemid not found
        if not item_id_col:
            for key in first_row_keys:
                key_lower = key.lower().replace(' ', '').replace('_', '')
                if 'itemid' in key_lower:
                    item_id_col = key
                    break
    
    # Create mapping dicts
    item_to_shop = {}
    item_to_cluster = {}
    if item_id_col and shop_id_col:
        for row in deallist_data:
            item_id = str(row.get(item_id_col, '')).strip()
            shop_id_raw = str(row.get(shop_id_col, '')).strip()
            cluster = str(row.get(cluster_col, '')).strip() if cluster_col else ''
            
            # Extract only numeric part from shop_id (remove brand+ prefix if exists)
            # e.g., "vinamilk+975865932" -> "975865932"
            if '+' in shop_id_raw:
                shop_id = shop_id_raw.split('+')[-1]  # Take part after the last +
            else:
                shop_id = shop_id_raw
            
            # Ensure shop_id is numeric only
            shop_id = ''.join(c for c in shop_id if c.isdigit())
            
            if item_id and shop_id:
                item_to_shop[item_id] = shop_id
            if item_id and cluster:
                item_to_cluster[item_id] = cluster

    
    # 2. Read Raw data sheet (GMV data) - same approach for handling notes row
    rawdata_sheet = spreadsheet.worksheet(rawdata_sheet_name)
    rawdata_values = rawdata_sheet.get_all_values()
    
    # Find header row
    raw_header_idx = 0
    for idx, row in enumerate(rawdata_values):
        row_text = ' '.join(str(cell).lower() for cell in row)
        if 'item' in row_text and ('id' in row_text or 'doanh' in row_text):
            raw_header_idx = idx
            break
    
    # Extract headers and data
    if raw_header_idx < len(rawdata_values):
        raw_headers = rawdata_values[raw_header_idx]
        raw_data_rows = rawdata_values[raw_header_idx + 1:]
    else:
        raw_headers = rawdata_values[0] if rawdata_values else []
        raw_data_rows = rawdata_values[1:] if len(rawdata_values) > 1 else []
    
    # Convert to list of dicts
    rawdata = []
    for row in raw_data_rows:
        if any(str(cell).strip() for cell in row):
            row_dict = {}
            for i, header in enumerate(raw_headers):
                if i < len(row):
                    row_dict[header] = row[i]
            rawdata.append(row_dict)
    
    # Find column names in raw data
    # Expected: DateTime, Item ID, Tên sản phẩm, Lượt click, Tỷ lệ click, Tổng đơn hàng, Các mặt hàng được bán, Doanh thu, Tỷ lệ click để đặt hàng, Thêm vào giỏ hàng
    
    gmv_items = []
    
    for row in rawdata:
        # Try to find item_id column
        item_id = None
        for key in row.keys():
            key_lower = key.lower().replace(' ', '').replace('_', '')
            if 'itemid' in key_lower:
                item_id = str(row[key]).strip()
                break
        
        if not item_id:
            continue
        
        # Get other fields
        item_name = ''
        datetime_str = ''
        revenue = 0
        clicks = 0
        ctr = ''
        orders = 0
        items_sold = 0
        add_to_cart = 0
        confirmed_revenue = 0
        
        for key, value in row.items():
            key_lower = key.lower().replace(' ', '')
            key_normalized = normalize_vietnamese(key)  # Remove Vietnamese diacritics
            
            if 'tensanpham' in key_normalized or 'itemname' in key_normalized:
                item_name = str(value)
            elif 'datetime' in key_lower or 'thoigian' in key_normalized:
                datetime_str = str(value)
            elif ('doanhthu' in key_normalized) and 'confirm' not in key_lower and 'nmv' not in key_lower:
                # Only match "Doanh thu" column, NOT "NMV (Confirmed Revenue)"
                try:
                    revenue = int(float(str(value).replace(',', '').replace('.', '').strip() or 0))
                except:
                    revenue = 0
            elif 'luotclick' in key_normalized or 'clicks' in key_normalized:
                try:
                    clicks = int(value or 0)
                except:
                    clicks = 0
            elif 'tyleclick' in key_normalized and 'dathang' not in key_normalized:
                ctr = str(value)
            elif 'tongdonhang' in key_normalized or 'orders' in key_normalized:
                try:
                    orders = int(value or 0)
                except:
                    orders = 0
            elif 'mathang' in key_normalized or 'itemssold' in key_normalized:
                try:
                    items_sold = int(value or 0)
                except:
                    items_sold = 0
            elif 'themvaogio' in key_normalized or 'giohang' in key_normalized or 'addtocart' in key_lower:
                try:
                    add_to_cart = int(value or 0)
                except:
                    add_to_cart = 0
            elif 'nmv' in key_lower or 'confirm' in key_lower:
                try:
                    confirmed_revenue = int(float(str(value).replace(',', '').replace('.', '').strip() or 0))
                except:
                    confirmed_revenue = 0
        # Map shop_id and cluster from deal list
        shop_id = item_to_shop.get(item_id, '')
        cluster = item_to_cluster.get(item_id, '')
        
        # Generate link
        link_sp = ''
        if shop_id and item_id:
            link_sp = f"https://shopee.vn/a-i.{shop_id}.{item_id}"
        
        gmv_items.append({
            'item_id': item_id,
            'item_name': item_name,
            'revenue': revenue,
            'shop_id': shop_id,
            'link_sp': link_sp,
            'datetime': datetime_str,
            'clicks': clicks,
            'ctr': ctr,
            'orders': orders,
            'items_sold': items_sold,
            'cluster': cluster,
            'add_to_cart': add_to_cart,
            'confirmed_revenue': confirmed_revenue
        })
    
    # 3. Save to SQLite - Keep LAST occurrence of each item_id
    # Since data is appended top-to-bottom, we iterate and OVERWRITE
    # so the last (most recent) row for each item is kept
    conn = get_db()
    cursor = conn.cursor()
    
    # Clear old data
    cursor.execute('DELETE FROM gmv_data')
    
    # Keep LAST occurrence of each item_id (just overwrite as we iterate)
    item_latest = {}
    for item in gmv_items:
        item_latest[item['item_id']] = item
    
    print(f"[SYNC] Processing {len(item_latest)} unique items")
    
    # Insert
    for item in item_latest.values():
        cursor.execute('''
            INSERT INTO gmv_data 
            (item_id, item_name, revenue, shop_id, link_sp, datetime, clicks, ctr, orders, items_sold, cluster, add_to_cart, confirmed_revenue)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (item_id) DO UPDATE SET
                item_name = EXCLUDED.item_name,
                revenue = EXCLUDED.revenue,
                shop_id = EXCLUDED.shop_id,
                link_sp = EXCLUDED.link_sp,
                datetime = EXCLUDED.datetime,
                clicks = EXCLUDED.clicks,
                ctr = EXCLUDED.ctr,
                orders = EXCLUDED.orders,
                items_sold = EXCLUDED.items_sold,
                cluster = EXCLUDED.cluster,
                add_to_cart = EXCLUDED.add_to_cart,
                confirmed_revenue = EXCLUDED.confirmed_revenue
        ''', (
            item['item_id'],
            item['item_name'],
            item['revenue'],
            item['shop_id'],
            item['link_sp'],
            item['datetime'],
            item['clicks'],
            item['ctr'],
            item['orders'],
            item['items_sold'],
            item['cluster'],
            item['add_to_cart'],
            item['confirmed_revenue']
        ))
    
    conn.commit()
    conn.close()
    
    # Update last sync time
    set_config('last_sync', datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S'))
    
    return len(item_latest)

# ============== Auto-Sync Functions ==============

def auto_sync_job():
    """Background job that syncs data every 5 minutes (300 seconds)"""
    global auto_sync_state
    
    now = datetime.now()
    
    # Perform sync
    try:
        spreadsheet_url = get_config('spreadsheet_url')
        rawdata_sheet = get_config('rawdata_sheet')
        deallist_sheet = get_config('deallist_sheet')
        
        if all([spreadsheet_url, rawdata_sheet, deallist_sheet]):
            count = sync_data_from_sheets(spreadsheet_url, rawdata_sheet, deallist_sheet)
            auto_sync_state['last_auto_sync'] = now.isoformat()
            print(f"[AUTO-SYNC] {now.strftime('%H:%M:%S')} - Synced {count} products successfully")
        else:
            print(f"[AUTO-SYNC] Missing configuration. Skipping sync.")
    except Exception as e:
        print(f"[AUTO-SYNC] Error: {str(e)}")
    
    # Update next sync time (5 minutes = 300 seconds)
    auto_sync_state['next_sync'] = (now.replace(second=0, microsecond=0) + 
                                     __import__('datetime').timedelta(seconds=300)).isoformat()

def start_auto_sync():
    """Start the auto-sync scheduler (runs every 5 minutes continuously)"""
    global auto_sync_state, scheduler
    
    if scheduler is None:
        print("[AUTO-SYNC] Scheduler not initialized")
        return False
    
    # Stop existing job if any
    if auto_sync_state['job_id']:
        stop_auto_sync()
    
    auto_sync_state['running'] = True
    
    # Run first sync immediately
    print(f"[AUTO-SYNC] Running first sync immediately...")
    auto_sync_job()
    
    # Schedule every 300 seconds (5 minutes)
    job = scheduler.add_job(
        auto_sync_job,
        'interval',
        seconds=300,
        id='auto_sync_job'
    )
    auto_sync_state['job_id'] = job.id
    print(f"[AUTO-SYNC] Started. Will run every 5 minutes continuously.")
    return True

def stop_auto_sync():
    """Stop the auto-sync scheduler"""
    global auto_sync_state, scheduler
    
    if auto_sync_state['job_id'] and scheduler:
        try:
            scheduler.remove_job(auto_sync_state['job_id'])
        except:
            pass
    
    auto_sync_state['running'] = False
    auto_sync_state['job_id'] = None
    auto_sync_state['next_sync'] = None
    print("[AUTO-SYNC] Stopped.")

# ============== Auth Decorators ==============

def admin_required(f):
    """Decorator to require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ============== Routes ==============

@app.route('/')
def index():
    """Public landing page - BeyondK Network"""
    return render_template('landing.html')

@app.route('/admin')
@admin_required
def admin():
    """Admin Dashboard - GMV Analytics (requires login)"""
    return render_template('index.html')

@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    """Item Analytics page (requires login)"""
    return render_template('analytics.html')

@app.route('/admin/history')
@admin_required
def admin_history():
    """Session History page - view archived sessions"""
    return render_template('history.html')

@app.route('/admin/setting')
@admin_required
def admin_setting():
    """Admin Settings panel"""
    config = {
        'spreadsheet_url': get_config('spreadsheet_url') or '',
        'rawdata_sheet': get_config('rawdata_sheet') or '',
        'deallist_sheet': get_config('deallist_sheet') or '',
        'deallist2_url': get_config('deallist2_url') or '',
        'deallist2_sheet': get_config('deallist2_sheet') or '',
        'last_sync': get_config('last_sync') or 'Chưa sync'
    }
    return render_template('admin.html', config=config)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin'))
        else:
            error = 'Mật khẩu không đúng'
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('is_admin', None)
    return redirect(url_for('index'))

# ============== API Routes ==============

@app.route('/api/top-gmv')
def api_top_gmv():
    """API: Get GMV data with pagination and filters"""
    # Pagination params
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Filter params
    shop_id_filter = request.args.get('shop_id', '', type=str).strip()
    search = request.args.get('search', '', type=str).strip()
    
    # Sort params - allow sorting by different columns
    sort_by = request.args.get('sort_by', 'revenue', type=str).strip()
    sort_dir = request.args.get('sort_dir', 'desc', type=str).strip().lower()
    
    # Validate sort params to prevent SQL injection
    allowed_sort_columns = ['revenue', 'clicks', 'add_to_cart', 'orders', 'item_name', 'confirmed_revenue', 'items_sold']
    if sort_by not in allowed_sort_columns:
        sort_by = 'revenue'
    if sort_dir not in ['asc', 'desc']:
        sort_dir = 'desc'
    
    # Limit per_page to reasonable values
    per_page = min(max(per_page, 10), 10000)  # Allow up to 10000 for full data load
    offset = (page - 1) * per_page
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Build query with filters
    where_clauses = []
    params = []
    
    if shop_id_filter:
        where_clauses.append("shop_id = %s")
        params.append(shop_id_filter)
    
    if search:
        where_clauses.append("(item_name ILIKE %s OR item_id ILIKE %s)")
        search_term = f"%{search}%"
        params.extend([search_term, search_term])
    
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
    
    # Get total count
    count_query = f"SELECT COUNT(*) as total FROM gmv_data {where_sql}"
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()['total']
    
    # Get paginated data with dynamic sorting - JOIN with deal_list for shop_id mapping
    data_query = f'''
        SELECT 
            g.item_id, 
            g.item_name, 
            g.revenue, 
            COALESCE(d.shop_id, g.shop_id) as shop_id,
            CASE 
                WHEN COALESCE(d.shop_id, g.shop_id) IS NOT NULL AND COALESCE(d.shop_id, g.shop_id) != ''
                THEN 'https://shopee.vn/a-i.' || COALESCE(d.shop_id, g.shop_id) || '.' || g.item_id
                ELSE g.link_sp
            END as link_sp,
            g.datetime, 
            g.clicks, 
            g.ctr, 
            g.orders, 
            g.items_sold, 
            g.confirmed_revenue,
            COALESCE(d.cluster, g.cluster) as cluster, 
            g.add_to_cart
        FROM gmv_data g
        LEFT JOIN deal_list d ON g.item_id = d.item_id
        {where_sql}
        ORDER BY g.{sort_by} {sort_dir.upper()}
        LIMIT %s OFFSET %s
    '''
    cursor.execute(data_query, params + [per_page, offset])
    
    rows = cursor.fetchall()
    
    # Also get all unique shop_ids for filter dropdown - JOIN with deal_list
    cursor.execute('''
        SELECT DISTINCT COALESCE(d.shop_id, g.shop_id) as shop_id 
        FROM gmv_data g
        LEFT JOIN deal_list d ON g.item_id = d.item_id
        WHERE COALESCE(d.shop_id, g.shop_id) IS NOT NULL 
          AND COALESCE(d.shop_id, g.shop_id) != ''
        ORDER BY shop_id
    ''')
    shop_ids = [row['shop_id'] for row in cursor.fetchall()]
    
    # Get stats (total revenue, total clicks for summary)
    stats_query = f'''
        SELECT 
            COUNT(*) as total_products,
            COALESCE(SUM(revenue), 0) as total_revenue,
            COALESCE(SUM(clicks), 0) as total_clicks,
            COALESCE(SUM(orders), 0) as total_orders,
            COALESCE(SUM(items_sold), 0) as total_items_sold,
            COALESCE(SUM(confirmed_revenue), 0) as total_confirmed_revenue,
            COUNT(CASE WHEN link_sp IS NOT NULL AND link_sp != '' THEN 1 END) as with_link
        FROM gmv_data
        {where_sql}
    '''
    cursor.execute(stats_query, params)
    stats = cursor.fetchone()
    # Get latest datetime from gmv_data
    cursor.execute('SELECT MAX(datetime) as latest_datetime FROM gmv_data')
    datetime_row = cursor.fetchone()
    latest_datetime = datetime_row['latest_datetime'] if datetime_row else None
    conn.close()
    
    data = []
    for row in rows:
        data.append({
            'item_id': row['item_id'],
            'item_name': row['item_name'],
            'revenue': row['revenue'],
            'shop_id': row['shop_id'],
            'link_sp': row['link_sp'],
            'datetime': row['datetime'],
            'clicks': row['clicks'],
            'ctr': row['ctr'],
            'orders': row['orders'],
            'items_sold': row['items_sold'],
            'cluster': row['cluster'],
            'add_to_cart': row.get('add_to_cart', 0),
            'confirmed_revenue': row.get('confirmed_revenue', 0)
        })
    
    total_pages = (total_count + per_page - 1) // per_page
    
    return jsonify({
        'success': True,
        'data': data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        },
        'stats': {
            'total_products': stats['total_products'],
            'total_revenue': stats['total_revenue'],
            'total_clicks': stats['total_clicks'],
            'total_orders': stats['total_orders'],
            'total_items_sold': stats['total_items_sold'],
            'total_confirmed_revenue': stats['total_confirmed_revenue'],
            'with_link': stats['with_link']
        },
        'shop_ids': shop_ids,
        'last_sync': latest_datetime
    })

@app.route('/api/all-data')
def api_all_data():
    """API: Get ALL data with server-side caching (for client-side processing)"""
    # Sort params
    sort_by = request.args.get('sort_by', '', type=str).strip()
    sort_dir = request.args.get('sort_dir', 'desc', type=str).strip().lower()
    
    # Session filter param
    session_id = request.args.get('session_id', '', type=str).strip()
    
    # Validate sort params
    allowed_sort_columns = ['revenue', 'clicks', 'add_to_cart', 'orders', 'confirmed_revenue', 'items_sold']
    if sort_by and sort_by not in allowed_sort_columns:
        sort_by = ''
    if sort_dir not in ['asc', 'desc']:
        sort_dir = 'desc'
    
    # Build cache key based on sort and session
    cache_key = f"{sort_by}_{sort_dir}_{session_id}" if sort_by or session_id else "no_sort"
    
    # Check cache first (only if same sort)
    cached = get_cached_data()
    if cached is not None and data_cache.get('sort_key') == cache_key:
        print(f"[CACHE] Serving {len(cached)} products from cache (sort: {cache_key})")
        return jsonify({
            'success': True,
            'data': cached,
            'shop_ids': data_cache['shop_ids'],
            'stats': data_cache['stats'],
            'last_sync': data_cache.get('latest_datetime'),
            'from_cache': True
        })
    
    # Cache miss - load from database
    print(f"[CACHE] Cache miss, loading from database (sort: {cache_key}, session: {session_id})...")
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Build WHERE clause for session filter
    where_clause = ""
    params = []
    if session_id:
        where_clause = "WHERE g.session_id = %s"
        params = [session_id]
    
    # Determine which deal_list to use based on session mapping
    deallist_table = "deal_list"
    if session_id:
        deallist_id = get_deallist_for_session(session_id)
        if deallist_id == 2:
            deallist_table = "deal_list_2"
            print(f"[API] Using deal_list_2 for session {session_id}")
    
    # Build ORDER BY clause
    order_clause = f"ORDER BY g.{sort_by} {sort_dir.upper()}" if sort_by else ""
    
    # Get all data with optional ORDER BY and session filter - JOIN with appropriate deal_list
    query = f'''
        SELECT 
            g.item_id, g.item_name, g.revenue,
            COALESCE(d.shop_id, g.shop_id) as shop_id,
            CASE 
                WHEN COALESCE(d.shop_id, g.shop_id) IS NOT NULL AND COALESCE(d.shop_id, g.shop_id) != ''
                THEN 'https://shopee.vn/a-i.' || COALESCE(d.shop_id, g.shop_id) || '.' || g.item_id
                ELSE g.link_sp
            END as link_sp,
            g.datetime, g.clicks, g.ctr, g.orders, g.items_sold, g.confirmed_revenue,
            COALESCE(d.cluster, g.cluster) as cluster, g.add_to_cart,
            g.session_id, g.session_title
        FROM gmv_data g
        LEFT JOIN {deallist_table} d ON g.item_id = d.item_id
        {where_clause}
        {order_clause}
    '''
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Get shop_ids - JOIN with deal_list to get all shop_ids including from deal_list
    cursor.execute('''
        SELECT DISTINCT COALESCE(d.shop_id, g.shop_id) as shop_id 
        FROM gmv_data g
        LEFT JOIN deal_list d ON g.item_id = d.item_id
        WHERE COALESCE(d.shop_id, g.shop_id) IS NOT NULL 
          AND COALESCE(d.shop_id, g.shop_id) != ''
        ORDER BY shop_id
    ''')
    shop_ids = [row['shop_id'] for row in cursor.fetchall()]
    
    # Get stats
    cursor.execute('''
        SELECT 
            COUNT(*) as total_products,
            COALESCE(SUM(revenue), 0) as total_revenue,
            COALESCE(SUM(clicks), 0) as total_clicks,
            COALESCE(SUM(orders), 0) as total_orders,
            COALESCE(SUM(items_sold), 0) as total_items_sold,
            COALESCE(SUM(confirmed_revenue), 0) as total_confirmed_revenue,
            COUNT(CASE WHEN link_sp IS NOT NULL AND link_sp != '' THEN 1 END) as with_link
        FROM gmv_data
    ''')
    stats_row = cursor.fetchone()
    # Get latest datetime from gmv_data
    cursor.execute('SELECT MAX(datetime) as latest_datetime FROM gmv_data')
    datetime_row = cursor.fetchone()
    latest_datetime = datetime_row['latest_datetime'] if datetime_row else None
    conn.close()
    
    # Convert to list of dicts
    data = []
    for row in rows:
        data.append({
            'item_id': row['item_id'],
            'item_name': row['item_name'],
            'revenue': row['revenue'],
            'shop_id': row['shop_id'],
            'link_sp': row['link_sp'],
            'datetime': row['datetime'],
            'clicks': row['clicks'],
            'ctr': row['ctr'],
            'orders': row['orders'],
            'items_sold': row['items_sold'],
            'cluster': row['cluster'],
            'add_to_cart': row.get('add_to_cart', 0),
            'confirmed_revenue': row.get('confirmed_revenue', 0)
        })
    
    stats = {
        'total_products': stats_row['total_products'],
        'total_revenue': stats_row['total_revenue'],
        'total_clicks': stats_row['total_clicks'],
        'total_orders': stats_row['total_orders'],
        'total_items_sold': stats_row['total_items_sold'],
        'total_confirmed_revenue': stats_row['total_confirmed_revenue'],
        'with_link': stats_row['with_link']
    }
    
    # Store in cache with sort key
    set_cached_data(data, shop_ids, stats)
    data_cache['sort_key'] = cache_key
    data_cache['latest_datetime'] = latest_datetime
    
    return jsonify({
        'success': True,
        'data': data,
        'shop_ids': shop_ids,
        'stats': stats,
        'last_sync': latest_datetime,
        'from_cache': False
    })

@app.route('/api/sheets', methods=['POST'])
@admin_required
def api_get_sheets():
    """API: Get list of sheets from spreadsheet URL AND save config"""
    data = request.get_json()
    spreadsheet_url = data.get('spreadsheet_url', '')
    deallist_sheet = data.get('deallist_sheet', '')
    
    if not spreadsheet_url:
        return jsonify({'success': False, 'error': 'URL không được để trống'})
    
    # Save config if provided
    set_config('spreadsheet_url', spreadsheet_url)
    if deallist_sheet:
        set_config('deallist_sheet', deallist_sheet)
    
    try:
        sheets = get_spreadsheet_sheets(spreadsheet_url)
        return jsonify({'success': True, 'sheets': sheets})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/config', methods=['POST'])
@admin_required
def api_save_config():
    """API: Save general config values"""
    data = request.get_json()
    
    # Save deallist2 config if provided
    if 'deallist2_url' in data:
        set_config('deallist2_url', data['deallist2_url'])
    if 'deallist2_sheet' in data:
        set_config('deallist2_sheet', data['deallist2_sheet'])
    
    return jsonify({'success': True, 'message': 'Config saved'})


@app.route('/api/sync', methods=['POST'])
@admin_required
def api_sync():
    """API: Sync data from Google Sheets to SQLite"""
    data = request.get_json()
    spreadsheet_url = data.get('spreadsheet_url', '')
    rawdata_sheet = data.get('rawdata_sheet', '')
    deallist_sheet = data.get('deallist_sheet', '')
    
    if not all([spreadsheet_url, rawdata_sheet, deallist_sheet]):
        return jsonify({'success': False, 'error': 'Vui lòng điền đầy đủ thông tin'})
    
    try:
        # Save config
        set_config('spreadsheet_url', spreadsheet_url)
        set_config('rawdata_sheet', rawdata_sheet)
        set_config('deallist_sheet', deallist_sheet)
        
        # Sync data
        count = sync_data_from_sheets(spreadsheet_url, rawdata_sheet, deallist_sheet)
        
        return jsonify({
            'success': True,
            'message': f'Đã sync thành công {count} sản phẩm',
            'count': count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/refresh-deallist', methods=['POST'])
@admin_required
def api_refresh_deallist():
    """API: Refresh Deal List mapping only (shop_id, link_sp, cluster) without touching GMV data"""
    spreadsheet_url = get_config('spreadsheet_url')
    deallist_sheet = get_config('deallist_sheet')
    
    if not spreadsheet_url or not deallist_sheet:
        return jsonify({'success': False, 'error': 'Chưa cấu hình spreadsheet URL hoặc Deal List sheet'})
    
    try:
        count, sheet_title = sync_deallist_only(spreadsheet_url, deallist_sheet)
        
        # Parse sheet title để lấy tên ngắn gọn
        from db_helpers import parse_sheet_title
        parsed_title = parse_sheet_title(sheet_title)
        
        # Lưu parsed title vào config để dùng cho session hiện tại
        if parsed_title:
            set_config('current_session_title', parsed_title)
            
            # Update session_title cho tất cả session active (chưa archive)
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE gmv_data 
                SET session_title = %s 
                WHERE (is_archived IS NULL OR is_archived = FALSE)
            ''',(parsed_title,))
            updated_rows = cursor.rowcount
            
            # Cũng update session_title trong gmv_history cho History page
            cursor.execute('''
                UPDATE gmv_history 
                SET session_title = %s 
            ''', (parsed_title,))
            history_updated = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Đã cập nhật {count} items. Session title: {parsed_title} ({updated_rows} rows updated)',
                'count': count,
                'parsed_title': parsed_title
            })
        
        return jsonify({
            'success': True,
            'message': f'Đã cập nhật {count} items với shop_id/link/cluster',
            'count': count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/refresh-deallist2', methods=['POST'])
@admin_required
def api_refresh_deallist2():
    """API: Refresh Deal List 2 mapping"""
    spreadsheet_url = get_config('deallist2_url')
    deallist_sheet = get_config('deallist2_sheet')
    
    if not spreadsheet_url or not deallist_sheet:
        return jsonify({'success': False, 'error': 'Chưa cấu hình Deal List 2 URL hoặc sheet'})
    
    try:
        count, sheet_title = sync_deallist2_only(spreadsheet_url, deallist_sheet)
        
        # Parse sheet title để lấy tên ngắn gọn
        from db_helpers import parse_sheet_title
        parsed_title = parse_sheet_title(sheet_title)
        
        if parsed_title:
            # Lấy danh sách session_id dùng Deal List 2
            mapping = get_session_deallist_mapping()
            sessions_using_dl2 = [sid for sid, dlid in mapping.items() if dlid == 2]
            
            updated_rows = 0
            if sessions_using_dl2:
                conn = get_db()
                cursor = conn.cursor()
                # Update session_title CHỈ cho các sessions dùng Deal List 2
                cursor.execute('''
                    UPDATE gmv_data 
                    SET session_title = %s 
                    WHERE session_id = ANY(%s)
                      AND (is_archived IS NULL OR is_archived = FALSE)
                ''', (parsed_title, sessions_using_dl2))
                updated_rows = cursor.rowcount
                
                # Cũng update session_title trong gmv_history cho History page
                cursor.execute('''
                    UPDATE gmv_history 
                    SET session_title = %s 
                    WHERE session_id = ANY(%s)
                ''', (parsed_title, sessions_using_dl2))
                history_updated = cursor.rowcount
                
                conn.commit()
                conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Đã cập nhật {count} items. Session title: {parsed_title} ({updated_rows} rows updated)',
                'count': count,
                'parsed_title': parsed_title
            })
        
        return jsonify({
            'success': True,
            'message': f'Đã cập nhật {count} items vào Deal List 2',
            'count': count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/session-deallist', methods=['GET'])
@admin_required
def api_get_session_deallist():
    """API: Get all session -> deallist mappings"""
    try:
        mapping = get_session_deallist_mapping()
        return jsonify({
            'success': True,
            'mapping': mapping
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/session-deallist', methods=['POST'])
@admin_required
def api_set_session_deallist():
    """API: Set which deallist a session uses"""
    data = request.get_json()
    session_id = data.get('session_id', '')
    deallist_id = int(data.get('deallist_id', 1))
    
    if not session_id:
        return jsonify({'success': False, 'error': 'session_id is required'})
    
    if deallist_id not in [1, 2]:
        return jsonify({'success': False, 'error': 'deallist_id must be 1 or 2'})
    
    try:
        set_session_deallist_mapping(session_id, deallist_id)
        return jsonify({
            'success': True,
            'message': f'Session {session_id} now uses Deal List {deallist_id}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/deallist-count')
def api_deallist_count():
    """API: Get count of items in both deal lists"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM deal_list')
        count1 = cursor.fetchone()[0]
        
        # Check if deal_list_2 exists
        cursor.execute('''
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'deal_list_2'
        ''')
        if cursor.fetchone()[0] > 0:
            cursor.execute('SELECT COUNT(*) FROM deal_list_2')
            count2 = cursor.fetchone()[0]
        else:
            count2 = 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'deallist1_count': count1,
            'deallist2_count': count2
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============== Multi-Session API Routes ==============

@app.route('/api/sessions')
def api_sessions():
    """API: Get list of active sessions in gmv_data"""
    try:
        sessions = get_active_sessions(DATABASE_URL)
        
        # Format timestamps for JSON
        formatted_sessions = []
        for s in sessions:
            formatted_sessions.append({
                'session_id': s.get('session_id'),
                'session_title': s.get('session_title') or f"Session {s.get('session_id', '')}",
                'item_count': s.get('item_count', 0),
                'last_scraped': s.get('last_scraped').isoformat() if s.get('last_scraped') else None
            })
        
        return jsonify({
            'success': True,
            'sessions': formatted_sessions,
            'count': len(formatted_sessions)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'sessions': []})


@app.route('/api/archived-sessions')
@admin_required
def api_archived_sessions():
    """API: Get list of archived sessions from gmv_history"""
    try:
        from db_helpers import get_archived_sessions
        sessions = get_archived_sessions(DATABASE_URL)
        
        formatted_sessions = []
        for s in sessions:
            formatted_sessions.append({
                'session_id': s.get('session_id'),
                'session_title': s.get('session_title') or f"Session {s.get('session_id', '')}",
                'item_count': s.get('item_count', 0),
                'timeslot_count': s.get('timeslot_count', 0),
                'last_archived': s.get('last_archived').isoformat() if s.get('last_archived') else None
            })
        
        return jsonify({
            'success': True,
            'sessions': formatted_sessions,
            'count': len(formatted_sessions)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'sessions': []})


@app.route('/api/history/timeslots')
def api_history_timeslots():
    """API: Get available archive timeslots for a session"""
    session_id = request.args.get('session_id', '')
    
    if not session_id:
        return jsonify({'success': False, 'error': 'session_id is required', 'timeslots': []})
    
    try:
        timeslots = get_history_timeslots(DATABASE_URL, session_id)
        
        # Format timestamps
        formatted_timeslots = []
        for t in timeslots:
            archived_at = t.get('archived_at')
            if archived_at:
                formatted_timeslots.append({
                    'archived_at': archived_at.isoformat() if hasattr(archived_at, 'isoformat') else str(archived_at),
                    'item_count': t.get('item_count', 0)
                })
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'timeslots': formatted_timeslots,
            'count': len(formatted_timeslots)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'timeslots': []})


@app.route('/api/history/data')
def api_history_data():
    """API: Get historical data for a session at a specific archived time"""
    session_id = request.args.get('session_id', '')
    archived_at = request.args.get('archived_at', '')
    
    if not session_id or not archived_at:
        return jsonify({'success': False, 'error': 'session_id and archived_at are required', 'data': []})
    
    try:
        data = get_history_data(DATABASE_URL, session_id, archived_at)
        
        # Calculate stats
        total_gmv = sum(d.get('revenue', 0) or 0 for d in data)
        total_nmv = sum(d.get('confirmed_revenue', 0) or 0 for d in data)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'archived_at': archived_at,
            'data': data,
            'count': len(data),
            'stats': {
                'total_gmv': total_gmv,
                'total_nmv': total_nmv,
                'gap': total_gmv - total_nmv
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'data': []})

@app.route('/api/analytics/top-products')
def api_analytics_top_products():
    """API: Get top 10 products by selected metric for chart"""
    try:
        metric = request.args.get('metric', 'revenue')
        session_id = request.args.get('session_id', '')  # 🆕
        
        # Validate metric
        valid_metrics = ['revenue', 'clicks', 'add_to_cart', 'orders']
        if metric not in valid_metrics:
            metric = 'revenue'
        
        # 🆕 Build WHERE clause
        where_clause = ""
        params = []
        if session_id:
            where_clause = "WHERE g.session_id = %s"
            params = [session_id]
        
        conn = get_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(f'''
            SELECT g.item_name as name, g.revenue, g.clicks, g.add_to_cart, g.orders
            FROM gmv_data g
            {where_clause}
            ORDER BY g.{metric} DESC NULLS LAST
            LIMIT 10
        ''', params)
        rows = cursor.fetchall()
        conn.close()
        return jsonify({'success': True, 'data': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
@app.route('/api/analytics/category-distribution')
def api_analytics_category_distribution():
    """API: Get metric distribution by cluster (category)"""
    try:
        metric = request.args.get('metric', 'revenue')
        session_id = request.args.get('session_id', '')
        
        valid_metrics = ['revenue', 'clicks', 'add_to_cart', 'orders']
        if metric not in valid_metrics:
            metric = 'revenue'
        
        # Build WHERE clause
        where_clause = ""
        params = []
        if session_id:
            where_clause = "WHERE g.session_id = %s"
            params = [session_id]
        
        # Determine which deal_list to use based on session mapping
        deallist_table = "deal_list"
        if session_id:
            deallist_id = get_deallist_for_session(session_id)
            if deallist_id == 2:
                deallist_table = "deal_list_2"
                print(f"[CHART] Using deal_list_2 for session {session_id}")
        
        conn = get_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(f'''
            SELECT 
                COALESCE(d.cluster, g.cluster, 'Không xác định') as cluster,
                SUM(g.revenue) as revenue,
                SUM(g.clicks) as clicks,
                SUM(g.add_to_cart) as add_to_cart,
                SUM(g.orders) as orders,
                COUNT(*) as count
            FROM gmv_data g
            LEFT JOIN {deallist_table} d ON g.item_id = d.item_id
            {where_clause}
            GROUP BY COALESCE(d.cluster, g.cluster, 'Không xác định')
            ORDER BY {metric} DESC NULLS LAST
        ''', params)
        rows = cursor.fetchall()
        conn.close()
        return jsonify({'success': True, 'data': [dict(r) for r in rows], 'metric': metric})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cache-status')
def api_cache_status():
    """API: Get cache/data status"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Count GMV items
    cursor.execute('SELECT COUNT(*) FROM gmv_data')
    gmv_count = cursor.fetchone()[0]
    
    # Count items with shop_id (mapped from deal list)
    cursor.execute("SELECT COUNT(*) FROM gmv_data WHERE shop_id IS NOT NULL AND shop_id != ''")
    mapped_count = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'gmv': {
            'count': gmv_count,
            'last_update': get_config('last_sync'),
            'age_seconds': 0,
            'ttl': 300
        },
        'deallist': {
            'count': mapped_count,
            'last_update': get_config('last_deallist_sync'),
            'age_seconds': 0,
            'ttl': 7200
        }
    })

# ============== Auto-Sync API Routes ==============

@app.route('/api/auto-sync/status')
@admin_required
def api_auto_sync_status():
    """API: Get auto-sync status"""
    return jsonify({
        'success': True,
        'running': auto_sync_state['running'],
        'end_time': auto_sync_state['end_time'],
        'last_auto_sync': auto_sync_state['last_auto_sync'],
        'next_sync': auto_sync_state['next_sync']
    })

@app.route('/api/auto-sync/start', methods=['POST'])
@admin_required
def api_auto_sync_start():
    """API: Start auto-sync scheduler (every 5 minutes continuously)"""
    # Check if config exists
    spreadsheet_url = get_config('spreadsheet_url')
    rawdata_sheet = get_config('rawdata_sheet')
    deallist_sheet = get_config('deallist_sheet')
    
    if not all([spreadsheet_url, rawdata_sheet, deallist_sheet]):
        return jsonify({'success': False, 'error': 'Chưa cấu hình Google Sheets. Vui lòng sync thủ công trước.'})
    
    result = start_auto_sync()
    if not result:
        return jsonify({'success': False, 'error': 'Scheduler chưa sẵn sàng. Vui lòng restart server.'})
    
    return jsonify({
        'success': True,
        'message': 'Auto-sync đã bắt đầu. Sẽ sync mỗi 5 phút liên tục.'
    })

@app.route('/api/auto-sync/stop', methods=['POST'])
@admin_required
def api_auto_sync_stop():
    """API: Stop auto-sync scheduler"""
    stop_auto_sync()
    return jsonify({'success': True, 'message': 'Auto-sync đã dừng'})

@app.route('/api/config')
@admin_required
def api_config():
    """API: Get current config"""
    return jsonify({
        'success': True,
        'config': {
            'spreadsheet_url': get_config('spreadsheet_url') or '',
            'rawdata_sheet': get_config('rawdata_sheet') or '',
            'deallist_sheet': get_config('deallist_sheet') or '',
            'last_sync': get_config('last_sync') or 'Chưa sync'
        }
    })

@app.route('/api/analytics/category-distribution')
def api_category_distribution():
    """API: Get revenue distribution by cluster/category"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('''
        SELECT cluster, SUM(revenue) as total_revenue, COUNT(*) as product_count
        FROM gmv_data
        WHERE cluster IS NOT NULL AND cluster != ''
        GROUP BY cluster
        ORDER BY total_revenue DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    data = []
    for row in rows:
        data.append({
            'cluster': row['cluster'],
            'revenue': row['total_revenue'],
            'count': row['product_count']
        })
    
    return jsonify({
        'success': True,
        'data': data
    })

@app.route('/api/analytics/top-products')
def api_top_products():
    """API: Get top 10 products for bar chart"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('''
        SELECT item_name, revenue, orders
        FROM gmv_data
        ORDER BY revenue DESC
        LIMIT 10
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    data = []
    for row in rows:
        # Shorten name for chart label
        name = row['item_name'] or 'N/A'
        if len(name) > 30:
            name = name[:30] + '...'
        data.append({
            'name': name,
            'revenue': row['revenue'] or 0,
            'orders': row['orders'] or 0
        })
    
    return jsonify({
        'success': True,
        'data': data
    })

# ============== Raw Session Data APIs ==============

@app.route('/api/sync-raw-monthly', methods=['POST'])
@admin_required
def api_sync_raw_monthly():
    """API: Sync raw monthly data from MERGE STACK sheet"""
    data = request.get_json()
    spreadsheet_url = data.get('spreadsheet_url', '')
    sheet_name = data.get('sheet_name', '')
    
    if not spreadsheet_url or not sheet_name:
        return jsonify({'success': False, 'error': 'URL và tên sheet không được để trống'})
    
    try:
        # Save config
        set_config('rawdata_monthly_url', spreadsheet_url)
        set_config('rawdata_monthly_sheet', sheet_name)
        
        # Get credentials
        gc = get_gspread_client()
        if not gc:
            return jsonify({'success': False, 'error': 'Không thể kết nối Google Sheets'})
        
        # Open spreadsheet
        spreadsheet = gc.open_by_url(spreadsheet_url)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # Get all data
        all_data = worksheet.get_all_records()
        
        if not all_data:
            return jsonify({'success': False, 'error': 'Sheet không có dữ liệu'})
        
        # Find column mappings
        first_row = all_data[0]
        keys = list(first_row.keys())
        
        item_name_col = None
        item_id_col = None
        revenue_col = None
        clicks_col = None
        file_col = None
        session_col = None
        
        for key in keys:
            key_lower = key.lower().replace(' ', '').replace('_', '')
            key_original = key.lower()
            
            # Match product name column
            if item_name_col is None:
                if 'tên sản phẩm' in key_original or 'tensanpham' in key_lower or 'tênsp' in key_lower or 'tensp' in key_lower or 'itemname' in key_lower or 'productname' in key_lower:
                    item_name_col = key
            
            # Match item ID column
            if item_id_col is None:
                if 'item id' in key_original or 'itemid' in key_lower:
                    item_id_col = key
            
            # Match revenue column
            if revenue_col is None:
                if 'doanh thu' in key_original or 'doanhthu' in key_lower or 'revenue' in key_lower:
                    revenue_col = key
            
            # Match clicks column
            if clicks_col is None:
                if 'click' in key_lower:
                    clicks_col = key
            
            # Match file column
            if file_col is None:
                if 'file' in key_lower:
                    file_col = key
            
            # Match session column
            if session_col is None:
                if 'phiên' in key_original or 'phien' in key_lower or 'session' in key_lower:
                    session_col = key
        
        if not item_id_col:
            return jsonify({'success': False, 'error': 'Không tìm thấy cột Item ID'})
        
        # Log detected columns for debugging
        print(f"[SYNC DEBUG] Headers: {keys}")
        print(f"[SYNC DEBUG] Detected: item_name_col={item_name_col}, item_id_col={item_id_col}, revenue_col={revenue_col}, clicks_col={clicks_col}, file_col={file_col}, session_col={session_col}")
        
        # Clear old data and insert new
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM raw_session_data')
        
        count = 0
        for row in all_data:
            item_id = str(row.get(item_id_col, '')).strip()
            if not item_id:
                continue
            
            item_name = str(row.get(item_name_col, '')).strip() if item_name_col else ''
            
            # Parse revenue
            revenue_raw = row.get(revenue_col, 0) if revenue_col else 0
            if isinstance(revenue_raw, str):
                revenue_raw = revenue_raw.replace(',', '').replace('.', '')
            try:
                revenue = int(revenue_raw)
            except:
                revenue = 0
            
            # Parse clicks
            clicks_raw = row.get(clicks_col, 0) if clicks_col else 0
            if isinstance(clicks_raw, str):
                clicks_raw = clicks_raw.replace(',', '')
            try:
                clicks = int(clicks_raw)
            except:
                clicks = 0
            
            file_name = str(row.get(file_col, '')).strip() if file_col else ''
            session_name = str(row.get(session_col, '')).strip() if session_col else ''
            
            cursor.execute('''
                INSERT INTO raw_session_data (item_name, item_id, revenue, clicks, file_name, session_name)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (item_name, item_id, revenue, clicks, file_name, session_name))
            count += 1
        
        conn.commit()
        conn.close()
        
        # Save sync time
        from datetime import datetime
        set_config('rawdata_monthly_sync', datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S'))
        
        return jsonify({'success': True, 'count': count})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/item-analytics/<item_id>')
def api_item_analytics(item_id):
    """API: Get analytics data for specific item"""
    import re
    
    def parse_session_date(session_name):
        """Parse session name like '1.12', '11.12 S2' to sortable tuple"""
        if not session_name:
            return (99, 99, '')
        match = re.match(r'^(\d{1,2})\.(\d{1,2})(?:\s*(.*))?$', session_name.strip())
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            suffix = match.group(3) or ''
            return (month, day, suffix)
        return (99, 99, session_name)
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute('''
        SELECT item_name, revenue, clicks, file_name, session_name
        FROM raw_session_data
        WHERE item_id = %s
    ''', (item_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return jsonify({'success': False, 'error': 'Không tìm thấy Item ID'})
    
    # Sort rows by date
    rows_list = [dict(row) for row in rows]
    rows_list.sort(key=lambda x: parse_session_date(x.get('session_name', '')))
    
    sessions = []
    total_revenue = 0
    total_clicks = 0
    item_name = ''
    
    # Get first non-empty item_name from raw_session_data
    for row in rows_list:
        if row.get('item_name') and row['item_name'].strip():
            item_name = row['item_name'].strip()
            break
    
    # Fallback: Get item_name from gmv_data table if not found
    if not item_name:
        conn2 = get_db()
        cursor2 = conn2.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor2.execute('SELECT item_name FROM gmv_data WHERE item_id = %s', (item_id,))
        gmv_row = cursor2.fetchone()
        conn2.close()
        if gmv_row and gmv_row['item_name']:
            item_name = gmv_row['item_name']
    
    for row in rows_list:
        sessions.append({
            'session': row.get('session_name') or 'N/A',
            'file': row.get('file_name') or 'N/A',
            'revenue': row.get('revenue') or 0,
            'clicks': row.get('clicks') or 0
        })
        total_revenue += row.get('revenue') or 0
        total_clicks += row.get('clicks') or 0
    
    return jsonify({
        'success': True,
        'item_id': item_id,
        'item_name': item_name,
        'total_revenue': total_revenue,
        'total_clicks': total_clicks,
        'session_count': len(sessions),
        'sessions': sessions
    })

@app.route('/api/rawdata-config')
@admin_required
def api_rawdata_config():
    """API: Get raw data config"""
    return jsonify({
        'success': True,
        'config': {
            'url': get_config('rawdata_monthly_url') or '',
            'sheet': get_config('rawdata_monthly_sheet') or '',
            'last_sync': get_config('rawdata_monthly_sync') or 'Chưa sync'
        }
    })

# ============== Main ==============

# Initialize database tables on module import (required for gunicorn)
try:
    init_db()
    print("[DB] Database tables initialized")
except Exception as e:
    print(f"[DB WARNING] init_db failed: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
