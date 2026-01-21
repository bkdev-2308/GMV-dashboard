# -*- coding: utf-8 -*-
"""
Helper module cho PostgreSQL và Google Sheets integration.
Import vào full_gmv.py để sử dụng.
"""
import os

# PostgreSQL
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

CSV_HEADER = ["DateTime","Item ID","Tên sản phẩm","Lượt click trên sản phẩm","Tỷ lệ click vào sản phẩm","Tổng đơn hàng","Các mặt hàng được bán","Doanh thu", "Tỷ lệ click để đặt hàng", "Thêm vào giỏ hàng"]

def get_gspread_client(key_path=None):
    """Tạo gspread client từ service account key"""
    if not HAS_GSPREAD:
        return None
    if key_path is None:
        key_path = os.path.join(os.path.dirname(__file__), 'service-account-key.json')
    if not os.path.exists(key_path):
        return None
    creds = Credentials.from_service_account_file(key_path, scopes=[
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ])
    return gspread.authorize(creds)

def load_sheets_from_url(sheet_url):
    """Load danh sách sheet names từ Google Sheet URL"""
    gc = get_gspread_client()
    if not gc:
        return []
    try:
        spreadsheet = gc.open_by_url(sheet_url)
        return [ws.title for ws in spreadsheet.worksheets()]
    except Exception as e:
        print(f"Error loading sheets: {e}")
        return []


import re

def parse_sheet_title(sheet_name):
    """
    Parse Google Sheet title để tạo session title ngắn gọn.
    
    Input: "[16.01] Internal | Vũ Ngọc Anh x Phát La"
    Output: "[16.01] Vũ Ngọc Anh x Phát La"
    
    Nếu không có format chuẩn, trả về sheet_name gốc.
    """
    if not sheet_name:
        return sheet_name
    
    # Tìm phần ngày trong []
    date_match = re.search(r'\[[\d.]+\]', sheet_name)
    date_part = date_match.group(0) if date_match else ""
    
    # Lấy phần sau dấu | (KOL name)
    if '|' in sheet_name:
        kol_part = sheet_name.split('|')[-1].strip()
    else:
        # Nếu không có |, lấy phần sau [] (bỏ "Internal")
        if date_part:
            after_date = sheet_name[sheet_name.find(']')+1:].strip()
            kol_part = after_date
        else:
            kol_part = sheet_name
    
    # Combine
    if date_part and kol_part:
        return f"{date_part} {kol_part}"
    elif date_part:
        return date_part
    elif kol_part:
        return kol_part
    else:
        return sheet_name

def save_to_google_sheet(rows, sheet_url, sheet_name, log_func=print):
    """
    Ghi dữ liệu vào Google Sheet (append mode như CSV).
    - Tự động thêm header nếu sheet trống
    - Append rows vào cuối sheet
    """
    if not HAS_GSPREAD:
        log_func("⚠️ gspread chưa được cài đặt")
        return False
    if not sheet_url or not sheet_name:
        log_func("⚠️ Chưa chọn Google Sheet hoặc sheet")
        return False
    try:
        gc = get_gspread_client()
        if not gc:
            log_func("⚠️ Không tìm thấy service-account-key.json")
            return False
        spreadsheet = gc.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # Check if need header
        existing = worksheet.get_all_values()
        if len(existing) == 0:
            worksheet.append_row(CSV_HEADER)
        
        # Append rows
        if rows:
            worksheet.append_rows(rows)
        log_func(f"✅ Google Sheet: Đã thêm {len(rows)} dòng vào '{sheet_name}'")
        return True
    except Exception as e:
        log_func(f"❌ Google Sheet error: {e}")
        return False

