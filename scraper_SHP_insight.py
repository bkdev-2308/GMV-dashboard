# -*- coding: utf-8 -*-
"""
Shopee SHP Insight Scraper
- Lấy dữ liệu từ liveDetail API
- Ghi trực tiếp vào Google Sheet theo tên cột
"""
import sys
import os
import json
import asyncio
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QGroupBox, QMessageBox, QInputDialog, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from playwright.async_api import async_playwright

# Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    print("⚠️ gspread không được cài. Chạy: pip install gspread google-auth")

# Paths
LOCAL_PATH = os.path.join(os.getenv("LOCALAPPDATA", ""), "Data All in One", "Dashboard")
os.makedirs(LOCAL_PATH, exist_ok=True)
ACCOUNT_FILE = os.path.join(LOCAL_PATH, "accounts.json")
SERVICE_ACCOUNT_KEY = os.path.join(os.path.dirname(__file__), "service-account-key.json")

# Đảm bảo file accounts tồn tại
if not os.path.exists(ACCOUNT_FILE):
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)


# Column mapping: Tên cột trong Sheet -> Path trong API response
# Format: "path.to.field" hoặc "field" (top level)
# Một số field cần đếm (COUNT) sẽ được xử lý riêng
COLUMN_MAPPING = {
    # KEY METRICS
    "NMV": "performance.confirmedSales",  # trong performance
    # "Cancellation Rate": skip - không điền
    "AOV": "keyMetrics.confirmedABS",
    
    # INTERACTIVE METRICS
    "Người xem tương tác": "keyMetrics.engagedViewers",  # trong keyMetrics
    "Tổng lượt bình luận": "performance.comments",
    "Mặt hàng đã bán": "performance.itemConfirmedOrders",  # trong performance
    "ATC": "keyMetrics.atc",
    "GPM": "keyMetrics.confirmedGPM",
    "Đơn hàng": "performance.confirmedOrders",  # trong performance
    "Tổng lượt xem": "performance.views",
    "PCU": "keyMetrics.peakViewers",  # trong keyMetrics
    "Tổng người mua": "performance.confirmedBuyers",  # trong performance
    "Lượt thích": "performance.likes",
    "Thời lượng xem trung bình": "keyMetrics.avgViewDuration",
    "Lượt chia sẻ": "performance.shares",
    "Tỷ lệ bình luận": "performance.commentRate",  # trong performance
    
    # CONVERSION METRICS
    "Tổng lượt nhấp vào sản phẩm": "keyMetrics.productClicks",
    "CTR": "keyMetrics.ctr",
    "Tỷ lệ nhấp vào sản phẩm": "keyMetrics.productClickRate",
    "Tỷ lệ chuyển đổi": "keyMetrics.conversionRate",
    
    # PROMOTION METRICS
    "Vòng tung xu": "promotion.coinsRound",
    "Vòng đấu giá": "promotion.auctionRound",
    "Tổng số xu đã nhận": "promotion.coinsClaimed",
    "Số người dùng đã nhận voucher": "promotion.userClaimed",
    "Tổng số lần người dùng nhận xu": "promotion.timeClaimed",
    "Số sản phẩm có mức giá ưu đãi": "COUNT:promotion.streamingPriceSets",  # Đếm số lượng
}


def load_accounts():
    with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_accounts(accounts):
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


