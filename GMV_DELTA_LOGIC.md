# GMV Delta Calculation Logic

## 🎯 Objective
Calculate **GMV đạt được** (Achieved GMV) during a host's shift by comparing the first and last GMV values within their session.

## 📊 Example Scenario

### Session Data (archived_at timeline):
```
Session ID: 31997375 | Host: Lisa Phạm | Time: 10h-14h (4 hours)

| archived_at      | placed_gmv | How it works                    |
|------------------|------------|---------------------------------|
| 10:05 (Đầu ca)   | 5,000,000  | ← GMV khi bắt đầu live        |
| 11:00            | 15,000,000 |                                 |
| 12:00            | 35,000,000 |                                 |
| 13:00            | 50,000,000 |                                 |
| 14:00 (Cuối ca)  | 62,000,000 | ← GMV khi kết thúc live       |

**Achieved GMV** = 62,000,000 - 5,000,000 = **57,000,000 VNĐ** ✅
```

This represents the **actual GMV increase** during Lisa's 4-hour shift.

---

## 🔧 SQL Implementation

### CTE: `session_metrics`
```sql
WITH session_metrics AS (
    SELECT 
        o.session_id,
        -- Last GMV (cuối ca)
        (ARRAY_AGG(o.placed_gmv ORDER BY o.archived_at DESC))[1] as last_gmv,
        -- First GMV (đầu ca)
        (ARRAY_AGG(o.placed_gmv ORDER BY o.archived_at ASC))[1] as first_gmv,
        -- Same for NMV
        (ARRAY_AGG(o.confirmed_gmv ORDER BY o.archived_at DESC))[1] as last_nmv,
        (ARRAY_AGG(o.confirmed_gmv ORDER BY o.archived_at ASC))[1] as first_nmv,
        -- Latest metrics for other fields
        (ARRAY_AGG(o.views ORDER BY o.archived_at DESC))[1] as views,
        ...
    FROM overview_history o
    WHERE 1=1 {time_condition}
    GROUP BY o.session_id
)
```

### Aggregation by Host
```sql
SELECT 
    h.host_name,
    COUNT(DISTINCT h.session_id) as total_sessions,
    SUM(COALESCE(h.duration_minutes, 0)) as total_minutes,
    
    -- Achieved GMV (Delta) = Last - First
    SUM(GREATEST(s.last_gmv - s.first_gmv, 0)) as achieved_gmv,
    SUM(GREATEST(s.last_nmv - s.first_nmv, 0)) as achieved_nmv,
    
    -- Total GMV (Last values)
    SUM(s.last_gmv) as total_gmv,
    SUM(s.last_nmv) as total_nmv,
    
    ...
FROM host_schedule h
LEFT JOIN session_metrics s ON h.session_id = s.session_id
GROUP BY h.host_name
ORDER BY achieved_gmv DESC
```

---

## 📋 New Columns

### 1. `achieved_gmv` (GMV Đạt Được)
- **Formula**: `SUM(last_gmv - first_gmv)` per host
- **Meaning**: Total GMV increase across all sessions
- **Use case**: Rank hosts by actual performance, not cumulative totals

### 2. `achieved_nmv` (NMV Đạt Được)
- **Formula**: `SUM(last_nmv - first_nmv)` per host
- **Meaning**: Total confirmed GMV increase
- **Use case**: Same as achieved_gmv but for confirmed orders

### 3. `total_gmv` (Tổng GMV Cuối Ca)
- **Formula**: `SUM(last_gmv)` per host
- **Meaning**: Sum of final GMV values from all sessions
- **Use case**: Overall contribution

### 4. `total_nmv` (Tổng NMV Cuối Ca)
- **Formula**: `SUM(last_nmv)` per host
- **Meaning**: Sum of final confirmed GMV values

---

## 🎨 Display in UI

**Table Columns (Recommended):**
| Rank | Host | Sessions | Hours | **Achieved GMV** | Total GMV | Avg Views | Avg PCU |
|------|------|----------|-------|------------------|-----------|-----------|---------|
| 🥇 #1 | Lisa Phạm | 5 | 20h | **285M** | 300M | 350K | 1,200 |
| 🥈 #2 | David Trần | 3 | 12h | **180M** | 200M | 400K | 1,500 |

**Sort Order**: `achieved_gmv DESC` (primary), `total_gmv DESC` (secondary)

---

## ✅ Why This Approach?

### Problem with Old Logic
❌ **Before**: Used only latest `archived_at` record
- Can't tell if host started with 0 or 50M
- Overvalues hosts who inherit high GMV from previous sessions

### Solution with Delta
✅ **After**: Calculate actual increase during shift
- Fair comparison across all hosts
- Measures true contribution, not just final state
- Handles session handoffs correctly

---

## 🔍 Edge Cases

### Case 1: Single Record per Session
```
If session has only 1 record:
- first_gmv = 5M
- last_gmv = 5M
- achieved_gmv = 0 ✅ (correct, no data to measure increase)
```

### Case 2: GMV Decreases (Cancelled Orders)
```
- first_gmv = 50M
- last_gmv = 45M
- achieved_gmv = GREATEST(45M - 50M, 0) = 0 ✅ (use GREATEST to prevent negative)
```

### Case 3: Multiple Sessions per Host
```
Host has 3 sessions:
- Session A: achieved = 30M
- Session B: achieved = 25M
- Session C: achieved = 40M
- Total achieved_gmv = 95M ✅
```

---

## 🚀 Deployment Impact

**Database**: No schema changes needed (uses existing columns)
**API**: Returns new columns automatically
**Frontend**: May need to add new columns to table display

**Backend changes only** - Frontend update optional!