def save_to_postgresql(rows, db_url, log_func=print):
    """
    Ghi dữ liệu vào PostgreSQL với upsert theo item_id.
    - Sử dụng batch insert để tối ưu tốc độ
    - Upsert: ghi đè item nếu đã tồn tại
    """
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return False
    if not db_url:
        log_func("⚠️ Chưa nhập DATABASE_URL")
        return False
    try:
        log_func("🐘 Đang kết nối PostgreSQL...")
        conn = psycopg2.connect(db_url, connect_timeout=10)
        log_func("🐘 Đã kết nối thành công!")
        cursor = conn.cursor()
        
        # Create table if not exists (with add_to_cart column)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gmv_data (
                item_id TEXT PRIMARY KEY,
                item_name TEXT,
                clicks INTEGER,
                ctr TEXT,
                orders INTEGER,
                items_sold INTEGER,
                revenue INTEGER,
                datetime TEXT,
                shop_id TEXT,
                link_sp TEXT,
                cluster TEXT,
                add_to_cart INTEGER,
                confirmed_revenue INTEGER
            )
        ''')
        
        # Add confirmed_revenue column if not exists (for existing tables)
        try:
            cursor.execute('ALTER TABLE gmv_data ADD COLUMN IF NOT EXISTS confirmed_revenue INTEGER DEFAULT 0')
        except:
            pass
        
        # Prepare batch data
        batch_data = []
        for row in rows:
            if len(row) < 8:
                continue
            datetime_val = str(row[0]) if row[0] else ""
            item_id = str(row[1]).strip() if row[1] else ""
            item_name = str(row[2]) if row[2] else ""
            
            def safe_int(val):
                if val is None or val == '':
                    return 0
                s = str(val).replace(',', '').replace('.', '').strip()
                try:
                    return int(s) if s else 0
                except:
                    return 0
            
            clicks = safe_int(row[3])
            ctr = str(row[4]) if row[4] else ""
            orders = safe_int(row[5])
            items_sold = safe_int(row[6])
            revenue = safe_int(row[7])
            # Index 8 = "Tỷ lệ click để đặt hàng" (click_to_order)
            # Index 9 = "Thêm vào giỏ hàng" (add_to_cart)
            add_to_cart = safe_int(row[9]) if len(row) > 9 else 0
            confirmed_revenue = safe_int(row[10]) if len(row) > 10 else 0
            
            if not item_id:
                continue
            
            batch_data.append((item_id, item_name, clicks, ctr, orders, items_sold, revenue, datetime_val, add_to_cart, confirmed_revenue))
        
        # XÓA DỮ LIỆU CŨ trước khi ghi mới (giống Google Sheet)
        log_func("🗑️ Xóa dữ liệu cũ...")
        cursor.execute("DELETE FROM gmv_data")
        
        # Batch insert (faster than upsert since table is empty)
        log_func(f"🐘 Đang ghi {len(batch_data)} items...")
        
        upsert_sql = '''
            INSERT INTO gmv_data (item_id, item_name, clicks, ctr, orders, items_sold, revenue, datetime, add_to_cart, confirmed_revenue)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (item_id) DO UPDATE SET
                item_name = EXCLUDED.item_name,
                clicks = EXCLUDED.clicks,
                ctr = EXCLUDED.ctr,
                orders = EXCLUDED.orders,
                items_sold = EXCLUDED.items_sold,
                revenue = EXCLUDED.revenue,
                datetime = EXCLUDED.datetime,
                add_to_cart = EXCLUDED.add_to_cart,
                confirmed_revenue = EXCLUDED.confirmed_revenue
        '''
        
        # Use execute_batch for speed (page_size=500 for optimal performance)
        psycopg2.extras.execute_batch(cursor, upsert_sql, batch_data, page_size=500)
        
        conn.commit()
        conn.close()
        log_func(f"✅ PostgreSQL: Upserted {len(batch_data)} items")
        return True
    except Exception as e:
        log_func(f"❌ PostgreSQL error: {e}")
        return False


def init_deal_list_table(db_url, log_func=print):
    """Tạo bảng deal_list nếu chưa có"""
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return False
    if not db_url:
        log_func("⚠️ Chưa có DATABASE_URL")
        return False
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deal_list (
                item_id TEXT PRIMARY KEY,
                shop_id TEXT,
                cluster TEXT
            )
        ''')
        conn.commit()
        conn.close()
        log_func("✅ Bảng deal_list đã sẵn sàng")
        return True
    except Exception as e:
        log_func(f"❌ Lỗi tạo bảng deal_list: {e}")
        return False


