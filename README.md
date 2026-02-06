# GMV Dashboard - BeyondK

Dashboard quản lý và theo dõi GMV (Gross Merchandise Value) cho Shopee Affiliate.
---

## Cấu trúc Project

```
dashboard_dev/
│
├── BACKEND (Python/Flask)
│   ├── web_gmv_dashboard.py    # Main Flask app (Entry point)
│   ├── db_helpers.py           # Database helper functions
│   └── gmv_app.py              # GMV business logic
│
├── FRONTEND
│   ├── templates/              # HTML Templates (Jinja2)
│   │   ├── index.html          # Admin Dashboard (GMV tracking)
│   │   ├── staff.html          # Staff Dashboard (view-only)
│   │   ├── login.html          # Google OAuth login
│   │   ├── admin_login.html    # Admin password login
│   │   ├── landing.html        # Landing page
│   │   ├── history.html        # Historical data viewer
│   │   ├── settings.html       # Admin-only settings
│   │   └── partials/
│   │       └── _sidebar.html   # Sidebar component
│   │
│   └── static/                 # Static assets
│       ├── css/
│       │   └── dashboard-all.css   # Main stylesheet
│       ├── js/
│       │   ├── session.js      # Session handling
│       │   └── utils.js        # Utility functions
│       └── *.ico               # Logo icons
│
├── CONFIG
│   ├── Procfile                # Railway/Gunicorn config
│   ├── requirements.txt        # Python dependencies
│   └── .gitignore              # Git ignore rules
│
└── README.md                # This file
```

---

## Tech Stack

### Backend
- **Python 3.11+**
- **Flask** - Web framework
- **Flask-Session** - Session management
- **Gunicorn** - WSGI HTTP Server
- **PostgreSQL** - Database (Railway)
- **gspread** - Google Sheets API
- **APScheduler** - Background tasks & data archiving
- **Google OAuth 2.0** - Authentication
- **Requests** - Shopee API integration

### Frontend
- **HTML5 / CSS3 / JavaScript**
- **Jinja2** - Template engine
- **Chart.js** - Data visualization
- **Vanilla CSS** - Custom styling (Dark theme)

---

## Installation

### 1. Clone repository
```bash
git clone https://github.com/Ecom-AI-Agent/beyondk-admin.git
cd beyondk-admin
```

### 2. Create virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set environment variables
```bash
# Required for Railway deployment
DATABASE_URL=postgresql://...
GOOGLE_CREDENTIALS_BASE64=...
ADMIN_PASSWORD=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SESSION_SECRET_KEY=...
```

### 5. Run locally
```bash
python web_gmv_dashboard.py
```

---

## � Authentication & Roles

### User Types
1. **BOD (Admin)** - Full access to all features
   - Google OAuth login with `bod` role
   - Password-based admin login
   - Access to `/admin/setting` (Shopee scraper config)

2. **Brand Users** - Filtered data access
   - Google OAuth login
   - View only their brand's shop data
   - Access to staff dashboard

3. **Staff** - Limited view access
   - Email-based access control
   - Read-only dashboard

---

## �📝 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Landing page |
| GET | `/login` | Google OAuth login |
| GET | `/admin/login` | Admin password login |
| GET | `/auth/callback` | OAuth callback handler |
| GET | `/logout` | Logout session |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard` | Admin dashboard (GMV tracking) |
| GET | `/staff` | Staff dashboard (view-only) |
| GET | `/history` | Historical data viewer |
| GET | `/admin/setting` | Admin settings & scraper |

### API Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/gmv-data` | Get GMV data (filtered by role) |
| GET | `/api/sessions` | Get all sessions |
| GET | `/api/timeslots` | Get timeslots for session |
| GET | `/api/analytics/top-products` | Top 10 products by metric |
| GET | `/api/analytics/category-distribution` | Category breakdown |
| POST | `/api/refresh-cache` | Refresh data cache |
| POST | `/api/scrape` | Trigger Shopee data scraping |
| POST | `/api/upload-cookie` | Upload Shopee auth cookie |
| POST | `/api/delete-cookie` | Delete stored cookie |

---

## ✨ Key Features

### 🎯 Dashboard Features
- **Real-time GMV Tracking** - Live session monitoring with auto-refresh
- **Multi-Session Support** - Track multiple livestream sessions simultaneously
- **Timeslot Filtering** - Filter data by specific time ranges within sessions
- **Interactive Charts** - Top 10 products & category distribution (Chart.js)
- **Column Sorting** - Sort by GMV, Clicks, ATC, Orders
- **Search & Filter** - Product name, Shop ID, Brand name search
- **Data Export** - Export filtered data to Excel

### 🔐 Access Control
- **Google OAuth Integration** - Secure brand authentication
- **Role-Based Access** - BOD, Brand, Staff permissions
- **Shop-Level Filtering** - Brands see only their shop data
- **Session Management** - Secure cookie-based sessions