# =============================================================================
# Scraper Thread
# =============================================================================
class ScraperThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, account_name, session_id, worksheet, header_row):
        super().__init__()
        self.account_name = account_name
        self.session_id = session_id
        self.worksheet = worksheet
        self.header_row = header_row  # List of column headers
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        asyncio.run(self.scrape_and_write())

    async def scrape_and_write(self):
        """Scrape từ API và ghi vào Google Sheet"""
        try:
            # Get authentication file
            SESSION_FILE = os.path.join(LOCAL_PATH, f"auth_state_{self.account_name}.json")

            if not os.path.exists(SESSION_FILE):
                self.log_signal.emit("❌ Chưa có session file. Vui lòng đăng nhập trước.")
                self.log_signal.emit(f"   Chạy: python scraper_api.py --account \"{self.account_name}\"")
                self.finished_signal.emit(False, "Authentication required")
                return

            # Launch browser
            self.log_signal.emit("🌐 Đang mở trình duyệt...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context(storage_state=SESSION_FILE)
                page = await context.new_page()

                # Navigate to creator center
                await page.goto("https://creator.shopee.vn")
                await page.wait_for_load_state("networkidle")

                # Fetch userInfo to get userName for matching
                self.log_signal.emit("👤 Đang lấy thông tin tài khoản...")
                user_name = await self.fetch_user_info(page)
                if user_name:
                    self.log_signal.emit(f"   ✅ Acc: {user_name}")
                else:
                    self.log_signal.emit("   ⚠️ Không lấy được userName")
                
                # Fetch data from liveDetail API
                self.log_signal.emit(f"📡 Đang gọi API liveDetail (session: {self.session_id})...")
                api_data = await self.fetch_live_detail(page)

                if api_data:
                    # Write to Google Sheet
                    self.log_signal.emit("📊 Đang ghi vào Google Sheet...")
                    success = self.write_to_sheet(api_data, user_name)
                    
                    if success:
                        self.log_signal.emit("✅ Hoàn thành ghi dữ liệu vào Google Sheet!")
                        self.finished_signal.emit(True, "Success")
                    else:
                        self.finished_signal.emit(False, "Write failed")
                else:
                    self.log_signal.emit("❌ Không lấy được dữ liệu từ API")
                    self.finished_signal.emit(False, "No data")

                await browser.close()

        except Exception as e:
            self.log_signal.emit(f"❌ Lỗi: {str(e)}")
            self.finished_signal.emit(False, str(e))
    async def fetch_user_info(self, page):
        """Fetch userName from userInfo API"""
        try:
            api_url = "https://creator.shopee.vn/supply/api/lm/sellercenter/userInfo"

            response = await page.evaluate('''
                async (url) => {
                    try {
                        const resp = await fetch(url, {
                            credentials: 'include',
                            headers: {'Accept': 'application/json'}
                        });
                        return await resp.json();
                    } catch(e) {
                        return { error: e.message };
                    }
                }
            ''', api_url)

            if response and response.get("code") == 0:
                data = response.get("data", {})
                user_name = data.get("userName", "")
                return user_name
            return None

        except Exception as e:
            self.log_signal.emit(f"⚠️ userInfo error: {e}")
            return None

    async def fetch_live_detail(self, page):
        """Fetch data from liveDetail API"""
        try:
            api_url = f"https://creator.shopee.vn/supply/api/lm/sellercenter/liveDetail?sessionId={self.session_id}"

            response = await page.evaluate('''
                async (url) => {
                    try {
                        const resp = await fetch(url, {
                            credentials: 'include',
                            headers: {'Accept': 'application/json'}
                        });
                        return await resp.json();
                    } catch(e) {
                        return { error: e.message };
                    }
                }
            ''', api_url)

            if not response or "error" in response:
                error_msg = response.get('error') if response else 'No response'
                self.log_signal.emit(f"❌ API Error: {error_msg}")
                return None

            data = response.get("data", {})
            if not data:
                self.log_signal.emit("⚠️ API trả về dữ liệu rỗng")
                return None

            # Parse và log một số thông tin
            self.log_signal.emit(f"   ✅ Views: {data.get('views', 0)}")
            self.log_signal.emit(f"   ✅ PCU: {data.get('pcu', 0)}")
            self.log_signal.emit(f"   ✅ NMV: {data.get('confirmedGmv', 0)}")

            return data

        except Exception as e:
            self.log_signal.emit(f"❌ Fetch error: {e}")
            return None

    def write_to_sheet(self, api_data, user_name=None):
        """Write data to Google Sheet based on column mapping"""
        try:
            if not self.worksheet or not self.header_row:
                self.log_signal.emit("❌ Chưa chọn worksheet hoặc chưa có header")
                return False

            self.log_signal.emit(f"   📋 Header row có {len(self.header_row)} cột")
            
            # Get live info for matching
            live_info = api_data.get("liveInfo", {})
            start_time_ms = live_info.get("startTime", 0)
            duration_ms = live_info.get("duration", 0)
            # Duration từ API là milliseconds, convert sang hours
            duration_hours = round(duration_ms / 3600000, 2) if duration_ms else 0
            
            # Convert startTime (milliseconds) to date
            if start_time_ms:
                from datetime import datetime
                live_date = datetime.fromtimestamp(start_time_ms / 1000)
                # Format dates for comparison (dd/mm/yyyy and mm/dd/yyyy)
                live_date_ddmm = live_date.strftime("%d/%m/%Y")
                live_date_mmdd = live_date.strftime("%m/%d/%Y")
                live_date_str = live_date.strftime("%Y-%m-%d")
                self.log_signal.emit(f"   📅 Live Date: {live_date_ddmm}")
                self.log_signal.emit(f"   ⏱️ Duration: {duration_hours} hrs")
                if user_name:
                    self.log_signal.emit(f"   👤 Acc: {user_name}")
            else:
                live_date_ddmm = None
                live_date_mmdd = None
                live_date_str = None
                self.log_signal.emit("   ⚠️ No startTime in API response")
            
            # Find matching row by Date (column A) + Acc live (column D) + Duration (column G)
            all_values = self.worksheet.get_all_values()
            target_row = None
            
            # Find column indexes
            date_col_idx = None
            acc_live_col_idx = None
            duration_col_idx = None
            for idx, h in enumerate(self.header_row):
                h_lower = h.lower().strip()
                if h_lower == "date" or "date" in h_lower:
                    date_col_idx = idx
                if "acc live" in h_lower or h_lower == "acc live":
                    acc_live_col_idx = idx
                if "duration" in h_lower:
                    duration_col_idx = idx
            
            self.log_signal.emit(f"   🔍 Date col: {date_col_idx}, Acc col: {acc_live_col_idx}, Duration col: {duration_col_idx}")
            
            # Helper function to parse duration from sheet (could be "6:00" time format or "6.0" decimal)
            def parse_sheet_duration(dur_str):
                if not dur_str:
                    return 0
                dur_str = dur_str.strip()
                # Handle time format like "6:00" or "6:30"
                if ":" in dur_str:
                    parts = dur_str.split(":")
                    hours = float(parts[0]) if parts[0] else 0
                    minutes = float(parts[1]) if len(parts) > 1 and parts[1] else 0
                    return hours + minutes / 60
                else:
                    # Regular number
                    return float(dur_str.replace(",", "."))
            
            # Search for matching row (start from row 3, which is index 2 in all_values)
            if date_col_idx is not None and live_date_ddmm:
                for row_idx, row in enumerate(all_values[2:], start=3):  # Start from row 3
                    if len(row) > date_col_idx:
                        sheet_date = row[date_col_idx].strip() if row[date_col_idx] else ""
                        
                        # Check if date matches (handle both dd/mm/yyyy and mm/dd/yyyy)
                        date_match = False
                        if sheet_date:
                            # Try to parse the sheet date
                            if sheet_date == live_date_ddmm or sheet_date == live_date_mmdd:
                                date_match = True
                            # Also try parsing the date parts
                            try:
                                parts = sheet_date.replace("-", "/").split("/")
                                if len(parts) == 3:
                                    # Could be dd/mm/yyyy or mm/dd/yyyy
                                    day1, month1, year1 = int(parts[0]), int(parts[1]), int(parts[2])
                                    day2, month2, year2 = int(parts[1]), int(parts[0]), int(parts[2])
                                    live_d = live_date.day
                                    live_m = live_date.month
                                    live_y = live_date.year
                                    if (day1 == live_d and month1 == live_m and year1 == live_y):
                                        date_match = True
                                    elif (day2 == live_d and month2 == live_m and year2 == live_y):
                                        date_match = True
                            except:
                                pass
                        
                        if date_match:
                            # Check Acc live column if user_name is available
                            acc_match = True
                            if user_name and acc_live_col_idx is not None and len(row) > acc_live_col_idx:
                                sheet_acc = row[acc_live_col_idx].strip().lower() if row[acc_live_col_idx] else ""
                                if sheet_acc and user_name.lower() not in sheet_acc and sheet_acc not in user_name.lower():
                                    acc_match = False
                                    continue  # Skip this row, account doesn't match
                            
                            # Log the check
                            sheet_acc_display = row[acc_live_col_idx] if acc_live_col_idx and len(row) > acc_live_col_idx else "N/A"
                            row_dur = 0
                            if duration_col_idx is not None and len(row) > duration_col_idx:
                                try:
                                    row_dur = parse_sheet_duration(row[duration_col_idx])
                                except:
                                    pass
                            self.log_signal.emit(f"      Checking row {row_idx}: date={sheet_date}, acc={sheet_acc_display}, dur={row_dur}")
                            
                            # If date matches and acc matches (or no acc check needed), use this row!
                            if acc_match:
                                target_row = row_idx
                                self.log_signal.emit(f"   🎯 Found match: row {target_row} (date={sheet_date}, acc={sheet_acc_display})")
                                break
            
            # If no match found, use next empty row
            if target_row is None:
                target_row = len(all_values) + 1
                self.log_signal.emit(f"   📝 No matching row found, will write to new row {target_row}")

            # Find columns that match our mapping and prepare updates
            updates = []
            matched_count = 0
            
            for col_idx, header in enumerate(self.header_row):
                header_clean = header.strip()
                
                # Check if this column has a mapping
                if header_clean in COLUMN_MAPPING:
                    api_path = COLUMN_MAPPING[header_clean]
                    
                    # Handle COUNT: prefix - count items in array
                    if api_path.startswith("COUNT:"):
                        field_path = api_path.replace("COUNT:", "")
                        array_data = self._get_nested_value(api_data, field_path)
                        if isinstance(array_data, list):
                            value = len(array_data)
                        else:
                            value = 0
                    else:
                        value = self._get_nested_value(api_data, api_path)
                    
                    # Format avgViewDuration to hh:mm:ss (value is in milliseconds)
                    if "avgViewDuration" in api_path and value:
                        try:
                            total_seconds = int(float(value) / 1000)  # ms to seconds
                            hours = total_seconds // 3600
                            minutes = (total_seconds % 3600) // 60
                            seconds = total_seconds % 60
                            value = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        except:
                            pass
                    
                    if value is not None and value != "":
                        # Column index is 1-based in gspread, col_idx is 0-based
                        cell_col = col_idx + 1
                        updates.append({
                            'range': f'{self._col_letter(cell_col)}{target_row}',
                            'values': [[str(value)]]
                        })
                        matched_count += 1
                        self.log_signal.emit(f"      ✓ {header_clean} = {value}")

            if not updates:
                self.log_signal.emit("⚠️ Không tìm thấy cột nào khớp với mapping")
                self.log_signal.emit(f"   Headers: {self.header_row[:10]}...")
                # Debug: show what's in the API data
                self.log_signal.emit(f"   API keys: {list(api_data.keys())}")
                return False

            # Batch update all cells
            self.worksheet.batch_update(updates, value_input_option='USER_ENTERED')
            
            self.log_signal.emit(f"   ✅ Đã ghi {matched_count} giá trị vào dòng {target_row}")
            return True

        except Exception as e:
            import traceback
            self.log_signal.emit(f"❌ Lỗi ghi sheet: {e}")
            self.log_signal.emit(traceback.format_exc())
            return False
    
    def _get_nested_value(self, data, path):
        """Get value from nested dict using dot notation path (e.g., 'keyMetrics.nmv')"""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
            if value is None:
                return None
        return value
    
    def _col_letter(self, col_num):
        """Convert column number to letter (1=A, 2=B, etc.)"""
        result = ""
        while col_num > 0:
            col_num, remainder = divmod(col_num - 1, 26)
            result = chr(65 + remainder) + result
        return result


# =============================================================================
# Main Application
# =============================================================================
class SHPInsightApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shopee SHP Insight Scraper")
        self.resize(550, 500)

        # Variables
        self.accounts = load_accounts()
        self.gsheet_client = None
        self.current_spreadsheet = None
        self.current_worksheet = None
        self.header_row = []
        self.scraper_thread = None

        self.init_ui()
        self.load_account_list()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # ===== Account Selection Group =====
        account_group = QGroupBox("📋 Chọn tài khoản")
        account_layout = QVBoxLayout()

        acc_row = QHBoxLayout()
        self.account_selector = QComboBox()
        self.account_selector.setMinimumWidth(180)
        acc_row.addWidget(self.account_selector)

        self.add_btn = QPushButton("Thêm")
        self.add_btn.clicked.connect(self.add_account)
        acc_row.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Sửa")
        self.edit_btn.clicked.connect(self.edit_account)
        acc_row.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Xóa")
        self.delete_btn.clicked.connect(self.delete_account)
        acc_row.addWidget(self.delete_btn)

        account_layout.addLayout(acc_row)
        account_group.setLayout(account_layout)
        main_layout.addWidget(account_group)

        # ===== Session ID Input =====
        session_group = QGroupBox("🔑 Session ID")
        session_layout = QHBoxLayout()
        session_layout.addWidget(QLabel("Session ID:"))
        self.session_input = QLineEdit()
        self.session_input.setPlaceholderText("Nhập Session ID (ví dụ: 31969509)")
        session_layout.addWidget(self.session_input)
        session_group.setLayout(session_layout)
        main_layout.addWidget(session_group)

        # ===== Google Sheet Settings =====
        gsheet_group = QGroupBox("📊 Google Sheet Settings")
        gsheet_layout = QVBoxLayout()

        # Sheet URL
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("Sheet URL:"))
        self.gsheet_url_input = QLineEdit()
        self.gsheet_url_input.setPlaceholderText("Paste Google Spreadsheet URL...")
        url_row.addWidget(self.gsheet_url_input)
        gsheet_layout.addLayout(url_row)

        # Load & Select Sheet
        select_row = QHBoxLayout()
        self.load_sheets_btn = QPushButton("📂 Load Sheets")
        self.load_sheets_btn.clicked.connect(self.load_google_sheets)
        select_row.addWidget(self.load_sheets_btn)

        select_row.addWidget(QLabel("Chọn Sheet:"))
        self.sheet_selector = QComboBox()
        self.sheet_selector.setMinimumWidth(150)
        self.sheet_selector.currentIndexChanged.connect(self.on_sheet_changed)
        select_row.addWidget(self.sheet_selector)
        gsheet_layout.addLayout(select_row)

        # Status
        self.gsheet_status = QLabel("⚪ Chưa kết nối Google Sheet")
        gsheet_layout.addWidget(self.gsheet_status)

        gsheet_group.setLayout(gsheet_layout)
        main_layout.addWidget(gsheet_group)

        # ===== Action Buttons =====
        action_row = QHBoxLayout()
        self.scrape_btn = QPushButton("🚀 Scrape & Ghi vào Sheet")
        self.scrape_btn.clicked.connect(self.start_scrape)
        self.scrape_btn.setStyleSheet("font-weight: bold; padding: 10px;")
        action_row.addWidget(self.scrape_btn)
        main_layout.addLayout(action_row)

        # ===== Log Output =====
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)
        main_layout.addWidget(self.log_output)

        self.setLayout(main_layout)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    # ===== Account Management =====
    def load_account_list(self):
        self.account_selector.clear()
        for acc in self.accounts:
            self.account_selector.addItem(acc.get("username", "Unknown"))

    def add_account(self):
        name, ok = QInputDialog.getText(self, "Thêm tài khoản", "Tên tài khoản:")
        if ok and name.strip():
            self.accounts.append({"username": name.strip(), "password": ""})
            save_accounts(self.accounts)
            self.load_account_list()
            self.account_selector.setCurrentIndex(len(self.accounts) - 1)
            self.log(f"✅ Đã thêm tài khoản: {name.strip()}")

    def edit_account(self):
        idx = self.account_selector.currentIndex()
        if idx < 0:
            return
        old_name = self.accounts[idx].get("username", "")
        new_name, ok = QInputDialog.getText(self, "Sửa tài khoản", "Tên mới:", text=old_name)
        if ok and new_name.strip():
            self.accounts[idx]["username"] = new_name.strip()
            save_accounts(self.accounts)
            self.load_account_list()
            self.account_selector.setCurrentIndex(idx)
            self.log(f"✅ Đã sửa tài khoản: {old_name} → {new_name.strip()}")

    def delete_account(self):
        idx = self.account_selector.currentIndex()
        if idx < 0:
            return
        name = self.accounts[idx].get("username", "")
        reply = QMessageBox.question(
            self, "Xác nhận", f"Xóa tài khoản '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self.accounts[idx]
            save_accounts(self.accounts)
            self.load_account_list()
            self.log(f"🗑️ Đã xóa tài khoản: {name}")

    # ===== Google Sheet =====
    def load_google_sheets(self):
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

            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY, scopes=scopes)
            self.gsheet_client = gspread.authorize(creds)

            self.current_spreadsheet = self.gsheet_client.open_by_url(url)
            worksheets = self.current_spreadsheet.worksheets()

            self.sheet_selector.clear()
            for ws in worksheets:
                self.sheet_selector.addItem(ws.title, ws)

            if worksheets:
                self.current_worksheet = worksheets[0]
                self.load_header_row()

            self.gsheet_status.setText(f"✅ Đã kết nối: {self.current_spreadsheet.title}")
            self.log(f"📊 Đã load {len(worksheets)} sheets từ: {self.current_spreadsheet.title}")

        except gspread.exceptions.SpreadsheetNotFound:
            QMessageBox.critical(self, "Lỗi", "Không tìm thấy Spreadsheet.\nHãy đảm bảo đã share với service account.")
            self.gsheet_status.setText("❌ Spreadsheet không tìm thấy")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi kết nối:\n{e}")
            self.gsheet_status.setText(f"❌ Lỗi: {e}")
            self.log(f"❌ Lỗi kết nối Google Sheet: {e}")

    def on_sheet_changed(self, index):
        if index >= 0:
            self.current_worksheet = self.sheet_selector.itemData(index)
            self.load_header_row()
            self.log(f"📋 Đã chọn sheet: {self.current_worksheet.title}")

    def load_header_row(self):
        """Load header row from the selected sheet (row 2 based on image)"""
        try:
            if self.current_worksheet:
                # Get row 2 (header row based on user's image)
                self.header_row = self.current_worksheet.row_values(2)
                self.log(f"   📝 Đã load {len(self.header_row)} cột header")
        except Exception as e:
            self.log(f"⚠️ Lỗi load header: {e}")
            self.header_row = []

    # ===== Scrape Action =====
    def start_scrape(self):
        # Validate inputs
        if self.account_selector.currentIndex() < 0:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn tài khoản")
            return

        session_id = self.session_input.text().strip()
        if not session_id:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập Session ID")
            return

        if not self.current_worksheet:
            QMessageBox.warning(self, "Lỗi", "Vui lòng load và chọn Google Sheet")
            return

        if not self.header_row:
            QMessageBox.warning(self, "Lỗi", "Sheet chưa có header row")
            return

        # Get account name
        account_name = self.accounts[self.account_selector.currentIndex()].get("username", "")

        # Start scraper thread
        self.scrape_btn.setEnabled(False)
        self.log(f"🚀 Bắt đầu scrape session {session_id}...")

        self.scraper_thread = ScraperThread(
            account_name=account_name,
            session_id=session_id,
            worksheet=self.current_worksheet,
            header_row=self.header_row
        )
        self.scraper_thread.log_signal.connect(self.log)
        self.scraper_thread.finished_signal.connect(self.on_scrape_finished)
        self.scraper_thread.start()

    def on_scrape_finished(self, success, message):
        self.scrape_btn.setEnabled(True)
        if success:
            self.log("🎉 Hoàn thành!")
        else:
            self.log(f"❌ Kết thúc: {message}")


# =============================================================================
# Main Entry
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SHPInsightApp()
    window.show()
    sys.exit(app.exec())