def save_deal_list_to_postgresql(deal_list_data, db_url, log_func=print):
    """
    Lưu Deal List vào PostgreSQL.
    deal_list_data: list of dicts với keys: item_id, shop_id, cluster
    """
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return 0
    if not db_url:
        log_func("⚠️ Chưa có DATABASE_URL")
        return 0
    if not deal_list_data:
        log_func("⚠️ Không có data để lưu")
        return 0
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor()
        
        # Tạo bảng nếu chưa có
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deal_list (
                item_id TEXT PRIMARY KEY,
                shop_id TEXT,
                cluster TEXT
            )
        ''')
        
        # Xóa data cũ
        cursor.execute("DELETE FROM deal_list")
        log_func(f"🗑️ Đã xóa data cũ trong deal_list")
        
        # Batch insert
        batch_data = []
        for item in deal_list_data:
            item_id = str(item.get('item_id', '')).strip()
            shop_id = str(item.get('shop_id', '')).strip()
            cluster = str(item.get('cluster', '')).strip()
            if item_id and shop_id:
                batch_data.append((item_id, shop_id, cluster))
        
        if batch_data:
            insert_sql = '''
                INSERT INTO deal_list (item_id, shop_id, cluster)
                VALUES (%s, %s, %s)
                ON CONFLICT (item_id) DO UPDATE SET
                    shop_id = EXCLUDED.shop_id,
                    cluster = EXCLUDED.cluster
            '''
            psycopg2.extras.execute_batch(cursor, insert_sql, batch_data, page_size=500)
        
        conn.commit()
        conn.close()
        log_func(f"✅ Đã lưu {len(batch_data)} items vào deal_list (PostgreSQL)")
        return len(batch_data)
    except Exception as e:
        log_func(f"❌ Lỗi lưu deal_list: {e}")
        return 0


def get_gmv_with_deallist(db_url, limit=500, sort_by='revenue', sort_dir='desc', log_func=print):
    """
    Lấy GMV data đã JOIN với deal_list.
    Tự động map shop_id, cluster, link từ deal_list.
    """
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return []
    if not db_url:
        log_func("⚠️ Chưa có DATABASE_URL")
        return []
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # LEFT JOIN để lấy shop_id và cluster từ deal_list
        query = '''
            SELECT 
                g.item_id,
                g.item_name,
                g.clicks,
                g.ctr,
                g.orders,
                g.items_sold,
                g.revenue,
                g.datetime,
                g.add_to_cart,
                COALESCE(d.shop_id, g.shop_id) as shop_id,
                COALESCE(d.cluster, g.cluster) as cluster,
                CASE 
                    WHEN COALESCE(d.shop_id, g.shop_id) IS NOT NULL AND COALESCE(d.shop_id, g.shop_id) != '' 
                    THEN 'https://shopee.vn/a-i.' || COALESCE(d.shop_id, g.shop_id) || '.' || g.item_id
                    ELSE g.link_sp
                END as link_sp
            FROM gmv_data g
            LEFT JOIN deal_list d ON g.item_id = d.item_id
            ORDER BY g.revenue DESC NULLS LAST
            LIMIT %s
        '''
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to list of dicts
        result = []
        for row in rows:
            result.append(dict(row))
        
        log_func(f"[DB] Loaded {len(result)} items with deal_list mapping")
        return result
    except Exception as e:
        log_func(f"❌ Lỗi đọc data: {e}")
        return []


# ============== MULTI-SESSION FUNCTIONS ==============

def init_multi_session_tables(db_url, log_func=print):
    """
    Khởi tạo schema cho multi-session:
    - Thêm cột session_id, session_title, scraped_at vào gmv_data
    - Tạo bảng gmv_history
    """
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return False
    if not db_url:
        log_func("⚠️ Chưa có DATABASE_URL")
        return False
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor()
        
        # 1. Add new columns to gmv_data if not exists
        alter_statements = [
            "ALTER TABLE gmv_data ADD COLUMN IF NOT EXISTS session_id TEXT",
            "ALTER TABLE gmv_data ADD COLUMN IF NOT EXISTS session_title TEXT",
            "ALTER TABLE gmv_data ADD COLUMN IF NOT EXISTS scraped_at TIMESTAMP DEFAULT NOW()"
        ]
        for stmt in alter_statements:
            try:
                cursor.execute(stmt)
            except Exception as e:
                log_func(f"⚠️ Column may already exist: {e}")
        
        # 2. Create gmv_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gmv_history (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                session_title TEXT,
                archived_at TIMESTAMP NOT NULL,
                item_id TEXT NOT NULL,
                item_name TEXT,
                revenue INTEGER,
                confirmed_revenue INTEGER,
                clicks INTEGER,
                orders INTEGER,
                items_sold INTEGER,
                add_to_cart INTEGER,
                ctr TEXT,
                datetime TEXT,
                shop_id TEXT,
                link_sp TEXT,
                cluster TEXT
            )
        ''')
        
        # 3. Create indexes for gmv_history
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_history_session ON gmv_history(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_history_archived ON gmv_history(archived_at)",
            "CREATE INDEX IF NOT EXISTS idx_history_session_archived ON gmv_history(session_id, archived_at)"
        ]
        for stmt in index_statements:
            try:
                cursor.execute(stmt)
            except Exception as e:
                log_func(f"⚠️ Index may already exist: {e}")
        
        # 4. Migrate gmv_data PRIMARY KEY to composite (item_id, session_id)
        # This allows same product to exist in multiple sessions independently
        try:
            # Check if we need to migrate (if old PK exists)
            cursor.execute('''
                SELECT COUNT(*) FROM pg_constraint 
                WHERE conname = 'gmv_data_pkey' 
                  AND contype = 'p'
            ''')
            pk_exists = cursor.fetchone()[0] > 0
            
            if pk_exists:
                # Check if it's already composite by looking at column count
                cursor.execute('''
                    SELECT COUNT(*) FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    WHERE t.relname = 'gmv_data' 
                      AND c.contype = 'p'
                      AND array_length(c.conkey, 1) = 1
                ''')
                is_single_column_pk = cursor.fetchone()[0] > 0
                
                if is_single_column_pk:
                    log_func("🔄 Migrating gmv_data PRIMARY KEY to composite (session_id, item_id)...")
                    # Drop old PK and create new composite PK
                    cursor.execute('ALTER TABLE gmv_data DROP CONSTRAINT gmv_data_pkey')
                    cursor.execute('ALTER TABLE gmv_data ADD PRIMARY KEY (session_id, item_id)')
                    log_func("✅ PRIMARY KEY migrated to composite (session_id, item_id)")
        except Exception as e:
            log_func(f"⚠️ PK migration note: {e}")
        
        # 5. Add is_archived column to gmv_data (for session lifecycle)
        try:
            cursor.execute('''
                ALTER TABLE gmv_data ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE
            ''')
            log_func("✅ Added is_archived column to gmv_data")
        except Exception as e:
            log_func(f"⚠️ is_archived column note: {e}")
        
        conn.commit()
        conn.close()
        log_func("✅ Multi-session schema initialized")
        return True
    except Exception as e:
        log_func(f"❌ Error initializing multi-session schema: {e}")
        return False


