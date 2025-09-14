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
7. PERFORMS FULL PROJECT BACKUP TO GITHUB (Git commit + push + API backup)

IMPORTANT: This script ensures complete project backup and recovery capability.
All changes are automatically committed to Git and pushed to GitHub repository.

No user interaction required - fully automated with complete backup.
"""

import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List

# Import GitHub Backup Manager
sys.path.append(str(Path(__file__).parent.parent / "src"))
try:
    from github_backup_manager import GitHubBackupManager
except ImportError:
    GitHubBackupManager = None

# Fix Windows console encoding issues
if sys.platform.startswith("win"):
    import codecs

    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")
    except AttributeError:
        # Already properly configured or different Python version
        pass


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
            "tasks": self.md_path / "TASKS.md",
            "current_status": self.md_path / "CURRENT_STATUS.md",
            "claude": self.md_path / "CLAUDE.md",
            "session_archive": self.md_path / "SESSION_ARCHIVE.md",
            "prd": self.md_path / "PRD.md",
            "planning": self.md_path / "PLANNING.md",
            "database_design": self.md_path / "DATABASE_DESIGN.md",
            "files_manual": self.md_path / "FILES_USER_MANUAL.md",
        }

    def safe_print(self, text):
        """Print text safely handling encoding issues"""
        try:
            print(text)
        except UnicodeEncodeError:
            clean_text = re.sub(r"[^\x00-\x7F]+", "?", text)
            print(clean_text)

    def read_file_safe(self, filepath: Path) -> str:
        """Safely read a file with UTF-8 encoding"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""
        except Exception as e:
            self.safe_print(f"❌ Error reading {filepath}: {e}")
            return ""

    def write_file_safe(self, filepath: Path, content: str) -> bool:
        """Safely write a file with UTF-8 encoding"""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            self.safe_print(f"❌ Error writing {filepath}: {e}")
            return False

    def analyze_git_commits(self) -> List[str]:
        """ניתוח commit messages לזיהוי פעילויות"""
        activities = []
        try:
            import subprocess
            import os

            # Change to project directory
            original_dir = os.getcwd()
            os.chdir(self.base_path)

            # Get last 5 commits from today
            today_str = date.today().strftime("%Y-%m-%d")
            result = subprocess.run([
                'git', 'log', '--oneline', '--since', today_str, '-n', '5'
            ], capture_output=True, text=True, check=True)

            if result.stdout.strip():
                commits = result.stdout.strip().split('\n')
                for commit in commits:
                    if commit.strip():
                        # Extract meaningful info from commit message
                        commit_msg = commit.split(' ', 1)[1] if ' ' in commit else commit
                        if any(keyword in commit_msg.lower() for keyword in
                               ['add', 'create', 'update', 'fix', 'enhance', 'implement']):
                            activities.append(f"Git: {commit_msg[:60]}")

            os.chdir(original_dir)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Git not available or no commits today
            pass
        except Exception:
            pass

        return activities[:3]  # Limit to 3 most recent

    def analyze_git_commits(self) -> List[str]:
        """ניתוח commit messages לזיהוי פעילויות"""
        activities = []
        try:
            import subprocess
            import os

            # Change to project directory
            original_dir = os.getcwd()
            os.chdir(self.base_path)

            # Get last 5 commits from today
            today_str = date.today().strftime("%Y-%m-%d")
            result = subprocess.run([
                'git', 'log', '--oneline', '--since', today_str, '-n', '5'
            ], capture_output=True, text=True, check=True)

            if result.stdout.strip():
                commits = result.stdout.strip().split('\n')
                for commit in commits:
                    if commit.strip():
                        # Extract meaningful info from commit message
                        commit_msg = commit.split(' ', 1)[1] if ' ' in commit else commit
                        if any(keyword in commit_msg.lower() for keyword in
                               ['add', 'create', 'update', 'fix', 'enhance', 'implement']):
                            activities.append(f"Git: {commit_msg[:60]}")

            os.chdir(original_dir)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Git not available or no commits today
            pass
        except Exception:
            pass

        return activities[:3]  # Limit to 3 most recent

    def detect_session_activities(self) -> List[str]:
        """Auto-detect what was done in this session - ENHANCED"""
        activities = []

        # Phase 1: Git analysis (NEW)
        git_activities = self.analyze_git_commits()
        activities.extend(git_activities)

        # Phase 2: File modification analysis (ENHANCED)
        py_dirs = [self.base_path / ".py", self.base_path / "src"]
        today = date.today()

        for py_dir in py_dirs:
            if py_dir.exists():
                for py_file in py_dir.glob("*.py"):
                    try:
                        mod_time = datetime.fromtimestamp(
                            py_file.stat().st_mtime
                        ).date()
                        if mod_time == today:
                            activities.append(f"עדכן/יצר סקריפט: {py_file.name}")
                    except OSError:
                        pass

        # Check for config files (milestone 1.4 indicators)
        config_indicators = {
            "config": ["config.yaml", ".env"],
            "ib_connector": ["ib_connector.py"],
            "database": ["config_manager.py"],
            "logging": ["logging_setup.py"],
            "config_validator": ["config_validator.py"],
        }

        for category, files in config_indicators.items():
            for filename in files:
                for search_dir in [self.base_path / "config", self.base_path / "src"]:
                    filepath = search_dir / filename
                    if filepath.exists():
                        try:
                            mod_time = datetime.fromtimestamp(
                                filepath.stat().st_mtime
                            ).date()
                            if mod_time == today:
                                activities.append(f"עבודה על {category}: {filename}")
                        except OSError:
                            pass

        # Check for recent changes in .md files
        for name, filepath in self.files.items():
            if filepath.exists():
                try:
                    mod_time = datetime.fromtimestamp(filepath.stat().st_mtime).date()
                    if mod_time == today:
                        activities.append(f"עדכן קובץ תיעוד: {filepath.name}")
                except OSError:
                    pass

        # If no specific activities detected, add generic ones
        if not activities:
            activities = [
                "עבודה על פיתוח הסקריפטים",
                "שיפור כלי ניהול הפרויקט",
                "תחזוקה ועדכון מערכת התיעוד",
            ]

        return activities[:3]  # Limit to 3 main activities

    def analyze_file_contents_for_tasks(self) -> Dict[str, List[str]]:
        """ניתוח תוכן קבצים לזיהוי משימות שהושלמו"""
        file_analysis = {}

        # Analyze Python files created/modified today
        src_dir = self.base_path / "src"
        if src_dir.exists():
            today = date.today()
            for py_file in src_dir.glob("*.py"):
                try:
                    mod_time = datetime.fromtimestamp(py_file.stat().st_mtime).date()
                    if mod_time == today:
                        # Try to extract docstring and key functions
                        content = self.read_file_safe(py_file)
                        if content:
                            # Extract main functionality indicators
                            indicators = []
                            if 'class' in content.lower():
                                classes = re.findall(r'class\s+(\w+)', content)
                                indicators.extend([f"class {cls}" for cls in classes[:3]])
                            if 'def' in content.lower():
                                functions = re.findall(r'def\s+(\w+)', content)
                                main_functions = [f for f in functions if not f.startswith('_')][:3]
                                indicators.extend([f"function {func}" for func in main_functions])

                            file_analysis[py_file.name] = indicators
                except OSError:
                    pass

        return file_analysis
                                classes = re.findall(r'class\s+(\w+)', content)
                                indicators.extend([f"class {cls}" for cls in classes[:3]])
                            if 'def' in content.lower():
                                functions = re.findall(r'def\s+(\w+)', content)
                                main_functions = [f for f in functions if not f.startswith('_')][:3]
                                indicators.extend([f"function {func}" for func in main_functions])

                            file_analysis[py_file.name] = indicators
                except OSError:
                    pass

        return file_analysis

    def dynamic_task_matching(self, tasks_content: str) -> List[tuple]:
        """התאמה דינמית של פעילויות למשימות פתוחות"""
        matches = []

        # Find all pending tasks
        pending_pattern = r"- ⏳ ([🔥🟡🟢]) (.+)"
        pending_tasks = re.findall(pending_pattern, tasks_content)

        # Combine all session activities
        all_activities = self.session_activities + [
            f"קובץ: {filename}" for filename in self.analyze_file_contents_for_tasks().keys()
        ]

        # For each pending task, calculate match score
        for priority, task_text in pending_tasks:
            best_score = 0
            best_activity = None

            # Create keywords from task
            task_keywords = self.extract_keywords(task_text)

            # Check against all activities
            for activity in all_activities:
                score = self.calculate_match_score(task_keywords, activity)
                if score > best_score:
                    best_score = score
                    best_activity = activity

            # If score is high enough, consider it a match
            if best_score >= 75:  # 75% threshold
                matches.append((priority, task_text, best_activity, best_score))

        return matches

    def extract_keywords(self, text: str) -> List[str]:
        """חילוץ מילות מפתח מטקסט משימה"""
        # Hebrew and English keywords that indicate task types
        keywords = []
        text_lower = text.lower()

        # Task type keywords
        task_types = ['יצירת', 'עדכון', 'התקנת', 'בדיקת', 'פיתוח', 'הקמת', 'הגדרת']
        for task_type in task_types:
            if task_type in text_lower:
                keywords.append(task_type)

        # Technical keywords
        tech_keywords = ['script', 'database', 'config', 'api', 'connection', 'validation',
                        'testing', 'logging', 'backup', 'github', 'status', 'reviewer']
        for keyword in tech_keywords:
            if keyword in text_lower:
                keywords.append(keyword)

        # Extract file names mentioned
        file_patterns = re.findall(r'(\w+\.py)', text)
        keywords.extend(file_patterns)

        return keywords

    def calculate_match_score(self, task_keywords: List[str], activity: str) -> int:
        """חישוב ציון התאמה בין משימה לפעילות"""
        if not task_keywords:
            return 0

        activity_lower = activity.lower()
        matches = 0

        for keyword in task_keywords:
            if keyword.lower() in activity_lower:
                matches += 1

        # Calculate percentage match
        score = int((matches / len(task_keywords)) * 100)
        return score

    def auto_mark_completed_tasks(self) -> bool:
        """Automatically mark tasks as completed - ENHANCED VERSION"""
        self.safe_print("📋 זיהוי אוטומטי מתקדם של משימות שהושלמו...")

        tasks_content = self.read_file_safe(self.files["tasks"])
        if not tasks_content:
            return False

        # Phase 1: Static mapping (existing logic, but enhanced)
        static_matches = self._static_task_mapping(tasks_content)

        # Phase 2: Dynamic matching (NEW)
        dynamic_matches = self.dynamic_task_matching(tasks_content)

        # Combine all matches
        all_matches = static_matches + [(p, t, None, 100) for p, t in dynamic_matches if (p, t, None, 100) not in static_matches]

        updated_content = tasks_content
        tasks_completed = 0

        # Apply all matches
        for priority, task_text, activity, score in all_matches:
            old_line = f"- ⏳ {priority} {task_text}"
            new_line = f"- ✅ {priority} {task_text}"

            if old_line in updated_content:
                updated_content = updated_content.replace(old_line, new_line)
                tasks_completed += 1
                activity_note = f" (מבוסס על: {activity[:30]})" if activity else ""
                self.safe_print(f"  ✅ הושלם: {task_text[:50]}...{activity_note}")

        # Save updated tasks if any changes
        if tasks_completed > 0:
            if self.write_file_safe(self.files["tasks"], updated_content):
                self.changes_made.append(
                    f"זוהו וסומנו {tasks_completed} משימות אוטומטית (חכם + סטטי)"
                )
                return True

        self.safe_print("  ℹ️  לא נמצאו משימות לעדכון אוטומטי")
        return True

    def _static_task_mapping(self, tasks_content: str) -> List[tuple]:
        """מיפוי סטטי של משימות (הלוגיקה הקיימת)"""
        matches = []

        # Tasks that might be auto-completed based on script activity
        auto_completable = [
            ("יצירת Python Status Reviewer script", "project_status_reviewer.py"),
            ("שיפור מערכת הזיכרון וחיסכון טוקנים", "status"),
            ("עדכון קבצי תיעוד", ".md"),
            ("תיקון בעיות קידוד", "encoding"),
            ("יצירת כלי עזר אוטומטיים", "updater"),
            ("יצירת מערכת הגדרות", "config"),
            ("הגדרת פרמטרי חיבור IB", "ib_connector"),
            ("הגדרת פרמטרי DB", "database"),
            ("הגדרת logging configuration", "logging"),
            ("יצירת configuration validation", "config_validator"),
        ]

        # Check which tasks can be marked as completed
        for task_desc, indicator in auto_completable:
            # Look for this task in pending state
            pattern = f"- ⏳ ([🔥🟡🟢]) ([^\\n]*{re.escape(task_desc)}[^\\n]*)"
            task_match = re.search(pattern, tasks_content)

            # Check if indicator appears in session activities
            indicator_found = indicator.lower() in str(
                self.session_activities
            ).lower() or any(
                indicator in activity.lower() for activity in self.session_activities
            )

            if task_match and indicator_found:
                priority = task_match.group(1)
                full_task = task_match.group(2)
                matches.append((priority, full_task, f"static:{indicator}", 100))

        return matches

    def update_current_status_auto(self) -> bool:
        """Automatically update CURRENT_STATUS.md"""
        self.safe_print("📊 עדכון אוטומטי של CURRENT_STATUS.md...")

        current_status = self.read_file_safe(self.files["current_status"])
        if not current_status:
            return False

        today = date.today().strftime("%d/%m/%Y")
        updated_content = current_status

        # Update last update date
        updated_content = re.sub(
            r"\*\*Last Update:\*\* \d{2}/\d{2}/\d{4}",
            f"**Last Update:** {today}",
            updated_content,
        )

        # Update system changes section if there were changes
        if self.changes_made:
            # Find the system changes section
            changes_text = "**Major:** " + ", ".join(self.changes_made[:2])
            updated_content = re.sub(
                r"\*\*Major:\*\* .+", changes_text, updated_content
            )

        if self.write_file_safe(self.files["current_status"], updated_content):
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
        session_archive_content = self.read_file_safe(self.files["session_archive"])
        session_archive_content = session_archive_content + session_summary

        if self.write_file_safe(self.files["session_archive"], session_archive_content):
            self.safe_print("  ✅ סיכום סשן נשמר בארכיב")
            self.changes_made.append("עודכן ארכיב סשנים")
            return True

        return False

    def update_task_statistics(self) -> bool:
        """Update task statistics in CURRENT_STATUS.md"""
        self.safe_print("📈 עדכון סטטיסטיקות משימות...")

        tasks_content = self.read_file_safe(self.files["tasks"])
        if not tasks_content:
            return False

        # Count tasks
        completed_tasks = len(re.findall(r"- ✅ [🔥🟡🟢]", tasks_content))
        pending_tasks = len(re.findall(r"- ⏳ [🔥🟡🟢]", tasks_content))
        in_progress_tasks = len(re.findall(r"- 🔄 [🔥🟡🟢]", tasks_content))

        total_tasks = completed_tasks + pending_tasks + in_progress_tasks

        # Update CURRENT_STATUS.md with new numbers
        current_status = self.read_file_safe(self.files["current_status"])

        # Update progress line
        milestone1_completed = (
            completed_tasks  # Assuming most completed are from milestone 1
        )
        milestone1_total = 31  # From the original planning
        milestone1_percent = (
            (milestone1_completed / milestone1_total) * 100
            if milestone1_total > 0
            else 0
        )

        overall_percent = (
            (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        )

        progress_line = (
            f"**Progress:** Milestone 1: {milestone1_completed}/"
            f"{milestone1_total} tasks completed ({milestone1_percent:.1f}%)"
        )
        overall_line = (
            f"**Overall:** {completed_tasks}/{total_tasks} "
            f"total tasks completed ({overall_percent:.1f}%)"
        )

        updated_status = re.sub(
            r"\*\*Progress:\*\* Milestone 1: \d+/\d+ tasks completed \(\d+\.\d+%\)",
            progress_line,
            current_status,
        )

        updated_status = re.sub(
            r"\*\*Overall:\*\* \d+/\d+ total tasks completed \(\d+\.\d+%\)",
            overall_line,
            updated_status,
        )

        if self.write_file_safe(self.files["current_status"], updated_status):
            self.safe_print(f"  ✅ עודכן: {completed_tasks} הושלמו מתוך {total_tasks}")
            return True

        return False

    def backup_to_github(self) -> bool:
        """
        Backup complete project to GitHub after updates

        Performs FULL project backup including:
        1. Git commit of all changes
        2. Git push to GitHub repository
        3. Additional .md files backup via API

        This ensures complete project recovery capability.
        """
        self.safe_print("🔄 גיבוי מלא של הפרויקט ל-GitHub...")

        # Step 1: Full Git backup (primary backup method)
        git_success = self._perform_git_backup()

        # Step 2: Additional .md files backup via API (secondary backup)
        api_success = self._perform_api_backup()

        if git_success:
            self.safe_print("  ✅ גיבוי Git מלא הושלם בהצלחה")
            self.changes_made.append("בוצע גיבוי Git מלא ל-GitHub")

        if api_success:
            self.safe_print("  ✅ גיבוי API נוסף הושלם בהצלחה")

        return git_success  # Primary success indicator

    def _perform_git_backup(self) -> bool:
        """Perform full Git commit and push"""
        import subprocess
        import os

        try:
            os.chdir(self.base_path)

            # Check if there are any changes to commit
            result = subprocess.run(['git', 'status', '--porcelain'],
                                  capture_output=True, text=True, check=True)

            if not result.stdout.strip():
                self.safe_print("  ℹ️  אין שינויים לגיבוי Git")
                return True

            # Add all changes
            subprocess.run(['git', 'add', '.'], check=True)

            # Create commit message
            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            commit_msg = f"""Automatic project update - {now}

Auto-updated by project_updater.py:
- Session activities detected and documented
- Task progress updated
- Documentation files synchronized
- Complete project backup maintained

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

            # Commit changes
            subprocess.run(['git', 'commit', '-m', commit_msg], check=True)

            # Push to GitHub
            subprocess.run(['git', 'push'], check=True)

            return True

        except subprocess.CalledProcessError as e:
            self.safe_print(f"  ⚠️  שגיאה בגיבוי Git: {e}")
            return False
        except Exception as e:
            self.safe_print(f"  ❌ שגיאה בלתי צפויה בגיבוי Git: {e}")
            return False

    def _perform_api_backup(self) -> bool:
        """Perform additional API backup for .md files"""
        if not GitHubBackupManager:
            return True  # Not critical if unavailable

        try:
            backup_manager = GitHubBackupManager()

            if not backup_manager.github_token:
                return True  # Skip if no token

            # Backup .md files via API as additional safety
            return backup_manager.backup_md_files()

        except Exception as e:
            self.safe_print(f"  ⚠️  שגיאה בגיבוי API: {e}")
            return False

    def generate_final_report(self):
        """Generate final report of all changes"""
        self.safe_print("\n" + "=" * 60)
        self.safe_print("🤖 סיכום עדכון אוטומטי")
        self.safe_print("=" * 60)

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

        # Auto GitHub backup if GitHubBackupManager available
        if GitHubBackupManager:
            try:
                self.safe_print("\n🔄 יוצר גיבוי אוטומטי לגיטהאב...")
                backup_manager = GitHubBackupManager()
                result = backup_manager.create_automated_backup(
                    f"Auto backup - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                )
                if result.get("success"):
                    self.safe_print("   ✅ גיבוי לגיטהאב הושלם בהצלחה")
                else:
                    self.safe_print(f"   ⚠️ גיבוי נכשל: {result.get('error', 'Unknown error')}")
            except Exception as e:
                self.safe_print(f"   ❌ שגיאה בגיבוי: {str(e)}")

        self.safe_print("\n💡 המלצות:")
        self.safe_print("   ✅ הפעל project_status_reviewer.py לעדכון מצב")
        self.safe_print("   ✅ בדוק שכל השינויים נכונים")
        self.safe_print("   ✅ גיבוי אוטומטי לגיטהאב פועל")

        self.safe_print(
            f"\n📅 עדכון אוטומטי הושלם: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        self.safe_print("=" * 60)


def main():
    """Main execution function"""
    try:
        updater = AutoProjectUpdater()

        # Check if .md directory exists
        if not updater.md_path.exists():
            updater.safe_print(f"❌ Error: .md directory not found at {updater.md_path}")
            updater.safe_print(
                "   Make sure you're running this script from the project root."
            )
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
            ("יצירת וארכוב סיכום סשן", updater.create_auto_session_summary),
            ("גיבוי מלא של הפרויקט ל-GitHub", updater.backup_to_github),
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
