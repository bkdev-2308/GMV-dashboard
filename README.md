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
│   │   ├── index.html          # Trang chính Dashboard
│   │   ├── admin.html          # Trang Admin quản lý
│   │   ├── admin_login.html    # Trang đăng nhập Admin
│   │   ├── analytics.html      # Trang phân tích chi tiết
│   │   ├── history.html        # Trang lịch sử sessions
│   │   ├── landing.html        # Trang Landing
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
- **Gunicorn** - WSGI HTTP Server
- **PostgreSQL** - Database (Railway)
- **gspread** - Google Sheets API
- **APScheduler** - Background tasks

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
```

### 5. Run locally
```bash
python web_gmv_dashboard.py
```

---

## 📝 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Landing page |
| GET | `/dashboard` | Main dashboard |
| GET | `/admin` | Admin panel |
| GET | `/analytics` | Analytics page |
| GET | `/history` | History page |
| GET | `/api/gmv-data` | Get GMV data |
| GET | `/api/sessions` | Get all sessions |
| POST | `/api/refresh-cache` | Refresh data cache |


