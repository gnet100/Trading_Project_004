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
- **Check TASKS.md before starting work - current progress and next actions**
- **Read SESSION_ARCHIVE.md - always check last session summary for context**
- **Mark completed tasks immediately**
- **Update CURRENT_STATUS.md when significant changes occur**

---

**נוצר:** 11/09/2025  
**עודכן אחרון:** 11/09/2025  
**גרסה:** 1.5 (Python Status Reviewer)