"""
Web GMV Dashboard - LOCAL DEV VERSION
Sử dụng SQLite để test locally thay vì PostgreSQL
"""

import os
import sqlite3
import json
from functools import wraps
from datetime import datetime

from flask import Flask, request, jsonify, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-local')

# Local SQLite database
DATABASE_PATH = 'gmv_dashboard.db'

# ============== Database Functions ==============

def get_db():
    """Get SQLite connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dicts
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create gmv_data table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gmv_data (
            item_id TEXT PRIMARY KEY,
            item_name TEXT,
            revenue INTEGER DEFAULT 0,
            shop_id TEXT,
            link_sp TEXT,
            datetime TEXT,
            clicks INTEGER DEFAULT 0,
            ctr REAL DEFAULT 0,
            orders INTEGER DEFAULT 0,
            items_sold INTEGER DEFAULT 0,
            cluster TEXT,
            add_to_cart INTEGER DEFAULT 0
        )
    ''')
    
    # Insert sample data if empty
    cursor.execute('SELECT COUNT(*) FROM gmv_data')
    if cursor.fetchone()[0] == 0:
        sample_data = [
            ('item001', 'Áo thun nam', 500000, 'shop001', 'https://shopee.vn/item001', '2024-01-01', 100, 5.0, 10, 8, 'Fashion', 20),
            ('item002', 'Quần jean nữ', 800000, 'shop002', 'https://shopee.vn/item002', '2024-01-01', 150, 4.5, 15, 12, 'Fashion', 30),
            ('item003', 'Giày sneaker', 1200000, 'shop001', 'https://shopee.vn/item003', '2024-01-01', 200, 6.0, 20, 18, 'Shoes', 50),
            ('item004', 'Túi xách', 300000, 'shop003', None, '2024-01-01', 50, 3.0, 5, 4, 'Accessories', 10),
            ('item005', 'Mũ lưỡi trai', 150000, 'shop002', 'https://shopee.vn/item005', '2024-01-01', 80, 4.0, 8, 6, 'Accessories', 15),
            ('item006', 'Áo khoác', 950000, 'shop001', 'https://shopee.vn/item006', '2024-01-01', 120, 5.5, 12, 10, 'Fashion', 25),
            ('item007', 'Váy đầm', 650000, 'shop003', None, '2024-01-01', 90, 4.2, 9, 7, 'Fashion', 18),
            ('item008', 'Sandal', 280000, 'shop002', 'https://shopee.vn/item008', '2024-01-01', 70, 3.8, 7, 5, 'Shoes', 12),
            ('item009', 'Balo laptop', 450000, 'shop001', 'https://shopee.vn/item009', '2024-01-01', 110, 5.2, 11, 9, 'Accessories', 22),
            ('item010', 'Đồng hồ', 2000000, 'shop003', 'https://shopee.vn/item010', '2024-01-01', 60, 3.5, 6, 5, 'Watches', 8),
        ]
        cursor.executemany('''
            INSERT INTO gmv_data (item_id, item_name, revenue, shop_id, link_sp, datetime, clicks, ctr, orders, items_sold, cluster, add_to_cart)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_data)
        print(f"[LOCAL DB] Inserted {len(sample_data)} sample products")
    
    conn.commit()
    conn.close()
    print("[LOCAL DB] Database initialized")

def get_config(key):
    """Get config value"""
    return None

# ============== Routes ==============

@app.route('/')
def index():
    """Landing page"""
    return render_template('landing.html')

@app.route('/admin')
def admin():
    """Admin Dashboard"""
    return render_template('index.html')

@app.route('/admin/setting')
def admin_setting():
    """Admin Settings"""
    config = {
        'spreadsheet_url': '',
        'rawdata_sheet': '',
        'deallist_sheet': ''
    }
    return render_template('admin.html', config=config)

# ============== API Routes ==============

@app.route('/api/all-data')
def api_all_data():
    """API: Get ALL data with optional sorting"""
    # Sort params
    sort_by = request.args.get('sort_by', '', type=str).strip()
    sort_dir = request.args.get('sort_dir', 'desc', type=str).strip().lower()
    
    # Validate sort params
    allowed_sort_columns = ['revenue', 'clicks', 'add_to_cart', 'orders']
    if sort_by and sort_by not in allowed_sort_columns:
        sort_by = ''
    if sort_dir not in ['asc', 'desc']:
        sort_dir = 'desc'
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Build query
    if sort_by:
        query = f'''
            SELECT item_id, item_name, revenue, shop_id, link_sp, datetime, clicks, ctr, orders, items_sold, cluster, add_to_cart
            FROM gmv_data
            ORDER BY {sort_by} {sort_dir.upper()}
        '''
        print(f"[LOCAL API] Fetching data with ORDER BY {sort_by} {sort_dir.upper()}")
    else:
        query = '''
            SELECT item_id, item_name, revenue, shop_id, link_sp, datetime, clicks, ctr, orders, items_sold, cluster, add_to_cart
            FROM gmv_data
        '''
        print("[LOCAL API] Fetching data without sorting")
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    # Get shop_ids
    cursor.execute("SELECT DISTINCT shop_id FROM gmv_data WHERE shop_id IS NOT NULL AND shop_id != '' ORDER BY shop_id")
    shop_ids = [row['shop_id'] for row in cursor.fetchall()]
    
    # Get stats
    cursor.execute('''
        SELECT 
            COUNT(*) as total_products,
            COALESCE(SUM(revenue), 0) as total_revenue,
            COALESCE(SUM(clicks), 0) as total_clicks,
            COALESCE(SUM(orders), 0) as total_orders,
            COUNT(CASE WHEN link_sp IS NOT NULL AND link_sp != '' THEN 1 END) as with_link
        FROM gmv_data
    ''')
    stats_row = cursor.fetchone()
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
            'add_to_cart': row['add_to_cart'] or 0
        })
    
    print(f"[LOCAL API] Returning {len(data)} products")
    
    return jsonify({
        'success': True,
        'data': data,
        'shop_ids': shop_ids,
        'stats': {
            'total_products': stats_row['total_products'],
            'total_revenue': stats_row['total_revenue'],
            'total_clicks': stats_row['total_clicks'],
            'total_orders': stats_row['total_orders'],
            'with_link': stats_row['with_link']
        },
        'last_sync': 'Local Dev',
        'from_cache': False
    })

@app.route('/api/analytics/top-products')
def api_top_products():
    """API: Top products for chart"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT item_name as name, revenue FROM gmv_data ORDER BY revenue DESC LIMIT 10')
    data = [{'name': row['name'][:20], 'revenue': row['revenue']} for row in cursor.fetchall()]
    conn.close()
    return jsonify({'success': True, 'data': data})

@app.route('/api/analytics/category-distribution')
def api_category_distribution():
    """API: Category distribution for chart"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT cluster, SUM(revenue) as revenue, COUNT(*) as count FROM gmv_data GROUP BY cluster ORDER BY revenue DESC')
    data = [{'cluster': row['cluster'], 'revenue': row['revenue'], 'count': row['count']} for row in cursor.fetchall()]
    conn.close()
    return jsonify({'success': True, 'data': data})

@app.route('/api/cache-status')
def api_cache_status():
    """API: Cache status"""
    return jsonify({
        'success': True,
        'gmv_fresh': True,
        'gmv_age': 0,
        'deallist_fresh': True,
        'deallist_age': 0
    })

# ============== Main ==============

if __name__ == '__main__':
    print("=" * 50)
    print("🔧 LOCAL DEVELOPMENT SERVER")
    print("=" * 50)
    print("Using SQLite database:", DATABASE_PATH)
    init_db()
    print("Starting Flask server on http://localhost:5000")
    print("Dashboard: http://localhost:5000/admin")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
