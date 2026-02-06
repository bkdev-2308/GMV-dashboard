# 📋 Google Sheets Template cho Host Schedule

## 🎯 Format File Import

File Google Sheets để import vào Host Performance cần có **CÁC CỘT SAU:**

### ✅ **Cột BẮT BUỘC:**

| Tên Cột | Mô Tả | Ví Dụ |
|---------|--------|--------|
| **Session ID** | Mã session của livestream | `31997375` |
| **Host** | Tên người host chính | `Lisa Phạm` |

### 📝 **Cột TÙY CHỌN (Nhưng NÊN CÓ):**

| Tên Cột | Mô Tả | Ví Dụ |
|---------|--------|--------|
| **Date** | Ngày live | `2026-02-05` hoặc `05/02/2026` |
| **Time** | **Mốc thời gian live (range)** | `10h-14h`, `19:00-22:00`, `20:30-23:30` |
| **Co-host** | Tên cohost | `Jenny Nguyễn` |

---

## 📊 **Template Mẫu:**

Tạo Google Sheets với các cột như sau:

| Session ID | Date | Time | Host | Co-host |
|-----------|------|------|------|---------|
| 31997375 | 2026-02-05 | 10h-14h | Lisa Phạm | Jenny Nguyễn |
| 31997376 | 2026-02-05 | 19:00-22:00 | David Trần | |
| 31997377 | 2026-02-06 | 20:30-23:30 | Lisa Phạm | Mike Lê |
| 31997378 | 2026-02-07 | 8h-12h | Sarah Kim | |


## ⏰ **Format Cột TIME (Mốc Thời Gian):**

Cột **Time** hỗ trợ **NHIỀU format** để biết host live bao nhiêu giờ:

### ✅ **Format 1: Giờ đơn giản (khuyến nghị)**
```
10h-14h         → Live từ 10:00 đến 14:00 (4 giờ)
8h-12h          → Live từ 8:00 đến 12:00 (4 giờ)
19h-22h         → Live từ 19:00 đến 22:00 (3 giờ)
```

### ✅ **Format 2: Giờ:Phút đầy đủ**
```
19:00-22:00     → Live từ 19:00 đến 22:00 (3 giờ)
10:30-14:00     → Live từ 10:30 đến 14:00 (3.5 giờ)
20:00-23:30     → Live từ 20:00 đến 23:30 (3.5 giờ)
```

### ✅ **Format 3: Mix (cũng được)**
```
10h-14:30       → Live từ 10:00 đến 14:30
19:30-22h       → Live từ 19:30 đến 22:00
```

### 🌙 **Live qua đêm (Overnight):**
```
22:00-02:00     → Live từ 22:00 hôm nay đến 02:00 ngày mai (4 giờ)
23h-1h          → Live từ 23:00 đến 01:00 ngày mai (2 giờ)
```

### ⚠️ **Backward Compatibility (Giờ đơn - không range):**
```
19:00           → Chỉ có giờ bắt đầu (không biết duration)
10h             → Chỉ có giờ bắt đầu
```

---

## 🔄 **Tên Cột Linh Hoạt (Code Hỗ Trợ):**

Code hiện tại **tự động nhận diện** nhiều cách đặt tên khác nhau:

### **Session ID:**
- `Session ID` ✅ (Khuyến nghị)
- `SessionID`
- `session_id`

### **Host:**
- `Host` ✅ (Khuyến nghị)
- `host`
- `host_name`

### **Co-host:**
- `Co-host` ✅ (Khuyến nghị)
- `Cohost`
- `cohost_name`

### **Date:**
- `Date` ✅ (Khuyến nghị)
- `date`
- `session_date`

### **Time:**
- `Time` ✅ (Khuyến nghị)
- `time`
- `start_time`

---

## 📌 **Lưu Ý Quan Trọng:**

