import asyncio, csv, os, traceback, re
from datetime import datetime, timedelta
from pathlib import Path
import argparse, json

from playwright.async_api import async_playwright
from typing import Optional

# Determine screen resolution to use a full-size viewport
try:
    import ctypes  # Works on Windows to get current screen size
    _w = ctypes.windll.user32.GetSystemMetrics(0)
    _h = ctypes.windll.user32.GetSystemMetrics(1)
    if not _w or not _h:
        raise ValueError("Invalid screen size")
    SCREEN_WIDTH, SCREEN_HEIGHT = int(_w), int(_h)
except Exception:
    # Fallback if detection fails or not on Windows
    SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080

# ─── CẤU HÌNH ─────────────────────────────────────────────────────────────
INITIAL_DELAY = 5   # Ghi lần đầu sau 10 giây
LOG_INTERVAL  = 3600 # Ghi mỗi tiếng 
USER_DESKTOP  = Path.home() / "Desktop"
DEST_DIR      = USER_DESKTOP / "Livestream_Reports"
DEST_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR = DEST_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# Schedule helper: compute the next 00:00 (local midnight)
def next_midnight_from(now: datetime) -> datetime:
    tomorrow = (now + timedelta(days=1)).date()
    return datetime.combine(tomorrow, datetime.min.time())

# ─── TÀI KHOẢN & SESSION ──────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--account", type=str, required=True)
args = parser.parse_args()

LOCAL_PATH   = Path(os.getenv("LOCALAPPDATA", "")) / "Data All in One" / "Dashboard"
ACCOUNT_FILE = LOCAL_PATH / "accounts.json"
SESSION_FILE = LOCAL_PATH / f"auth_state_{args.account}.json"

with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
    account_list = json.load(f)
account = next((acc for acc in account_list if acc["username"] == args.account), None)
if account is None:
    raise Exception(f"Không tìm thấy tài khoản: {args.account}")

# ─── XPATH ────────────────────────────────────────────────────────────────
GMV_XPATH               = "/html/body/div[1]/div/div/div[1]/div[2]/div[1]/div[2]"
VIEW_XPATH              = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[1]/div[2]/div[3]/div[2]"
GPM_XPATH               = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[2]/div[2]/div[2]/div[2]"
PCU_XPATH               = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[1]/div[2]/div[4]/div[2]"
TONGDONHANG_XPATH       = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[3]/div[2]/div[1]/div[2]"
AVGDONHANG_XPATH        = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[3]/div[2]/div[2]/div[2]/div"
NGUOIMUA_XPATH          = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[3]/div[2]/div[3]/div[2]"
TYLECLICK_XPATH         = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[2]/div[2]/div[3]/div[2]"
TYLENHAPCHUOT_XPATH     = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[2]/div[2]/div[4]/div[2]"
MATHANGDUOCBAN_XPATH    = "/html/body/div[1]/div/div/div[1]/div[2]/div[2]/div[3]/div[2]/div[4]/div[2]"

# ─── HÀM GIÚP ─────────────────────────────────────────────────────────────
async def decode_scroller(page, xpath) -> Optional[int]:
    js = '''
    (xp) => {
      const root = document.evaluate(xp, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
      if (!root) return null;
      const digits = [];
      root.querySelectorAll('.index-module__numberScroller--gHI3g').forEach(s => {
        const hidden = s.querySelector('.index-module__numberWrapHidden--ugWwk')?.textContent?.trim?.();
        if (hidden === ',') return;
        if (hidden === '.') { digits.push('.'); return; }
        const anim = s.querySelector('.index-module__numberAnimation---1dZw');
        if (!anim) return;
        const top = Math.abs(parseFloat(anim.style.top || "0"));
        const step = parseFloat(getComputedStyle(s).getPropertyValue('--number-size') || "1");
        if (!isFinite(top) || !isFinite(step) || step === 0) return;
        const digit = Math.round(top / step) % 10;
        digits.push(String(digit));
      });
      const intText = digits.join('').replace(/\./g, '');
      return intText ? parseInt(intText, 10) : null;
    }
    '''
    try:
        return await page.evaluate(js, xpath)
    except:
        return None

def extract_live_id(url: str) -> Optional[str]:
    """
    Lấy live_id từ URL dạng: .../dashboard/live/{id}
    """
    m = re.search(r"/dashboard/live/(\d+)", url)
    return m.group(1) if m else None