def save_to_postgresql_multi_session(rows, db_url, session_id, session_title="", log_func=print):
    """
    Ghi dữ liệu vào PostgreSQL với multi-session support.
    - UPSERT theo (item_id, session_id)
    - Không xóa data của session khác
    """
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return False
    if not db_url:
        log_func("⚠️ Chưa nhập DATABASE_URL")
        return False
    if not session_id:
        log_func("⚠️ Chưa có session_id")
        return False
    
    try:
        log_func(f"🐘 Đang kết nối PostgreSQL (session: {session_id})...")
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor()
        
        # Ensure multi-session columns exist
        init_multi_session_tables(db_url, log_func=lambda x: None)  # Silent init
        
        # Prepare batch data
        batch_data = []
        for row in rows:
            if len(row) < 8:
                continue
            datetime_val = str(row[0]) if row[0] else ""
            item_id = str(row[1]).strip() if row[1] else ""
            item_name = str(row[2]) if row[2] else ""
            
            def safe_int(val):
                if val is None or val == '':
                    return 0
                s = str(val).replace(',', '').replace('.', '').strip()
                try:
                    return int(s) if s else 0
                except:
                    return 0
            
            clicks = safe_int(row[3])
            ctr = str(row[4]) if row[4] else ""
            orders = safe_int(row[5])
            items_sold = safe_int(row[6])
            revenue = safe_int(row[7])
            add_to_cart = safe_int(row[9]) if len(row) > 9 else 0
            confirmed_revenue = safe_int(row[10]) if len(row) > 10 else 0
            
            if not item_id:
                continue
            
            batch_data.append((
                item_id, session_id, session_title,
                item_name, clicks, ctr, orders, items_sold, revenue,
                datetime_val, add_to_cart, confirmed_revenue
            ))
        
        # UPSERT with session_id (no DELETE!)
        log_func(f"🐘 Đang ghi {len(batch_data)} items (session: {session_id})...")
        
        upsert_sql = '''
            INSERT INTO gmv_data (
                item_id, session_id, session_title,
                item_name, clicks, ctr, orders, items_sold, revenue,
                datetime, add_to_cart, confirmed_revenue, scraped_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (session_id, item_id) DO UPDATE SET
                session_title = EXCLUDED.session_title,
                item_name = EXCLUDED.item_name,
                clicks = EXCLUDED.clicks,
                ctr = EXCLUDED.ctr,
                orders = EXCLUDED.orders,
                items_sold = EXCLUDED.items_sold,
                revenue = EXCLUDED.revenue,
                datetime = EXCLUDED.datetime,
                add_to_cart = EXCLUDED.add_to_cart,
                confirmed_revenue = EXCLUDED.confirmed_revenue,
                scraped_at = NOW()
        '''
        
        psycopg2.extras.execute_batch(cursor, upsert_sql, batch_data, page_size=500)
        
        conn.commit()
        conn.close()
        log_func(f"✅ PostgreSQL: Upserted {len(batch_data)} items (session: {session_id})")
        return True
    except Exception as e:
        log_func(f"❌ PostgreSQL error: {e}")
        return False


