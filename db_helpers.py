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
                cover_image TEXT,
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
            cursor.execute('''
                ALTER TABLE gmv_data 
                ADD COLUMN IF NOT EXISTS confirmed_revenue INTEGER DEFAULT 0
            ''')
        except Exception as e:
            # Column might already exist or PostgreSQL version doesn't support IF NOT EXISTS
            try:
                cursor.execute('ALTER TABLE gmv_data ADD COLUMN confirmed_revenue INTEGER DEFAULT 0')
            except:
                pass  # Column already exists
        
        # Add cover_image column if not exists
        try:
            cursor.execute('''
                ALTER TABLE gmv_data 
                ADD COLUMN IF NOT EXISTS cover_image TEXT
            ''')
        except Exception as e:
            # Column might already exist or PostgreSQL version doesn't support IF NOT EXISTS
            try:
                cursor.execute('ALTER TABLE gmv_data ADD COLUMN cover_image TEXT')
            except:
                pass  # Column already exists
        
        # Prepare batch data
        batch_data = []
        for row in rows:
            if len(row) < 8:
                continue
            datetime_val = str(row[0]) if row[0] else ""
            item_id = str(row[1]).strip() if row[1] else ""
            item_name = str(row[2]) if row[2] else ""
            cover_image = str(row[3]) if len(row) > 3 and row[3] else ""
            
            def safe_int(val):
                if val is None or val == '':
                    return 0
                s = str(val).replace(',', '').replace('.', '').strip()
                try:
                    return int(s) if s else 0
                except:
                    return 0
            
            clicks = safe_int(row[4]) if len(row) > 4 else 0
            ctr = str(row[5]) if len(row) > 5 and row[5] else ""
            orders = safe_int(row[6]) if len(row) > 6 else 0
            items_sold = safe_int(row[7]) if len(row) > 7 else 0
            revenue = safe_int(row[8]) if len(row) > 8 else 0
            # Index 9 = "Tỷ lệ click để đặt hàng" (click_to_order)
            # Index 10 = "Thêm vào giỏ hàng" (add_to_cart)
            add_to_cart = safe_int(row[10]) if len(row) > 10 else 0
            confirmed_revenue = safe_int(row[11]) if len(row) > 11 else 0
            
            if not item_id:
                continue
            
            batch_data.append((item_id, item_name, cover_image, clicks, ctr, orders, items_sold, revenue, datetime_val, add_to_cart, confirmed_revenue))
        
        # XÓA DỮ LIỆU CŨ trước khi ghi mới (giống Google Sheet)
        log_func("🗑️ Xóa dữ liệu cũ...")
        cursor.execute("DELETE FROM gmv_data")
        
        # Batch insert (faster than upsert since table is empty)
        log_func(f"🐘 Đang ghi {len(batch_data)} items...")
        
        upsert_sql = '''
            INSERT INTO gmv_data (item_id, item_name, cover_image, clicks, ctr, orders, items_sold, revenue, datetime, add_to_cart, confirmed_revenue)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (item_id) DO UPDATE SET
                item_name = EXCLUDED.item_name,
                cover_image = EXCLUDED.cover_image,
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
                g.cover_image,
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
            "ALTER TABLE gmv_data ADD COLUMN IF NOT EXISTS scraped_at TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE gmv_data ADD COLUMN IF NOT EXISTS cover_image TEXT"
        ]
        for stmt in alter_statements:
            try:
                cursor.execute(stmt)
            except Exception as e:
                # Fallback for PostgreSQL versions that don't support IF NOT EXISTS
                if "cover_image" in stmt:
                    try:
                        cursor.execute("ALTER TABLE gmv_data ADD COLUMN cover_image TEXT")
                    except:
                        pass  # Column already exists
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
                cover_image TEXT,
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

        # 6. Ensure Unique Index for ON CONFLICT (Critical for UPSERT)
        # First: Delete duplicates if any (keep latest)
        try:
            cursor.execute('''
                DELETE FROM gmv_data a USING gmv_data b
                WHERE a.ctid < b.ctid
                  AND a.item_id = b.item_id
                  AND a.session_id IS NOT DISTINCT FROM b.session_id
            ''')
            if cursor.rowcount > 0:
                log_func(f"🧹 Removed {cursor.rowcount} duplicate rows from gmv_data")
        except Exception as e:
            log_func(f"⚠️ Duplicate cleanup note: {e}")

        # Second: Re-create the index (Drop first to be sure)
        try:
            cursor.execute('DROP INDEX IF EXISTS idx_gmv_data_session_item')
            cursor.execute('''
                CREATE UNIQUE INDEX idx_gmv_data_session_item 
                ON gmv_data (session_id, item_id)
            ''')
            log_func("✅ Ensured unique index on (session_id, item_id)")
        except Exception as e:
            log_func(f"⚠️ Index creation note: {e}")
        
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
        
        # Ensure multi-session columns exist (Pass log_func to see errors!)
        init_multi_session_tables(db_url, log_func=log_func)
        
        # Prepare batch data
        batch_data = []
        for row in rows:
            if len(row) < 8:
                continue
            datetime_val = str(row[0]) if row[0] else ""
            item_id = str(row[1]).strip() if row[1] else ""
            item_name = str(row[2]) if row[2] else ""
            cover_image = str(row[3]) if len(row) > 3 and row[3] else ""
            
            def safe_int(val):
                if val is None or val == '':
                    return 0
                s = str(val).replace(',', '').replace('.', '').strip()
                try:
                    return int(s) if s else 0
                except:
                    return 0
            
            clicks = safe_int(row[4]) if len(row) > 4 else 0
            ctr = str(row[5]) if len(row) > 5 and row[5] else ""
            orders = safe_int(row[6]) if len(row) > 6 else 0
            items_sold = safe_int(row[7]) if len(row) > 7 else 0
            revenue = safe_int(row[8]) if len(row) > 8 else 0
            add_to_cart = safe_int(row[10]) if len(row) > 10 else 0
            confirmed_revenue = safe_int(row[11]) if len(row) > 11 else 0
            
            if not item_id:
                continue
            
            batch_data.append((
                item_id, session_id, session_title,
                item_name, cover_image, clicks, ctr, orders, items_sold, revenue,
                datetime_val, add_to_cart, confirmed_revenue
            ))
        
        # Remove duplicate item_ids (keep last occurrence)
        seen = {}
        for item in batch_data:
            item_id = item[0]  # item_id is first element in tuple
            seen[item_id] = item  # Overwrite with latest
        batch_data = list(seen.values())
        log_func(f"📦 Unique items after dedup: {len(batch_data)}")
        
        # DELETE existing data for this session, then INSERT fresh
        # This is more robust than UPSERT which requires unique index
        log_func(f"🐘 Đang ghi {len(batch_data)} items (session: {session_id})...")
        
        # 1. Delete existing data for this session
        cursor.execute('DELETE FROM gmv_data WHERE session_id = %s', (session_id,))
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            log_func(f"🗑️ Đã xóa {deleted_count} items cũ của session {session_id}")
        
        # 2. Insert all new data
        insert_sql = '''
            INSERT INTO gmv_data (
                item_id, session_id, session_title,
                item_name, cover_image, clicks, ctr, orders, items_sold, revenue,
                datetime, add_to_cart, confirmed_revenue, scraped_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        '''
        
        psycopg2.extras.execute_batch(cursor, insert_sql, batch_data, page_size=500)
        
        conn.commit()
        conn.close()
        log_func(f"✅ PostgreSQL: Inserted {len(batch_data)} items (session: {session_id})")
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
        
        # Check if recently archived (within 50 mins) to prevent duplicates
        cursor.execute('''
            SELECT 1 FROM gmv_history 
            WHERE session_id = %s 
              AND archived_at > (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh' - INTERVAL '50 minutes')
            LIMIT 1
        ''', (session_id,))
        if cursor.fetchone():
            log_func(f"⏳ Session {session_id} đã được archive trong vòng 50 phút qua. Bỏ qua.")
            conn.close()
            return True  # Return True so caller resets timer
        
        # Ensure cover_image column exists in gmv_history
        cursor.execute('''
            ALTER TABLE gmv_history ADD COLUMN IF NOT EXISTS cover_image TEXT
        ''')
        
        # 1. Copy data từ gmv_data vào gmv_history
        log_func(f"📦 Archiving session {session_id}...")
        cursor.execute('''
            INSERT INTO gmv_history (
                session_id, session_title, archived_at,
                item_id, item_name, cover_image, revenue, confirmed_revenue,
                clicks, orders, items_sold, add_to_cart,
                ctr, datetime, shop_id, link_sp, cluster
            )
            SELECT 
                session_id, session_title, (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh'),
                item_id, item_name, cover_image, revenue, confirmed_revenue,
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



def get_session_title_by_id(db_url, session_id, log_func=print):
    """
    Lấy session_title hiện tại trong DB (nếu có).
    Ưu tiên lấy title không phải là 'Session ...'
    """
    if not HAS_PSYCOPG2 or not db_url:
        return None
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor()
        
        # Lấy title phổ biến nhất hoặc title dài nhất
        # Ưu tiên title KHÔNG bắt đầu bằng "Session "
        cursor.execute('''
            SELECT session_title 
            FROM gmv_data 
            WHERE session_id = %s 
              AND session_title IS NOT NULL 
              AND session_title != ''
            ORDER BY 
                CASE WHEN session_title LIKE 'Session %%' THEN 1 ELSE 0 END,
                LENGTH(session_title) DESC
            LIMIT 1
        ''', (session_id,))
        
        row = cursor.fetchone()
        
        # Nếu không tìm thấy trong gmv_data, thử tìm trong gmv_history
        if not row:
            cursor.execute('''
                SELECT session_title 
                FROM gmv_history 
                WHERE session_id = %s 
                  AND session_title IS NOT NULL 
                  AND session_title != ''
                ORDER BY 
                    CASE WHEN session_title LIKE 'Session %%' THEN 1 ELSE 0 END,
                    LENGTH(session_title) DESC
                LIMIT 1
            ''', (session_id,))
            row = cursor.fetchone()

        conn.close()
        
        return row[0] if row else None
    except Exception as e:
        log_func(f"⚠️ Error getting session title: {e}")
        return None


def update_session_title(db_url, session_id, new_title, log_func=print):
    """
    Cập nhật session_title cho một session_id.
    Cập nhật cả trong gmv_data và gmv_history (nếu có).
    """
    if not HAS_PSYCOPG2 or not db_url:
        return False
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor()
        
        # 1. Update gmv_data
        cursor.execute('''
            UPDATE gmv_data 
            SET session_title = %s 
            WHERE session_id = %s
        ''', (new_title, session_id))
        count_data = cursor.rowcount
        
        # 2. Update gmv_history (optional but good for consistency)
        cursor.execute('''
            UPDATE gmv_history 
            SET session_title = %s 
            WHERE session_id = %s
        ''', (new_title, session_id))
        count_history = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        log_func(f"✅ Updated title for session {session_id}: '{new_title}' (Data: {count_data}, History: {count_history})")
        return True
    except Exception as e:
        log_func(f"❌ Error updating session title: {e}")
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
                    MAX(session_title) as session_title,
                    COUNT(*) as item_count,
                    MAX(scraped_at) as last_scraped
                FROM gmv_data
                WHERE session_id IS NOT NULL
                  AND (is_archived IS NULL OR is_archived = FALSE)
                GROUP BY session_id
                ORDER BY session_id DESC
                LIMIT 2
            ''')
        else:
            # Fallback if column doesn't exist yet
            cursor.execute('''
                SELECT 
                    session_id,
                    MAX(session_title) as session_title,
                    COUNT(*) as item_count,
                    MAX(scraped_at) as last_scraped
                FROM gmv_data
                WHERE session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY session_id DESC
                LIMIT 2
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
    KHÔNG JOIN với deal_list - sử dụng data đã lưu trong history.
    """
    if not HAS_PSYCOPG2 or not db_url or not session_id or not archived_at:
        return []
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Use historical shop_id, cluster, link_sp from gmv_history directly
        # Do NOT join with deal_list - it contains current session data, not historical
        cursor.execute('''
            SELECT 
                h.item_id,
                h.item_name,
                h.cover_image,
                h.revenue,
                h.confirmed_revenue,
                h.clicks,
                h.orders,
                h.items_sold,
                h.add_to_cart,
                h.ctr,
                h.datetime,
                h.shop_id,
                h.cluster,
                h.link_sp
            FROM gmv_history h
            WHERE h.session_id = %s AND h.archived_at = %s
            ORDER BY h.revenue DESC NULLS LAST
        ''', (session_id, archived_at))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        log_func(f"❌ Error getting history data: {e}")
        return []


def cleanup_old_sessions_auto(db_url, log_func=print):
    """
    Auto-cleanup: Keep only 2 newest sessions, delete old ones.
    Called on app startup.
    """
    if not HAS_PSYCOPG2 or not db_url:
        return False
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor()
        
        # Get all sessions ordered by session_id DESC (newest first)
        cursor.execute('''
            SELECT DISTINCT session_id 
            FROM gmv_data 
            WHERE session_id IS NOT NULL
            ORDER BY session_id DESC
        ''')
        all_sessions = [row[0] for row in cursor.fetchall()]
        
        if len(all_sessions) <= 2:
            conn.close()
            log_func(f"[CLEANUP] Only {len(all_sessions)} session(s), no cleanup needed")
            return True
        
        # Keep only 2 newest, delete the rest
        sessions_to_delete = all_sessions[2:]
        
        log_func(f"[CLEANUP] Deleting {len(sessions_to_delete)} old sessions: {sessions_to_delete}")
        
        # Delete old sessions
        deleted_count = 0
        for session_id in sessions_to_delete:
            cursor.execute('DELETE FROM gmv_data WHERE session_id = %s', (session_id,))
            deleted_count += cursor.rowcount
        
        conn.commit()
        conn.close()
        
        log_func(f"[CLEANUP] Deleted {deleted_count} items from {len(sessions_to_delete)} old sessions")
        return True
    except Exception as e:
        log_func(f"[CLEANUP] Error: {e}")
        return False


# ============== OVERVIEW METRICS FUNCTIONS ==============

def init_overview_tables(db_url=None, conn=None, log_func=print):
    """
    Khởi tạo schema cho overview metrics:
    - Tạo bảng overview_live (lưu dữ liệu real-time)
    - Tạo bảng overview_history (lưu dữ liệu đã archive)
    - Tạo indexes cho tối ưu truy vấn
    
    Args:
        db_url: PostgreSQL connection string (if conn not provided)
        conn: Existing connection (if provided, will not close it)
        log_func: Logging function
    """
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return False
    
    # Use existing connection or create new one
    close_conn = False
    if conn is None:
        if not db_url:
            log_func("⚠️ Chưa có DATABASE_URL")
            return False
        try:
            conn = psycopg2.connect(db_url, connect_timeout=10)
            close_conn = True
        except Exception as e:
            log_func(f"❌ Cannot connect to database: {e}")
            return False
    
    try:
        cursor = conn.cursor()
        
        # 1. Create overview_live table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS overview_live (
                session_id TEXT PRIMARY KEY,
                session_title TEXT,
                scraped_at TIMESTAMP DEFAULT NOW(),
                engaged_viewers INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                atc INTEGER DEFAULT 0,
                views BIGINT DEFAULT 0,
                avg_view_time NUMERIC DEFAULT 0,
                comments_rate TEXT DEFAULT '0%',
                gpm INTEGER DEFAULT 0,
                placed_order INTEGER DEFAULT 0,
                abs INTEGER DEFAULT 0,
                viewers INTEGER DEFAULT 0,
                pcu INTEGER DEFAULT 0,
                ctr TEXT DEFAULT '0%',
                co TEXT DEFAULT '0%',
                buyers INTEGER DEFAULT 0,
                placed_items_sold INTEGER DEFAULT 0
            )
        ''')
        log_func("✅ Bảng overview_live đã sẵn sàng")
        
        # 1.1. Drop old confirmed columns if they exist (one by one)
        columns_to_drop = ['gmv', 'confirmed_gmv', 'confirmed_order', 'confirmed_items_sold']
        for col in columns_to_drop:
            try:
                cursor.execute(f'ALTER TABLE overview_live DROP COLUMN IF EXISTS {col}')
            except Exception as drop_error:
                pass  # Column might not exist
        log_func("✅ Removed old metrics columns from overview_live")
        
        # 1.2. Create index for faster queries
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_overview_live_session ON overview_live(session_id)')
            log_func("✅ Created index on overview_live.session_id")
        except Exception as idx_error:
            log_func(f"[DEBUG] Index note: {idx_error}")
        
        # 2. Create overview_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS overview_history (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                session_title TEXT,
                archived_at TIMESTAMP NOT NULL,
                engaged_viewers INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                atc INTEGER DEFAULT 0,
                views BIGINT DEFAULT 0,
                avg_view_time NUMERIC DEFAULT 0,
                comments_rate TEXT DEFAULT '0%',
                gpm INTEGER DEFAULT 0,
                placed_order INTEGER DEFAULT 0,
                abs INTEGER DEFAULT 0,
                viewers INTEGER DEFAULT 0,
                pcu INTEGER DEFAULT 0,
                ctr TEXT DEFAULT '0%',
                co TEXT DEFAULT '0%',
                buyers INTEGER DEFAULT 0,
                placed_items_sold INTEGER DEFAULT 0
            )
        ''')
        log_func("✅ Bảng overview_history đã sẵn sàng")
        
        # 2.1. Drop old confirmed columns if they exist (one by one)
        columns_to_drop = ['gmv', 'confirmed_gmv', 'confirmed_order', 'confirmed_items_sold']
        for col in columns_to_drop:
            try:
                cursor.execute(f'ALTER TABLE overview_history DROP COLUMN IF EXISTS {col}')
            except Exception as drop_error:
                pass  # Column might not exist
        log_func("✅ Removed old metrics columns from overview_history")
        
        # 3. Create indexes for overview_history
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_overview_history_session ON overview_history(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_overview_history_archived ON overview_history(archived_at)",
            "CREATE INDEX IF NOT EXISTS idx_overview_history_session_archived ON overview_history(session_id, archived_at)"
        ]
        for stmt in index_statements:
            try:
                cursor.execute(stmt)
            except Exception as e:
                log_func(f"⚠️ Index may already exist: {e}")
        
        log_func("✅ Indexes cho overview_history đã được tạo")
        
        conn.commit()
        if close_conn:
            conn.close()
        log_func("✅ Overview metrics schema initialized")
        return True
    except Exception as e:
        log_func(f"❌ Error initializing overview schema: {e}")
        import traceback
        log_func(traceback.format_exc())
        if close_conn and conn:
            conn.close()
        return False


def save_overview_to_postgresql(metrics, db_url, session_id, session_title="", log_func=print):
    """
    Ghi overview metrics vào PostgreSQL.
    
    Args:
        metrics: dict với 22 keys (gmv, engaged_viewers, comments, atc, views, 
                 avg_view_time, comments_rate, gpm, placed_order, abs, viewers, 
                 pcu, ctr, co, buyers, placed_items_sold, confirmed_gmv, 
                 confirmed_order, confirmed_items_sold)
        db_url: PostgreSQL connection string
        session_id: Session ID
        session_title: Session title
        log_func: Logging function
    
    Returns:
        bool: True if successful
    
    Logic:
        1. DELETE FROM overview_live WHERE session_id = ?
        2. INSERT INTO overview_live VALUES (...)
    """
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return False
    if not db_url:
        log_func("⚠️ Chưa có DATABASE_URL")
        return False
    if not session_id:
        log_func("⚠️ Chưa có session_id")
        return False
    if not metrics:
        log_func("⚠️ Không có metrics để lưu")
        return False
    
    try:
        log_func(f"[DEBUG] Connecting to database...")
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor()
        log_func(f"[DEBUG] Connected successfully")
        
        # Ensure overview tables exist
        log_func(f"[DEBUG] Initializing overview tables...")
        tables_ok = init_overview_tables(conn=conn, log_func=log_func)
        if not tables_ok:
            log_func(f"❌ Failed to initialize overview tables")
            conn.close()
            return False
        log_func(f"[DEBUG] Tables initialized")
        
        # 1. DELETE existing row for this session_id
        try:
            log_func(f"[DEBUG] Deleting old data for session {session_id}...")
            cursor.execute('DELETE FROM overview_live WHERE session_id = %s', (session_id,))
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                log_func(f"🗑️ Đã xóa {deleted_count} dữ liệu overview cũ của session {session_id}")
            else:
                log_func(f"[DEBUG] No old data to delete")
        except Exception as delete_error:
            log_func(f"❌ Error deleting old overview data: {delete_error}")
            import traceback
            log_func(traceback.format_exc())
            conn.close()
            return False
        
        # 2. INSERT new metrics row with current timestamp
        insert_sql = '''
            INSERT INTO overview_live (
                session_id, session_title, scraped_at,
                engaged_viewers, comments, atc, views, avg_view_time,
                comments_rate, gpm, placed_order, abs, viewers, pcu,
                ctr, co, buyers, placed_items_sold
            )
            VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        
        try:
            log_func(f"[DEBUG] Inserting new overview data...")
            log_func(f"[DEBUG] Metrics: views={metrics.get('views')}, pcu={metrics.get('pcu')}, placed_order={metrics.get('placed_order')}")
            cursor.execute(insert_sql, (
                session_id,
                session_title,
                metrics.get('engaged_viewers', 0),
                metrics.get('comments', 0),
                metrics.get('atc', 0),
                metrics.get('views', 0),
                metrics.get('avg_view_time', 0),
                metrics.get('comments_rate', '0%'),
                metrics.get('gpm', 0),
                metrics.get('placed_order', 0),
                metrics.get('abs', 0),
                metrics.get('viewers', 0),
                metrics.get('pcu', 0),
                metrics.get('ctr', '0%'),
                metrics.get('co', '0%'),
                metrics.get('buyers', 0),
                metrics.get('placed_items_sold', 0)
            ))
            log_func(f"[DEBUG] Insert successful")
        except Exception as insert_error:
            log_func(f"❌ Error inserting overview data: {insert_error}")
            log_func(f"SQL: {insert_sql}")
            import traceback
            log_func(traceback.format_exc())
            conn.close()
            return False
        
        conn.commit()
        conn.close()
        
        log_func(f"✅ Overview metrics saved for session {session_id}")
        return True
    except psycopg2.OperationalError as conn_error:
        log_func(f"❌ Database connection failed: {conn_error}")
        return False
    except Exception as e:
        log_func(f"❌ Error saving overview metrics: {e}")
        import traceback
        log_func(traceback.format_exc())
        return False


def archive_overview_data(db_url, session_id, log_func=print):
    """
    Archive overview data từ overview_live vào overview_history.
    
    Args:
        db_url: PostgreSQL connection string
        session_id: Session ID to archive
        log_func: Logging function
    
    Returns:
        bool: True if successful
    
    Logic:
        1. Check if archived within last 50 minutes (prevent duplicates)
        2. INSERT INTO overview_history SELECT * FROM overview_live WHERE session_id = ?
        3. Keep data in overview_live (không xóa)
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
        
        # Check if recently archived (within 50 mins) to prevent duplicates
        try:
            cursor.execute('''
                SELECT 1 FROM overview_history 
                WHERE session_id = %s 
                  AND archived_at > (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh' - INTERVAL '50 minutes')
                LIMIT 1
            ''', (session_id,))
            if cursor.fetchone():
                log_func(f"⏳ Session {session_id} overview đã được archive trong vòng 50 phút qua. Bỏ qua.")
                conn.close()
                return True  # Return True so caller resets timer
        except Exception as check_error:
            log_func(f"❌ Error checking archive history: {check_error}")
            conn.close()
            return False
        
        # Copy data từ overview_live vào overview_history (15 metrics, no gmv/confirmed)
        log_func(f"📦 Archiving overview data for session {session_id}...")
        try:
            cursor.execute('''
                INSERT INTO overview_history (
                    session_id, session_title, archived_at,
                    engaged_viewers, comments, atc, views, avg_view_time,
                    comments_rate, gpm, placed_order, abs, viewers, pcu,
                    ctr, co, buyers, placed_items_sold
                )
                SELECT 
                    session_id, session_title, (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh'),
                    engaged_viewers, comments, atc, views, avg_view_time,
                    comments_rate, gpm, placed_order, abs, viewers, pcu,
                    ctr, co, buyers, placed_items_sold
                FROM overview_live
                WHERE session_id = %s
            ''', (session_id,))
            archived_count = cursor.rowcount
        except Exception as archive_error:
            log_func(f"❌ Error archiving overview data: {archive_error}")
            import traceback
            log_func(traceback.format_exc())
            conn.close()
            return False
        
        # NOTE: Không xóa data từ overview_live - giữ nguyên để dashboard luôn có data live
        # (Copy-paste, không cut-paste)
        
        conn.commit()
        conn.close()
        
        log_func(f"✅ Archived {archived_count} overview record to overview_history (kept in overview_live)")
        return True
    except psycopg2.OperationalError as conn_error:
        log_func(f"❌ Database connection failed: {conn_error}")
        return False
    except Exception as e:
        log_func(f"❌ Overview archive error: {e}")
        import traceback
        log_func(traceback.format_exc())
        return False


def get_overview_live(db_url, session_id, log_func=print):
    """
    Lấy overview data real-time từ overview_live.
    
    Args:
        db_url: PostgreSQL connection string
        session_id: Session ID to query
        log_func: Logging function
    
    Returns:
        dict: Overview metrics với 15 metrics + session metadata, 
              hoặc None nếu không có data
    """
    import time
    start_time = time.time()
    
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return None
    if not db_url:
        log_func("⚠️ Chưa có DATABASE_URL")
        return None
    if not session_id:
        log_func("⚠️ Chưa có session_id")
        return None
    
    try:
        conn_start = time.time()
        conn = psycopg2.connect(db_url, connect_timeout=10)
        conn_time = time.time() - conn_start
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Query overview_live for specific session_id (15 metrics, no gmv/confirmed)
        query_start = time.time()
        cursor.execute('''
            SELECT 
                session_id,
                session_title,
                scraped_at,
                engaged_viewers,
                comments,
                atc,
                views,
                avg_view_time,
                comments_rate,
                gpm,
                placed_order,
                abs,
                viewers,
                pcu,
                ctr,
                co,
                buyers,
                placed_items_sold
            FROM overview_live
            WHERE session_id = %s
        ''', (session_id,))
        
        row = cursor.fetchone()
        query_time = time.time() - query_start
        conn.close()
        
        total_time = time.time() - start_time
        log_func(f"[DB TIMING] get_overview_live: connect={conn_time:.3f}s, query={query_time:.3f}s, total={total_time:.3f}s")
        
        if row:
            log_func(f"[DB] Loaded overview data for session {session_id}")
            return dict(row)
        else:
            log_func(f"[DB] No overview data found for session {session_id}")
            return None
    except Exception as e:
        log_func(f"❌ Error getting overview live data: {e}")
        return None


def get_overview_history(db_url, session_id, limit=10, log_func=print):
    """
    Lấy overview history data từ overview_history.
    
    Args:
        db_url: PostgreSQL connection string
        session_id: Session ID to query
        limit: Number of records to return (default: 10)
        log_func: Logging function
    
    Returns:
        list[dict]: Danh sách overview snapshots, sorted by archived_at DESC (newest first),
                    hoặc empty list nếu không có data
    """
    if not HAS_PSYCOPG2:
        log_func("⚠️ psycopg2 chưa được cài đặt")
        return []
    if not db_url:
        log_func("⚠️ Chưa có DATABASE_URL")
        return []
    if not session_id:
        log_func("⚠️ Chưa có session_id")
        return []
    
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Query overview_history for specific session_id (15 metrics, no gmv/confirmed)
        cursor.execute('''
            SELECT 
                id,
                session_id,
                session_title,
                archived_at,
                engaged_viewers,
                comments,
                atc,
                views,
                avg_view_time,
                comments_rate,
                gpm,
                placed_order,
                abs,
                viewers,
                pcu,
                ctr,
                co,
                buyers,
                placed_items_sold
            FROM overview_history
            WHERE session_id = %s
            ORDER BY archived_at DESC
            LIMIT %s
        ''', (session_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = [dict(row) for row in rows]
        log_func(f"[DB] Loaded {len(result)} overview history records for session {session_id}")
        return result
    except Exception as e:
        log_func(f"❌ Error getting overview history data: {e}")
        return []


def get_overview_sessions(db_url, log_func=print):
    """
    Lấy danh sách sessions có overview data từ overview_live.
    
    Args:
        db_url: PostgreSQL connection string
        log_func: Logging function
    
    Returns:
        list[dict]: Danh sách sessions với format:
                    [{'session_id': '...', 'session_title': '...', 'last_scraped': '...'}, ...]
                    Sorted by session_id DESC (newest first)
                    Trả về empty list nếu không có data hoặc có lỗi
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
        
        # Query distinct session_ids from overview_live with their metadata
        cursor.execute('''
            SELECT 
                session_id,
                session_title,
                scraped_at as last_scraped
            FROM overview_live
            WHERE session_id IS NOT NULL
            ORDER BY session_id DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        result = [dict(row) for row in rows]
        log_func(f"[DB] Loaded {len(result)} overview sessions")
        return result
    except Exception as e:
        log_func(f"❌ Error getting overview sessions: {e}")
        return []


def parse_overview_metrics(api_response):
    """
    Parse overview metrics từ Shopee Creator API response.
    
    Extracts 15 metrics from API response JSON (18 total columns in DB - 3 metadata fields):
    - Keeps avgViewTime as seconds (frontend converts to hh:mm:ss)
    - Preserves percentage format with "%" character
    - Converts numeric values to integers
    - Handles null/undefined with defaults (0 or "0%")
    - Extracts comments from nested engagementData object
    
    Args:
        api_response: dict - API response JSON từ overview endpoint
                      Expected structure: {'code': 0, 'data': {...}}
    
    Returns:
        dict: Dictionary với 15 metrics keys, hoặc None nếu response không hợp lệ
              Keys: engaged_viewers, comments, atc, views, avg_view_time,
                    comments_rate, gpm, placed_order, abs, viewers, pcu, ctr, co,
                    buyers, placed_items_sold
    
    Example:
        >>> response = {'code': 0, 'data': {'views': 25000, 'pcu': 5000, 'avgViewTime': 1617469, ...}}
        >>> metrics = parse_overview_metrics(response)
        >>> print(metrics['views'])  # 25000
        >>> print(metrics['avg_view_time'])  # 1617469.0 (kept as seconds)
    """
    if not api_response:
        return None
    
    # Check if response is valid
    if api_response.get('code') != 0:
        return None
    
    # Check if data key exists (even if empty)
    if 'data' not in api_response:
        return None
    
    data = api_response.get('data', {})
    # Note: Even if data is empty, we still return metrics with default values
    # This allows the system to handle API responses gracefully
    
    # Helper function to safely get integer value with default 0
    def safe_int(value, default=0):
        if value is None or value == '':
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    # Helper function to safely get percentage string with default "0%"
    def safe_percentage(value, default='0%'):
        if value is None or value == '':
            return default
        # Ensure value is string and has % character
        value_str = str(value)
        if '%' not in value_str:
            value_str = value_str + '%'
        return value_str
    
    # Helper function to convert milliseconds to "ms/60" format (NOT minutes)
    # API returns avgViewTime in milliseconds, we divide by 60 only
    # Frontend will divide by 1000 to get actual minutes
    def milliseconds_divide_60(milliseconds):
        if milliseconds is None or milliseconds == '':
            return 0.0
        try:
            return round(float(milliseconds) / 60, 2)
        except (ValueError, TypeError):
            return 0.0
    
    # Extract 15 metrics from API response (removed: gmv, confirmed_gmv, confirmed_order, confirmed_items_sold)
    metrics = {
        # Numeric metrics (integers)
        'engaged_viewers': safe_int(data.get('engagedViewers')),
        'atc': safe_int(data.get('atc')),
        'views': safe_int(data.get('views')),
        'gpm': safe_int(data.get('gpm')),
        'placed_order': safe_int(data.get('placedOrder')),
        'abs': safe_int(data.get('abs')),
        'viewers': safe_int(data.get('viewers')),
        'pcu': safe_int(data.get('pcu')),
        'buyers': safe_int(data.get('buyers')),
        'placed_items_sold': safe_int(data.get('placedItemsSold')),
        
        # Nested object extraction: comments from engagementData
        'comments': safe_int(data.get('engagementData', {}).get('comments')),
        
        # Time: avgViewTime stored as ms/60 (frontend divides by 1000 to get minutes)
        'avg_view_time': milliseconds_divide_60(data.get('avgViewTime')),
        
        # Percentage metrics (preserve "%" format)
        'comments_rate': safe_percentage(data.get('commentsRate')),
        'ctr': safe_percentage(data.get('ctr')),
        'co': safe_percentage(data.get('co')),
    }
    
    return metrics

