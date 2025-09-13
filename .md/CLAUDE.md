# Claude Code Project Guide
# Trading Project 004 - אפליקציית מסחר

## הנחיות עבודה למפגשי Claude Code

### קריאה חובה בתחילת כל שיחה חדשה

**🐍 סקריפטי עזר לניהול הפרויקט:**

**📊 לקבלת מצב נוכחי (בתחילת שיחה):**
- **קרא ישירות:** CURRENT_STATUS.md ו-SESSION_ARCHIVE.md לסשן האחרון

**🔄 לעדכון התקדמות (בסוף שיחה/סשן):**

**⚡ אוטומטי (מומלץ):**
- **Run: `python .py/auto_project_updater.py`** - automatic update of all project status
- **תכולה:** זיהוי אוטומטי של פעילויות, עדכון משימות, סטטיסטיקות, סיכום סשן + ארכוב
- **יתרונות:** ללא צורך באינטראקציה, מהיר, עקבי

**🎛️ אינטראקטיבי:**
- **Run: `python .py/project_progress_updater.py`** - manual update with user choices
- **תכולה:** בחירה ידנית של משימות שהושלמו, הוספת משימות חדשות, עדכון מסמכי תיעוד
- **מתי להפעיל:** כשצריך שליטה מלאה על העדכונים

**📖 קריאה ידנית מלאה:**
- **Always read RULES.md first - project rules and work guidelines**
- **Always read CURRENT_STATUS.md - quick project context and current phase**
- **Always read PRD.md - complete product specification**
- **Always read PLANNING.md - architecture and technology stack**
- **Always read DATABASE_DESIGN.md - DNA Database schema and research parameters**
- **Check TASKS.md before starting work - current progress and next actions**
- **Read SESSION_ARCHIVE.md - always check last session summary for context**
- **Mark completed tasks immediately**
- **Update CURRENT_STATUS.md when significant changes occur**

**🗃️ בעבודה על מאגר נתונים (Milestone 3+):**
- **קרא DATABASE_DESIGN.md תמיד** - מכיל schema מפורט, פרמטרי מחקר וארכיטקטורה
- **זכור: DNA Database = כל דקה עם סימולציית עסקה + אינדיקטורים**
- **פרמטרים קבועים: LONG only, 50 shares, SL=$2.8, TP=$3.2**
- **תזמון: 09:30-09:45 Warmup, 09:45-16:00 Trading, 16:00-20:00 After-Market**

---

**נוצר:** 11/09/2025
**עודכן אחרון:** 13/09/2025
**גרסה:** 1.6 (Database Design Integration)
