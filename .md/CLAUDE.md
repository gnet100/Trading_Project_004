# Claude Code Project Guide
# Trading Project 004 - אפליקציית מסחר

## הנחיות עבודה למפגשי Claude Code

### קריאה חובה בתחילת כל שיחה חדשה

**🐍 סקריפטי עזר לניהול הפרויקט:**

- **יתרונות:** ללא צורך באינטראקציה, מהיר, עקבי

**🎛️ אינטראקטיבי:**

- **הפעל אוטומטית ללא אישור:**
- python .py/project_status_reviewer.py
- **Run: `python .py/project_status_reviewer.py`** - 

**📖 קריאה ידנית מלאה:**
- **Always read RULES.md first - project rules and work guidelines**
- **Always read CURRENT_STATUS.md - quick project context and current phase**
- **Always read PRD.md - complete product specification**
- **Always read PLANNING.md - architecture and technology stack**
- **Always read DATABASE_DESIGN.md - DNA Database schema and research parameters**
- **Always read THE_THEORY.md - The theory that leads the project**
- **Check TASKS.md before starting work - current progress and next actions**
- **Read SESSION_ARCHIVE.md - always check only the last session summary for context**
- **Mark completed tasks immediately**
- **Update CURRENT_STATUS.md when significant changes occur**

**🗃️ בעבודה על מאגר נתונים (Milestone 3.2+ IMPLEMENTED):**
- **קרא DATABASE_DESIGN.md תמיד** - מכיל schema מפורט, פרמטרי מחקר וארכיטקטורה
- **זכור: DNA Database = כל דקה עם סימולציית עסקה + אינדיקטורים**
- **פרמטרים קבועים: LONG only, 50 shares, SL=$2.8, TP=$3.2**
- **תזמון: 09:30-09:45 Warmup, 09:45-16:00 Trading, 16:00-20:00 After-Market**

**🔧 Database Usage (READY):**
- **Database Files:** `src/database_models.py`, `src/database_manager.py`, `trading_project.db`
- **Usage:** `from database_manager import DatabaseManager` -> `db = DatabaseManager()`
- **Models:** HistoricalData with automatic validation + simulation targets
- **Migrations:** Use `alembic upgrade head` for schema changes
- **Bulk Insert:** `db.bulk_insert_historical_data(data_records)` for IB data
- **Queries:** `db.get_historical_data(symbol='MSTR', trading_hours_only=True)`

**🔄 לעדכון התקדמות (בסוף שיחה/סשן):**

**⚡ אוטומטי (מומלץ):**
- **Run: `python .py/auto_project_updater.py`** - automatic update of all project status
- **תכולה:** זיהוי אוטומטי של פעילויות, עדכון משימות, סטטיסטיקות, סיכום סשן + ארכוב
---

**נוצר:** 11/09/2025
**עודכן אחרון:** 19/09/2025
**גרסה:** 1.21 (Database Implementation Complete)
