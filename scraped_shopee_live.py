# -*- coding: utf-8 -*-
"""
Shopee Live Product Scraper v9 - RoxyBrowser
==============================================
Kết nối tới RoxyBrowser qua API → CDP → Playwright.
- Anti-detect browser = không bị CAPTCHA
- Random interval 3-5 phút giữa các lần cào

Cách dùng:
  1. Mở RoxyBrowser, bật API
  2. python scraper_shopee_live.py [session_id]
"""

import asyncio
import json
import csv
import os
import sys
import random
import requests
import psycopg2
import psycopg2.extras
from datetime import datetime
from playwright.async_api import async_playwright


# =============================================================================
# CẤU HÌNH
# =============================================================================

SESSION_ID = ""  # Để trống = tự detect từ URL tab
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
DATABASE_URL = os.environ.get('DATABASE_PUBLIC_URL', 'postgresql://postgres:yOjpEWRgIdVIXqjjMCiFAQeqtNbCgXxj@gondola.proxy.rlwy.net:40226/railway')

# RoxyBrowser
ROXY_API_KEY = "7f6cc3dba66fa76977e706c2e36f87c0"
ROXY_PROFILE_ID = "82055e79d85dea79229788b8f008a826"
ROXY_WORKSPACE_ID = "UVZ0077003"
ROXY_API_HOST = "http://127.0.0.1:50000"

MIN_DELAY = 3.0    # delay giữa mỗi trang (giây)
MAX_DELAY = 5.0    # tăng lên để tránh CAPTCHA
REPEAT_MIN = 80   # 2 phút giữa mỗi lần cào
REPEAT_MAX = 120   # 3 phút giữa mỗi lần cào
JOINV2_INTERVAL = (25, 45)  # joinv2 cào riêng, random 25-45 giây

SESSION_BUDGET = 8          # Sau N lần cào sp/more → nghỉ dài
SESSION_REST_MIN = 300      # Nghỉ tối thiểu 5 phút
SESSION_REST_MAX = 400     # Nghỉ tối đa 7.5 phút

MAX_RECONNECT = 5       # Số lần thử kết nối lại tối đa khi mất CDP
RECONNECT_DELAY = 30    # Giây chờ giữa mỗi lần reconnect


# =============================================================================
# ROXYBROWSER HELPERS
# =============================================================================

def roxy_start_profile():
    """Gọi RoxyBrowser API để mở profile → trả về CDP WebSocket URL."""
    url = f"{ROXY_API_HOST}/browser/open"
    headers = {
        "Authorization": f"Bearer {ROXY_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "workspaceId": ROXY_WORKSPACE_ID,
        "dirId": ROXY_PROFILE_ID,
    }
    
    print(f"🌐 Mở RoxyBrowser profile...")
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        data = resp.json()
        
        code = data.get("code", -1)
        if code == 0:
            ws_url = data.get("data", {}).get("ws", "")
            if ws_url:
                print(f"   ✅ Profile đã mở")
                print(f"   🔗 WS: {ws_url[:60]}...")
                return ws_url
            else:
                print(f"   ⚠️ Không tìm thấy WS URL:")
                print(f"   {json.dumps(data, indent=2)[:300]}")
                return None
        else:
            msg = data.get("msg", resp.text[:200])
            print(f"   ❌ Lỗi: {msg}")
            return None
    except requests.ConnectionError:
        print(f"   ❌ Không kết nối được RoxyBrowser!")
        print(f"   💡 Mở RoxyBrowser và bật API (API Configuration)")
        return None
    except Exception as e:
        print(f"   ❌ {e}")
        return None


def roxy_stop_profile():
    """Đóng profile RoxyBrowser."""
    url = f"{ROXY_API_HOST}/browser/close"
    headers = {"Authorization": f"Bearer {ROXY_API_KEY}"}
    try:
        requests.post(url, headers=headers, json={"workspaceId": ROXY_WORKSPACE_ID, "dirId": ROXY_PROFILE_ID}, timeout=10)
    except:
        pass


# =============================================================================
# API METHOD
# =============================================================================

async def api_page_evaluate(page, url, retries=3):
    """Gọi API qua page.evaluate (browser JS context)."""
    for attempt in range(retries):
        try:
            result = await page.evaluate('''
                async (url) => {
                    try {
                        const resp = await fetch(url, {
                            credentials: 'include',
                            headers: {
                                'Accept': 'application/json, text/plain, */*',
                                'x-livestreaming-source': 'shopee'
                            }
                        });
                        return { status: resp.status, data: await resp.json() };
                    } catch(e) {
                        return { error: e.message };
                    }
                }
            ''', url)
            return result
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(1)
            else:
                return {"error": str(e)}


