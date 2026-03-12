# 📋 Update Log — GMV Dashboard (BeyondK)

> **Ngày cập nhật**: 12/03/2026
> **Repositories**:
> - 🔗 [GMV-dashboard](https://github.com/bkdev-2308/GMV-dashboard)
> - 🔗 [beyondk-admin](https://github.com/Ecom-AI-Agent/beyondk-admin)

---

## 🧭 Tổng quan

Đợt cập nhật này tập trung vào **2 mục tiêu chính**:

1. **Xây dựng hoàn chỉnh React Frontend** — Thay thế giao diện Jinja2/HTML cũ bằng ứng dụng React SPA hiện đại
2. **Cải thiện Backend & Tooling** — Nâng cấp business logic, bổ sung scraper API, và tài liệu kỹ thuật

---

## 📦 Commit History

| Hash | Message | Date |
|------|---------|------|
| `26da1ff` | feat: add new and update existing frontend dependencies | 2026-03-11 |
| `904afbe` | Update dashboard features and templates | 2026-02-06 |
| `21d48dc` | Update gmv_app.py — GUI application improvements | 2026-02-03 |
| `99a045c` | Update web dashboard — Add Tet theme, improve UI/UX and fix bugs | 2026-02-03 |
| `2db2f64` | Update: searchable dropdown for History page, fix session title | 2026-01-22 |
| `81e4ab2` | Initial commit — GMV Dashboard (BE + FE) | 2026-01-21 |

---

## 🚀 Files Pushed lên [beyondk-admin](https://github.com/Ecom-AI-Agent/beyondk-admin)

> Tổng: **58 files** thay đổi (so với `origin/main`)

### 🆕 React Frontend (Mới hoàn toàn)

Toàn bộ thư mục `frontend/` được thêm mới — ứng dụng React SPA dùng **Vite 7 + React 19 + TypeScript**.

#### Tech Stack Frontend
| Package | Version | Mô tả |
|---------|---------|-------|
| React | 19.2.0 | UI Library |
| TanStack Router | 1.166.7 | File-based routing |
| TanStack React Query | 5.90.21 | Server state management |
| Zustand | 5.0.11 | Client state management |
| Recharts | 3.8.0 | Chart/data visualization |
| TailwindCSS | 4.2.1 | Utility-first CSS |
| Lucide React | 0.577.0 | Icon library |
| Zod | 4.3.6 | Schema validation |
| React Hook Form | 7.71.2 | Form management |

#### Cấu trúc Frontend

```
frontend/
├── package.json, tsconfig.json, vite.config.ts, eslint.config.js
├── index.html
├── public/static/
│   ├── BK_logo.ico
│   └── logo.ico
└── src/
    ├── App.tsx                          # Root component
    ├── main.tsx                         # Entry point
    ├── router.tsx                       # TanStack Router config
    ├── styles/index.css                 # Global styles
    │
    ├── components/
    │   ├── dashboard/
    │   │   ├── CategoryChart.tsx        # Biểu đồ phân bố danh mục
    │   │   ├── OverviewMetrics.tsx      # Thẻ tổng quan (GMV, Clicks, ATC, Orders)
    │   │   ├── ProductTable.tsx         # Bảng sản phẩm (GIÁ LIVE, GIẢM STOCK, Pinned)
    │   │   └── RevenueChart.tsx         # Biểu đồ doanh thu
    │   └── ui/
    │       ├── RankBadge.tsx            # Badge xếp hạng sản phẩm
    │       ├── SessionFilter.tsx        # Dropdown lọc session
    │       ├── Spinner.tsx              # Loading spinner
    │       ├── StatCard.tsx             # Card hiển thị số liệu
    │       ├── Toast.tsx                # Toast notification
    │       └── ToastContainer.tsx       # Toast container
    │
    ├── layouts/
    │   ├── AppLayout.tsx                # Layout chính (sidebar + content)
    │   ├── MobileHeader.tsx             # Header cho mobile
    │   └── Sidebar.tsx                  # Sidebar navigation
    │
    ├── pages/
    │   ├── AdminLoginPage.tsx           # Trang login admin
    │   ├── AnalyticsPage.tsx            # Trang phân tích dữ liệu
    │   ├── BrandPage.tsx                # Trang quản lý brand
    │   ├── DashboardPage.tsx            # Trang dashboard chính
    │   ├── FixHistoryPage.tsx           # Trang sửa lịch sử
    │   ├── HistoryPage.tsx              # Trang xem lịch sử
    │   ├── HostPerformancePage.tsx      # Trang hiệu suất host
    │   ├── LandingPage.tsx              # Landing page
    │   ├── LoginPage.tsx                # Trang đăng nhập Google OAuth
    │   ├── SettingsPage.tsx             # Trang cài đặt
    │   └── StaffPage.tsx                # Trang staff (view-only)
    │
    ├── services/
    │   ├── api.ts                       # Axios/fetch base config
    │   ├── analytics.service.ts         # API calls cho analytics
    │   ├── auth.service.ts              # API calls cho authentication
    │   └── session.service.ts           # API calls cho session management
    │
    ├── store/
    │   ├── auth.store.ts                # Zustand store — auth state
    │   ├── session.store.ts             # Zustand store — session state
    │   └── toast.store.ts               # Zustand store — toast notifications
    │
    ├── config/
    │   └── api.ts                       # API endpoint config
    │
    ├── types/
    │   └── index.ts                     # TypeScript type definitions
    │
    └── utils/
        ├── clipboard.ts                 # Clipboard helper
        ├── cn.ts                        # classNames utility (clsx + tailwind-merge)
        └── format.ts                    # Number/date formatting
```

#### Modified Backend Files

| Status | File | Mô tả |
|--------|------|-------|
| ✏️ Modified | `gmv_app.py` | Cập nhật business logic, GUI improvements |
| ✏️ Modified | `web_gmv_dashboard.py` | Cập nhật Flask routes, API endpoints |
| ✏️ Modified | `.gitignore` | Thêm rules cho frontend build |
| 🆕 Added | `hello.py` | Test/utility script |
| 🆕 Added | `.python-version` | Python version lock |

---

## 🔧 Files Pushed lên [GMV-dashboard](https://github.com/bkdev-2308/GMV-dashboard)

> Tổng: **82 files** thay đổi (so với `gmv-dashboard/main`)
> Bao gồm tất cả files của beyondk-admin + các files bổ sung sau:

### 🆕 Files bổ sung (chỉ có trên GMV-dashboard)

#### Backend & Scripts
| Status | File | Mô tả |
|--------|------|-------|
| 🆕 Added | `scraper_api.py` | Shopee scraper API module |
| 🆕 Added | `scraper_chup_va_ghi3.py` | Screenshot & recording scraper |
| 🆕 Added | `full_gmv_api.py` | Full GMV data API handler |
| 🆕 Added | `python_app_gui2.py` | Python GUI application v2 |
| 🆕 Added | `web_local_dev.py` | Local development server script |
| 🆕 Added | `check_gmv_column.py` | Utility: kiểm tra cột GMV |
| 🆕 Added | `convert_to_base64.py` | Utility: convert file sang base64 |
| 🆕 Added | `base64_output.txt` | Output file từ base64 converter |
| ✏️ Modified | `requirements.txt` | Cập nhật Python dependencies |

#### Documentation
| Status | File | Mô tả |
|--------|------|-------|
| ✏️ Modified | `README.md` | Cập nhật tài liệu project |
| 🆕 Added | `GMV_DELTA_LOGIC.md` | Tài liệu logic tính Delta GMV |
| 🆕 Added | `GOOGLE_SHEETS_TEMPLATE.md` | Template hướng dẫn Google Sheets |

#### Templates (HTML/Jinja2)
| Status | File | Mô tả |
|--------|------|-------|
| ✏️ Modified | `templates/admin.html` | Cập nhật giao diện admin |
| ✏️ Modified | `templates/analytics.html` | Cập nhật trang analytics |
| ✏️ Modified | `templates/history.html` | Cập nhật trang history |
| ✏️ Modified | `templates/index.html` | Cập nhật trang chính |
| ✏️ Modified | `templates/login.html` | Cập nhật trang login |
| 🆕 Added | `templates/brand.html` | Trang brand (mới) |
| 🆕 Added | `templates/host_performance.html` | Trang host performance (mới) |

#### Assets
| Status | File | Mô tả |
|--------|------|-------|
| 🆕 Added | `logo/BK_logo.ico` | BeyondK logo icon |
| 🆕 Added | `logo/beyondk-wordmark-black.png` | BeyondK wordmark logo |
| 🆕 Added | `logo/s (3).webp` | Shopee logo asset |
| 🆕 Added | `logo/z7476504935199_*.jpg` | Additional logo asset |
| 🆕 Added | `BK - LỊCH HOST.xlsx` | Lịch host livestream |

---

## 🔄 So sánh 2 Repository

| Nội dung | beyondk-admin | GMV-dashboard |
|----------|:---:|:---:|
| React Frontend | ✅ | ✅ |
| Backend core (`gmv_app.py`, `web_gmv_dashboard.py`) | ✅ | ✅ |
| Scraper scripts | ❌ | ✅ |
| GUI apps (`python_app_gui2.py`) | ❌ | ✅ |
| HTML Templates (Jinja2) | ❌ | ✅ |
| GMV Delta Logic docs | ❌ | ✅ |
| Google Sheets Template docs | ❌ | ✅ |
| Logo & assets | ❌ | ✅ |
| Total files changed | 58 | 82 |

> **Lưu ý**: `beyondk-admin` chỉ chứa source code chính (frontend + backend core), trong khi `GMV-dashboard` chứa đầy đủ bao gồm scripts, templates, docs, và assets.

---

## 🏗️ Kiến trúc mới

```
┌──────────────────────────────────────────────────┐
│                  React Frontend                  │
│  (Vite + React 19 + TanStack Router + Zustand)   │
│                                                  │
│  Pages: Dashboard, Analytics, History, Settings  │
│         Brand, Staff, HostPerformance, FixHistory│
│  Charts: Recharts (CategoryChart, RevenueChart)  │
│  State: Zustand (auth, session, toast)           │
└──────────────────┬───────────────────────────────┘
                   │ REST API
┌──────────────────▼───────────────────────────────┐
│                Flask Backend                     │
│         (web_gmv_dashboard.py)                   │
│                                                  │
│  Auth: Google OAuth + Admin Password             │
│  Data: PostgreSQL + Google Sheets API            │
│  Jobs: APScheduler (hourly archive)              │
└──────────────────┬───────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
   PostgreSQL           Shopee API
  (gmv_data,          (Cookie-based
   gmv_history,        scraping)
   user_shop_mapping)
```

---

## 📞 Contact

**BeyondK Tech Team** 🚀