def open_csv_for_live(live_id: str, today_str: str):
    """
    Mở file CSV (mode append nếu tồn tại), trả về (writer, file_obj, path)
    """
    # Nếu muốn thêm account vào tên file: đổi dòng dưới thành f"{args.account}_SHP_Live_{live_id}_{today_str}.csv"
    path = DEST_DIR / f"SHP_Live_{live_id}_{today_str}.csv"
    is_new = not path.exists() or os.path.getsize(path) == 0
    mode = "w" if is_new else "a"
    f = open(path, mode, newline="", encoding="utf-8-sig")  # BOM để Excel mở UTF-8
    w = csv.writer(f, quoting=csv.QUOTE_ALL)
    if is_new:
        w.writerow([
            "Date", "Time", "LiveID",
            "GMV", "Live Views", "GPM", "PCU",
            "Total order", "Giá trị đơn hàng trung bình", "Buyer",
            "Tỷ lệ click vào sản phẩm", "Tỷ lệ click để đặt hàng", "Sold SKU"
        ])
    return w, f, path

def create_session_screens_dir(account_name: str, live_id: str) -> Path:
    """
    Tạo thư mục chứa ảnh cho mỗi phiên theo mẫu:
    Desktop/Livestream_Reports/screenshots/{account}_{liveId}_{YYYYMMDD_HHMMSS}
    """
    ts = datetime.now().strftime("%Y%m%d")
    session_dir = SCREENSHOTS_DIR / f"{account_name}_{live_id}_{ts}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