def check_api_ok(result):
    """Check API result."""
    if "error" in result:
        return False
    if result.get("status") != 200:
        return False
    data = result.get("data", {})
    if data.get("err_code") != 0:
        return False
    return True


# =============================================================================
# SCRAPING
# =============================================================================

async def simulate_human_behavior(page):
    """Giả lập scroll + mouse move như người thật để tránh CAPTCHA."""
    try:
        # Scroll xuống ngẫu nhiên
        scroll_y = random.randint(80, 400)
        await page.evaluate(f"window.scrollBy(0, {scroll_y})")
        await asyncio.sleep(random.uniform(0.4, 1.2))

        # Di chuyển chuột ngẫu nhiên (không click)
        x = random.randint(150, 900)
        y = random.randint(150, 550)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.2, 0.7))

        # Scroll lại lên một chút
        await page.evaluate(f"window.scrollBy(0, -{random.randint(30, scroll_y // 2)})")
        await asyncio.sleep(random.uniform(0.3, 0.8))

        # Thỉnh thoảng (30%) di chuyển thêm một lần nữa
        if random.random() < 0.3:
            x2 = random.randint(200, 800)
            y2 = random.randint(100, 500)
            await page.mouse.move(x2, y2)
            await asyncio.sleep(random.uniform(0.2, 0.5))

        print(f"   🖱️ [human] scroll={scroll_y}px, mouse=({x},{y})")
    except Exception as e:
        print(f"   ⚠️ simulate_human_behavior: {e}")


async def setup_resource_blocking(page):
    """Block ảnh/CSS/font/analytics để giảm bandwidth và tránh bot detection."""
    BLOCK_TYPES = {"image", "stylesheet", "font", "media", "ping", "other"}
    BLOCK_DOMAINS = ["google-analytics", "facebook", "doubleclick", "hotjar", "gtag"]

    async def handle_route(route):
        req = route.request
        if req.resource_type in BLOCK_TYPES:
            await route.abort()
        elif any(d in req.url for d in BLOCK_DOMAINS):
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", handle_route)
    print("🚫 Resource blocking: ảnh/CSS/font/analytics đã bị chặn")


async def detect_page_size(api_fn, session_id):
    """Detect max limit."""
    base = f"https://live.shopee.vn/api/v1/session/{session_id}/sp_items"
    for size in [50, 20, 15, 10, 5]:
        r = await api_fn(f"{base}?offset=0&limit={size}")
        if check_api_ok(r):
            return size
        await asyncio.sleep(0.3)
    return 1


async def scrape_endpoint(api_fn, session_id, endpoint="sp_items", limit=10, label="🔴"):
    """Cào SP từ 1 endpoint."""
    all_items = []
    offset = 0
    page_num = 1
    base = f"https://live.shopee.vn/api/v1/session/{session_id}/{endpoint}"
    
    print(f"\n{'='*60}")
    print(f"{label} SCRAPING {endpoint.upper()} (limit={limit})")
    print(f"{'='*60}\n")
    
    while True:
        print(f"{label} Trang {page_num} (offset={offset})...", end=" ", flush=True)
        
        r = await api_fn(f"{base}?offset={offset}&limit={limit}")
        
        if not check_api_ok(r):
            err = r.get("error", r.get("data", {}).get("err_msg", r.get("data", {})))
            print(f"\n❌ Lỗi: {err}")
            break
        
        data = r["data"]["data"]
        items = data.get("items", [])
        
        if page_num == 1:
            total = data.get("all_total", data.get("total_count", "?"))
            count = data.get("total_count", "?")
            print(f"\n   📊 total={total}, count={count}")
            print(f"   ", end="")
        
        if not items:
            print("✅ Hết.")
            break
        
        print(f"{len(items)} SP (tổng: {len(all_items) + len(items)})")
        all_items.extend(items)
        
        if not data.get("has_more", False):
            print("✅ Xong!")
            break
        
        offset = data.get("next_offset", offset + limit)
        page_num += 1
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
    
    print(f"\n📊 {endpoint}: {len(all_items)} SP\n")
    return all_items