### 1. **Dòng Header (Dòng 1)**
- Dòng đầu tiên **BẮT BUỘC** phải là tên cột
- Không được merge cells ở header
- Không có dòng trống trước header

### 2. **Định Dạng Dữ Liệu**

**Session ID:**
- Kiểu: Text hoặc Number
- Không được để trống
- Ví dụ: `31997375`

**Date:**
- Format khuyến nghị: `YYYY-MM-DD` (2026-02-05)
- Hoặc: `DD/MM/YYYY` (05/02/2026)
- Có thể để trống

**Time:**
- Format khuyến nghị: **Range** (VD: `10h-14h`, `19:00-22:00`)
- Hoặc đơn giản: `10h-14h` (giờ đơn giản)
- Hoặc chi tiết: `19:00-22:30` (có phút)
- Có thể để trống
- **Lợi ích**: Hệ thống tự tính duration (số giờ live)

**Host:**
- Kiểu: Text
- Không được để trống
- Ví dụ: `Lisa Phạm`

**Co-host:**
- Kiểu: Text
- Có thể để trống nếu không có

### 3. **Dữ Liệu Hợp Lệ**
- Mỗi dòng phải có **Session ID** và **Host**
- Các trường khác có thể bỏ trống
- Không có dòng trống giữa các records

---

## ✅ **Ví Dụ File Đúng:**

```
| Session ID | Date       | Time        | Host         | Co-host       |
|-----------|-----------|-------------|--------------|---------------|
| 31997375  | 2026-02-05| 10h-14h     | Lisa Phạm    | Jenny Nguyễn  |
| 31997376  | 2026-02-05| 19:00-22:00 | David Trần   |               |
| 31997377  | 2026-02-06| 20:30-23:30 | Lisa Phạm    | Mike Lê       |
| 31997378  |           | 8h-12h      | Sarah Kim    |               |
```

**Kết quả sau khi import:**
- Session 31997375: Start 10:00, End 14:00, **Duration: 240 phút (4 giờ)** ✅
- Session 31997376: Start 19:00, End 22:00, **Duration: 180 phút (3 giờ)** ✅
- Session 31997377: Start 20:30, End 23:30, **Duration: 180 phút (3 giờ)** ✅
- Session 31997378: Start 08:00, End 12:00, **Duration: 240 phút (4 giờ)** ✅

## ❌ **Ví Dụ File SAI:**

```
| SessionID | NgayLive  | Gio   | NguoiHost    |
|-----------|-----------|-------|--------------|
| 31997375  | 05-02-2026| 7pm   | Lisa         |
|           | 06-02-2026| 8pm   | David        |  ← SAI: Thiếu Session ID
```

---

## 🚀 **Cách Sử Dụng:**

1. **Tạo Google Sheets mới** hoặc edit file có sẵn
2. **Copy template** trên vào sheet
3. **Điền dữ liệu** theo format
4. **Share sheet** với email service account: `dashboard-service@...iam.gserviceaccount.com`
5. **Copy link** của Google Sheets
6. Vào **Host Performance** page → Nhập link → Click **Sync**

---

## 📥 **Template Sẵn Sàng:**

Bạn có thể copy template này:

👉 **[LINK GOOGLE SHEETS MẪU]**: https://docs.google.com/spreadsheets/d/YOUR_TEMPLATE_ID

Hoặc tự tạo theo format trên.

---

## 🔍 **Kiểm Tra Sau Khi Import:**

1. Vào `/admin/host-performance`
2. Kiểm tra số records đã sync
3. Filter theo host name
4. Xem kết quả trong bảng

---

## 💡 **Tips:**

- **Định dạng chuẩn**: Dùng `Session ID`, `Date`, `Time`, `Host`, `Co-host` cho dễ nhớ
- **Share quyền**: Đừng quên share sheet với service account
- **Test nhỏ**: Import 2-3 dòng trước để test
- **Re-import**: Mỗi lần sync sẽ **XÓA** data cũ và import lại toàn bộ
