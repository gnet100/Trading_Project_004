# DATABASE_DESIGN.md
# Trading Project 004 - תכנון מפורט מאגר הנתונים

---

## 🎯 סקירה כללית

**מטרה:** יצירת מאגר "DNA" של תנועות מחיר המאפשר מחקר סטטיסטי מעמיק לחיזוי רווחיות עסקאות

**גישה:** כל דקת מסחר = נקודת החלטה פוטנציאלית עם סימולציית עסקה וחישוב תוצאות

---

## 📊 ארכיטקטורת מאגר הנתונים

### Phase 1: Historical Data Foundation (Milestone 3)

#### טבלה ראשית: `historical_data`

```sql
CREATE TABLE historical_data (
    -- מזהים ראשיים
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol              VARCHAR(10) DEFAULT 'MSTR',
    date                DATE NOT NULL,
    time                TIME NOT NULL,
    timestamp           DATETIME NOT NULL UNIQUE,

    -- נתוני OHLCV מ-Interactive Brokers
    open_price          DECIMAL(10,4) NOT NULL,
    high_price          DECIMAL(10,4) NOT NULL,
    low_price           DECIMAL(10,4) NOT NULL,
    close_price         DECIMAL(10,4) NOT NULL,
    volume              BIGINT NOT NULL DEFAULT 0,

    -- Metadata איכות נתונים
    timeframe           VARCHAR(10) NOT NULL DEFAULT '1min',
    data_quality_score  DECIMAL(4,2) NOT NULL DEFAULT 100.00,
    is_trading_hours    BOOLEAN NOT NULL DEFAULT FALSE,
    is_warmup_period    BOOLEAN NOT NULL DEFAULT FALSE,

    -- אינדקסים לביצועים
    INDEX idx_symbol_datetime (symbol, timestamp),
    INDEX idx_date (date),
    INDEX idx_trading_hours (is_trading_hours),
    INDEX idx_symbol_date (symbol, date),
    INDEX idx_quality (data_quality_score)
);
```

---

## ⏰ תזמון איסוף נתונים

### שעות פעילות (EST)

| תקופה | שעות | תיאור | פעולות |
|--------|------|--------|---------|
| Warmup | 09:30-09:45 | 15 דקות ראשונות | איסוף נתונים בלבד, `is_warmup_period=TRUE` |
| Trading | 09:45-16:00 | שעות מסחר פעילות | איסוף + סימולציית עסקאות, `is_trading_hours=TRUE` |
| After-Market | 16:00-20:00 | מסחר לאחר שעות | מעקב עסקאות פתוחות |
| Force Close | 19:30 | 30 דקות לפני סגירה | סגירת עסקאות שנותרו פתוחות |

---

## 💼 פרמטרי סימולציית מסחר

### הגדרות עסקה בסיסיות
```yaml
trading_parameters:
  direction: LONG_ONLY
  quantity: 50 shares
  stop_loss: entry_price - $2.8
  take_profit: entry_price + $3.2
  max_concurrent: unlimited

entry_logic:
  price: open_price של הדקה
  timing: כל דקה בשעות 09:45-16:00

exit_logic:
  trigger: High >= TP OR Low <= SL
  price: open_price של הדקה הבאה לאחר הטריגר
  forced_close: 30 דקות לפני סוף After-Market
```

---

## 🔄 Phase 2: Technical Indicators (עתידי)

### מבנה גמיש לאינדיקטורים

**אופציה A: עמודות דינמיות**
```sql
-- הוספה בהדרגה
ALTER TABLE historical_data ADD COLUMN rsi_14 DECIMAL(6,2);
ALTER TABLE historical_data ADD COLUMN sma_20 DECIMAL(10,4);
ALTER TABLE historical_data ADD COLUMN bollinger_upper DECIMAL(10,4);
ALTER TABLE historical_data ADD COLUMN bollinger_middle DECIMAL(10,4);
ALTER TABLE historical_data ADD COLUMN bollinger_lower DECIMAL(10,4);
ALTER TABLE historical_data ADD COLUMN macd_line DECIMAL(8,4);
ALTER TABLE historical_data ADD COLUMN macd_signal DECIMAL(8,4);
ALTER TABLE historical_data ADD COLUMN atr_14 DECIMAL(8,4);
```