async def scrape_show_item(api_fn, session_id, page=None):
    """Lấy data từ joinv2 (POST với uuid + ver)."""
    print(f"\n📌 Lấy data từ joinv2...", end=" ", flush=True)
    
    if not page:
        print(f"⚠️ Không có page")
        return []
    
    try:
        import uuid
        request_uuid = str(uuid.uuid4())
        
        result = await page.evaluate('''async ([sid, reqUuid]) => {
            try {
                const resp = await fetch('/api/v1/session/' + sid + '/joinv2', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json, text/plain, */*',
                        'Content-Type': 'application/json',
                        'x-livestreaming-source': 'shopee'
                    },
                    body: JSON.stringify({uuid: reqUuid, ver: 1})
                });
                return await resp.json();
            } catch(e) {
                return {error: e.message};
            }
        }''', [str(session_id), request_uuid])
        
        if result and result.get("err_code") == 0:
            inner = result.get("data", {})
            show_item = inner.get("show_item")
            if show_item and isinstance(show_item, dict):
                name = show_item.get("name", "?")[:40]
                print(f"✅ {name}")
                return [show_item]
            else:
                print(f"✅ joinv2 OK (no show_item pinned)")
                return []
        elif result and result.get("error"):
            print(f"⚠️ {result['error']}")
        else:
            print(f"⚠️ err_code: {result.get('err_code')}, msg: {result.get('err_msg', '?')}")
        
        return []
    except Exception as e:
        print(f"⚠️ Lỗi: {e}")
        return []


async def joinv2_loop(session_id, page, stop_event: asyncio.Event):
    """Task riêng: cào joinv2 random JOINV2_INTERVAL giây, tự push DB."""
    run = 0
    while not stop_event.is_set():
        run += 1
        print(f"\n⏱️ [joinv2 #{run}] Cào joinv2...", end=" ", flush=True)
        try:
            api_fn = lambda url, retries=3: api_page_evaluate(page, url, retries)
            show_items = await scrape_show_item(api_fn, session_id, page=page)
            for it in show_items:
                it['_source'] = 2
            if show_items:
                save_show_item(show_items, session_id)
                push_to_postgresql(show_items, session_id)
        except Exception as e:
            print(f"⚠️ joinv2_loop error: {e}")
        # Chờ ngẫu nhiên trong khoảng JOINV2_INTERVAL, vẫn check stop_event mỗi 1s
        wait_sec = random.randint(*JOINV2_INTERVAL)
        print(f"   ⏳ [joinv2] Chờ {wait_sec}s (random {JOINV2_INTERVAL[0]}-{JOINV2_INTERVAL[1]}s)...")
        for _ in range(wait_sec):
            if stop_event.is_set():
                break
            await asyncio.sleep(1)
    print("🛑 joinv2_loop dừng.")


# =============================================================================
# PARSE & SAVE
# =============================================================================

def parse_product(item):
    p = {}
    p["item_id"] = item.get("item_id", item.get("itemid", ""))
    p["shop_id"] = item.get("shop_id", item.get("shopid", ""))
    p["name"] = item.get("name", item.get("title", ""))
    
    price = item.get("price", 0)
    p["price"] = int(price) if str(price).isdigit() else price
    
    price_b = item.get("price_before_discount", 0)
    p["price_before_discount"] = int(price_b) if str(price_b).isdigit() else price_b
    
    # Live tag
    has_stream_price = False
    promo_labels = item.get("label", {}).get("promotion_labels", [])
    for lbl in promo_labels:
        if lbl.get("type_name") == "ongoing_platform_stream_price":
            has_stream_price = True
            break
    p["has_live_tag"] = has_stream_price or item.get("is_sp_final_price", False)
    
    p["discount"] = item.get("discount", 0)
    
    out_price = item.get("out_of_live_price", 0)
    p["out_of_live_price"] = int(out_price) if str(out_price).isdigit() else out_price
    
    p["display_stock"] = item.get("display_total_stock", item.get("stock", 0))
    p["status"] = item.get("status", "")
    
    image = item.get("image", item.get("img", ""))
    p["image_url"] = f"https://cf.shopee.vn/file/{image}" if image and not image.startswith("http") else image
    
    p["sold"] = item.get("sold", item.get("itemSold", 0))
    p["stock"] = item.get("stock", 0)
    p["likes"] = item.get("liked_count", 0)
    p["product_url"] = f"https://shopee.vn/product/{p['shop_id']}/{p['item_id']}" if p["item_id"] and p["shop_id"] else ""
    p["_source"] = item.get("_source", 0)
    return p


