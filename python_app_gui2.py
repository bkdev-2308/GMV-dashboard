
import sys, json, subprocess, os, asyncio
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QMessageBox, QInputDialog, QTabWidget,
                             QLineEdit, QTextEdit, QGroupBox, QCheckBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QFileDialog)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from playwright.async_api import async_playwright
import psycopg2

# Import db_helpers for database functions
try:
    from db_helpers import get_gspread_client
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

ACCOUNT_FILE = os.path.join(os.getenv("LOCALAPPDATA"), "Data All in One", "Dashboard", "accounts.json")
os.makedirs(os.path.dirname(ACCOUNT_FILE), exist_ok=True)
if not os.path.exists(ACCOUNT_FILE):
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

def load_accounts():
    with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_accounts(accounts):
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)

# =============================================================================
# Unified Scraper Thread (NEW - Saves to both CSV and PostgreSQL)
# =============================================================================
class UnifiedScraperThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)  # success, message

    def __init__(self, account_name, save_to_csv, save_to_postgres, session_id="", session_title="", db_url=""):
        super().__init__()
        self.account_name = account_name
        self.save_to_csv = save_to_csv
        self.save_to_postgres = save_to_postgres
        self.session_id = session_id
        self.session_title = session_title or session_id
        self.db_url = db_url
        self.should_stop = False

    def stop(self):
        self.should_stop = True

    def run(self):
        asyncio.run(self.scrape_and_save())

    async def scrape_and_save(self):
        """Scrape overview data and save to selected destinations using single browser"""
        try:
            # Validate selections
            if not self.save_to_csv and not self.save_to_postgres:
                self.log_signal.emit("⚠️ Please select at least one output destination")
                self.finished_signal.emit(False, "No destination selected")
                return

            # Get authentication file
            LOCAL_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "Data All in One", "Dashboard")
            SESSION_FILE = os.path.join(LOCAL_PATH, f"auth_state_{self.account_name}.json")

            if not os.path.exists(SESSION_FILE):
                self.log_signal.emit("❌ Session file not found. Please authenticate first.")
                self.log_signal.emit("   Run: python scraper_api.py --account \"" + self.account_name + "\"")
                self.finished_signal.emit(False, "Authentication required")
                return

            # Validate PostgreSQL config if selected
            if self.save_to_postgres and (not self.session_id or not self.db_url):
                self.log_signal.emit("⚠️ Missing PostgreSQL configuration")
                self.finished_signal.emit(False, "Missing configuration")
                return

            # Launch single browser for both operations
            self.log_signal.emit("🌐 Opening browser...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(storage_state=SESSION_FILE)
                page = await context.new_page()

                # Navigate to Creator Center
                await page.goto("https://creator.shopee.vn")
                await page.wait_for_load_state("networkidle")

                # Fetch overview data
                self.log_signal.emit(f"� Fetching overview data...")
                
                # Determine session ID to use
                session_to_scrape = self.session_id if self.save_to_postgres else None
                if not session_to_scrape and self.save_to_csv:
                    # Try to get from current page URL or dashboard
                    try:
                        await page.goto("https://creator.shopee.vn/lm/sellercenter/dashboard", wait_until="networkidle")
                        await asyncio.sleep(2)
                        # Extract from URL if navigated to live page
                        url = page.url
                        import re
                        match = re.search(r'/dashboard/live/(\d+)', url)
                        if match:
                            session_to_scrape = match.group(1)
                        else:
                            self.log_signal.emit("⚠️ Could not determine session ID from dashboard")
                    except Exception as e:
                        self.log_signal.emit(f"⚠️ Error detecting session: {e}")

                if session_to_scrape:
                    overview_data = await self.fetch_overview_api(page, session_to_scrape)
                    
                    if overview_data:
                        # Save to CSV if selected
                        if self.save_to_csv:
                            await self.save_to_csv_file(session_to_scrape, overview_data)
                        
                        # Save to PostgreSQL if selected
                        if self.save_to_postgres:
                            await self.save_to_postgres_db(overview_data)
                        
                        # Success message
                        destinations = []
                        if self.save_to_csv:
                            destinations.append("CSV")
                        if self.save_to_postgres:
                            destinations.append("PostgreSQL")
                        
                        msg = f"✅ Saved to: {', '.join(destinations)}"
                        self.log_signal.emit(msg)
                        self.finished_signal.emit(True, msg)
                    else:
                        self.log_signal.emit("❌ Failed to fetch overview data")
                        self.finished_signal.emit(False, "No data")
                else:
                    self.log_signal.emit("❌ No session ID available")
                    self.finished_signal.emit(False, "Missing session ID")

                await browser.close()

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            self.log_signal.emit(error_msg)
            self.finished_signal.emit(False, error_msg)

    async def fetch_overview_api(self, page, session_id):
        """Fetch overview data from Shopee API"""
        try:
            api_url = f"https://creator.shopee.vn/supply/api/lm/sellercenter/realtime/dashboard/overview?sessionId={session_id}"
            
            self.log_signal.emit(f"📡 Calling API for session {session_id}...")
            
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
                self.log_signal.emit("⚠️ API returned empty data")
                return None

            # Parse and return overview data
            avg_view_time_raw = data.get("avgViewTime", 0)
            avg_view_time = round(avg_view_time_raw / 60, 2) if avg_view_time_raw > 0 else 0

            overview = {
                "session_id": session_id,
                "placed_gmv": data.get("placedGmv", 0),
                "engaged_viewers": data.get("engagedViewers", 0),
                "comments": data.get("engagementData", {}).get("comments", 0),
                "atc": data.get("atc", 0),
                "views": data.get("views", 0),
                "avg_view_time": avg_view_time,
                "comments_rate": data.get("commentsRate", "0%"),
                "gpm": data.get("gpm", 0),
                "placed_order": data.get("placedOrder", 0),
                "abs": data.get("abs", 0),
                "viewers": data.get("viewers", 0),
                "pcu": data.get("pcu", 0),
                "ctr": data.get("ctr", "0%"),
                "co": data.get("co", "0%"),
                "buyers": data.get("buyers", 0),
                "placed_items_sold": data.get("placedItemsSold", 0),
                "confirmed_gmv": data.get("confirmedGmv", 0),
                "confirmed_order": data.get("confirmedOrder", 0),
                "confirmed_items_sold": data.get("confirmedItemsSold", 0),
            }

            self.log_signal.emit(f"✅ Fetched: Views={overview['views']}, PCU={overview['pcu']}, GMV={overview['placed_gmv']}")
            return overview

        except Exception as e:
            self.log_signal.emit(f"❌ Fetch error: {e}")
            return None

    async def save_to_csv_file(self, session_id, overview_data):
        """Save overview data to CSV file"""
        try:
            import csv
            from datetime import datetime
            
            # Determine CSV path
            LOCAL_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "Data All in One", "Dashboard")
            DEST_DIR = os.path.join(LOCAL_PATH, "CSV")
            os.makedirs(DEST_DIR, exist_ok=True)
            
            today_str = datetime.now().strftime("%d-%m")
            csv_path = os.path.join(DEST_DIR, f"SHP_Live_{session_id}_{today_str}.csv")
            
            # Check if file exists
            is_new = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
            
            # CSV Header (same as scraper_api.py)
            CSV_HEADER = [
                "Date", "Time", "LiveID",
                "GMV", "Người xem tương tác", "Tổng lượt bình luận", "Thêm vào giỏ hàng",
                "Tổng lượt xem", "Số lượt xem trung bình (phút)", "Tỷ lệ bình luận",
                "GPM", "Tổng đơn hàng", "Giá trị đơn hàng trung bình", "Tổng người xem",
                "PCU", "Tỷ lệ click vào sản phẩm", "Tỷ lệ click để đặt hàng", "Người mua",
                "Các mặt hàng được bán", "NMV", "Đơn hàng (Confirmed)", "Mặt hàng bán (Confirmed)"
            ]
            
            # Write to CSV
            mode = 'w' if is_new else 'a'
            with open(csv_path, mode, newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                if is_new:
                    writer.writerow(CSV_HEADER)
                
                # Write data row
                now = datetime.now()
                row = [
                    now.strftime("%Y-%m-%d"),
                    now.strftime("%H:%M:%S"),
                    session_id,
                    overview_data["placed_gmv"],
                    overview_data["engaged_viewers"],
                    overview_data["comments"],
                    overview_data["atc"],
                    overview_data["views"],
                    overview_data["avg_view_time"],
                    overview_data["comments_rate"],
                    overview_data["gpm"],
                    overview_data["placed_order"],
                    overview_data["abs"],
                    overview_data["viewers"],
                    overview_data["pcu"],
                    overview_data["ctr"],
                    overview_data["co"],
                    overview_data["buyers"],
                    overview_data["placed_items_sold"],
                    overview_data["confirmed_gmv"],
                    overview_data["confirmed_order"],
                    overview_data["confirmed_items_sold"],
                ]
                writer.writerow(row)
            
            self.log_signal.emit(f"✅ CSV saved: {csv_path}")
            
        except Exception as e:
            self.log_signal.emit(f"❌ CSV Error: {e}")

    async def save_to_postgres_db(self, overview_data):
        """Save overview data to PostgreSQL database"""
        try:
            import psycopg2
            from datetime import datetime
            
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            # Create table if not exists (FULL SCHEMA - 19 metrics)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS overview_history (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    session_title TEXT,
                    placed_gmv BIGINT DEFAULT 0,
                    engaged_viewers INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    atc INTEGER DEFAULT 0,
                    views INTEGER DEFAULT 0,
                    avg_view_time NUMERIC DEFAULT 0,
                    comments_rate TEXT DEFAULT '0%',
                    gpm BIGINT DEFAULT 0,
                    placed_order INTEGER DEFAULT 0,
                    abs INTEGER DEFAULT 0,
                    viewers INTEGER DEFAULT 0,
                    pcu INTEGER DEFAULT 0,
                    ctr TEXT DEFAULT '0%',
                    co TEXT DEFAULT '0%',
                    buyers INTEGER DEFAULT 0,
                    placed_items_sold INTEGER DEFAULT 0,
                    confirmed_gmv BIGINT DEFAULT 0,
                    confirmed_order INTEGER DEFAULT 0,
                    confirmed_items_sold INTEGER DEFAULT 0,
                    archived_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Migration: Add missing columns to existing tables
            migration_columns = [
                ('placed_gmv', 'BIGINT DEFAULT 0'),
                ('engaged_viewers', 'INTEGER DEFAULT 0'),
                ('comments', 'INTEGER DEFAULT 0'),
                ('atc', 'INTEGER DEFAULT 0'),
                ('avg_view_time', 'NUMERIC DEFAULT 0'),
                ('comments_rate', "TEXT DEFAULT '0%'"),
                ('abs', 'INTEGER DEFAULT 0'),
                ('viewers', 'INTEGER DEFAULT 0'),
                ('ctr', "TEXT DEFAULT '0%'"),
                ('co', "TEXT DEFAULT '0%'"),
                ('placed_items_sold', 'INTEGER DEFAULT 0'),
                ('confirmed_gmv', 'BIGINT DEFAULT 0'),
                ('confirmed_order', 'INTEGER DEFAULT 0'),
                ('confirmed_items_sold', 'INTEGER DEFAULT 0'),
            ]
            
            for col_name, col_def in migration_columns:
                try:
                    cursor.execute(f'''
                        ALTER TABLE overview_history 
                        ADD COLUMN IF NOT EXISTS {col_name} {col_def}
                    ''')
                except Exception:
                    pass
            
            # Insert ALL data (19 metrics)
            cursor.execute('''
                INSERT INTO overview_history (
                    session_id, session_title, placed_gmv, engaged_viewers, comments, atc,
                    views, avg_view_time, comments_rate, gpm, placed_order, abs,
                    viewers, pcu, ctr, co, buyers, placed_items_sold,
                    confirmed_gmv, confirmed_order, confirmed_items_sold, archived_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                overview_data["session_id"],
                self.session_title or f"Session {overview_data['session_id']}",
                overview_data["placed_gmv"],
                overview_data["engaged_viewers"],
                overview_data["comments"],
                overview_data["atc"],
                overview_data["views"],
                overview_data["avg_view_time"],
                overview_data["comments_rate"],
                overview_data["gpm"],
                overview_data["placed_order"],
                overview_data["abs"],
                overview_data["viewers"],
                overview_data["pcu"],
                overview_data["ctr"],
                overview_data["co"],
                overview_data["buyers"],
                overview_data["placed_items_sold"],
                overview_data["confirmed_gmv"],
                overview_data["confirmed_order"],
                overview_data["confirmed_items_sold"],
                datetime.now()
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.log_signal.emit(f"✅ PostgreSQL saved ALL 19 metrics: GMV={overview_data['placed_gmv']:,}, NMV={overview_data['confirmed_gmv']:,}, Views={overview_data['views']}, PCU={overview_data['pcu']}, Orders={overview_data['placed_order']}")
            
        except Exception as e:
            self.log_signal.emit(f"❌ PostgreSQL Error: {e}")


# =============================================================================
# Main Application - Single Unified Tab
# =============================================================================
class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shopee Livestream Scraper")
        self.resize(650, 600)

        # Main layout
        main_layout = QVBoxLayout()

        # Title
        title = QLabel("📊 Shopee Livestream Scraper")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        main_layout.addWidget(title)

        # === Account Selection ===
        account_group = QGroupBox("👤 Account Selection")
        account_layout = QVBoxLayout()

        self.account_selector = QComboBox()
        self.load_account_list()

        account_btn_layout = QHBoxLayout()
        self.add_button = QPushButton("➕ Add")
        self.edit_button = QPushButton("📝 Edit")
        self.delete_button = QPushButton("❌ Delete")
        account_btn_layout.addWidget(self.add_button)
        account_btn_layout.addWidget(self.edit_button)
        account_btn_layout.addWidget(self.delete_button)

        account_layout.addWidget(self.account_selector)
        account_layout.addLayout(account_btn_layout)
        account_group.setLayout(account_layout)
        main_layout.addWidget(account_group)

        # === Output Destinations ===
        dest_group = QGroupBox("💾 Save Destinations")
        dest_layout = QVBoxLayout()

        self.csv_checkbox = QCheckBox("📄 Save to CSV (Local)")
        self.csv_checkbox.setChecked(True)
        
        self.postgres_checkbox = QCheckBox("🗄️ Save to PostgreSQL (Database)")
        self.postgres_checkbox.setChecked(False)
        self.postgres_checkbox.toggled.connect(self.on_postgres_toggled)

        dest_layout.addWidget(self.csv_checkbox)
        dest_layout.addWidget(self.postgres_checkbox)
        dest_group.setLayout(dest_layout)
        main_layout.addWidget(dest_group)

        # === PostgreSQL Configuration (Hidden by default) ===
        self.pg_config_group = QGroupBox("🗄️ PostgreSQL Configuration")
        pg_config_layout = QVBoxLayout()

        pg_config_layout.addWidget(QLabel("Database URL:"))
        self.db_url_input = QLineEdit()
        self.db_url_input.setPlaceholderText("postgresql://user:pass@host:port/dbname")
        pg_config_layout.addWidget(self.db_url_input)

        pg_config_layout.addWidget(QLabel("Session ID:"))
        self.session_id_input = QLineEdit()
        self.session_id_input.setPlaceholderText("e.g., 31997375")
        pg_config_layout.addWidget(self.session_id_input)

        pg_config_layout.addWidget(QLabel("Session Title (Optional):"))
        self.session_title_input = QLineEdit()
        self.session_title_input.setPlaceholderText("e.g., Livestream 14.01")
        pg_config_layout.addWidget(self.session_title_input)

        self.pg_config_group.setLayout(pg_config_layout)
        self.pg_config_group.setVisible(False)  # Hidden initially
        main_layout.addWidget(self.pg_config_group)

        # === Auto-Scrape Settings ===
        auto_group = QGroupBox("⏱️ Auto-Scrape Settings")
        auto_layout = QHBoxLayout()

        auto_layout.addWidget(QLabel("Interval:"))
        self.interval_spin = QLineEdit("30")
        self.interval_spin.setMaximumWidth(60)
        auto_layout.addWidget(self.interval_spin)
        auto_layout.addWidget(QLabel("minutes"))
        auto_layout.addStretch()

        auto_group.setLayout(auto_layout)
        main_layout.addWidget(auto_group)

        # === Control Buttons ===
        btn_layout = QHBoxLayout()
        self.start_button = QPushButton("▶️ Start Auto-Scrape")
        self.start_button.setStyleSheet("background-color: #10b981; color: white; padding: 10px; font-weight: bold;")
        
        self.stop_button = QPushButton("⏸️ Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #ef4444; color: white; padding: 10px; font-weight: bold;")
        
        self.manual_button = QPushButton("🔄 Manual Scrape")
        self.manual_button.setStyleSheet("background-color: #3b82f6; color: white; padding: 10px; font-weight: bold;")

        btn_layout.addWidget(self.start_button)
        btn_layout.addWidget(self.stop_button)
        btn_layout.addWidget(self.manual_button)
        main_layout.addLayout(btn_layout)

        # === Log Output ===
        log_group = QGroupBox("📋 Activity Log")
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # === Status ===
        self.status_label = QLabel("🟢 Ready")
        self.status_label.setStyleSheet("font-weight: bold; padding: 5px;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

        # Connect signals
        self.add_button.clicked.connect(self.add_account)
        self.edit_button.clicked.connect(self.edit_account)
        self.delete_button.clicked.connect(self.delete_account)
        self.start_button.clicked.connect(self.start_auto_scrape)
        self.stop_button.clicked.connect(self.stop_auto_scrape)
        self.manual_button.clicked.connect(self.manual_scrape)

        # Scraper variables
        self.scraper_thread = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_scrape_tick)

    def on_postgres_toggled(self, checked):
        """Show/hide PostgreSQL config when checkbox is toggled"""
        self.pg_config_group.setVisible(checked)

    def load_account_list(self):
        """Load accounts from JSON file"""
        accounts = load_accounts()
        self.account_selector.clear()
        for acc in accounts:
            # Handle multiple formats: prioritize label > username > name
            if isinstance(acc, dict):
                name = acc.get("label") or acc.get("username") or acc.get("name", "Unknown")
            else:
                name = acc
            self.account_selector.addItem(name, acc)

    def add_account(self):
        """Add new account"""
        name, ok = QInputDialog.getText(self, "Add Account", "Account Name:")
        if ok and name:
            accounts = load_accounts()
            accounts.append({"name": name})
            save_accounts(accounts)
            self.load_account_list()
            QMessageBox.information(self, "Success", f"Account '{name}' added!")

    def edit_account(self):
        """Edit selected account"""
        current_idx = self.account_selector.currentIndex()
        if current_idx == -1:
            QMessageBox.warning(self, "Warning", "Please select an account first!")
            return

        accounts = load_accounts()
        old_acc = accounts[current_idx]
        if isinstance(old_acc, dict):
            old_name = old_acc.get("label") or old_acc.get("username") or old_acc.get("name", "")
        else:
            old_name = old_acc
        new_name, ok = QInputDialog.getText(self, "Edit Account", "New Name:", text=old_name)
        
        if ok and new_name:
            accounts[current_idx] = {"name": new_name}
            save_accounts(accounts)
            self.load_account_list()
            self.account_selector.setCurrentIndex(current_idx)
            QMessageBox.information(self, "Success", f"Account renamed to '{new_name}'!")

    def delete_account(self):
        """Delete selected account"""
        current_idx = self.account_selector.currentIndex()
        if current_idx == -1:
            QMessageBox.warning(self, "Warning", "Please select an account first!")
            return

        accounts = load_accounts()
        acc = accounts[current_idx]
        if isinstance(acc, dict):
            name = acc.get("label") or acc.get("username") or acc.get("name", "Unknown")
        else:
            name = acc
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete account '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            accounts.pop(current_idx)
            save_accounts(accounts)
            self.load_account_list()
            QMessageBox.information(self, "Success", f"Account '{name}' deleted!")

    def validate_inputs(self):
        """Validate inputs before scraping"""
        if self.account_selector.currentIndex() == -1:
            QMessageBox.warning(self, "Warning", "Please select an account!")
            return False

        if not self.csv_checkbox.isChecked() and not self.postgres_checkbox.isChecked():
            QMessageBox.warning(self, "Warning", "Please select at least one save destination!")
            return False

        if self.postgres_checkbox.isChecked():
            if not self.db_url_input.text().strip():
                QMessageBox.warning(self, "Warning", "Database URL is required for PostgreSQL mode!")
                return False
            if not self.session_id_input.text().strip():
                QMessageBox.warning(self, "Warning", "Session ID is required for PostgreSQL mode!")
                return False

        return True

    def start_auto_scrape(self):
        """Start auto-scraping with timer"""
        if not self.validate_inputs():
            return

        try:
            interval = int(self.interval_spin.text())
            if interval < 1:
                raise ValueError
        except:
            QMessageBox.warning(self, "Warning", "Invalid interval! Must be a positive number.")
            return

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.manual_button.setEnabled(False)
        
        self.status_label.setText("🔄 Auto-scraping active...")
        self.log_output.append(f"⏱️ Auto-scrape started (every {interval} minutes)")
        
        # Start timer
        self.timer.start(interval * 60 * 1000)  # Convert to milliseconds
        
        # Perform first scrape immediately
        self.auto_scrape_tick()

    def stop_auto_scrape(self):
        """Stop auto-scraping"""
        self.timer.stop()
        
        if self.scraper_thread and self.scraper_thread.isRunning():
            self.scraper_thread.stop()
            self.scraper_thread.wait()
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.manual_button.setEnabled(True)
        
        self.status_label.setText("🟡 Stopped")
        self.log_output.append("⏸️ Auto-scrape stopped")

    def auto_scrape_tick(self):
        """Called by timer for automatic scraping"""
        self.perform_scrape()

    def manual_scrape(self):
        """Perform single manual scrape"""
        if not self.validate_inputs():
            return
        
        self.log_output.append("🔄 Manual scrape triggered...")
        self.perform_scrape()

    def perform_scrape(self):
        """Execute scrape operation"""
        if self.scraper_thread and self.scraper_thread.isRunning():
            self.log_output.append("⚠️ Scraper already running, skipping...")
            return

        acc_data = self.account_selector.currentData()
        if isinstance(acc_data, dict):
            account_name = acc_data.get("label") or acc_data.get("username") or acc_data.get("name", "Unknown")
        else:
            account_name = acc_data
        save_csv = self.csv_checkbox.isChecked()
        save_pg = self.postgres_checkbox.isChecked()
        
        session_id = self.session_id_input.text().strip()
        session_title = self.session_title_input.text().strip()
        db_url = self.db_url_input.text().strip()

        self.status_label.setText("🔄 Scraping...")
        self.log_output.append(f"🚀 Starting scrape for '{account_name}'...")

        # Create and start unified scraper thread
        self.scraper_thread = UnifiedScraperThread(
            account_name=account_name,
            save_to_csv=save_csv,
            save_to_postgres=save_pg,
            session_id=session_id,
            session_title=session_title,
            db_url=db_url
        )
        
        self.scraper_thread.log_signal.connect(self.on_log)
        self.scraper_thread.finished_signal.connect(self.on_scrape_finished)
        self.scraper_thread.start()

    def on_log(self, message):
        """Handle log messages from scraper thread"""
        self.log_output.append(message)

    def on_scrape_finished(self, success, message):
        """Handle scrape completion"""
        if success:
            self.status_label.setText("🟢 Ready")
        else:
            self.status_label.setText("🔴 Error")
        
        self.log_output.append(f"{'✅' if success else '❌'} {message}")
        self.log_output.append("─" * 50)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())