**אופציה B: טבלה נפרדת**
```sql
CREATE TABLE indicators_data (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    historical_id       BIGINT NOT NULL,
    indicator_name      VARCHAR(50) NOT NULL,
    indicator_value     DECIMAL(12,6) NOT NULL,
    calculation_params  JSON,

    FOREIGN KEY (historical_id) REFERENCES historical_data(id),
    INDEX idx_hist_indicator (historical_id, indicator_name),
    INDEX idx_indicator_name (indicator_name)
);
```

### רשימת אינדיקטורים מתוכננים

```yaml
indicators_library:
  moving_averages:
    - sma_10, sma_20, sma_50, sma_200
    - ema_12, ema_26, ema_50

  momentum:
    - rsi_14, rsi_21
    - macd_line, macd_signal, macd_histogram
    - stoch_k, stoch_d
    - williams_r

  volatility:
    - bollinger_upper, bollinger_middle, bollinger_lower, bollinger_width
    - atr_14, atr_21

  volume:
    - volume_sma_20
    - on_balance_volume
```

---

## 📈 Phase 3: Trading Simulation (מחקר)

### הרחבת הטבלה לסימולציה

```sql
-- עמודות סימולציית מסחר
ALTER TABLE historical_data ADD COLUMN trade_num BIGINT;
ALTER TABLE historical_data ADD COLUMN entry_price DECIMAL(10,4);
ALTER TABLE historical_data ADD COLUMN stop_loss_price DECIMAL(10,4);
ALTER TABLE historical_data ADD COLUMN take_profit_price DECIMAL(10,4);
ALTER TABLE historical_data ADD COLUMN exit_price DECIMAL(10,4);
ALTER TABLE historical_data ADD COLUMN exit_timestamp DATETIME;
ALTER TABLE historical_data ADD COLUMN pnl DECIMAL(10,2);
ALTER TABLE historical_data ADD COLUMN exit_reason VARCHAR(30);
ALTER TABLE historical_data ADD COLUMN trade_success BOOLEAN;
ALTER TABLE historical_data ADD COLUMN bars_to_exit INTEGER;
ALTER TABLE historical_data ADD COLUMN concurrent_trades INTEGER;

-- אינדקסים נוספים
ALTER TABLE historical_data ADD INDEX idx_trade_num (trade_num);
ALTER TABLE historical_data ADD INDEX idx_pnl (pnl);
ALTER TABLE historical_data ADD INDEX idx_exit_reason (exit_reason);
```

### חישובי P&L

```python
# דוגמה לחישוב רווח/הפסד
def calculate_pnl(entry_price: float, exit_price: float, shares: int = 50) -> float:
    """
    חישוב רווח/הפסד עבור עסקת LONG

    Args:
        entry_price: מחיר כניסה
        exit_price: מחיר יציאה בפועל (open של בר שלאחר טריגר)
        shares: כמות מניות (ברירת מחדל: 50)

    Returns:
        float: רווח/הפסד בדולרים
    """
    return (exit_price - entry_price) * shares

# דוגמאות:
# Entry: $100, Exit: $103.15 (TP triggered) → PnL = $157.50
# Entry: $100, Exit: $97.85 (SL triggered) → PnL = -$107.50
# Entry: $100, Exit: $96.50 (SL gap down) → PnL = -$175.00
```

---

## 🔧 מערכת איכות נתונים

### בדיקות איכות אוטומטיות

```sql
-- View לבדיקת איכות נתונים
CREATE VIEW data_quality_check AS
SELECT
    date,
    COUNT(*) as total_bars,
    COUNT(CASE WHEN high_price < low_price THEN 1 END) as invalid_hl,
    COUNT(CASE WHEN open_price < 0 THEN 1 END) as invalid_prices,
    COUNT(CASE WHEN volume < 0 THEN 1 END) as invalid_volume,
    AVG(data_quality_score) as avg_quality_score,
    COUNT(CASE WHEN data_quality_score < 95.0 THEN 1 END) as low_quality_bars
FROM historical_data
WHERE is_trading_hours = TRUE
GROUP BY date
ORDER BY date DESC;
```

### מעקב פערים בנתונים