### 📊 Data Management
- **Shopee API Integration** - Cookie-based authentication (no browser needed)
- **Google Sheets Sync** - Automatic deal list import
- **PostgreSQL Storage** - Efficient data persistence
- **Auto-Archive System** - Hourly data archiving to `gmv_history`
- **Data Deduplication** - Prevent duplicate entries

### ⚙️ Admin Tools
- **Settings Page** - Shopee scraper configuration
- **Cookie Management** - Upload/delete Shopee authentication cookies
- **Manual Scraping** - Trigger on-demand data collection
- **Session Control** - Add/remove sessions via Google Sheets URLs

---

## 🗄️ Database Schema

### `gmv_data` (Live Sessions)
```sql
CREATE TABLE gmv_data (
    id SERIAL PRIMARY KEY,
    session_id TEXT,
    timeslot TEXT,
    shop_id TEXT,
    shop_name TEXT,
    brand_name TEXT,
    item_id TEXT,
    product_name TEXT,
    category TEXT,
    gmv NUMERIC DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    atc INTEGER DEFAULT 0,
    orders INTEGER DEFAULT 0,
    nmv NUMERIC DEFAULT 0,
    affiliate_link TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `gmv_history` (Archived Data)
- Same structure as `gmv_data`
- Stores historical session data
- Populated hourly by APScheduler

### `user_shop_mapping` (Access Control)
```sql
CREATE TABLE user_shop_mapping (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    shop_id TEXT,
    brand_name TEXT,
    role TEXT  -- 'bod', 'brand', 'staff'
);
```

---

## 🔄 Data Flow

```
Google Sheets (Deal List)
         ↓
    gspread API
         ↓
   PostgreSQL (gmv_data) ←─── Shopee API (Cookie-based)
         ↓                          ↑
   APScheduler Archive      Admin Settings Upload
         ↓
   PostgreSQL (gmv_history)
         ↓
   Flask API (/api/gmv-data)
         ↓
   Dashboard (Chart.js + Vanilla JS)
```

### Data Update Flow
1. **Admin** uploads session Google Sheets URL + Shopee cookie
2. **Scraper** fetches data from Shopee API using cookie authentication
3. **Data** saved to PostgreSQL `gmv_data` table
4. **Dashboard** displays real-time data via `/api/gmv-data`
5. **APScheduler** archives data to `gmv_history` every hour
6. **History Page** displays archived sessions

---

## 🚀 Deployment

### Railway Deployment
1. Connect GitHub repository to Railway
2. Set environment variables in Railway dashboard:
   ```
   DATABASE_URL (auto-provided by Railway PostgreSQL)
   GOOGLE_CREDENTIALS_BASE64
   ADMIN_PASSWORD
   GOOGLE_CLIENT_ID
   GOOGLE_CLIENT_SECRET
   SESSION_SECRET_KEY
   ```
3. Railway automatically detects `Procfile` and deploys with Gunicorn

### Production URL
- **Live**: `https://gmv-dashboard-production.up.railway.app`
- **Admin**: `https://gmv-dashboard-production.up.railway.app/admin/login`

---

## 🛠️ Development

### Local Development
```bash
# Activate virtual environment
.venv\Scripts\activate

# Run Flask development server
python web_gmv_dashboard.py

# Access locally
http://localhost:5000
```

### File Structure Tips
- **Templates**: Keep Jinja2 HTML in `templates/`
- **Static Assets**: CSS/JS in `static/`
- **Database Logic**: Use `db_helpers.py` for all PostgreSQL operations
- **Business Logic**: GMV calculations in `gmv_app.py`
- **API Routes**: All routes defined in `web_gmv_dashboard.py`

---

## 📌 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection URL | ✅ |
| `GOOGLE_CREDENTIALS_BASE64` | Google Sheets API credentials (base64) | ✅ |
| `ADMIN_PASSWORD` | Admin panel password | ✅ |
| `GOOGLE_CLIENT_ID` | OAuth 2.0 client ID | ✅ |
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 client secret | ✅ |
| `SESSION_SECRET_KEY` | Flask session encryption key | ✅ |

---

## 📝 Notes

- **Tet Header**: Special Lunar New Year themed header in `static/tet_header.css`
- **Time Zone**: All timestamps use Vietnam timezone (UTC+7)
- **Data Retention**: Live sessions archived hourly, historical data retained indefinitely
- **Performance**: PostgreSQL indexes on `item_id`, `session_id`, `shop_id` for faster queries

---

## 🤝 Contributing

1. Create feature branch from `main`
2. Test locally before pushing
3. Update README if adding new features
4. Push to GitHub triggers automatic Railway deployment

---

## 📞 Support

For issues or questions, contact: **BeyondK Tech Team** 🚀

