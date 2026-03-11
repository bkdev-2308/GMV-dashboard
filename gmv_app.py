# -*- coding: utf-8 -*-
"""
GMV App - Gộp Scraper + Web Dashboard

Mode:
  --gui   : Chạy Scraper GUI (PyQt6) - mặc định
  --web   : Chạy Flask Web Server

Luồng hoạt động:
  Scraper (GUI) → ghi song song 3 nơi:
    1. CSV (local file)
    2. Google Sheet (Raw Data)
    3. SQLite (gmv_dashboard.db)
  Web → chỉ sync Deal List (shop_id, cluster, link)
"""
import asyncio
import json
import os
import sys
import re
import csv
import argparse
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import threading

# Import Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    print("⚠️ gspread không được cài. Chạy: pip install gspread google-auth")

# Import PostgreSQL helper
try:
    from db_helpers import (
        save_to_postgresql, save_deal_list_to_postgresql, 
        get_gmv_with_deallist, HAS_PSYCOPG2,
        # Multi-session functions
        save_to_postgresql_multi_session, archive_session_data, 
        init_multi_session_tables
    )
except ImportError:
    HAS_PSYCOPG2 = False
    def save_to_postgresql(*args, **kwargs):
        print("⚠️ db_helpers không tìm thấy")
        return False
    def save_deal_list_to_postgresql(*args, **kwargs):
        print("⚠️ db_helpers không tìm thấy")
        return 0
    def get_gmv_with_deallist(*args, **kwargs):
        print("⚠️ db_helpers không tìm thấy")
        return []
    def save_to_postgresql_multi_session(*args, **kwargs):
        print("⚠️ db_helpers không tìm thấy")
        return False
    def archive_session_data(*args, **kwargs):
        print("⚠️ db_helpers không tìm thấy")
        return False
    def init_multi_session_tables(*args, **kwargs):
        print("⚠️ db_helpers không tìm thấy")
        return False

# ============== Common Config ==============

# Thêm path để import module gốc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Database path
DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), 'gmv_dashboard.db'))

# Service Account Key path
SERVICE_ACCOUNT_KEY = os.path.join(os.path.dirname(__file__), "service-account-key.json")

# Output directory for CSV
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# CSV Header mở rộng với coverImage và Confirmed data
CSV_HEADER_API = [
    "DateTime", "Item ID", "Tên sản phẩm", "coverImage",
    "Lượt click trên sản phẩm", "Tỷ lệ click vào sản phẩm",
    "Tổng đơn hàng", "Các mặt hàng được bán", "Doanh thu",
    "Tỷ lệ click để đặt hàng", "Thêm vào giỏ hàng",
    "NMV (Confirmed Revenue)", "Tổng đơn hàng (Confirmed)", "Các mặt hàng được bán (Confirmed)"
]

# Google Sheets scope
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Raw Data Sheet ID - Scraper ghi vào đây, Web đọc từ đây
RAW_DATA_SHEET_ID = os.environ.get('RAW_DATA_SHEET_ID', '1DVnQERNWJWDF3LCxVSsa7nenNppRz9CWZ4dzKiE05Lc')

# Cache config
GMV_CACHE_TTL = 300  # 5 phút cho GMV data
DEALLIST_CACHE_TTL = 7200  # 2 tiếng cho Deal List

# GMV Cache
_gmv_cache = {
    'data': None,
    'timestamp': None
}

# Deal List Cache (shop_id, cluster mapping)
_deallist_cache = {
    'item_to_shop': {},
    'item_to_cluster': {},
    'timestamp': None
}

# Admin password from environment
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# ============== Database Functions ==============

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
            cover_image TEXT,
            revenue INTEGER,
            shop_id TEXT,
            link_sp TEXT,
            datetime TEXT,
            clicks INTEGER,
            ctr TEXT,
            orders INTEGER,
            items_sold INTEGER,
            confirmed_revenue INTEGER,
            cluster TEXT
        )
    ''')
    
    # Add confirmed_revenue column if not exists
    try:
        cursor.execute('ALTER TABLE gmv_data ADD COLUMN confirmed_revenue INTEGER DEFAULT 0')
    except:
        pass  # Column already exists
    
    # Add cover_image column if not exists
    try:
        cursor.execute('ALTER TABLE gmv_data ADD COLUMN cover_image TEXT')
    except:
        pass  # Column already exists
    
    # Raw session data table (for monthly analytics)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_session_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT,
            item_id TEXT,
            revenue INTEGER,
            clicks INTEGER,
            file_name TEXT,
            session_name TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_config(key):
    """Get config value by key"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else None

def set_config(key, value):
    """Set config value"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)
    ''', (key, value))
    conn.commit()
    conn.close()