def archive_session_data(db_url, session_id, log_func=print):
    """
    Archive data của 1 session vào gmv_history, sau đó xóa khỏi gmv_data.
    Gọi hàm này mỗi 1 tiếng.
    """
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return False
    if not db_url or not session_id:
        log_func("⚠️ Thiếu db_url hoặc session_id")
        return False
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor()
        
        # 1. Copy data từ gmv_data vào gmv_history
        log_func(f"📦 Archiving session {session_id}...")
        cursor.execute('''
            INSERT INTO gmv_history (
                session_id, session_title, archived_at,
                item_id, item_name, revenue, confirmed_revenue,
                clicks, orders, items_sold, add_to_cart,
                ctr, datetime, shop_id, link_sp, cluster
            )
            SELECT 
                session_id, session_title, (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh'),
                item_id, item_name, revenue, confirmed_revenue,
                clicks, orders, items_sold, add_to_cart,
                ctr, datetime, shop_id, link_sp, cluster
            FROM gmv_data
            WHERE session_id = %s
        ''', (session_id,))
        archived_count = cursor.rowcount
        
        # NOTE: Không xóa data từ gmv_data - giữ nguyên để dashboard luôn có data live
        # (Đổi từ cut-paste sang copy-paste)
        
        conn.commit()
        conn.close()
        
        log_func(f"✅ Archived {archived_count} items to gmv_history (kept in gmv_data)")
        return True
    except Exception as e:
        log_func(f"❌ Archive error: {e}")
        return False


