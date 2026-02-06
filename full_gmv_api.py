# -*- coding: utf-8 -*-
"""
Phiên bản nâng cao của full_gmv.py với tính năng:
1. Gọi API trực tiếp với pageSize=500
2. Ghi song song vào CSV và Google Sheet
"""
import asyncio
import json
import os
import sys
import re
import csv
from datetime import datetime

# Import module gốc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backup_full_gmv import ShopeeScraperApp, OUTPUT_DIR

# Import PyQt6
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QPushButton, QComboBox, QLabel, QMessageBox, QTextEdit, QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt

# Import Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    print("⚠️ gspread không được cài. Chạy: pip install gspread google-auth")

# CSV Header mở rộng với 3 cột mới cho Confirmed data
CSV_HEADER_API = [
    "DateTime", "Item ID", "Tên sản phẩm",
    "Lượt click trên sản phẩm", "Tỷ lệ click vào sản phẩm",
    "Tổng đơn hàng", "Các mặt hàng được bán", "Doanh thu",
    "Tỷ lệ click để đặt hàng", "Thêm vào giỏ hàng",
    "NMV (Confirmed Revenue)", "Tổng đơn hàng (Confirmed)", "Các mặt hàng được bán (Confirmed)"
]

# Service Account Key path
SERVICE_ACCOUNT_KEY = os.path.join(os.path.dirname(__file__), "service-account-key.json")