# ─── LUỒNG CHÍNH ──────────────────────────────────────────────────────────
async def main():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        ctx = None

        # — Ưu tiên dùng session đã lưu —
        if SESSION_FILE.exists():
            try:
                ctx = await browser.new_context(
                    storage_state=str(SESSION_FILE),
                    viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
                )
                page = await ctx.new_page()
                try:
                    await page.set_viewport_size({"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT})
                except Exception:
                    pass
                await page.goto("https://creator.shopee.vn", wait_until="domcontentloaded")
                if "/login" in page.url.lower():
                    ctx = None
            except:
                ctx = None

        # — Nếu chưa có session, yêu cầu đăng nhập 1 lần —
        if ctx is None:
            ctx = await browser.new_context(
                viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
            )
            page = await ctx.new_page()
            try:
                await page.set_viewport_size({"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT})
            except Exception:
                pass
            await page.goto("https://creator.shopee.vn", wait_until="domcontentloaded")
            print("➡️ Đăng nhập rồi mở dashboard/live... (giữ nguyên tab này)")
            while True:
                await asyncio.sleep(2)
                if any("/dashboard/live" in pg.url for pg in ctx.pages):
                    await ctx.storage_state(path=str(SESSION_FILE))
                    print(f"💾 Đã lưu session vào {SESSION_FILE.name}")
                    break

        print("✅ Bắt đầu theo dõi dashboard.")

        # Mỗi tab có 1 state riêng
        # page_state[page] = {
        #   "live_id": "...",
        #   "writer": csv.writer,
        #   "file": file_obj,
        #   "next_log_time": datetime
        # }
        page_state = {}

        try:
            while True:
                now = datetime.now()
                today_slug = now.strftime("%d-%m")

                # Quét các tab hiện có
                for pg in list(ctx.pages):
                    # Nếu tab rời khỏi /dashboard/live => đóng file & xoá state
                    if "/dashboard/live" not in pg.url:
                        if pg in page_state:
                            st = page_state.pop(pg)
                            try:
                                st["file"].close()
                                print(f"🔒 Đóng file do tab rời live (live_id={st.get('live_id')})")
                            except:
                                pass
                        continue

                    # Tab đang ở /dashboard/live => lấy live_id
                    live_id = extract_live_id(pg.url)
                    if not live_id:
                        # Có thể đang là trang list live (chưa chọn phiên cụ thể)
                        # Nếu tab đã có state trước đó nhưng giờ không còn live_id => đóng file, xoá state
                        if pg in page_state:
                            st = page_state.pop(pg)
                            try:
                                st["file"].close()
                                print(f"🔒 Đóng file do tab không còn live_id (trước đó {st.get('live_id')})")
                            except:
                                pass
                        continue

                    # Nếu tab mới phát hiện lần đầu
                    if pg not in page_state:
                        w, f, path = open_csv_for_live(live_id, today_slug)
                        session_dir = create_session_screens_dir(args.account, live_id)
                        page_state[pg] = {
                            "live_id": live_id,
                            "writer": w,
                            "file": f,
                            "next_log_time": datetime.now() + timedelta(seconds=INITIAL_DELAY),
                            "next_shot_time": next_midnight_from(datetime.now()),
                            "session_dir": session_dir,
                        }
                        print(f"➕ Theo dõi Tab live_id={live_id} => {path.name}")
                    else:
                        # Tab đã theo dõi; kiểm tra có đổi phiên không
                        old_id = page_state[pg]["live_id"]
                        if old_id != live_id:
                            # Đổi phiên: đóng file cũ & mở file mới, reset timer
                            try:
                                page_state[pg]["file"].close()
                            except:
                                pass
                            w, f, path = open_csv_for_live(live_id, today_slug)
                            session_dir = create_session_screens_dir(args.account, live_id)
                            page_state[pg].update({
                                "live_id": live_id,
                                "writer": w,
                                "file": f,
                                "next_log_time": datetime.now() + timedelta(seconds=INITIAL_DELAY),
                                "next_shot_time": next_midnight_from(datetime.now()),
                                "session_dir": session_dir,
                            })
                            print(f"🔄 Tab đổi phiên: {old_id} ➜ {live_id} => {path.name}")

                # Ghi số liệu cho từng tab/phiên
                for pg, st in list(page_state.items()):
                    try:
                        if pg.is_closed():
                            # Tab đóng => dọn dẹp
                            try:
                                st["file"].close()
                            except:
                                pass
                            page_state.pop(pg, None)
                            print(f"🧹 Dọn dẹp tab đóng (live_id={st.get('live_id')})")
                            continue
                        
                        # Screenshot at midnight (00:00) per tab
                        now = datetime.now()
                        if st.get("next_shot_time") and now >= st["next_shot_time"]:
                            try:
                                shot_name = f"{now.strftime('%Y-%m-%d_%H-%M-%S')}.png"
                                shot_dir = st.get("session_dir", SCREENSHOTS_DIR)
                                shot_dir.mkdir(parents=True, exist_ok=True)
                                shot_path = shot_dir / shot_name
                                await pg.screenshot(path=str(shot_path), full_page=True)
                                print(f"• Screenshot: {shot_path}")
                            except Exception as se:
                                print(f"Lỗi chụp ảnh: {se}")
                            st["next_shot_time"] = next_midnight_from(now)

                        metrics = await asyncio.gather(
                            decode_scroller(pg, GMV_XPATH),
                            decode_scroller(pg, VIEW_XPATH),
                            decode_scroller(pg, GPM_XPATH),
                            decode_scroller(pg, PCU_XPATH),
                            decode_scroller(pg, TONGDONHANG_XPATH),
                            decode_scroller(pg, AVGDONHANG_XPATH),
                            decode_scroller(pg, NGUOIMUA_XPATH),
                            decode_scroller(pg, TYLECLICK_XPATH),
                            decode_scroller(pg, TYLENHAPCHUOT_XPATH),
                            decode_scroller(pg, MATHANGDUOCBAN_XPATH)
                        )

                        # Hourly data logging (CSV) independent of screenshot schedule
                        _now = datetime.now()
                        if _now >= st["next_log_time"]:
                            if None not in metrics:
                                w = st["writer"]
                                f = st["file"]
                                live_id = st["live_id"]
                                w.writerow([_now.strftime("%d/%m"), _now.strftime("%H:%M"), live_id] + metrics)
                                f.flush()
                                print(f"• Ghi live_id {live_id} lúc {_now.strftime('%H:%M:%S')}")
                            st["next_log_time"] = _now + timedelta(seconds=LOG_INTERVAL)
                            continue

                        # Đến mốc ghi của riêng tab này?
                        if datetime.now() >= st["next_log_time"]:
                            # Chụp full page mỗi giờ
                            try:
                                now = datetime.now()
                                shot_name = f"{now.strftime('%Y-%m-%d_%H-%M-%S')}.png"
                                shot_dir = st.get("session_dir", SCREENSHOTS_DIR)
                                shot_dir.mkdir(parents=True, exist_ok=True)
                                shot_path = shot_dir / shot_name
                                await pg.screenshot(path=str(shot_path), full_page=True)
                                print(f"✓ Screenshot: {shot_path}")
                            except Exception as se:
                                print(f"Lỗi chụp ảnh: {se}")
                            # Chỉ ghi nếu không có None trong metrics
                            if None not in metrics:
                                w = st["writer"]
                                f = st["file"]
                                live_id = st["live_id"]
                                now = datetime.now()
                                w.writerow([now.strftime("%d/%m"), now.strftime("%H:%M"), live_id] + metrics)
                                f.flush()
                                print(f"🕒 Ghi live_id {live_id} lúc {now.strftime('%H:%M:%S')}")
                                st["next_log_time"] = datetime.now() + timedelta(seconds=LOG_INTERVAL)
                            # Đặt lịch lần sau (dù có ghi CSV hay không)
                            st["next_log_time"] = datetime.now() + timedelta(seconds=LOG_INTERVAL)

                    except Exception as e:
                        print(f"❌ Lỗi xử lý Tab live_id={st.get('live_id')}: {e}")
                        traceback.print_exc()

                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("\n⏹️ Dừng. Lưu file...")
            # Đóng mọi file còn mở
            for _, st in list(page_state.items()):
                try:
                    st["file"].close()
                except:
                    pass
            print("✅ Hoàn tất.")

if __name__ == "__main__":
    asyncio.run(main())