def get_active_sessions(db_url, log_func=print):
    """
    Lấy danh sách các session đang LIVE.
    """
    if not HAS_PSYCOPG2 or not db_url:
        return []
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if is_archived column exists
        cursor.execute('''
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'gmv_data' AND column_name = 'is_archived'
        ''')
        has_is_archived = cursor.fetchone() is not None
        
        if has_is_archived:
            cursor.execute('''
                SELECT 
                    session_id,
                    session_title,
                    COUNT(*) as item_count,
                    MAX(scraped_at) as last_scraped
                FROM gmv_data
                WHERE session_id IS NOT NULL
                  AND (is_archived IS NULL OR is_archived = FALSE)
                GROUP BY session_id, session_title
                ORDER BY last_scraped DESC
            ''')
        else:
            # Fallback if column doesn't exist yet
            cursor.execute('''
                SELECT 
                    session_id,
                    session_title,
                    COUNT(*) as item_count,
                    MAX(scraped_at) as last_scraped
                FROM gmv_data
                WHERE session_id IS NOT NULL
                GROUP BY session_id, session_title
                ORDER BY last_scraped DESC
            ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        log_func(f"❌ Error getting sessions: {e}")
        return []


def get_archived_sessions(db_url, log_func=print):
    """
    Lấy danh sách các session ĐÃ ARCHIVED (có trong gmv_history).
    """
    if not HAS_PSYCOPG2 or not db_url:
        return []
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute('''
            SELECT 
                session_id,
                session_title,
                COUNT(DISTINCT item_id) as item_count,
                COUNT(DISTINCT archived_at) as timeslot_count,
                MAX(archived_at) as last_archived
            FROM gmv_history
            WHERE session_id IS NOT NULL
            GROUP BY session_id, session_title
            ORDER BY last_archived DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        log_func(f"❌ Error getting archived sessions: {e}")
        return []


def get_history_timeslots(db_url, session_id, log_func=print):
    """
    Lấy danh sách các timeslot đã archive cho 1 session.
    """
    if not HAS_PSYCOPG2 or not db_url or not session_id:
        return []
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute('''
            SELECT 
                archived_at,
                COUNT(*) as item_count
            FROM gmv_history
            WHERE session_id = %s
            GROUP BY archived_at
            ORDER BY archived_at DESC
        ''', (session_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        log_func(f"❌ Error getting history timeslots: {e}")
        return []


def get_history_data(db_url, session_id, archived_at, log_func=print):
    """
    Lấy data từ gmv_history cho 1 session tại 1 thời điểm cụ thể.
    """
    if not HAS_PSYCOPG2 or not db_url or not session_id or not archived_at:
        return []
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute('''
            SELECT 
                h.item_id,
                h.item_name,
                h.revenue,
                h.confirmed_revenue,
                h.clicks,
                h.orders,
                h.items_sold,
                h.add_to_cart,
                h.ctr,
                h.datetime,
                COALESCE(d.shop_id, h.shop_id) as shop_id,
                COALESCE(d.cluster, h.cluster) as cluster,
                CASE 
                    WHEN COALESCE(d.shop_id, h.shop_id) IS NOT NULL AND COALESCE(d.shop_id, h.shop_id) != '' 
                    THEN 'https://shopee.vn/a-i.' || COALESCE(d.shop_id, h.shop_id) || '.' || h.item_id
                    ELSE h.link_sp
                END as link_sp
            FROM gmv_history h
            LEFT JOIN deal_list d ON h.item_id = d.item_id
            WHERE h.session_id = %s AND h.archived_at = %s
            ORDER BY h.revenue DESC NULLS LAST
        ''', (session_id, archived_at))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        log_func(f"❌ Error getting history data: {e}")
        return []

