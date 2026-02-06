# -*- coding: utf-8 -*-
"""
Scraper Dashboard Overview sử dụng API trực tiếp.
Thay thế cho scraper_chup_va_ghi3.py với phương pháp đơn giản và ổn định hơn.

API Endpoint:
https://creator.shopee.vn/supply/api/lm/sellercenter/realtime/dashboard/overview?sessionId={session_id}
"""
import asyncio
import csv
import os
import re
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from playwright.async_api import async_playwright

# ─── CẤU HÌNH ─────────────────────────────────────────────────────────────
INITIAL_DELAY = 5    # Ghi lần đầu sau 5 giây
LOG_INTERVAL = 3600  # Ghi mỗi tiếng (3600 giây)
USER_DESKTOP = Path.home() / "Desktop"
DEST_DIR = USER_DESKTOP / "Livestream_Reports"
DEST_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR = DEST_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# ─── TÀI KHOẢN & SESSION ──────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--account", type=str, required=True)
args = parser.parse_args()

LOCAL_PATH = Path(os.getenv("LOCALAPPDATA", "")) / "Data All in One" / "Dashboard"
ACCOUNT_FILE = LOCAL_PATH / "accounts.json"
SESSION_FILE = LOCAL_PATH / f"auth_state_{args.account}.json"

with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
    account_list = json.load(f)

# Support multiple account formats: label, username, name, or string
account = None
for acc in account_list:
    if isinstance(acc, dict):
        acc_name = acc.get("label") or acc.get("username") or acc.get("name", "")
    else:
        acc_name = acc
    
    if acc_name == args.account:
        account = acc
        break

if account is None:
    raise Exception(f"Không tìm thấy tài khoản: {args.account}")

# CSV Header cho overview data (22 cột)
CSV_HEADER = [
    "Date", "Time", "LiveID",
    "GMV",                          # placedGmv
    "Người xem tương tác",          # engagedViewers
    "Tổng lượt bình luận",          # comments
    "Thêm vào giỏ hàng",            # atc
    "Tổng lượt xem",                # views
    "Số lượt xem trung bình (phút)", # avgViewTime (đổi ra phút)
    "Tỷ lệ bình luận",              # commentsRate
    "GPM",                          # gpm
    "Tổng đơn hàng",                # placedOrder
    "Giá trị đơn hàng trung bình",  # abs
    "Tổng người xem",               # viewers
    "PCU",                          # pcu
    "Tỷ lệ click vào sản phẩm",     # ctr
    "Tỷ lệ click để đặt hàng",      # co
    "Người mua",                    # buyers
    "Các mặt hàng được bán",        # placedItemsSold
    "NMV",                          # confirmedGmv
    "Đơn hàng (Confirmed)",         # confirmedOrder
    "Mặt hàng bán (Confirmed)",     # confirmedItemsSold
]


def extract_live_id(url: str):
    """Lấy live_id từ URL dạng: .../dashboard/live/{id}"""
    m = re.search(r"/dashboard/live/(\d+)", url)
    return m.group(1) if m else None


def open_csv_for_live(live_id: str, today_str: str):
    """Mở file CSV (mode append nếu tồn tại), trả về (writer, file_obj, path)"""
    path = DEST_DIR / f"SHP_Live_{live_id}_{today_str}.csv"
    is_new = not path.exists() or os.path.getsize(path) == 0
    mode = "w" if is_new else "a"
    f = open(path, mode, newline="", encoding="utf-8-sig")
    w = csv.writer(f, quoting=csv.QUOTE_ALL)
    if is_new:
        w.writerow(CSV_HEADER)
    return w, f, path