def save_results(items, session_id):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parsed = [parse_product(i) for i in items]
    
    cp = os.path.join(OUTPUT_DIR, f"shopee_live_{session_id}.csv")
    file_exists = os.path.exists(cp)
    
    with open(cp, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        if not file_exists:
            w.writerow(["STT","Thời gian","Item ID","Shop ID","Tên SP","Giá Live","Giá gốc",
                         "Giảm %","Giá ngoài Live","Tag Live","Tồn kho","Đã bán","Link","Hình"])
        for i, pr in enumerate(parsed, 1):
            w.writerow([i, ts_display, pr["item_id"], pr["shop_id"], pr["name"], pr["price"],
                        pr["price_before_discount"], f"{pr['discount']}%" if pr["discount"] else "",
                        pr["out_of_live_price"] or "", "CÓ" if pr["has_live_tag"] else "",
                        pr["display_stock"], pr["sold"], pr["product_url"], pr["image_url"]])
    
    print(f"📄 CSV: {cp} (+{len(parsed)} dòng)")


def save_show_item(show_items, session_id):
    """Lưu SP đang ghim vào file riêng."""
    if not show_items:
        return
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parsed = [parse_product(i) for i in show_items]
    
    cp = os.path.join(OUTPUT_DIR, f"shopee_live_show_{session_id}.csv")
    file_exists = os.path.exists(cp)
    
    with open(cp, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        if not file_exists:
            w.writerow(["Thời gian","Item ID","Shop ID","Tên SP","Giá Live","Giá gốc",
                         "Giảm %","Tag Live","Tồn kho","Đã bán","Link"])
        for pr in parsed:
            w.writerow([ts_display, pr["item_id"], pr["shop_id"], pr["name"], pr["price"],
                        pr["price_before_discount"], f"{pr['discount']}%" if pr["discount"] else "",
                        "CÓ" if pr["has_live_tag"] else "",
                        pr["display_stock"], pr["sold"], pr["product_url"]])
    
    print(f"📌 CSV ghim: {cp} (+{len(parsed)} dòng)")


def print_summary(items):
    parsed = [parse_product(i) for i in items]
    print(f"\n{'─'*80}")
    print(f"{'#':>4} │ {'Tên SP':<40} │ {'Giá':>12} │ {'Bán':>8}")
    print(f"{'─'*80}")
    for i, pr in enumerate(parsed[:15], 1):
        nm = pr["name"][:38] + ".." if len(pr["name"]) > 40 else pr["name"]
        px = f"{pr['price']:,.0f}đ" if isinstance(pr["price"], (int, float)) and pr["price"] > 0 else "?"
        print(f"{i:>4} │ {nm:<40} │ {px:>12} │ {str(pr['sold']):>8}")
    if len(parsed) > 15:
        print(f"     │ ... và {len(parsed)-15} sản phẩm nữa")
    print(f"{'─'*80}\n")


def push_to_postgresql(items, session_id):
    """Đẩy data lên PostgreSQL (Railway)."""
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL chưa set → bỏ qua push DB")
        return
    
    parsed = [parse_product(i) for i in items]
    now = datetime.now()
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS live_data (
                id SERIAL PRIMARY KEY,
                session_id TEXT,
                item_id TEXT,
                shop_id TEXT,
                name TEXT,
                price BIGINT DEFAULT 0,
                price_before_discount BIGINT DEFAULT 0,
                discount TEXT,
                stock INTEGER DEFAULT 0,
                sold INTEGER DEFAULT 0,
                has_live_tag BOOLEAN DEFAULT FALSE,
                image_url TEXT,
                source SMALLINT DEFAULT 0,
                scraped_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        # Add source column if not exists (for existing tables)
        try:
            cursor.execute('ALTER TABLE live_data ADD COLUMN IF NOT EXISTS source SMALLINT DEFAULT 0')
        except:
            pass
        
        # Batch insert
        rows = []
        for pr in parsed:
            price = pr['price'] if isinstance(pr['price'], (int, float)) else 0
            price_b = pr['price_before_discount'] if isinstance(pr['price_before_discount'], (int, float)) else 0
            stock = pr.get('display_stock', pr.get('stock', 0)) or 0
            sold = pr.get('sold', 0) or 0
            rows.append((
                session_id,
                str(pr.get('item_id', '')),
                str(pr.get('shop_id', '')),
                pr.get('name', ''),
                int(price),
                int(price_b),
                str(pr.get('discount', '')),
                int(stock),
                int(sold),
                bool(pr.get('has_live_tag', False)),
                pr.get('image_url', ''),
                int(pr.get('_source', 0)),
                now,
            ))
        
        insert_sql = '''
            INSERT INTO live_data (session_id, item_id, shop_id, name, price, 
                price_before_discount, discount, stock, sold, has_live_tag, image_url, source, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        psycopg2.extras.execute_batch(cursor, insert_sql, rows, page_size=500)
        
        conn.commit()
        conn.close()
        print(f"🗄️ PostgreSQL: +{len(rows)} rows")
    except Exception as e:
        print(f"⚠️ DB push lỗi: {e}")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
    session_id = SESSION_ID
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
    
    print(f"🚀 Shopee Live Scraper v9 (RoxyBrowser)")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ===== MỞ ROXYBROWSER PROFILE =====
    cdp_url = roxy_start_profile()
    if not cdp_url:
        return
        # ===== PLAYWRIGHT CDP =====
    async with async_playwright() as p:
        run_count = 0
        stop_event = asyncio.Event()
        reconnect_attempt = 0

        while True:
            # Re-fetch CDP URL nếu đây là lần reconnect
            if reconnect_attempt > 0:
                print(f"\n🔄 Reconnect lần {reconnect_attempt}/{MAX_RECONNECT}...")
                cdp_url = roxy_start_profile()
                if not cdp_url:
                    print("❌ Không lấy được CDP URL mới, dừng.")
                    break
                stop_event.clear() # Clear stop event for new connection

            print(f"\n🔗 Kết nối RoxyBrowser qua CDP...")
            try:
                browser = await p.chromium.connect_over_cdp(cdp_url)
            except Exception as e:
                print(f"❌ Không kết nối được: {e}")
                reconnect_attempt += 1
                if reconnect_attempt > MAX_RECONNECT:
                    print(f"❌ Quá {MAX_RECONNECT} lần reconnect, dừng.")
                    break
                await asyncio.sleep(RECONNECT_DELAY)
                continue
        
            print(f"   ✅ Đã kết nối!")

            # Tìm tab live.shopee.vn
            contexts = browser.contexts
            page = None

            print(f"   🔍 Tìm tab... ({len(contexts)} context(s))")
            for ctx in contexts:
                pages = ctx.pages
                print(f"      Context có {len(pages)} tab(s):")
                for pg in pages:
                    try:
                        url = pg.url
                        print(f"         - {url[:80]}")
                        if "live.shopee.vn" in url:
                            page = pg
                            print(f"   📍 Tìm thấy tab live: {url[:80]}")
                            break
                    except Exception as e:
                        print(f"         - [lỗi đọc URL: {e}]")
                if page:
                    break

            # Auto-detect session_id từ URL tab
            if page and not session_id:
                import re
                m = re.search(r'session=(\d+)', page.url)
                if m:
                    session_id = m.group(1)
                    print(f"   🔗 Auto-detect session: {session_id}")

            if not page:
                print(f"\n   ⚠️ Không tìm thấy tab live.shopee.vn!")
                print(f"   👉 Mở link live stream trên RoxyBrowser, rồi nhấn Enter...")
                try:
                    input()
                except EOFError:
                    print(f"   ⚠️ Chạy ở chế độ non-interactive, thử tìm lại sau 5 giây...")
                    await asyncio.sleep(5)

                # Tìm lại
                print(f"   🔍 Tìm lại tab...")
                for ctx in browser.contexts:
                    for pg in ctx.pages:
                        try:
                            url = pg.url
                            print(f"      - {url[:80]}")
                            if "live.shopee.vn" in url:
                                page = pg
                                print(f"   📍 Tab: {url[:80]}")
                                break
                        except Exception as e:
                            print(f"      - [lỗi: {e}]")
                    if page:
                        break

                if page and not session_id:
                    import re
                    m = re.search(r'session=(\d+)', page.url)
                    if m:
                        session_id = m.group(1)
                        print(f"   🔗 Auto-detect session: {session_id}")

                if not page:
                    print(f"   ❌ Vẫn không tìm thấy tab live.shopee.vn")
                    break

            # ===== BLOCK RESOURCES =====
            await setup_resource_blocking(page)

            # ===== TEST API =====
            test_url = f"https://live.shopee.vn/api/v1/session/{session_id}/sp_items?offset=0&limit=1"
            print(f"\n🔍 Test API...")
            r = await api_page_evaluate(page, test_url, retries=2)

            if not check_api_ok(r):
                err_code = r.get("data", {}).get("err_code", r.get("error", "?"))
                print(f"   ❌ API lỗi: {err_code}")
                print(f"   💡 Đảm bảo RoxyBrowser đã login Shopee và mở link live stream.")
                break

            resp_data = r["data"]["data"]
            total = resp_data.get("all_total", "?")
            count = resp_data.get("total_count", "?")
            print(f"   ✅ OK! (all_total={total}, total_count={count})")

            # API function
            api_fn = lambda url, retries=3: api_page_evaluate(page, url, retries)

            # Detect limit
            print(f"\n📐 Detect limit...", end=" ")
            limit = await detect_page_size(api_fn, session_id)
            print(f"→ {limit}")

            # ===== SCRAPE LOOP =====
            async def sp_more_loop():
                """Vòng lặp cào sp_items + more_items (giữ nguyên logic cũ)."""
                nonlocal run_count
                try:
                    while not stop_event.is_set():
                        run_count += 1

                        # Giả lập hành vi người dùng trước khi cào
                        print(f"\n🖱️ Giả lập hành vi người dùng...")
                        await simulate_human_behavior(page)

                        # Cào sp_items trước, xong mới cào more_items (tuần tự)
                        sp_items = await scrape_endpoint(api_fn, session_id, "sp_items", limit, "🔴")
                        wait_between = random.uniform(3, 6)
                        print(f"\n⏳ Chờ {wait_between:.1f}s trước khi cào more_items...")
                        await asyncio.sleep(wait_between)
                        more_items = await scrape_endpoint(api_fn, session_id, "more_items", limit, "🔵")

                        # Tag source: 0=sp, 1=more
                        for it in sp_items:
                            it['_source'] = 0
                        for it in more_items:
                            it['_source'] = 1

                        # Merge & dedup
                        seen_ids = set()
                        items = []
                        for it in sp_items + more_items:
                            iid = it.get("item_id", it.get("itemid", ""))
                            if iid and iid not in seen_ids:
                                seen_ids.add(iid)
                                items.append(it)
                            elif not iid:
                                items.append(it)

                        total_raw = len(sp_items) + len(more_items)
                        print(f"\n📊 TỔNG: {len(items)} SP (sp={len(sp_items)}, more={len(more_items)}, trùng={total_raw - len(items)})")
                        print(f"   (joinv2 cào riêng mỗi {JOINV2_INTERVAL[0]}-{JOINV2_INTERVAL[1]}s ngẫu nhiên)")

                        if items:
                            print_summary(items)
                            save_results(items, session_id)
                            push_to_postgresql(items, session_id)
                            print(f"✅ Lần {run_count}: {len(items)} sản phẩm")
                        else:
                            print(f"❌ Lần {run_count}: Không có dữ liệu.")

                        # Random wait 1-2 phút
                        wait = random.randint(REPEAT_MIN, REPEAT_MAX)
                        print(f"\n⏳ Chờ {wait//60}:{wait%60:02d}... (Ctrl+C để dừng)")
                        await asyncio.sleep(wait)

                        # Session budget: sau mỗi N lần cào → nghỉ dài để tránh CAPTCHA
                        if run_count % SESSION_BUDGET == 0:
                            rest = random.randint(SESSION_REST_MIN, SESSION_REST_MAX)
                            print(f"\n☕ [Session budget] Đã cào {run_count} lần → nghỉ dài {rest//60}:{rest%60:02d} để tránh CAPTCHA...")
                            await asyncio.sleep(rest)
                            print(f"✅ Hết nghỉ, tiếp tục cào...")

                        print(f"\n🔄 Scrape lần {run_count + 1}...")

                except asyncio.CancelledError:
                    pass

            try:
                # Chạy cả 2 task song song
                await asyncio.gather(
                    sp_more_loop(),
                    joinv2_loop(session_id, page, stop_event),
                )
                break  # Thoát bình thường
            except (KeyboardInterrupt, asyncio.CancelledError):
                stop_event.set()
                print(f"\n🛑 Dừng. Đã scrape {run_count} lần.")
                break
            except Exception as e:
                reconnect_attempt += 1
                if reconnect_attempt > MAX_RECONNECT:
                    print(f"❌ Quá {MAX_RECONNECT} lần reconnect, dừng hẳn.")
                    break
                print(f"\n⚠️ Mất kết nối CDP: {e}")
                print(f"🔄 Thử reconnect sau {RECONNECT_DELAY}s... (lần {reconnect_attempt}/{MAX_RECONNECT})")
                stop_event.clear()
                await asyncio.sleep(RECONNECT_DELAY)

        print("✅ Xong. RoxyBrowser vẫn mở.")


if __name__ == "__main__":
    asyncio.run(main())
