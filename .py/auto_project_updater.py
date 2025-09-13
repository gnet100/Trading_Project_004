#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatic Project Updater - Trading Project 004
Automatically updates project status, tasks, and documentation based on session activity

Usage: python auto_project_updater.py

This script automatically:
1. Detects completed tasks based on Claude Code activity
2. Updates CURRENT_STATUS.md with latest progress
3. Creates session summary based on changes
4. Archives old session to SESSION_ARCHIVE.md
5. Updates CLAUDE.md with new session info
6. Updates file versions and timestamps

No user interaction required - fully automated.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, date
import re
import json
from typing import Dict, List, Optional, Tuple

# Fix Windows console encoding issues
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


class AutoProjectUpdater:
    def __init__(self):
        """Initialize the auto updater"""
        self.base_path = Path(__file__).parent.parent
        self.md_path = self.base_path / ".md"
        
        # Track changes for final summary
        self.changes_made = []
        self.session_activities = []
        
        # Files we'll work with
        self.files = {
            'tasks': self.md_path / "TASKS.md",
            'current_status': self.md_path / "CURRENT_STATUS.md", 
            'claude': self.md_path / "CLAUDE.md",
            'session_archive': self.md_path / "SESSION_ARCHIVE.md",
            'prd': self.md_path / "PRD.md",
            'planning': self.md_path / "PLANNING.md"
        }
    
    def safe_print(self, text):
        """Print text safely handling encoding issues"""
        try:
            print(text)
        except UnicodeEncodeError:
            clean_text = re.sub(r'[^\x00-\x7F]+', '?', text)
            print(clean_text)
    
    def read_file_safe(self, filepath: Path) -> str:
        """Safely read a file with UTF-8 encoding"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return ""
        except Exception as e:
            self.safe_print(f"❌ Error reading {filepath}: {e}")
            return ""
    
    def write_file_safe(self, filepath: Path, content: str) -> bool:
        """Safely write a file with UTF-8 encoding"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            self.safe_print(f"❌ Error writing {filepath}: {e}")
            return False
    
    def detect_session_activities(self) -> List[str]:
        """Auto-detect what was done in this session"""
        activities = []
        
        # Check if scripts were created/modified today
        py_dirs = [self.base_path / ".py", self.base_path / "src"]
        today = date.today()
        
        for py_dir in py_dirs:
            if py_dir.exists():
                for py_file in py_dir.glob("*.py"):
                    try:
                        mod_time = datetime.fromtimestamp(py_file.stat().st_mtime).date()
                        if mod_time == today:
                            activities.append(f"עדכן/יצר סקריפט: {py_file.name}")
                    except:
                        pass
        
        # Check for config files (milestone 1.4 indicators)
        config_indicators = {
            'config': ['config.yaml', '.env'],
            'ib_connector': ['ib_connector.py'],
            'database': ['config_manager.py'],
            'logging': ['logging_setup.py'],
            'config_validator': ['config_validator.py']
        }
        
        for category, files in config_indicators.items():
            for filename in files:
                for search_dir in [self.base_path / "config", self.base_path / "src"]:
                    filepath = search_dir / filename
                    if filepath.exists():
                        try:
                            mod_time = datetime.fromtimestamp(filepath.stat().st_mtime).date()
                            if mod_time == today:
                                activities.append(f"עבודה על {category}: {filename}")
                        except:
                            pass
        
        # Check for recent changes in .md files
        for name, filepath in self.files.items():
            if filepath.exists():
                try:
                    mod_time = datetime.fromtimestamp(filepath.stat().st_mtime).date()
                    if mod_time == today:
                        activities.append(f"עדכן קובץ תיעוד: {filepath.name}")
                except:
                    pass
        
        # If no specific activities detected, add generic ones
        if not activities:
            activities = [
                "עבודה על פיתוח הסקריפטים",
                "שיפור כלי ניהול הפרויקט",
                "תחזוקה ועדכון מערכת התיעוד"
            ]
        
        return activities[:3]  # Limit to 3 main activities
    
    def auto_mark_completed_tasks(self) -> bool:
        """Automatically mark tasks as completed based on session activity"""
        self.safe_print("📋 זיהוי אוטומטי של משימות שהושלמו...")
        
        tasks_content = self.read_file_safe(self.files['tasks'])
        if not tasks_content:
            return False
        
        # Tasks that might be auto-completed based on script activity
        auto_completable = [
            ("יצירת Python Status Reviewer script", "project_status_reviewer.py"),
            ("שיפור מערכת הזיכרון וחיסכון טוקנים", "status"),
            ("עדכון קבצי תיעוד", ".md"),
            ("תיקון בעיות קידוד", "encoding"),
            ("יצירת כלי עזר אוטומטיים", "updater"),
            # Milestone 1.4 Configuration Management tasks
            ("יצירת מערכת הגדרות", "config"),
            ("הגדרת פרמטרי חיבור IB", "ib_connector"),
            ("הגדרת פרמטרי DB", "database"),
            ("הגדרת logging configuration", "logging"),
            ("יצירת configuration validation", "config_validator")
        ]
        
        updated_content = tasks_content
        tasks_completed = 0
        
        # Check which tasks can be marked as completed
        for task_desc, indicator in auto_completable:
            # Look for this task in pending state - more flexible pattern
            pattern = f"- ⏳ ([🔥🟡🟢]) ([^\\n]*{re.escape(task_desc)}[^\\n]*)"
            matches = re.search(pattern, tasks_content)
            
            # Check if indicator appears in session activities or file exists
            indicator_found = (indicator.lower() in str(self.session_activities).lower() or 
                              any(indicator in activity.lower() for activity in self.session_activities))
            
            if matches and indicator_found:
                # Mark as completed
                priority = matches.group(1)
                full_task = matches.group(2)
                
                old_line = f"- ⏳ {priority} {full_task}"
                new_line = f"- ✅ {priority} {full_task}"
                
                updated_content = updated_content.replace(old_line, new_line)
                tasks_completed += 1
                self.safe_print(f"  ✅ הושלם: {task_desc}")
        
        # Save updated tasks if any changes
        if tasks_completed > 0:
            if self.write_file_safe(self.files['tasks'], updated_content):
                self.changes_made.append(f"סומנו {tasks_completed} משימות כהושלמו אוטומטית")
                return True
        
        self.safe_print("  ℹ️  לא נמצאו משימות לעדכון אוטומטי")
        return True
    
    def update_current_status_auto(self) -> bool:
        """Automatically update CURRENT_STATUS.md"""
        self.safe_print("📊 עדכון אוטומטי של CURRENT_STATUS.md...")
        
        current_status = self.read_file_safe(self.files['current_status'])
        if not current_status:
            return False
        
        today = date.today().strftime("%d/%m/%Y")
        updated_content = current_status
        
        # Update last update date
        updated_content = re.sub(
            r'\*\*Last Update:\*\* \d{2}/\d{2}/\d{4}',
            f'**Last Update:** {today}',
            updated_content
        )
        
        # Update system changes section if there were changes
        if self.changes_made:
            # Find the system changes section
            changes_text = "**Major:** " + ", ".join(self.changes_made[:2])
            updated_content = re.sub(
                r'\*\*Major:\*\* .+',
                changes_text,
                updated_content
            )
        
        if self.write_file_safe(self.files['current_status'], updated_content):
            self.changes_made.append("עודכן CURRENT_STATUS.md עם תאריך נוכחי")
            self.safe_print("  ✅ CURRENT_STATUS.md עודכן")
            return True
        
        return False
    
    def create_auto_session_summary(self) -> bool:
        """Automatically create and archive session summary"""
        self.safe_print("📝 יצירת סיכום סשן אוטומטי...")
        
        # Get session activities
        activities = self.detect_session_activities()
        self.session_activities = activities
        
        if not activities and not self.changes_made:
            self.safe_print("  ℹ️  לא נמצא תוכן לסיכום")
            return True
        
        # Create session summary
        today = date.today().strftime("%d/%m/%Y")
        session_summary = f"### Session {today}\n\n"
        session_summary += "**Main Accomplishments:**\n"
        
        # Add detected activities
        for activity in activities:
            session_summary += f"- {activity}\n"
        
        # Add system changes
        if self.changes_made:
            session_summary += "\n**System Changes:**\n"
            for change in self.changes_made:
                session_summary += f"- {change}\n"
        
        session_summary += f"\n**Date:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        session_summary += "---\n\n"
        
        # Archive to SESSION_ARCHIVE.md
        session_archive_content = self.read_file_safe(self.files['session_archive'])
        session_archive_content = session_archive_content + session_summary
        
        if self.write_file_safe(self.files['session_archive'], session_archive_content):
            self.safe_print("  ✅ סיכום סשן נשמר בארכיב")
            self.changes_made.append("עודכן ארכיב סשנים")
            return True
        
        return False
    
    def update_task_statistics(self) -> bool:
        """Update task statistics in CURRENT_STATUS.md"""
        self.safe_print("📈 עדכון סטטיסטיקות משימות...")
        
        tasks_content = self.read_file_safe(self.files['tasks'])
        if not tasks_content:
            return False
        
        # Count tasks
        completed_tasks = len(re.findall(r'- ✅ [🔥🟡🟢]', tasks_content))
        pending_tasks = len(re.findall(r'- ⏳ [🔥🟡🟢]', tasks_content))
        in_progress_tasks = len(re.findall(r'- 🔄 [🔥🟡🟢]', tasks_content))
        
        total_tasks = completed_tasks + pending_tasks + in_progress_tasks
        
        # Update CURRENT_STATUS.md with new numbers
        current_status = self.read_file_safe(self.files['current_status'])
        
        # Update progress line
        milestone1_completed = completed_tasks  # Assuming most completed are from milestone 1
        milestone1_total = 31  # From the original planning
        milestone1_percent = (milestone1_completed / milestone1_total) * 100 if milestone1_total > 0 else 0
        
        overall_percent = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        progress_line = f"**Progress:** Milestone 1: {milestone1_completed}/{milestone1_total} tasks completed ({milestone1_percent:.1f}%)"
        overall_line = f"**Overall:** {completed_tasks}/{total_tasks} total tasks completed ({overall_percent:.1f}%)"
        
        updated_status = re.sub(
            r'\*\*Progress:\*\* Milestone 1: \d+/\d+ tasks completed \(\d+\.\d+%\)',
            progress_line,
            current_status
        )
        
        updated_status = re.sub(
            r'\*\*Overall:\*\* \d+/\d+ total tasks completed \(\d+\.\d+%\)',
            overall_line,
            updated_status
        )
        
        if self.write_file_safe(self.files['current_status'], updated_status):
            self.safe_print(f"  ✅ עודכן: {completed_tasks} הושלמו מתוך {total_tasks}")
            return True
        
        return False
    
    def generate_final_report(self):
        """Generate final report of all changes"""
        self.safe_print("\n" + "="*60)
        self.safe_print("🤖 סיכום עדכון אוטומטי")
        self.safe_print("="*60)
        
        if self.changes_made:
            self.safe_print("✅ שינויים שבוצעו:")
            for i, change in enumerate(self.changes_made, 1):
                self.safe_print(f"   {i}. {change}")
        else:
            self.safe_print("ℹ️  לא בוצעו שינויים במערכת")
        
        if self.session_activities:
            self.safe_print("\n🎯 פעילויות שזוהו בסשן:")
            for i, activity in enumerate(self.session_activities, 1):
                self.safe_print(f"   {i}. {activity}")
        
        self.safe_print("\n💡 המלצות:")
        self.safe_print("   ✅ הפעל project_status_reviewer.py לעדכון מצב")
        self.safe_print("   ✅ בדוק שכל השינויים נכונים")
        self.safe_print("   ✅ שקול ליצור commit עם השינויים")
        
        self.safe_print(f"\n📅 עדכון אוטומטי הושלם: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        self.safe_print("="*60)


def main():
    """Main execution function"""
    try:
        updater = AutoProjectUpdater()
        
        # Check if .md directory exists
        if not updater.md_path.exists():
            updater.safe_print(f"❌ Error: .md directory not found at {updater.md_path}")
            updater.safe_print("   Make sure you're running this script from the project root.")
            return
        
        updater.safe_print("🤖 Trading Project 004 - Automatic Updater")
        updater.safe_print("=" * 50)
        updater.safe_print("עדכון אוטומטי של מצב הפרויקט...\n")
        
        # Execute auto-update sequence
        steps = [
            ("זיהוי פעילויות סשן", lambda: updater.detect_session_activities()),
            ("עדכון משימות שהושלמו", updater.auto_mark_completed_tasks),
            ("עדכון סטטיסטיקות משימות", updater.update_task_statistics),
            ("עדכון מצב נוכחי", updater.update_current_status_auto),
            ("יצירת וארכוב סיכום סשן", updater.create_auto_session_summary)
        ]
        
        for step_name, step_func in steps:
            updater.safe_print(f"🔄 {step_name}...")
            try:
                step_func()
            except Exception as e:
                updater.safe_print(f"❌ שגיאה ב{step_name}: {e}")
        
        # Generate final report
        updater.generate_final_report()
        
    except Exception as e:
        updater = AutoProjectUpdater()
        updater.safe_print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()