```sql
-- זיהוי דקות חסרות בשעות מסחר
CREATE VIEW missing_minutes AS
WITH expected_minutes AS (
    SELECT
        date,
        TIMESTAMPADD(MINUTE, n, TIMESTAMP(date, '09:30:00')) as expected_time
    FROM historical_data hd
    CROSS JOIN (
        SELECT n FROM (
            SELECT 0 as n UNION SELECT 1 UNION SELECT 2 UNION ... UNION SELECT 389
        ) numbers
    ) minutes
    WHERE n <= 389 -- 390 דקות = 6.5 שעות מסחר
)
SELECT
    em.date,
    em.expected_time,
    'MISSING' as status
FROM expected_minutes em
LEFT JOIN historical_data hd ON hd.timestamp = em.expected_time
WHERE hd.id IS NULL
ORDER BY em.date DESC, em.expected_time;
```

---

## 📋 דוגמת מבנה נתונים

### רשומה טיפוסית

```json
{
  "id": 123456,
  "symbol": "MSTR",
  "date": "2025-01-15",
  "time": "10:30:00",
  "timestamp": "2025-01-15 10:30:00",
  "open_price": 100.25,
  "high_price": 100.85,
  "low_price": 99.95,
  "close_price": 100.60,
  "volume": 15750,
  "timeframe": "1min",
  "data_quality_score": 100.0,
  "is_trading_hours": true,
  "is_warmup_period": false,

  // Phase 2 (עתידי)
  "rsi_14": 65.4,
  "sma_20": 99.8,
  "bollinger_upper": 102.5,

  // Phase 3 (מחקר)
  "trade_num": 789012,
  "entry_price": 100.25,
  "stop_loss_price": 97.45,
  "take_profit_price": 103.45,
  "exit_price": 103.15,
  "pnl": 145.0,
  "exit_reason": "TAKE_PROFIT",
  "trade_success": true,
  "bars_to_exit": 12
}
```

---

## 🚀 יעדי ביצועים

### מדדי הצלחה

| מדד | יעד | הערות |
|-----|-----|-------|
| איכות נתונים | 99.95%+ | validation score ממוצע |
| כיסוי נתונים | 99%+ | אחוז דקות ללא פערים |
| זמן שאילתה | <100ms | לשאילתת יום מסחר |
| גודל מאגר | 3M+ records | 2 שנים של נתונים |
| זמינות | 99.9% | uptime של המערכת |

### אופטימיזציות ביצועים

```sql
-- Partitioning לפי תאריך (MySQL 8.0+)
ALTER TABLE historical_data
PARTITION BY RANGE (YEAR(date)) (
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026)
);

-- אינדקס מורכב לשאילתות מחקר
CREATE INDEX idx_research_queries
ON historical_data (symbol, date, is_trading_hours, data_quality_score);
```

---

## 🔄 תהליכי Backup & Recovery

### אסטרטגיית גיבוי

```bash
# גיבוי יומי
mysqldump --single-transaction --routines --triggers \
  trading_project historical_data > backup_$(date +%Y%m%d).sql

# דחיסה וארכוב
gzip backup_$(date +%Y%m%d).sql
mv backup_$(date +%Y%m%d).sql.gz /backups/daily/

# גיבוי שבועי מלא
mysqldump --single-transaction --all-databases > full_backup_$(date +%Y%m%d).sql
```

### תרחיש שחזור

1. זיהוי בעיה
2. עצירת כתיבה למאגר
3. שחזור מגיבוי עדכני
4. אימות שלמות נתונים
5. חידוש פעילות

---

## 📝 הערות טכניות

### בחירת טכנולוגיה

**SQLite (פיתוח):**
- מהירות התחלה
- אפס תצורה
- מושלם לפיתוח ובדיקות

**PostgreSQL (ייצור):**
- ביצועים גבוהים עם נתונים גדולים
- תמיכה מתקדמת ב-JSON
- כלי ניהול מתקדמים

### Migration Path

```python
# כלי להעברה מ-SQLite ל-PostgreSQL
def migrate_sqlite_to_postgres():
    """
    העברת נתונים מ-SQLite לפיתוח ל-PostgreSQL לייצור
    """
    pass
```

---

**נוצר:** 13/09/2025
**גרסה:** 1.0
**מעודכן אחרון:** 13/09/2025
**סטטוס:** מסמך טכני מפורט למילסטון 3