def save_to_sqlite(rows):
    """Ghi dữ liệu trực tiếp vào SQLite gmv_data table"""
    if not rows:
        return 0
    
    conn = get_db()
    cursor = conn.cursor()
    count = 0
    
    def parse_int(val):
        """Parse value to int, handling various formats"""
        if val is None or val == '':
            return 0
        if isinstance(val, (int, float)):
            return int(val)
        # Remove common formatting characters
        cleaned = str(val).replace(',', '').replace('.', '').replace('₫', '').replace('%', '').strip()
        try:
            return int(cleaned) if cleaned else 0
        except ValueError:
            try:
                return int(float(cleaned))
            except:
                return 0
    
    for row in rows:
        try:
            # row format from scraper:
            # [0] DateTime, [1] Item ID, [2] Tên SP, [3] Clicks, [4] CTR, 
            # [5] Orders, [6] Items Sold, [7] Revenue, [8] CTO, [9] ATC,
            # [10] NMV, [11] ConfOrders, [12] ConfItems
            if len(row) < 8:
                print(f"⚠️ Row quá ngắn ({len(row)} cols): {row[:3]}...")
                continue
            
            dt_str = str(row[0]) if row[0] else ''
            item_id = str(row[1]).strip() if row[1] else ''
            item_name = str(row[2]) if row[2] else ''
            cover_image = str(row[3]) if len(row) > 3 and row[3] else ''
            clicks = parse_int(row[4]) if len(row) > 4 else 0
            ctr = str(row[5]) if len(row) > 5 and row[5] else ''
            orders = parse_int(row[6]) if len(row) > 6 else 0
            items_sold = parse_int(row[7]) if len(row) > 7 else 0
            revenue = parse_int(row[8]) if len(row) > 8 else 0
            confirmed_revenue = parse_int(row[11]) if len(row) > 11 else 0
            
            if not item_id:
                continue
            
            # Debug first few items
            if count < 3:
                print(f"[SQLITE] Inserting: {item_id[:20]}... revenue={revenue}, orders={orders}")
            
            cursor.execute('''
                INSERT OR REPLACE INTO gmv_data 
                (item_id, item_name, cover_image, revenue, datetime, clicks, ctr, orders, items_sold, confirmed_revenue)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (item_id, item_name, cover_image, revenue, dt_str, clicks, ctr, orders, items_sold, confirmed_revenue))
            count += 1
            
        except Exception as e:
            print(f"⚠️ Lỗi ghi SQLite row: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    conn.commit()
    
    # Update last sync timestamp
    cursor.execute('''
        INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)
    ''', ('last_sync', datetime.now().isoformat()))
    conn.commit()
    
    conn.close()
    print(f"[SQLITE] Total saved: {count} items")
    return count

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
        if os.path.exists(SERVICE_ACCOUNT_KEY):
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY, scopes=SCOPES)
        else:
            raise Exception("No Google service account credentials found")
    
    return gspread.authorize(creds)

def get_spreadsheet_sheets(spreadsheet_url):
    """Get list of sheet names from spreadsheet"""
    client = get_gspread_client()
    spreadsheet = client.open_by_url(spreadsheet_url)
    return [sheet.title for sheet in spreadsheet.worksheets()]

def get_deallist_mapping(deallist_url=None, deallist_sheet_name=None, force_refresh=False):
    """
    Lấy Deal List mapping (item_id -> shop_id, cluster) với cache 2 tiếng.
    Returns: (item_to_shop dict, item_to_cluster dict)
    """
    global _deallist_cache
    
    # Trả về empty nếu không có config
    if not deallist_url or not deallist_sheet_name:
        return {}, {}
    
    # Kiểm tra cache (nếu không force_refresh)
    if not force_refresh and _deallist_cache['timestamp'] is not None:
        cache_age = (datetime.now() - _deallist_cache['timestamp']).total_seconds()
        if cache_age < DEALLIST_CACHE_TTL:
            print(f"[DEALLIST CACHE] Using cached ({cache_age:.0f}s / {DEALLIST_CACHE_TTL}s)")
            return _deallist_cache['item_to_shop'], _deallist_cache['item_to_cluster']
    
    print(f"[DEALLIST] Loading fresh data from Sheet...")
    
    item_to_shop = {}
    item_to_cluster = {}
    
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(deallist_url)
        sheet = spreadsheet.worksheet(deallist_sheet_name)
        
        # Lấy full data (A:Z để tránh filter)
        try:
            values = sheet.get('A:Z')
        except:
            values = sheet.get_all_values()
        
        print(f"[DEALLIST] Loaded {len(values)} rows")
        
        # Find header row
        header_idx = 0
        for idx, row in enumerate(values):
            row_text = ' '.join(str(c).lower() for c in row)
            if 'item' in row_text and 'id' in row_text:
                header_idx = idx
                break
        
        if header_idx < len(values):
            headers = values[header_idx]
            data = values[header_idx + 1:]
            
            # Find columns (ưu tiên finalitemid)
            item_col, shop_col, cluster_col = None, None, None
            for i, h in enumerate(headers):
                h_lower = h.lower().replace(' ', '').replace('_', '')
                if 'finalitemid' in h_lower:
                    item_col = i
                elif item_col is None and 'itemid' in h_lower and 'origin' not in h_lower:
                    item_col = i
                if 'shopid' in h_lower:
                    shop_col = i
                if 'cluster' in h_lower:
                    cluster_col = i
            
            print(f"[DEALLIST] Columns: item={item_col}, shop={shop_col}, cluster={cluster_col}")
            
            if item_col is not None and shop_col is not None:
                for row in data:
                    if len(row) > max(item_col, shop_col):
                        item_id = str(row[item_col]).strip()
                        shop_id_raw = str(row[shop_col]).strip()
                        
                        # Parse shop_id
                        if '+' in shop_id_raw:
                            shop_id = shop_id_raw.split('+')[-1]
                        else:
                            shop_id = shop_id_raw
                        shop_id = ''.join(c for c in shop_id if c.isdigit())
                        
                        if item_id and shop_id:
                            item_to_shop[item_id] = shop_id
                        
                        if cluster_col is not None and len(row) > cluster_col:
                            item_to_cluster[item_id] = str(row[cluster_col]).strip()
                
                print(f"[DEALLIST] Mapped {len(item_to_shop)} items")
        
        # Update cache
        _deallist_cache['item_to_shop'] = item_to_shop
        _deallist_cache['item_to_cluster'] = item_to_cluster
        _deallist_cache['timestamp'] = datetime.now()
        
    except Exception as e:
        print(f"[DEALLIST] Error: {e}")
    
    return item_to_shop, item_to_cluster

def get_gmv_from_sheet(limit=500, deallist_url=None, deallist_sheet_name=None, force_refresh=False):
    """
    Đọc GMV data trực tiếp từ Google Sheet (RAW_DATA_SHEET_ID).
    Kết hợp với Deal List để lấy shop_id, cluster, link.
    Sử dụng cache để tránh gọi API mỗi request.
    """
    global _gmv_cache
    
    # Kiểm tra cache (nếu không force_refresh)
    if not force_refresh and _gmv_cache['data'] is not None and _gmv_cache['timestamp'] is not None:
        cache_age = (datetime.now() - _gmv_cache['timestamp']).total_seconds()
        if cache_age < GMV_CACHE_TTL:
            print(f"[GMV CACHE] Using cached ({cache_age:.0f}s / {GMV_CACHE_TTL}s)")
            cached_data = _gmv_cache['data']
            return cached_data[:limit]
    
    print("[CACHE] Fetching fresh data from Google Sheet...")
    
    client = get_gspread_client()
    
    # 1. Đọc Raw Data Sheet
    spreadsheet = client.open_by_key(RAW_DATA_SHEET_ID)
    worksheet = spreadsheet.sheet1  # Sheet1
    
    all_values = worksheet.get_all_values()
    if not all_values or len(all_values) < 2:
        return []
    
    header = all_values[0]
    data_rows = all_values[1:]
    
    # 2. Lấy Deal List mapping từ cache
    item_to_shop, item_to_cluster = get_deallist_mapping(deallist_url, deallist_sheet_name, force_refresh=force_refresh)
    
    # 3. Parse GMV data
    # Header expected: DateTime, Item ID, Tên sản phẩm, Clicks, CTR, Orders, Items Sold, Revenue, ...
    def find_col(keywords):
        for i, h in enumerate(header):
            h_lower = h.lower().replace(' ', '')
            for kw in keywords:
                if kw in h_lower:
                    return i
        return None
    
    col_item_id = find_col(['itemid'])
    col_item_name = find_col(['tênsp', 'tênsan', 'tensanpham', 'sảnphẩm'])
    col_revenue = find_col(['doanhthu', 'revenue'])
    col_clicks = find_col(['click', 'lượtclick'])
    col_ctr = find_col(['tỷlệclick', 'ctr'])
    col_orders = find_col(['tổngđơn', 'orders', 'đơnhàng'])
    col_items_sold = find_col(['mặthàng', 'itemssold', 'đượcbán'])
    col_datetime = find_col(['datetime', 'thờigian'])
    
    if col_item_id is None or col_revenue is None:
        # Fallback: use index-based
        col_datetime = 0
        col_item_id = 1
        col_item_name = 2
        col_clicks = 3
        col_ctr = 4
        col_orders = 5
        col_items_sold = 6
        col_revenue = 7
    
    def parse_int(val):
        if val is None or val == '':
            return 0
        cleaned = str(val).replace(',', '').replace('.', '').replace('₫', '').strip()
        try:
            return int(cleaned) if cleaned else 0
        except:
            return 0
    
    results = []
    seen_items = {}  # Keep last occurrence
    
    for row in data_rows:
        if len(row) <= col_item_id:
            continue
        
        item_id = str(row[col_item_id]).strip() if col_item_id < len(row) else ''
        if not item_id:
            continue
        
        item_name = str(row[col_item_name]) if col_item_name is not None and col_item_name < len(row) else ''
        revenue = parse_int(row[col_revenue]) if col_revenue is not None and col_revenue < len(row) else 0
        clicks = parse_int(row[col_clicks]) if col_clicks is not None and col_clicks < len(row) else 0
        ctr = str(row[col_ctr]) if col_ctr is not None and col_ctr < len(row) else ''
        orders = parse_int(row[col_orders]) if col_orders is not None and col_orders < len(row) else 0
        items_sold = parse_int(row[col_items_sold]) if col_items_sold is not None and col_items_sold < len(row) else 0
        dt_str = str(row[col_datetime]) if col_datetime is not None and col_datetime < len(row) else ''
        
        shop_id = item_to_shop.get(item_id, '')
        cluster = item_to_cluster.get(item_id, '')
        link_sp = f"https://shopee.vn/a-i.{shop_id}.{item_id}" if shop_id else ''
        
        # Overwrite to keep last occurrence
        seen_items[item_id] = {
            'item_id': item_id,
            'item_name': item_name,
            'revenue': revenue,
            'shop_id': shop_id,
            'link_sp': link_sp,
            'datetime': dt_str,
            'clicks': clicks,
            'ctr': ctr,
            'orders': orders,
            'items_sold': items_sold,
            'cluster': cluster
        }
    
    # Sort by revenue desc and limit
    results = list(seen_items.values())
    results.sort(key=lambda x: x['revenue'], reverse=True)
    
    # Cập nhật cache (lưu toàn bộ data, không chỉ limit)
    _gmv_cache['data'] = results
    _gmv_cache['timestamp'] = datetime.now()
    print(f"[CACHE] Updated cache with {len(results)} items")
    
    return results[:limit]

def sync_deal_list_only(spreadsheet_url, deallist_sheet_name):
    """
    CHỈ sync Deal List để map shop_id, cluster, tạo link.
    KHÔNG xóa/ghi đè gmv_data - chỉ UPDATE các item đã có.
    """
    client = get_gspread_client()
    spreadsheet = client.open_by_url(spreadsheet_url)
    
    # Read Deal list - dùng range get để lấy full data không bị filter
    deallist_sheet = spreadsheet.worksheet(deallist_sheet_name)
    try:
        deallist_values = deallist_sheet.get('A:Z')
    except:
        deallist_values = deallist_sheet.get_all_values()
    
    print(f"[SYNC] Deal List: {len(deallist_values)} rows from {deallist_sheet_name}")
    
    # Find header row
    header_row_idx = 0
    for idx, row in enumerate(deallist_values):
        row_text = ' '.join(str(cell).lower() for cell in row)
        if 'item' in row_text and 'id' in row_text:
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
        for key in first_row_keys:
            key_lower = key.lower().replace(' ', '').replace('_', '')
            if 'finalitemid' in key_lower or 'itemid' in key_lower:
                item_id_col = key
            if 'shopid' in key_lower:
                shop_id_col = key
            if 'cluster' in key_lower:
                cluster_col = key
    
    if not item_id_col or not shop_id_col:
        raise Exception("Không tìm thấy cột Item ID hoặc Shop ID trong Deal List")
    
    # Update gmv_data với shop_id, cluster, link
    conn = get_db()
    cursor = conn.cursor()
    updated = 0
    
    for row in deallist_data:
        item_id = str(row.get(item_id_col, '')).strip()
        shop_id_raw = str(row.get(shop_id_col, '')).strip()
        cluster = str(row.get(cluster_col, '')).strip() if cluster_col else ''
        
        # Extract numeric shop_id
        if '+' in shop_id_raw:
            shop_id = shop_id_raw.split('+')[-1]
        else:
            shop_id = shop_id_raw
        shop_id = ''.join(c for c in shop_id if c.isdigit())
        
        if not item_id or not shop_id:
            continue
        
        # Generate link
        link_sp = f"https://shopee.vn/a-i.{shop_id}.{item_id}"
        
        # UPDATE existing record (không INSERT mới)
        cursor.execute('''
            UPDATE gmv_data 
            SET shop_id = ?, cluster = ?, link_sp = ?
            WHERE item_id = ?
        ''', (shop_id, cluster, link_sp, item_id))
        
        if cursor.rowcount > 0:
            updated += 1
    
    conn.commit()
    conn.close()
    
    # === LƯU VÀO POSTGRESQL ===
    # Thu thập deal_list data để lưu
    postgres_url = os.environ.get('DATABASE_URL', '')
    if postgres_url:
        deal_list_for_postgres = []
        for row in deallist_data:
            item_id = str(row.get(item_id_col, '')).strip()
            shop_id_raw = str(row.get(shop_id_col, '')).strip()
            cluster = str(row.get(cluster_col, '')).strip() if cluster_col else ''
            
            # Extract numeric shop_id
            if '+' in shop_id_raw:
                shop_id = shop_id_raw.split('+')[-1]
            else:
                shop_id = shop_id_raw
            shop_id = ''.join(c for c in shop_id if c.isdigit())
            
            if item_id and shop_id:
                deal_list_for_postgres.append({
                    'item_id': item_id,
                    'shop_id': shop_id,
                    'cluster': cluster
                })
        
        saved_count = save_deal_list_to_postgresql(deal_list_for_postgres, postgres_url)
        print(f"[SYNC] Saved {saved_count} items to PostgreSQL deal_list")
    
    # Update last sync time
    set_config('last_deallist_sync', datetime.now().isoformat())
    
    return updated


# ============== GUI SCRAPER MODE ==============

def run_gui_mode():
    """Khởi động GUI Scraper mode"""
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
        QPushButton, QComboBox, QLabel, QMessageBox, QTextEdit, QGroupBox, QCheckBox
    )
    from PyQt6.QtCore import Qt
    
    # Import module gốc
    from backup_full_gmv import ShopeeScraperApp
    
    class ShopeeScraperWithGSheet(ShopeeScraperApp):
        """Phiên bản mở rộng với tính năng Google Sheet + SQLite"""
        
        def __init__(self):
            super().__init__()
            self.setWindowTitle("GMV App - Scraper (CSV + Sheet + SQLite)")
            self.resize(500, 400)
            
            # Google Sheet variables
            self.gsheet_client = None
            self.current_spreadsheet = None
            self.current_worksheet = None
            self.gsheet_enabled = False
            self.gsheet_header_written = False
            
            # Initialize DB
            init_db()
            
            # PostgreSQL variables
            self.postgres_enabled = False
            self.last_archive_time = datetime.now()  # Initialize archive timer
            
            # Overview scraper variables
            self.overview_running = False
            self.last_overview_archive = None
            
            # Thêm UI elements cho Google Sheet
            self._add_gsheet_ui()
            
            # Thêm UI elements cho PostgreSQL
            self._add_postgres_ui()
        
        def _add_gsheet_ui(self):
            """Thêm UI elements cho Google Sheet"""
            gsheet_group = QGroupBox("📊 Google Sheet Settings")
            gsheet_layout = QVBoxLayout()
            
            # Row 1: Sheet URL
            url_row = QHBoxLayout()
            url_row.addWidget(QLabel("Sheet URL:"))
            self.gsheet_url_input = QLineEdit()
            self.gsheet_url_input.setPlaceholderText("Paste Google Spreadsheet URL here...")
            url_row.addWidget(self.gsheet_url_input)
            gsheet_layout.addLayout(url_row)
            
            # Row 2: Load button + Sheet selector
            selector_row = QHBoxLayout()
            self.load_sheets_btn = QPushButton("📂 Load Sheets")
            self.load_sheets_btn.clicked.connect(self.load_google_sheets)
            selector_row.addWidget(self.load_sheets_btn)
            
            selector_row.addWidget(QLabel("Chọn Sheet:"))
            self.sheet_selector = QComboBox()
            self.sheet_selector.setMinimumWidth(150)
            selector_row.addWidget(self.sheet_selector)
            
            # Checkbox enable/disable
            self.gsheet_checkbox = QCheckBox("Ghi vào Sheet")
            self.gsheet_checkbox.setChecked(False)
            self.gsheet_checkbox.stateChanged.connect(self._on_gsheet_toggle)
            selector_row.addWidget(self.gsheet_checkbox)
            
            gsheet_layout.addLayout(selector_row)
            
            # Status label
            self.gsheet_status = QLabel("⚪ Chưa kết nối Google Sheet")
            gsheet_layout.addWidget(self.gsheet_status)
            
            gsheet_group.setLayout(gsheet_layout)
            
            # Thêm vào layout chính
            main_layout = self.layout
            main_layout.insertWidget(main_layout.count() - 1, gsheet_group)
            
            # Thêm log_output nếu chưa có
            if not hasattr(self, 'log_output') or self.log_output is None:
                self.log_output = QTextEdit()
                self.log_output.setReadOnly(True)
                main_layout.addWidget(self.log_output)
        
        def _add_postgres_ui(self):
            """Thêm UI elements cho PostgreSQL"""
            from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox
            
            postgres_group = QGroupBox("🐘 PostgreSQL (Railway)")
            postgres_layout = QVBoxLayout()
            
            # Row 1: DATABASE_URL input
            url_row = QHBoxLayout()
            url_row.addWidget(QLabel("DATABASE_URL:"))
            self.postgres_url_input = QLineEdit()
            self.postgres_url_input.setPlaceholderText("postgresql://...")
            # Lấy từ environment nếu có
            env_url = os.environ.get('DATABASE_URL', '')
            if env_url:
                self.postgres_url_input.setText(env_url)
            url_row.addWidget(self.postgres_url_input)
            postgres_layout.addLayout(url_row)
            
            # Row 2: Checkbox enable/disable
            self.postgres_checkbox = QCheckBox("Ghi vào PostgreSQL")
            self.postgres_checkbox.setChecked(False)
            self.postgres_checkbox.stateChanged.connect(self._on_postgres_toggle)
            postgres_layout.addWidget(self.postgres_checkbox)
            
            # Status label
            self.postgres_status = QLabel("⚪ Chưa bật PostgreSQL")
            postgres_layout.addWidget(self.postgres_status)
            
            postgres_group.setLayout(postgres_layout)
            
            # Thêm vào layout chính
            main_layout = self.layout
            main_layout.insertWidget(main_layout.count() - 1, postgres_group)
        
        def _on_postgres_toggle(self, state):
            """Xử lý khi toggle checkbox PostgreSQL"""
            from PyQt6.QtCore import Qt
            self.postgres_enabled = (state == Qt.CheckState.Checked.value)
            if self.postgres_enabled:
                db_url = self.postgres_url_input.text().strip()
                if not db_url:
                    self.log("⚠️ Chưa nhập DATABASE_URL")
                    self.postgres_checkbox.setChecked(False)
                    self.postgres_enabled = False
                    self.postgres_status.setText("⚠️ Chưa nhập DATABASE_URL")
                elif not HAS_PSYCOPG2:
                    self.log("⚠️ psycopg2 chưa được cài đặt")
                    self.postgres_checkbox.setChecked(False)
                    self.postgres_enabled = False
                    self.postgres_status.setText("⚠️ Thiếu psycopg2")
                else:
                    self.postgres_status.setText("✅ Đã bật PostgreSQL")
            else:
                self.postgres_status.setText("⚪ Chưa bật PostgreSQL")
        
        def _on_gsheet_toggle(self, state):
            """Xử lý khi toggle checkbox Google Sheet"""
            self.gsheet_enabled = (state == Qt.CheckState.Checked.value)
            if self.gsheet_enabled and not self.current_worksheet:
                self.log("⚠️ Chưa chọn sheet. Vui lòng Load Sheets và chọn sheet trước.")
                self.gsheet_checkbox.setChecked(False)
                self.gsheet_enabled = False
        
        def load_google_sheets(self):
            """Kết nối Google Sheet và load danh sách worksheets"""
            if not GSPREAD_AVAILABLE:
                QMessageBox.warning(self, "Lỗi", "gspread chưa được cài.\nChạy: pip install gspread google-auth")
                return
            
            url = self.gsheet_url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Lỗi", "Vui lòng nhập URL Google Spreadsheet")
                return
            
            try:
                self.gsheet_status.setText("🔄 Đang kết nối...")
                QApplication.processEvents()
                
                if not os.path.exists(SERVICE_ACCOUNT_KEY):
                    QMessageBox.critical(self, "Lỗi", f"Không tìm thấy file:\n{SERVICE_ACCOUNT_KEY}")
                    self.gsheet_status.setText("❌ Không tìm thấy service account key")
                    return
                
                creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY, scopes=SCOPES)
                self.gsheet_client = gspread.authorize(creds)
                self.current_spreadsheet = self.gsheet_client.open_by_url(url)
                
                worksheets = self.current_spreadsheet.worksheets()
                
                self.sheet_selector.clear()
                for ws in worksheets:
                    self.sheet_selector.addItem(ws.title, ws)
                
                if worksheets:
                    self.current_worksheet = worksheets[0]
                    self.sheet_selector.currentIndexChanged.connect(self._on_sheet_changed)
                
                self.gsheet_status.setText(f"✅ Đã kết nối: {self.current_spreadsheet.title}")
                self.log(f"📊 Đã load {len(worksheets)} sheets từ: {self.current_spreadsheet.title}")
                
            except gspread.exceptions.SpreadsheetNotFound:
                QMessageBox.critical(self, "Lỗi", "Không tìm thấy Spreadsheet.\nHãy đảm bảo đã share với:\nbigquery-sheets-uploader@beyondk-live-data.iam.gserviceaccount.com")
                self.gsheet_status.setText("❌ Spreadsheet không tìm thấy")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Lỗi kết nối:\n{e}")
                self.gsheet_status.setText(f"❌ Lỗi: {e}")
                self.log(f"❌ Lỗi kết nối Google Sheet: {e}")
        
        def _on_sheet_changed(self, index):
            """Xử lý khi chọn sheet khác"""
            if index >= 0:
                self.current_worksheet = self.sheet_selector.itemData(index)
                self.log(f"📋 Đã chọn sheet: {self.current_worksheet.title}")
        
        def save_to_gsheet(self, rows, overwrite=False):
            """
            Ghi dữ liệu vào Google Sheet đã chọn trong GUI.
            overwrite=False: Append data mới vào dưới header (giữ data cũ)
            overwrite=True: Xóa data cũ, ghi data mới
            """
            if not self.gsheet_enabled:
                return False
            
            if not rows:
                return False
            
            # Kiểm tra đã chọn sheet chưa
            if not self.current_worksheet:
                self.log("⚠️ Chưa chọn sheet để ghi dữ liệu")
                return False
            
            try:
                # Dùng sheet đã chọn trong GUI
                worksheet = self.current_worksheet
                
                # Chuẩn bị data
                all_rows = [CSV_HEADER_API]  # Luôn có header
                
                for row in rows:
                    row_data = list(row) if isinstance(row, (list, tuple)) else [str(row)]
                    if len(row_data) < len(CSV_HEADER_API):
                        row_data += [""] * (len(CSV_HEADER_API) - len(row_data))
                    elif len(row_data) > len(CSV_HEADER_API):
                        row_data = row_data[:len(CSV_HEADER_API)]
                    
                    row_data = [str(x) if x is not None else "" for x in row_data]
                    all_rows.append(row_data)
                
                if overwrite:
                    # XÓA toàn bộ data cũ và ghi mới
                    worksheet.clear()
                    worksheet.update('A1', all_rows, value_input_option='USER_ENTERED')
                    self.log(f"📊 Đã GHI ĐÈ {len(rows)} dòng vào Google Sheet (xóa data cũ)")
                else:
                    # Append (giữ data cũ)
                    worksheet.append_rows(all_rows[1:], value_input_option='USER_ENTERED')  # Bỏ header
                    self.log(f"📊 Đã THÊM {len(rows)} dòng vào Google Sheet")
                
                return True
                
            except Exception as e:
                self.log(f"❌ Lỗi ghi Google Sheet: {e}")
                import traceback
                self.log(traceback.format_exc())
                return False
        
        async def fetch_overview_data(self, page, session_id):
            """
            Gọi API overview và parse metrics.
            
            Args:
                page: Playwright page object
                session_id: Session ID for the livestream
            
            Returns:
                dict: 19 metrics hoặc None nếu lỗi
            
            Requirements: 1.1, 1.2, 7.1, 7.3
            """
            from db_helpers import parse_overview_metrics
            import asyncio
            
            api_url = f"https://creator.shopee.vn/supply/api/lm/sellercenter/realtime/dashboard/overview?sessionId={session_id}"
            
            try:
                self.log(f"📊 Fetching overview data from API...")
                
                # Use page.evaluate() to fetch with credentials (with 30s timeout)
                try:
                    response = await asyncio.wait_for(
                        page.evaluate('''
                            async (url) => {
                                try {
                                    const resp = await fetch(url, {
                                        credentials: 'include',
                                        headers: {
                                            'Accept': 'application/json',
                                        }
                                    });
                                    return await resp.json();
                                } catch(e) {
                                    return { error: e.message };
                                }
                            }
                        ''', api_url),
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    self.log(f"⚠️ Overview API timeout (>30s) - skipping this cycle")
                    return None
                
                # Check for errors
                if not response:
                    self.log("❌ No response from overview API")
                    return None
                
                if "error" in response:
                    self.log(f"❌ Overview API error: {response.get('error')}")
                    return None
                
                # Parse metrics using helper function
                try:
                    metrics = parse_overview_metrics(response)
                except Exception as parse_error:
                    self.log(f"❌ Parse error: {parse_error}")
                    self.log(f"Response body: {str(response)[:500]}...")  # Log first 500 chars for debugging
                    return None
                
                if metrics:
                    self.log(f"✅ Overview data fetched: GMV={metrics.get('gmv', 0)}, Views={metrics.get('views', 0)}")
                    return metrics
                else:
                    self.log("⚠️ Failed to parse overview metrics from API response")
                    self.log(f"Response body: {str(response)[:500]}...")  # Log first 500 chars for debugging
                    return None
                    
            except Exception as e:
                self.log(f"❌ Error fetching overview data: {e}")
                import traceback
                self.log(traceback.format_exc())
                return None
        
        async def overview_scraper_loop(self, page, session_id, session_title):
            """
            Overview scraper loop - chạy độc lập với product scraper.
            Scrape mỗi 3 phút, archive mỗi 60 phút.
            
            Args:
                page: Playwright page object
                session_id: Session ID for the livestream
                session_title: Session title for the livestream
            
            Requirements: 1.1, 1.3, 3.1, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5
            """
            from db_helpers import save_overview_to_postgresql, archive_overview_data
            from datetime import timedelta
            
            self.log(f"🚀 Starting overview scraper loop for session {session_id} ({session_title})...")
            
            # Initialize last archive time
            if self.last_overview_archive is None:
                self.last_overview_archive = datetime.now()
            
            while self.overview_running:
                try:
                    current_time = datetime.now().strftime('%H:%M:%S')
                    
                    # 1. Fetch overview data from API
                    self.log(f"📊 [Overview] [{current_time}] Fetching data for session {session_id}...")
                    metrics = await self.fetch_overview_data(page, session_id)
                    
                    if metrics and self.postgres_enabled:
                        # 2. Save to PostgreSQL
                        db_url = self.postgres_url_input.text().strip()
                        success = save_overview_to_postgresql(
                            metrics, 
                            db_url, 
                            session_id, 
                            session_title, 
                            log_func=self.log
                        )
                        
                        if success:
                            self.log(f"✅ [Overview] [{current_time}] Saved 1 record to PostgreSQL (Session: {session_id}, GMV: {metrics.get('gmv', 0):,})")
                        else:
                            self.log(f"⚠️ [Overview] [{current_time}] Failed to save to PostgreSQL (Session: {session_id})")
                    elif not metrics:
                        self.log(f"⚠️ [Overview] [{current_time}] No metrics fetched (Session: {session_id})")
                    
                    # 3. Check if need to archive (every 60 minutes)
                    elapsed = datetime.now() - self.last_overview_archive
                    if elapsed > timedelta(minutes=60):
                        if self.postgres_enabled:
                            self.log(f"📦 [Overview] [{current_time}] Archiving data (60 minutes elapsed, Session: {session_id})...")
                            db_url = self.postgres_url_input.text().strip()
                            archive_success = archive_overview_data(
                                db_url, 
                                session_id, 
                                log_func=self.log
                            )
                            
                            if archive_success:
                                self.last_overview_archive = datetime.now()
                                archive_time = self.last_overview_archive.strftime('%H:%M:%S')
                                self.log(f"✅ [Overview] [{archive_time}] Archived successfully (Session: {session_id})")
                            else:
                                self.log(f"⚠️ [Overview] [{current_time}] Archive failed (Session: {session_id}), will retry next cycle")
                    
                    # 4. Wait 3 minutes (180 seconds)
                    self.log(f"⏱️ [Overview] [{current_time}] Waiting 3 minutes until next fetch...")
                    await asyncio.sleep(180)
                    
                except Exception as e:
                    error_time = datetime.now().strftime('%H:%M:%S')
                    self.log(f"❌ [Overview] [{error_time}] Scraper error (Session: {session_id}): {e}")
                    import traceback
                    self.log(traceback.format_exc())
                    # Retry after 1 minute on error
                    self.log(f"⏱️ [Overview] [{error_time}] Retrying in 1 minute...")
                    await asyncio.sleep(60)
            
            self.log(f"🛑 Overview scraper loop stopped (Session: {session_id})")
        
        def save_to_csv_and_db(self, rows):
            """Ghi CSV + SQLite song song (+ Google Sheet nếu enabled)"""
            if not rows:
                return ""
            
            path = self.session_csv_path
            final_path = path
            
            # Xác định có cần ghi header không
            header_needed = True
            try:
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    header_needed = False
            except Exception:
                header_needed = not os.path.exists(path)
            
            # Chuẩn hóa dữ liệu
            cols = len(CSV_HEADER_API)
            norm_rows = []
            for r in rows:
                r = list(r) if isinstance(r, (list, tuple)) else [str(r)]
                if len(r) > cols:
                    r = r[:cols]
                elif len(r) < cols:
                    r = r + [""] * (cols - len(r))
                r = [("" if x is None else str(x)) for x in r]
                norm_rows.append(r)
            
            try:
                # === 1. GHI CSV + GOOGLE SHEET (mỗi 3 cycles = 15 phút) ===
                # Khởi tạo cycle counter nếu chưa có
                if not hasattr(self, 'file_cycle_counter'):
                    self.file_cycle_counter = 0
                self.file_cycle_counter += 1
                
                if self.file_cycle_counter >= 3:
                    # Ghi CSV
                    mode = "w" if header_needed else "a"
                    encoding = "utf-8-sig" if header_needed else "utf-8"
                    with open(path, mode, encoding=encoding, newline="") as f:
                        w = csv.writer(f, quoting=csv.QUOTE_ALL)
                        if header_needed:
                            w.writerow(CSV_HEADER_API)
                        for r in norm_rows:
                            w.writerow(r)
                    self.log(f"✅ Đã ghi {len(norm_rows)} dòng vào CSV")
                    
                    # Ghi Google Sheet
                    if self.gsheet_enabled:
                        self.save_to_gsheet(norm_rows)
                    
                    self.file_cycle_counter = 0  # Reset counter
                else:
                    self.log(f"� CSV/GSheet: Đợi thêm {3 - self.file_cycle_counter} cycles nữa (15p interval)...")
                
                # === 3. GHI SQLITE ===
                sqlite_count = save_to_sqlite(norm_rows)
                self.log(f"💾 Đã ghi/cập nhật {sqlite_count} dòng vào SQLite")
                
                # === 4. GHI POSTGRESQL (Multi-Session) ===
                self.log(f"🐘 PostgreSQL enabled: {self.postgres_enabled}")
                if self.postgres_enabled:
                    db_url = self.postgres_url_input.text().strip()
                    session_id = getattr(self, 'current_session_id', None)
                    session_title = getattr(self, 'current_session_title', '')
                    
                    if session_id:
                        self.log(f"🐘 Đang ghi vào PostgreSQL (session: {session_id})...")
                        save_to_postgresql_multi_session(
                            norm_rows, db_url, session_id, session_title, 
                            log_func=self.log
                        )
                    
                    # === 5. HOURLY ARCHIVE CHECK ===
                    if self.postgres_enabled and session_id:
                        elapsed = datetime.now() - self.last_archive_time
                        elapsed_mins = int(elapsed.total_seconds() / 60)
                        self.log(f"⏱️ Timer: {elapsed_mins} phút kể từ lần archive trước")
                        if elapsed > timedelta(minutes=60):  # TODO: Đổi lại hours=1 sau khi test
                            self.log(f"⏰ Đã qua {elapsed_mins} phút (> 60). Tiến hành archive data...")
                            success = archive_session_data(db_url, session_id, log_func=self.log)
                            if success:
                                self.last_archive_time = datetime.now()
                                self.log(f"✅ Archive hoàn tất. Reset timer.")
                        else:
                            self.log(f"⏳ Chưa đến 60 phút, còn {60 - elapsed_mins} phút nữa mới archive")
                
                self.log("✅ Hoàn thành ghi dữ liệu")
                return final_path
            
            except PermissionError:
                try:
                    ts = datetime.now().strftime("_%H%M%S")
                    alt = path.replace(".csv", f"{ts}.csv")
                    with open(alt, "w", encoding="utf-8-sig", newline="") as f:
                        w = csv.writer(f, quoting=csv.QUOTE_ALL)
                        w.writerow(CSV_HEADER_API)
                        for r in norm_rows:
                            w.writerow(r)
                    final_path = alt
                    self.log(f"⚠️ File chính có thể đang mở. Đã ghi tạm {len(norm_rows)} dòng vào: {alt}")
                    
                    # Vẫn ghi Google Sheet và SQLite
                    if self.gsheet_enabled:
                        self.save_to_gsheet(norm_rows)
                    save_to_sqlite(norm_rows)
                    
                    return final_path
                except Exception as e2:
                    import traceback
                    self.log(f"❌ Lỗi khi ghi file phụ: {e2!r}")
                    self.log(traceback.format_exc())
                    return ""
            
            except Exception as e:
                import traceback
                self.log(f"❌ Lỗi ghi CSV: {e!r}")
                self.log(traceback.format_exc())
                return ""
    
    # Extract data via API function
    async def extract_data_via_api(self, page, session_id):
        """Lấy dữ liệu sản phẩm trực tiếp từ API với pageSize=500."""
        results = []
        page_num = 1
        page_size = 500
        total_products = 0
        now = datetime.now()
        dt_str = now.strftime("%d-%m:%H:%M:%S")
        
        self.log(f"🚀 Đang lấy dữ liệu qua API với pageSize={page_size}...")
        
        while True:
            api_url = (
                f"https://creator.shopee.vn/supply/api/lm/sellercenter/realtime/dashboard/productList"
                f"?sessionId={session_id}"
                f"&productName="
                f"&productListTimeRange=0"
                f"&sort=desc"
                f"&page={page_num}"
                f"&pageSize={page_size}"
            )
            
            try:
                response = await page.evaluate('''
                    async (url) => {
                        try {
                            const resp = await fetch(url, {
                                credentials: 'include',
                                headers: {
                                    'Accept': 'application/json',
                                }
                            });
                            return await resp.json();
                        } catch(e) {
                            return { error: e.message };
                        }
                    }
                ''', api_url)
                
                if not response:
                    self.log("❌ Không nhận được response từ API")
                    break
                
                if "error" in response:
                    self.log(f"❌ Lỗi API: {response.get('error')}")
                    break
                
                data = response.get("data", {})
                product_list = data.get("productList", [])
                
                if not product_list:
                    product_list = data.get("list", [])
                if not product_list:
                    product_list = data.get("items", [])
                if not product_list:
                    product_list = data.get("products", [])
                
                total_count = data.get("totalCount", data.get("total", 0))
                
                if not product_list:
                    if page_num == 1:
                        self.log("⚠️ Không có sản phẩm nào trong phiên live này")
                    break
                
                self.log(f"📦 Trang {page_num}: Lấy được {len(product_list)} sản phẩm (Tổng: {total_count})")
                
                for product in product_list:
                    try:
                        item_id = str(product.get("itemId", ""))
                        name = product.get("title", "")
                        cover_image = product.get("coverImage", "")
                        clicks = str(product.get("productClicks", 0))
                        
                        ctr = product.get("ctr", "0%")
                        if not str(ctr).endswith("%"):
                            try:
                                ctr = f"{float(ctr)*100:.1f}%"
                            except:
                                ctr = f"{ctr}%"
                        
                        total_orders = str(product.get("ordersCreated", 0))
                        items_sold = str(product.get("itemSold", 0))
                        
                        revenue_raw = product.get("revenue", 0)
                        if isinstance(revenue_raw, (int, float)):
                            revenue = str(int(revenue_raw))
                        else:
                            revenue = str(revenue_raw).replace("₫", "").replace(",", "").replace(".", "").strip()
                        
                        cto_rate = product.get("cor", "0%")
                        if not str(cto_rate).endswith("%"):
                            try:
                                cto_rate = f"{float(cto_rate)*100:.1f}%"
                            except:
                                cto_rate = f"{cto_rate}%"
                        
                        add_to_cart = str(product.get("atc", 0))
                        
                        # Confirmed data
                        nmv_raw = product.get("confirmedRevenue", 0)
                        if isinstance(nmv_raw, (int, float)):
                            nmv = str(int(nmv_raw))
                        else:
                            nmv = str(nmv_raw).replace("₫", "").replace(",", "").replace(".", "").strip()
                        
                        confirmed_orders = str(product.get("confirmedOrderCnt", 0))
                        confirmed_items_sold = str(product.get("ComfirmedItemsold", product.get("confirmedItemSold", 0)))
                        
                        results.append([
                            dt_str, item_id, name, cover_image,
                            clicks, ctr, total_orders, items_sold,
                            revenue, cto_rate, add_to_cart,
                            nmv, confirmed_orders, confirmed_items_sold,
                        ])
                        total_products += 1
                        
                    except Exception as e:
                        self.log(f"⚠️ Lỗi parse sản phẩm: {e}")
                        continue
                
                if len(product_list) < page_size:
                    break
                
                page_num += 1
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.log(f"❌ Lỗi khi gọi API trang {page_num}: {e}")
                import traceback
                self.log(traceback.format_exc())
                break
        
        self.log(f"✅ Hoàn thành lấy dữ liệu qua API: {total_products} sản phẩm")
        return results
    
    # Patched run_loop
    original_run_loop = ShopeeScraperApp.run_loop
    
    async def patched_run_loop(self):
        """Phiên bản run_loop sử dụng API trực tiếp với pageSize=500."""
        from playwright.async_api import async_playwright
        
        LOCAL_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "Data All in One", "Dashboard")
        
        if len(self.accounts) == 0:
            self.log("Chưa có tài khoản. Vui lòng thêm tài khoản trước.")
            return

        account = self.accounts[self.account_selector.currentIndex()]
        username, password = account["username"], account["password"]
        session_file = os.path.join(LOCAL_PATH, f"auth_state_{username}.json")
        url = self.live_url_input.text().strip()
        
        # Tạo file CSV duy nhất cho cả phiên
        if not self.session_csv_path:
            live_id_part = ""
            if "dashboard/live/" in url:
                live_id_part = "_" + url.split("dashboard/live/")[-1].split("/")[0]
            start_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.session_csv_path = os.path.join(
                OUTPUT_DIR,
                f"SHP_live_session{live_id_part}_{start_time_str}.csv"
            )
        
        # Chuẩn bị session
        if not os.path.exists(session_file):
            self.log("Chưa có session → mở trình duyệt để đăng nhập.")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                try:
                    await page.goto("https://creator.shopee.vn", timeout=90_000)
                except Exception:
                    pass
                self.log("Hãy đăng nhập và vào được dashboard/home, sau đó chờ app lưu session...")
                start = datetime.now()
                while (datetime.now() - start).total_seconds() < 300:
                    try:
                        if any(k in page.url for k in ("dashboard", "home")):
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(1)
                await context.storage_state(path=session_file)
                await browser.close()
            self.log("💾 Đã lưu session.")

        # Dùng session để scrape
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=session_file)
            page = await context.new_page()

            dashboard_page = None
            try:
                await page.goto("https://creator.shopee.vn", timeout=90_000)
            except Exception:
                pass

            if url:
                try:
                    await page.goto(url, timeout=90_000)
                    dashboard_page = page
                except Exception as e:
                    self.log(f"❌ Lỗi khi mở URL phiên live: {e!r}")

            if not dashboard_page:
                dashboard_page = await self.find_dashboard_tab(context, url or "")
            if not dashboard_page:
                self.log("Không tìm thấy dashboard. Kết thúc.")
                await context.close()
                await browser.close()
                return

            self.log(f"📄 Dashboard: {dashboard_page.url}")
            
            # Lấy session_id từ URL
            session_id = None
            current_url = dashboard_page.url
            if "dashboard/live/" in current_url:
                session_id = current_url.split("dashboard/live/")[-1].split("/")[0].split("?")[0]
            
            if not session_id:
                self.log("❌ Không tìm thấy session_id trong URL. Sử dụng phương pháp cũ...")
                await original_run_loop(self)
                return
            
            self.log(f"🔑 Session ID: {session_id}")
            
            # Store session_id as instance attribute
            self.current_session_id = session_id
            
            # Fetch session info từ API để lấy session title
            session_title = ""
            try:
                session_info_url = f"https://creator.shopee.vn/supply/api/lm/sellercenter/realtime/dashboard/sessionInfo?sessionId={session_id}"
                session_info = await dashboard_page.evaluate('''
                    async (url) => {
                        try {
                            const resp = await fetch(url, {credentials: 'include'});
                            return await resp.json();
                        } catch(e) {
                            return {error: e.message};
                        }
                    }
                ''', session_info_url)
                
                if session_info and session_info.get('code') == 0:
                    data = session_info.get('data', {})
                    session_title = data.get('sessionTitle', '') or data.get('title', '') or ''
                    self.log(f"📺 Session Title (API): {session_title}")
                else:
                    self.log(f"⚠️ Không lấy được session title, sử dụng ID")
            except Exception as e:
                self.log(f"⚠️ Lỗi fetch session info: {e}")
            
            # --- LOGIC XÁC ĐỊNH SESSION TITLE (Updated) ---
            # Yêu cầu mới: 
            # 1. Mặc định là "Session {session_id}"
            # 2. KHÔNG tự lấy từ API hay Sheet nữa (tránh sai tên)
            # 3. Nếu trong DB đã có tên "xịn" (do Admin map/đặt), thì giữ nguyên.
            
            final_session_title = f"Session {session_id}"
            
            # Check DB for existing custom title
            if self.postgres_enabled:
                try:
                    from db_helpers import get_session_title_by_id
                    db_url = self.postgres_url_input.text().strip()
                    existing_title = get_session_title_by_id(db_url, session_id, log_func=self.log)
                    
                    # Nếu DB có title và không phải là "Session ...", thì đó là tên chuẩn -> Dùng nó
                    if existing_title and not existing_title.startswith("Session "):
                        self.log(f"🔄 Found existing custom title in DB: {existing_title}")
                        final_session_title = existing_title
                except Exception as e:
                    self.log(f"⚠️ Error checking existing title: {e}")
            
            self.current_session_title = final_session_title

            
            # Initialize multi-session schema
            if self.postgres_enabled:
                db_url = self.postgres_url_input.text().strip()
                init_multi_session_tables(db_url, log_func=self.log)
            
            # Archive tracking
            last_archive_time = datetime.now()
            ARCHIVE_INTERVAL_MINS = 60  # Archive every 60 minutes

            # Start overview scraper thread
            self.overview_running = True
            overview_task = asyncio.create_task(
                self.overview_scraper_loop(dashboard_page, session_id, final_session_title)
            )
            self.log("🚀 Overview scraper thread started")

            # Vòng scrape sử dụng API
            self.is_running = True
            try:
                while self.is_running:
                    try:
                        cycle_start = datetime.now()
                        
                        data = await extract_data_via_api(self, dashboard_page, session_id)
                        
                        if data:
                            self.save_to_csv_and_db(data)
                        else:
                            self.log("⚠️ Không có dữ liệu để ghi")
                        
                        # (Archive logic removed here as it is already handled in save_to_csv_and_db)

                        # Chờ tới mốc 5 phút
                        target_secs = 5 * 60
                        elapsed = (datetime.now() - cycle_start).total_seconds()
                        wait_secs = max(0, int(target_secs - elapsed))

                        self.log(f"⏱️ Sẽ cập nhật lại sau {wait_secs//60} phút...")
                        for _ in range(wait_secs):
                            if not self.is_running:
                                break
                            await asyncio.sleep(1)
                    except Exception as e:
                        import traceback
                        self.log(f"❌ Lỗi trong vòng scrape: {e!r}")
                        self.log(traceback.format_exc())
                        await asyncio.sleep(2)
            finally:
                # Stop overview scraper
                self.overview_running = False
                self.log("🛑 Stopping overview scraper...")
                
                # Wait for overview task to complete (with timeout)
                try:
                    await asyncio.wait_for(overview_task, timeout=5.0)
                    self.log("✅ Overview scraper stopped cleanly")
                except asyncio.TimeoutError:
                    self.log("⚠️ Overview scraper did not stop within timeout, cancelling...")
                    overview_task.cancel()
                    try:
                        await overview_task
                    except asyncio.CancelledError:
                        self.log("✅ Overview scraper cancelled")
                except Exception as e:
                    self.log(f"⚠️ Error stopping overview scraper: {e}")
                
                self.log("Đóng trình duyệt...")
                await context.close()
                await browser.close()
                self.log("Đã dừng theo dõi.")
    
    # Gán các phương thức
    ShopeeScraperWithGSheet.extract_data_via_api = extract_data_via_api
    ShopeeScraperWithGSheet.run_loop = patched_run_loop
    ShopeeScraperWithGSheet.save_to_csv_api = ShopeeScraperWithGSheet.save_to_csv_and_db
    
    # Chạy app
    app = QApplication(sys.argv)
    window = ShopeeScraperWithGSheet()
    window.show()
    sys.exit(app.exec())


# ============== WEB SERVER MODE ==============

def create_app():
    """Tạo Flask app - dùng cho cả gunicorn và local development"""
    from flask import Flask, render_template, request, jsonify, session, redirect, url_for
    from apscheduler.schedulers.background import BackgroundScheduler
    
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Initialize DB
    try:
        init_db()
    except Exception as e:
        print(f"[WARNING] init_db failed: {e}")
    
    # ============== Background Auto-Refresh GMV ==============
    # DISABLED: Scraper local now writes directly to PostgreSQL
    # The scheduler was reading from Google Sheet and overwriting PostgreSQL data
    scheduler = None
    
    # def auto_refresh_gmv():
    #     """Background job: tự động refresh GMV cache mỗi 5 phút"""
    #     try:
    #         deallist_url = get_config('spreadsheet_url')
    #         deallist_sheet = get_config('deallist_sheet')
    #         
    #         if deallist_url and deallist_sheet:
    #             print(f"[AUTO-REFRESH] Starting GMV refresh at {datetime.now()}")
    #             data = get_gmv_from_sheet(
    #                 limit=500,
    #                 deallist_url=deallist_url,
    #                 deallist_sheet_name=deallist_sheet,
    #                 force_refresh=True
    #             )
    #             print(f"[AUTO-REFRESH] Completed: {len(data)} items cached")
    #         else:
    #             print("[AUTO-REFRESH] Skipped: Deal List config not set")
    #     except Exception as e:
    #         print(f"[AUTO-REFRESH] Error: {e}")
    
    # Scheduler DISABLED - GMV data comes from local scraper -> PostgreSQL
    # try:
    #     from apscheduler.schedulers.background import BackgroundScheduler
    #     scheduler = BackgroundScheduler()
    #     scheduler.add_job(auto_refresh_gmv, 'interval', minutes=5, id='auto_refresh_gmv')
    #     scheduler.start()
    #     print("[SCHEDULER] Background scheduler started with auto-refresh GMV every 5 min")
    # except Exception as e:
    #     print(f"[WARNING] Scheduler failed to start: {e}")
    
    print("[INFO] GMV data comes from local scraper -> PostgreSQL (scheduler disabled)")

    
    auto_sync_state = {
        'running': False,
        'job_id': None,
        'last_auto_sync': None,
        'next_sync': None
    }
    
    def auto_sync_job():
        """Background job that syncs Deal List every 5 minutes"""
        now = datetime.now()
        
        try:
            spreadsheet_url = get_config('spreadsheet_url')
            deallist_sheet = get_config('deallist_sheet')
            
            if spreadsheet_url and deallist_sheet:
                count = sync_deal_list_only(spreadsheet_url, deallist_sheet)
                auto_sync_state['last_auto_sync'] = now.isoformat()
                print(f"[AUTO-SYNC] {now.strftime('%H:%M:%S')} - Updated {count} products with Deal List")
            else:
                print(f"[AUTO-SYNC] Missing configuration. Skipping sync.")
        except Exception as e:
            print(f"[AUTO-SYNC] Error: {str(e)}")
        
        auto_sync_state['next_sync'] = (now.replace(second=0, microsecond=0) + 
                                         __import__('datetime').timedelta(seconds=300)).isoformat()
    
    def start_auto_sync():
        """Start the auto-sync scheduler"""
        if scheduler is None:
            return False
        
        if auto_sync_state['job_id']:
            stop_auto_sync()
        
        auto_sync_state['running'] = True
        auto_sync_job()
        
        job = scheduler.add_job(
            auto_sync_job,
            'interval',
            seconds=300,
            id='auto_sync_job'
        )
        auto_sync_state['job_id'] = job.id
        return True
    
    def stop_auto_sync():
        """Stop the auto-sync scheduler"""
        if auto_sync_state['job_id'] and scheduler:
            try:
                scheduler.remove_job(auto_sync_state['job_id'])
            except:
                pass
        
        auto_sync_state['running'] = False
        auto_sync_state['job_id'] = None
        auto_sync_state['next_sync'] = None
    
    # ============== Auth Decorator ==============
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('is_admin'):
                return redirect(url_for('admin_login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ============== Routes ==============
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/analytics')
    def analytics():
        return render_template('analytics.html')
    
    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
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
        session.pop('is_admin', None)
        return redirect(url_for('index'))
    
    @app.route('/admin')
    @admin_required
    def admin():
        config = {
            'spreadsheet_url': get_config('spreadsheet_url') or '',
            'rawdata_sheet': get_config('rawdata_sheet') or '',
            'deallist_sheet': get_config('deallist_sheet') or '',
            'last_sync': get_config('last_deallist_sync') or 'Chưa sync'
        }
        return render_template('admin.html', config=config)
    
    # ============== API Routes ==============
    @app.route('/api/top-gmv')
    def api_top_gmv():
        limit = request.args.get('limit', 500, type=int)
        
        # Đọc từ PostgreSQL với JOIN deal_list
        db_url = os.environ.get('DATABASE_URL', '')
        
        if db_url:
            try:
                # Dùng function mới đọc với JOIN deal_list
                data = get_gmv_with_deallist(db_url, limit=limit)
                
                if data:
                    return jsonify({
                        'success': True,
                        'data': data,
                        'count': len(data),
                        'source': 'postgresql_with_deallist',
                        'last_sync': get_config('last_deallist_sync') or datetime.now().isoformat()
                    })
            except Exception as e:
                print(f"[API] PostgreSQL error: {e}")
        
        # Fallback: Đọc từ Google Sheet
        deallist_url = get_config('spreadsheet_url')
        deallist_sheet = get_config('deallist_sheet')
        
        try:
            data = get_gmv_from_sheet(
                limit=limit,
                deallist_url=deallist_url,
                deallist_sheet_name=deallist_sheet
            )
            
            return jsonify({
                'success': True,
                'data': data,
                'count': len(data),
                'source': 'google_sheet',
                'last_sync': datetime.now().isoformat()
            })
        except Exception as e:
            print(f"[API] Error reading from Sheet: {e}")
            # Fallback to SQLite if Sheet fails
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT item_id, item_name, revenue, shop_id, link_sp, datetime, clicks, ctr, orders, items_sold, cluster
                    FROM gmv_data
                    ORDER BY revenue DESC
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
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
                        'cluster': row['cluster']
                    })
                
                return jsonify({
                    'success': True,
                    'data': data,
                    'count': len(data),
                    'source': 'sqlite_fallback',
                    'error': str(e),
                    'last_sync': get_config('last_deallist_sync')
                })
            except Exception as e2:
                return jsonify({
                    'success': False,
                    'error': f'Sheet error: {e}, SQLite error: {e2}'
                }), 500
    
    @app.route('/api/refresh-gmv', methods=['POST'])
    @admin_required
    def api_refresh_gmv():
        """Force refresh GMV cache"""
        try:
            deallist_url = get_config('spreadsheet_url')
            deallist_sheet = get_config('deallist_sheet')
            
            data = get_gmv_from_sheet(
                limit=500,
                deallist_url=deallist_url,
                deallist_sheet_name=deallist_sheet,
                force_refresh=True
            )
            
            return jsonify({
                'success': True,
                'message': f'Đã refresh {len(data)} items từ GMV Sheet',
                'count': len(data),
                'cache_ttl': GMV_CACHE_TTL,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/refresh-deallist', methods=['POST'])
    @admin_required
    def api_refresh_deallist():
        """Force refresh Deal List cache + clear GMV cache"""
        global _gmv_cache
        try:
            deallist_url = get_config('spreadsheet_url')
            deallist_sheet = get_config('deallist_sheet')
            
            item_to_shop, item_to_cluster = get_deallist_mapping(
                deallist_url=deallist_url,
                deallist_sheet_name=deallist_sheet,
                force_refresh=True
            )
            
            # Clear GMV cache để lần load tiếp theo sẽ apply mapping mới
            _gmv_cache['data'] = None
            _gmv_cache['timestamp'] = None
            
            return jsonify({
                'success': True,
                'message': f'Đã refresh {len(item_to_shop)} items từ Deal List. GMV cache đã xóa.',
                'count': len(item_to_shop),
                'cache_ttl': DEALLIST_CACHE_TTL,
                'gmv_cache_cleared': True,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/cache-status')
    @admin_required
    def api_cache_status():
        """Get cache status"""
        now = datetime.now()
        
        gmv_age = None
        deallist_age = None
        
        if _gmv_cache['timestamp']:
            gmv_age = (now - _gmv_cache['timestamp']).total_seconds()
        if _deallist_cache['timestamp']:
            deallist_age = (now - _deallist_cache['timestamp']).total_seconds()
        
        return jsonify({
            'gmv': {
                'has_data': _gmv_cache['data'] is not None,
                'count': len(_gmv_cache['data']) if _gmv_cache['data'] else 0,
                'age_seconds': gmv_age,
                'ttl': GMV_CACHE_TTL,
                'last_update': _gmv_cache['timestamp'].isoformat() if _gmv_cache['timestamp'] else None
            },
            'deallist': {
                'count': len(_deallist_cache['item_to_shop']),
                'age_seconds': deallist_age,
                'ttl': DEALLIST_CACHE_TTL,
                'last_update': _deallist_cache['timestamp'].isoformat() if _deallist_cache['timestamp'] else None
            }
        })
    @app.route('/api/sheets', methods=['POST'])
    @admin_required
    def api_get_sheets():
        data = request.get_json()
        spreadsheet_url = data.get('spreadsheet_url', '')
        deallist_sheet = data.get('deallist_sheet', '')
        
        if not spreadsheet_url:
            return jsonify({'success': False, 'error': 'URL không được để trống'})
        
        # Nếu có deallist_sheet, lưu cả 2 vào config
        if deallist_sheet:
            set_config('spreadsheet_url', spreadsheet_url)
            set_config('deallist_sheet', deallist_sheet)
            print(f"[CONFIG] Saved: URL={spreadsheet_url[:50]}... Sheet={deallist_sheet}")
        
        try:
            sheets = get_spreadsheet_sheets(spreadsheet_url)
            return jsonify({'success': True, 'sheets': sheets})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/sync-deallist', methods=['POST'])
    @admin_required
    def api_sync_deallist():
        """API: Sync Deal List only (map shop_id, cluster, link)"""
        data = request.get_json()
        spreadsheet_url = data.get('spreadsheet_url', '')
        deallist_sheet = data.get('deallist_sheet', '')
        
        if not spreadsheet_url or not deallist_sheet:
            return jsonify({'success': False, 'error': 'Vui lòng điền đầy đủ thông tin'})
        
        try:
            # Save config
            set_config('spreadsheet_url', spreadsheet_url)
            set_config('deallist_sheet', deallist_sheet)
            
            # Sync Deal List only
            count = sync_deal_list_only(spreadsheet_url, deallist_sheet)
            
            return jsonify({
                'success': True,
                'message': f'Đã cập nhật {count} sản phẩm với Deal List',
                'count': count
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/auto-sync/status')
    @admin_required
    def api_auto_sync_status():
        return jsonify({
            'success': True,
            'running': auto_sync_state['running'],
            'last_auto_sync': auto_sync_state['last_auto_sync'],
            'next_sync': auto_sync_state['next_sync']
        })
    
    @app.route('/api/auto-sync/start', methods=['POST'])
    @admin_required
    def api_auto_sync_start():
        spreadsheet_url = get_config('spreadsheet_url')
        deallist_sheet = get_config('deallist_sheet')
        
        if not spreadsheet_url or not deallist_sheet:
            return jsonify({'success': False, 'error': 'Chưa cấu hình. Vui lòng sync thủ công trước.'})
        
        result = start_auto_sync()
        if not result:
            return jsonify({'success': False, 'error': 'Scheduler chưa sẵn sàng.'})
        
        return jsonify({
            'success': True,
            'message': 'Auto-sync Deal List đã bắt đầu. Mỗi 5 phút.'
        })
    
    @app.route('/api/auto-sync/stop', methods=['POST'])
    @admin_required
    def api_auto_sync_stop():
        stop_auto_sync()
        return jsonify({'success': True, 'message': 'Auto-sync đã dừng'})
    
    @app.route('/api/config')
    @admin_required
    def api_config():
        return jsonify({
            'success': True,
            'config': {
                'spreadsheet_url': get_config('spreadsheet_url') or '',
                'deallist_sheet': get_config('deallist_sheet') or '',
                'last_sync': get_config('last_deallist_sync') or 'Chưa sync'
            }
        })
    
    @app.route('/api/analytics/category-distribution')
    def api_category_distribution():
        conn = get_db()
        cursor = conn.cursor()
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
        
        return jsonify({'success': True, 'data': data})
    
    @app.route('/api/analytics/top-products')
    def api_top_products():
        conn = get_db()
        cursor = conn.cursor()
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
            name = row['item_name'] or 'N/A'
            if len(name) > 30:
                name = name[:30] + '...'
            data.append({
                'name': name,
                'revenue': row['revenue'] or 0,
                'orders': row['orders'] or 0
            })
        
        return jsonify({'success': True, 'data': data})
    
    @app.route('/api/item-analytics/<item_id>')
    def api_item_analytics(item_id):
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT item_name, revenue, clicks, file_name, session_name
            FROM raw_session_data
            WHERE item_id = ?
        ''', (item_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return jsonify({'success': False, 'error': 'Không tìm thấy Item ID'})
        
        sessions = []
        total_revenue = 0
        total_clicks = 0
        item_name = ''
        
        for row in rows:
            if not item_name and row['item_name']:
                item_name = row['item_name']
            
            sessions.append({
                'session': row['session_name'] or 'N/A',
                'file': row['file_name'] or 'N/A',
                'revenue': row['revenue'] or 0,
                'clicks': row['clicks'] or 0
            })
            total_revenue += row['revenue'] or 0
            total_clicks += row['clicks'] or 0
        
        # Fallback to gmv_data
        if not item_name:
            conn2 = get_db()
            cursor2 = conn2.cursor()
            cursor2.execute('SELECT item_name FROM gmv_data WHERE item_id = ?', (item_id,))
            gmv_row = cursor2.fetchone()
            conn2.close()
            if gmv_row and gmv_row['item_name']:
                item_name = gmv_row['item_name']
        
        return jsonify({
            'success': True,
            'item_id': item_id,
            'item_name': item_name,
            'total_revenue': total_revenue,
            'total_clicks': total_clicks,
            'session_count': len(sessions),
            'sessions': sessions
        })
    
    # ============== Overview Metrics API Routes ==============
    
    @app.route('/api/overview/live')
    @admin_required
    def api_overview_live():
        """
        Get real-time overview metrics for a session.
        
        Query params:
            session_id: Session ID (required)
        
        Returns:
            {
                'success': True,
                'data': {metrics dict},
                'session_id': '...',
                'session_title': '...',
                'scraped_at': '...'
            }
        """
        from db_helpers import get_overview_live
        
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'Missing session_id'}), 400
        
        db_url = os.environ.get('DATABASE_URL', '')
        if not db_url:
            return jsonify({'success': False, 'error': 'Database not configured'}), 500
        
        data = get_overview_live(db_url, session_id)
        
        if data:
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'error': 'No data found'}), 404
    
    @app.route('/api/overview/history')
    @admin_required
    def api_overview_history():
        """
        Get historical overview metrics for a session.
        
        Query params:
            session_id: Session ID (required)
            limit: Number of records (default: 10)
        
        Returns:
            {
                'success': True,
                'data': [list of metrics snapshots],
                'count': N
            }
        """
        from db_helpers import get_overview_history
        
        session_id = request.args.get('session_id')
        limit = request.args.get('limit', 10, type=int)
        
        if not session_id:
            return jsonify({'success': False, 'error': 'Missing session_id'}), 400
        
        db_url = os.environ.get('DATABASE_URL', '')
        data = get_overview_history(db_url, session_id, limit)
        
        return jsonify({'success': True, 'data': data, 'count': len(data)})
    
    @app.route('/api/overview/sessions')
    @admin_required
    def api_overview_sessions():
        """
        Get list of sessions with overview data.
        
        Returns:
            {
                'success': True,
                'sessions': [
                    {'session_id': '...', 'session_title': '...', 'last_scraped': '...'},
                    ...
                ]
            }
        """
        from db_helpers import get_overview_sessions
        
        db_url = os.environ.get('DATABASE_URL', '')
        sessions = get_overview_sessions(db_url)
        
        return jsonify({'success': True, 'sessions': sessions})
    
    # Return app for gunicorn
    return app

def run_web_mode():
    """Chạy Flask app với development server"""
    app = create_app()
    port = int(os.environ.get('PORT', 4000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)


# ============== Module Level App (for gunicorn) ==============
# Gunicorn import module và tìm 'app' - chỉ tạo khi được import, không phải khi chạy trực tiếp
if __name__ != '__main__':
    app = create_app()

# ============== Main Entry Point ==============

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GMV App - Scraper + Web Dashboard')
    parser.add_argument('--mode', '-m', choices=['gui', 'web'], default='gui',
                        help='Mode: gui (Scraper GUI) hoặc web (Flask Server)')
    parser.add_argument('--web', '-w', action='store_true',
                        help='Shortcut cho --mode web')
    parser.add_argument('--gui', '-g', action='store_true',
                        help='Shortcut cho --mode gui')
    
    args = parser.parse_args()
    
    # Xác định mode
    if args.web:
        mode = 'web'
    elif args.gui:
        mode = 'gui'
    else:
        mode = args.mode
    
    print(f"🚀 GMV App - Starting in {mode.upper()} mode...")
    
    if mode == 'web':
        run_web_mode()
    else:
        run_gui_mode()