class ShopeeScraperWithGSheet(ShopeeScraperApp):
    """Phiên bản mở rộng với tính năng Google Sheet"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shopee Scraper (API + Google Sheet)")
        self.resize(450, 350)
        
        # Google Sheet variables
        self.gsheet_client = None
        self.current_spreadsheet = None
        self.current_worksheet = None
        self.gsheet_enabled = False
        self.gsheet_header_written = False  # Track đã ghi header chưa
        
        # Thêm UI elements cho Google Sheet
        self._add_gsheet_ui()
    
    def _add_gsheet_ui(self):
        """Thêm UI elements cho Google Sheet"""
        # Tạo group box cho Google Sheet settings
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
        
        # Thêm vào layout chính (trước log_output)
        # Tìm vị trí của log_output và chèn trước đó
        main_layout = self.layout
        main_layout.insertWidget(main_layout.count() - 1, gsheet_group)
        
        # Thêm log_output nếu chưa có
        if not hasattr(self, 'log_output') or self.log_output is None:
            self.log_output = QTextEdit()
            self.log_output.setReadOnly(True)
            main_layout.addWidget(self.log_output)
    
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
            
            # Kết nối với service account
            if not os.path.exists(SERVICE_ACCOUNT_KEY):
                QMessageBox.critical(self, "Lỗi", f"Không tìm thấy file:\n{SERVICE_ACCOUNT_KEY}")
                self.gsheet_status.setText("❌ Không tìm thấy service account key")
                return
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY, scopes=scopes)
            self.gsheet_client = gspread.authorize(creds)
            
            # Mở spreadsheet
            self.current_spreadsheet = self.gsheet_client.open_by_url(url)
            
            # Lấy danh sách worksheets
            worksheets = self.current_spreadsheet.worksheets()
            
            # Clear và populate dropdown
            self.sheet_selector.clear()
            for ws in worksheets:
                self.sheet_selector.addItem(ws.title, ws)
            
            # Chọn sheet đầu tiên
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
    
    def save_to_gsheet(self, rows):
        """Ghi dữ liệu vào Google Sheet (batch mode để tránh rate limit)"""
        if not self.gsheet_enabled or not self.current_worksheet:
            return False
        
        if not rows:
            return False
        
        try:
            # Chuẩn bị dữ liệu để ghi batch
            all_rows = []
            
            # CHỈ ghi header lần đầu tiên trong session
            if not self.gsheet_header_written:
                # Kiểm tra xem sheet đã có header chưa
                existing_data = self.current_worksheet.get_all_values()
                has_header = False
                if existing_data and len(existing_data) > 0:
                    first_row = existing_data[0]
                    if len(first_row) >= 3 and first_row[0] == "DateTime" and first_row[1] == "Item ID":
                        has_header = True
                
                # Nếu chưa có header, thêm vào batch
                if not has_header:
                    all_rows.append(CSV_HEADER_API)
                
                # Đánh dấu đã xử lý header
                self.gsheet_header_written = True
            
            # Chuẩn hóa và thêm tất cả rows vào batch
            for row in rows:
                row_data = list(row) if isinstance(row, (list, tuple)) else [str(row)]
                if len(row_data) < len(CSV_HEADER_API):
                    row_data += [""] * (len(CSV_HEADER_API) - len(row_data))
                elif len(row_data) > len(CSV_HEADER_API):
                    row_data = row_data[:len(CSV_HEADER_API)]
                
                # Convert all to string
                row_data = [str(x) if x is not None else "" for x in row_data]
                all_rows.append(row_data)
            
            # GHI BATCH - 1 lần API call duy nhất!
            if all_rows:
                self.current_worksheet.append_rows(all_rows, value_input_option='USER_ENTERED')
            
            self.log(f"📊 Đã ghi {len(rows)} dòng vào Google Sheet (batch mode)")
            return True
            
        except Exception as e:
            self.log(f"❌ Lỗi ghi Google Sheet: {e}")
            return False


def save_to_csv_api(self, rows):
    """Ghi CSV với header mở rộng (13 cột) + ghi Google Sheet song song."""
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
    
    # Chuẩn hóa dữ liệu trước khi ghi
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
        mode = "w" if header_needed else "a"
        encoding = "utf-8-sig" if header_needed else "utf-8"
        with open(path, mode, encoding=encoding, newline="") as f:
            w = csv.writer(f, quoting=csv.QUOTE_ALL)
            if header_needed:
                w.writerow(CSV_HEADER_API)
            for r in norm_rows:
                w.writerow(r)
        
        self.log(f"✅ Đã ghi {len(norm_rows)} dòng vào CSV")
        
        # === GHI SONG SONG VÀO GOOGLE SHEET ===
        if hasattr(self, 'save_to_gsheet') and hasattr(self, 'gsheet_enabled'):
            if self.gsheet_enabled:
                self.save_to_gsheet(norm_rows)
        
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


# Thêm phương thức mới để gọi API trực tiếp
async def extract_data_via_api(self, page, session_id):
    """
    Lấy dữ liệu sản phẩm trực tiếp từ API với pageSize=500.
    Nhanh hơn nhiều so với việc click từng trang (10 SP/trang).
    """
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
            # Gọi API bằng cách evaluate JavaScript trong context của trang
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
            
            # Kiểm tra cấu trúc response
            data = response.get("data", {})
            
            product_list = data.get("productList", [])
            
            # Thử các tên trường khác nếu productList rỗng
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
            
            # Parse dữ liệu sản phẩm
            for product in product_list:
                try:
                    # Lấy itemId từ API
                    item_id = str(product.get("itemId", ""))
                    
                    # title = Tên sản phẩm
                    name = product.get("title", "")
                    
                    # productClicks = Lượt click trên sản phẩm
                    clicks = str(product.get("productClicks", 0))
                    
                    # ctr = Tỷ lệ click vào sản phẩm (đã có sẵn dạng %)
                    ctr = product.get("ctr", "0%")
                    if not str(ctr).endswith("%"):
                        try:
                            ctr = f"{float(ctr)*100:.1f}%"
                        except:
                            ctr = f"{ctr}%"
                    
                    # ordersCreated = Tổng đơn hàng
                    total_orders = str(product.get("ordersCreated", 0))
                    
                    # itemSold = Các mặt hàng được bán
                    items_sold = str(product.get("itemSold", 0))
                    
                    # revenue = Doanh thu (chuẩn hóa về số thô)
                    revenue_raw = product.get("revenue", 0)
                    if isinstance(revenue_raw, (int, float)):
                        revenue = str(int(revenue_raw))
                    else:
                        revenue = str(revenue_raw).replace("₫", "").replace(",", "").replace(".", "").strip()
                    
                    # cor = Tỷ lệ click để đặt hàng
                    cto_rate = product.get("cor", "0%")
                    if not str(cto_rate).endswith("%"):
                        try:
                            cto_rate = f"{float(cto_rate)*100:.1f}%"
                        except:
                            cto_rate = f"{cto_rate}%"
                    
                    # atc = Thêm vào giỏ hàng
                    add_to_cart = str(product.get("atc", 0))
                    
                    # ===== 3 CỘT MỚI (Confirmed data) =====
                    # confirmedRevenue = NMV (Doanh thu đã xác nhận)
                    nmv_raw = product.get("confirmedRevenue", 0)
                    if isinstance(nmv_raw, (int, float)):
                        nmv = str(int(nmv_raw))
                    else:
                        nmv = str(nmv_raw).replace("₫", "").replace(",", "").replace(".", "").strip()
                    
                    # confirmedOrderCnt = Tổng đơn hàng (Confirmed)
                    confirmed_orders = str(product.get("confirmedOrderCnt", 0))
                    
                    # ComfirmedItemsold = Các mặt hàng được bán (Confirmed)
                    confirmed_items_sold = str(product.get("ComfirmedItemsold", product.get("confirmedItemSold", 0)))
                    
                    results.append([
                        dt_str, item_id, name,
                        clicks, ctr, total_orders, items_sold,
                        revenue, cto_rate, add_to_cart,
                        # 3 cột mới
                        nmv, confirmed_orders, confirmed_items_sold,
                    ])
                    total_products += 1
                    
                except Exception as e:
                    self.log(f"⚠️ Lỗi parse sản phẩm: {e}")
                    continue
            
            # Kiểm tra còn trang tiếp theo không
            if len(product_list) < page_size:
                break  # Đã lấy hết
            
            # Còn sản phẩm → trang tiếp theo
            page_num += 1
            await asyncio.sleep(0.5)  # Delay nhẹ để tránh rate limit
            
        except Exception as e:
            self.log(f"❌ Lỗi khi gọi API trang {page_num}: {e}")
            import traceback
            self.log(traceback.format_exc())
            break
    
    self.log(f"✅ Hoàn thành lấy dữ liệu qua API: {total_products} sản phẩm")
    return results


# Lưu phương thức gốc để có thể fallback
original_run_loop = ShopeeScraperApp.run_loop


async def patched_run_loop(self):
    """Phiên bản run_loop sử dụng API trực tiếp với pageSize=500."""
    import threading
    from playwright.async_api import async_playwright
    
    LOCAL_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "Data All in One", "Dashboard")
    
    if len(self.accounts) == 0:
        self.log("Chưa có tài khoản. Vui lòng thêm tài khoản trước.")
        return

    account = self.accounts[self.account_selector.currentIndex()]
    username, password = account["username"], account["password"]
    session_file = os.path.join(LOCAL_PATH, f"auth_state_{username}.json")
    url = self.live_url_input.text().strip()
    
    # === Tạo file CSV duy nhất cho cả phiên ===
    if not self.session_csv_path:
        live_id_part = ""
        if "dashboard/live/" in url:
            live_id_part = "_" + url.split("dashboard/live/")[-1].split("/")[0]
        start_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_csv_path = os.path.join(
            OUTPUT_DIR,
            f"SHP_live_session{live_id_part}_{start_time_str}.csv"
        )
    
    # 1) Chuẩn bị session (nếu chưa có)
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

    # 2) Dùng session để scrape
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=session_file)
        page = await context.new_page()

        # tới dashboard page
        dashboard_page = None
        try:
            await page.goto("https://creator.shopee.vn", timeout=90_000)
        except Exception:
            pass

        # nếu có URL phiên live thì mở thẳng
        if url:
            try:
                await page.goto(url, timeout=90_000)
                dashboard_page = page
            except Exception as e:
                self.log(f"❌ Lỗi khi mở URL phiên live: {e!r}")

        # không có/không mở được → cố gắng tìm tab dashboard
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

        # 4) Vòng scrape sử dụng API
        self.is_running = True
        try:
            while self.is_running:
                try:
                    cycle_start = datetime.now()
                    
                    # SỬ DỤNG API TRỰC TIẾP VỚI pageSize=500
                    data = await extract_data_via_api(self, dashboard_page, session_id)
                    
                    if data:
                        saved = save_to_csv_api(self, data)
                        if saved:
                            self.log(f"✅ Hoàn thành ghi CSV: {saved}")
                    else:
                        self.log("⚠️ Không có dữ liệu để ghi")

                    # ---- CHỜ tới mốc 15 phút kể từ cycle_start ----
                    target_secs = 15 * 60
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
            self.log("Đóng trình duyệt...")
            await context.close()
            await browser.close()
            self.log("Đã dừng theo dõi.")


# Gán các phương thức mới
ShopeeScraperWithGSheet.extract_data_via_api = extract_data_via_api
ShopeeScraperWithGSheet.run_loop = patched_run_loop
ShopeeScraperWithGSheet.save_to_csv_api = save_to_csv_api


# Chạy app
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ShopeeScraperWithGSheet()
    window.show()
    sys.exit(app.exec())