async def fetch_overview_data(page, session_id):
    """
    Gọi API overview để lấy dữ liệu dashboard.
    Trả về dict với các metric hoặc None nếu lỗi.
    """
    api_url = f"https://creator.shopee.vn/supply/api/lm/sellercenter/realtime/dashboard/overview?sessionId={session_id}"
    
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
        
        if not response or "error" in response:
            print(f"❌ Lỗi API: {response.get('error') if response else 'No response'}")
            return None
        
        data = response.get("data", {})
        if not data:
            print("⚠️ API trả về data rỗng")
            return None
        
        # Parse các metric từ response (22 cột theo thứ tự mới)
        
        # avgViewTime: API trả về milliseconds, chỉ chia 60 (không chia 1000)
        # Lưu dạng "milliseconds/60" vào DB (để frontend chia thêm 1000)
        avg_view_time_raw = data.get("avgViewTime", 0)
        if isinstance(avg_view_time_raw, (int, float)) and avg_view_time_raw > 0:
            avg_view_time = round(avg_view_time_raw / 60, 2)  # ms / 60 (NOT /1000)
        else:
            avg_view_time = 0
        
        metrics = {
            "placedGmv": data.get("placedGmv", 0),
            "engagedViewers": data.get("engagedViewers", 0),
            # comments nằm trong engagementData
            "comments": data.get("engagementData", {}).get("comments", 0),
            "atc": data.get("atc", 0),
            "views": data.get("views", 0),
            "avgViewTime": avg_view_time,  # Store as ms/60
            "commentsRate": data.get("commentsRate", "0%"),
            "gpm": data.get("gpm", 0),
            "placedOrder": data.get("placedOrder", 0),
            "abs": data.get("abs", 0),
            "viewers": data.get("viewers", 0),
            "pcu": data.get("pcu", 0),
            "ctr": data.get("ctr", "0%"),
            "co": data.get("co", "0%"),
            "buyers": data.get("buyers", 0),
            "placedItemsSold": data.get("placedItemsSold", 0),
            "confirmedGmv": data.get("confirmedGmv", 0),
            "confirmedOrder": data.get("confirmedOrder", 0),
            "confirmedItemsSold": data.get("confirmedItemsSold", 0),
        }
        
        return metrics
        
    except Exception as e:
        print(f"❌ Lỗi khi gọi API overview: {e}")
        return None


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = None

        # — Ưu tiên dùng session đã lưu —
        if SESSION_FILE.exists():
            try:
                ctx = await browser.new_context(storage_state=str(SESSION_FILE))
                page = await ctx.new_page()
                await page.goto("https://creator.shopee.vn", wait_until="domcontentloaded")
                if "/login" in page.url.lower():
                    ctx = None
            except:
                ctx = None

        # — Nếu chưa có session, yêu cầu đăng nhập 1 lần —
        if ctx is None:
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto("https://creator.shopee.vn", wait_until="domcontentloaded")
            print("➡️ Đăng nhập rồi mở dashboard/live... (giữ nguyên tab này)")
            while True:
                await asyncio.sleep(2)
                if any("/dashboard/live" in pg.url for pg in ctx.pages):
                    await ctx.storage_state(path=str(SESSION_FILE))
                    print(f"💾 Đã lưu session vào {SESSION_FILE.name}")
                    break

        print("✅ Bắt đầu theo dõi dashboard (API Mode).")

        # State cho mỗi tab
        page_state = {}

        try:
            while True:
                now = datetime.now()
                today_slug = now.strftime("%d-%m")

                # Quét các tab hiện có
                for pg in list(ctx.pages):
                    # Tab không phải dashboard/live
                    if "/dashboard/live" not in pg.url:
                        if pg in page_state:
                            st = page_state.pop(pg)
                            try:
                                st["file"].close()
                                print(f"🔒 Đóng file do tab rời live (live_id={st.get('live_id')})")
                            except:
                                pass
                        continue

                    # Lấy live_id từ URL
                    live_id = extract_live_id(pg.url)
                    if not live_id:
                        if pg in page_state:
                            st = page_state.pop(pg)
                            try:
                                st["file"].close()
                            except:
                                pass
                        continue

                    # Tab mới phát hiện
                    if pg not in page_state:
                        w, f, path = open_csv_for_live(live_id, today_slug)
                        page_state[pg] = {
                            "live_id": live_id,
                            "writer": w,
                            "file": f,
                            "next_log_time": datetime.now() + timedelta(seconds=INITIAL_DELAY),
                        }
                        print(f"➕ Theo dõi Tab live_id={live_id} => {path.name}")
                    else:
                        # Kiểm tra đổi phiên
                        old_id = page_state[pg]["live_id"]
                        if old_id != live_id:
                            try:
                                page_state[pg]["file"].close()
                            except:
                                pass
                            w, f, path = open_csv_for_live(live_id, today_slug)
                            page_state[pg].update({
                                "live_id": live_id,
                                "writer": w,
                                "file": f,
                                "next_log_time": datetime.now() + timedelta(seconds=INITIAL_DELAY),
                            })
                            print(f"🔄 Tab đổi phiên: {old_id} ➜ {live_id}")

                # Ghi số liệu cho từng tab
                for pg, st in list(page_state.items()):
                    try:
                        if pg.is_closed():
                            try:
                                st["file"].close()
                            except:
                                pass
                            page_state.pop(pg, None)
                            continue

                        # Đến mốc ghi?
                        if datetime.now() >= st["next_log_time"]:
                            live_id = st["live_id"]
                            
                            # GỌI API ĐỂ LẤY DỮ LIỆU
                            metrics = await fetch_overview_data(pg, live_id)
                            
                            if metrics:
                                w = st["writer"]
                                f = st["file"]
                                now = datetime.now()
                                
                                row = [
                                    now.strftime("%d/%m"),
                                    now.strftime("%H:%M"),
                                    live_id,
                                    metrics.get("placedGmv", 0),
                                    metrics.get("engagedViewers", 0),
                                    metrics.get("comments", 0),
                                    metrics.get("atc", 0),
                                    metrics.get("views", 0),
                                    metrics.get("avgViewTime", 0),
                                    metrics.get("commentsRate", "0%"),
                                    metrics.get("gpm", 0),
                                    metrics.get("placedOrder", 0),
                                    metrics.get("abs", 0),
                                    metrics.get("viewers", 0),
                                    metrics.get("pcu", 0),
                                    metrics.get("ctr", "0%"),
                                    metrics.get("co", "0%"),
                                    metrics.get("buyers", 0),
                                    metrics.get("placedItemsSold", 0),
                                    metrics.get("confirmedGmv", 0),
                                    metrics.get("confirmedOrder", 0),
                                    metrics.get("confirmedItemsSold", 0),
                                ]
                                
                                w.writerow(row)
                                f.flush()
                                print(f"🕒 Ghi live_id {live_id} lúc {now.strftime('%H:%M:%S')} [API Mode]")
                            
                            st["next_log_time"] = datetime.now() + timedelta(seconds=LOG_INTERVAL)

                    except Exception as e:
                        print(f"❌ Lỗi xử lý Tab: {e}")

                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("\n⏹️ Dừng. Lưu file...")
            for _, st in list(page_state.items()):
                try:
                    st["file"].close()
                except:
                    pass
            print("✅ Hoàn tất.")


if __name__ == "__main__":
    asyncio.run(main())
