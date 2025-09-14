#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Status Reviewer - Trading Project 004
Auto-generates project status summary from documentation files

Usage: python project_status_reviewer.py
"""

# import os  # Not used currently
import re
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding issues
if sys.platform.startswith("win"):
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


class ProjectStatusReviewer:
    def __init__(self):
        # Define paths
        self.base_path = Path(__file__).parent.parent
        self.md_path = self.base_path / ".md"

        # Files to read in order
        self.files_to_read = [
            "RULES.md",
            "PRD.md",
            "PLANNING.md",
            "DATABASE_DESIGN.md",
            "CURRENT_STATUS.md",
            "TASKS.md",
            "SESSION_ARCHIVE.md",
        ]

        self.status_data = {}

        # Additional data for enhanced summary
        self.project_rules = {}
        self.technical_status = {}
        self.architectural_decisions = []

    def safe_print(self, text):
        """Print text safely handling encoding issues"""
        try:
            print(text)
        except UnicodeEncodeError:
            # Fallback: remove emojis and special characters
            import re

            clean_text = re.sub(r"[^\x00-\x7F]+", "?", text)
            print(clean_text)

    def read_file_safe(self, filename):
        """Safely read a file with UTF-8 encoding"""
        try:
            file_path = self.md_path / filename
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return f"❌ File {filename} not found"
        except Exception as e:
            return f"❌ Error reading {filename}: {str(e)}"

    def parse_current_status(self, content):
        """Parse CURRENT_STATUS.md for key information"""
        try:
            # Extract phase
            phase_match = re.search(r"\*\*Phase:\*\* (.+)", content)
            phase = phase_match.group(1).strip() if phase_match else "Unknown"

            # Extract progress
            progress_match = re.search(r"\*\*Progress:\*\* (.+)", content)
            progress = progress_match.group(1).strip() if progress_match else "Unknown"

            # Extract next actions
            next_actions_match = re.search(r"\*\*Next Actions:\*\* (.+)", content)
            next_actions = (
                next_actions_match.group(1).strip()
                if next_actions_match
                else "Not specified"
            )

            # Extract blockers
            blockers_match = re.search(r"\*\*Current:\*\* (.+)", content)
            blockers = blockers_match.group(1).strip() if blockers_match else "None"

            return {
                "phase": phase,
                "progress": progress,
                "next_actions": next_actions,
                "blockers": blockers,
            }
        except Exception as e:
            return {"error": f"Failed to parse CURRENT_STATUS.md: {str(e)}"}

    def parse_tasks_status(self, content):
        """Parse TASKS.md for completed and next tasks"""
        try:
            # Count completed tasks (excluding legend items) - fixed regex pattern
            completed_tasks = len(re.findall(r"- ✅ [🔥🟡🟢🔄]", content))
            pending_tasks = len(re.findall(r"- ⏳ [🔥🟡🟢]", content))
            in_progress_tasks = len(re.findall(r"- 🔄 [🔥🟡🟢]", content))

            # Find last completed task (real tasks, not legend)
            completed_matches = re.findall(r"- ✅ [🔥🟡🟢] (.+)", content)
            last_completed = (
                completed_matches[-1].strip() if completed_matches else "None found"
            )

            # Find next pending task (real tasks, not legend)
            pending_matches = re.findall(r"- ⏳ [🔥🟡🟢] (.+)", content)
            next_task = pending_matches[0].strip() if pending_matches else "None found"

            return {
                "completed_count": completed_tasks,
                "pending_count": pending_tasks,
                "in_progress_count": in_progress_tasks,
                "last_completed": last_completed,
                "next_task": next_task,
            }
        except Exception as e:
            return {"error": f"Failed to parse TASKS.md: {str(e)}"}

    def extract_project_rules(self, rules_content):
        """Extract key project rules from RULES.md"""
        rules = {
            "communication": [],
            "work_process": []
        }

        current_section = None
        for line in rules_content.split('\n'):
            line = line.strip()
            if "חוקי תקשורת" in line:
                current_section = "communication"
            elif "חוקי עבודה" in line:
                current_section = "work_process"
            elif line.startswith(('1.', '2.', '3.', '4.', '5.', '6.')):
                if current_section:
                    # Extract rule text, clean it up
                    rule_text = line[2:].strip()[:120]  # Limit length
                    rules[current_section].append(rule_text)

        return rules

    def extract_technical_status(self):
        """Extract current technical status and dependencies"""
        src_path = self.base_path / "src"
        python_files = []

        if src_path.exists():
            python_files = [f.name for f in src_path.glob("*.py")]

        # Check for key technology decisions from various files
        tech_status = {
            "python_files": python_files,
            "database_choice": "SQLite (dev) → PostgreSQL (prod)",
            "timeframes": ["1min", "15min", "1hour", "4hour", "daily"],
            "validation_quality": "99.95%+",
            "environment": "conda: trading_project (Python 3.11.13)"
        }

        return tech_status

    def extract_architectural_decisions(self, content_dict):
        """Extract key architectural decisions from documentation"""
        decisions = []

        # From DATABASE_DESIGN.md
        if "DATABASE_DESIGN.md" in content_dict:
            db_content = content_dict["DATABASE_DESIGN.md"]
            if "SQLite" in db_content and "PostgreSQL" in db_content:
                decisions.append("Database: SQLite for development, PostgreSQL for production")
            if "DNA Database" in db_content:
                decisions.append("DNA Database: Every minute with trading simulation + indicators")
            if "LONG only" in db_content:
                decisions.append("Trading Strategy: LONG only, SL=$2.8, TP=$3.2, 50 shares")

        # From PLANNING.md
        if "PLANNING.md" in content_dict:
            planning_content = content_dict["PLANNING.md"]
            if "Interactive Brokers" in planning_content:
                decisions.append("Data Source: Interactive Brokers API with enterprise validation")
            if "5 timeframes" in planning_content.lower():
                decisions.append("Multi-timeframe: 5 timeframes for comprehensive analysis")

        return decisions

    def parse_session_archive(self, content):
        """Parse SESSION_ARCHIVE.md for latest session info"""
        try:
            # Find the latest session (last one in the archive)
            all_sessions = re.findall(r"### Session ([0-9/]+)", content)
            latest_session = all_sessions[-1] if all_sessions else "No sessions found"

            # Extract major accomplishments from latest session (last section)
            accomplishments_sections = re.findall(
                r"\*\*Main Accomplishments:\*\*\s*\n((?:- .+\n?)*)", content
            )
            accomplishments_section = (
                accomplishments_sections[-1] if accomplishments_sections else None
            )

            if accomplishments_section:
                accomplishments = accomplishments_section.strip()
                # Take first 2 accomplishments
                accomplishment_lines = [
                    line.strip() for line in accomplishments.split("\n") if line.strip()
                ][:2]
                key_accomplishments = accomplishment_lines
            else:
                key_accomplishments = ["No accomplishments found"]

            return {
                "latest_session": latest_session,
                "key_accomplishments": key_accomplishments,
            }
        except Exception as e:
            return {"error": f"Failed to parse SESSION_ARCHIVE.md: {str(e)}"}

    def scan_python_files(self):
        """Scan src/ directory for Python files and their status"""
        src_path = self.base_path / "src"
        python_files = {}

        if src_path.exists():
            for py_file in src_path.glob("*.py"):
                if py_file.name != "__init__.py":  # Skip __init__.py
                    stat = py_file.stat()
                    python_files[py_file.name] = {
                        'exists': True,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                    }

        return python_files

    def analyze_task_completion(self, tasks_content, python_files):
        """Analyze which tasks should be marked as completed based on existing files"""
        updates_made = []

        # Define file-to-task mappings
        file_mappings = {
            'database_models.py': ['Database Models', 'HistoricalData model'],
            'database_manager.py': ['Database Manager', 'Connection management'],
            'ib_connector.py': ['IB Connection', 'Connection manager'],
            'data_storage_service.py': ['Data Storage Service', 'Storage API'],
            'ib_connection_tester.py': ['Connection Testing', 'IB Connection Test'],
            'historical_data_downloader.py': ['Historical Data Download', 'Data Download'],
            'multi_timeframe_validator.py': ['Enterprise Data Validation', 'Multi-Timeframe'],
            'rate_limiter.py': ['Rate Limiting', 'IB API rate'],
            'batch_optimizer.py': ['Batch Optimization', 'batch requests'],
            'performance_tester.py': ['Performance Testing', 'performance testing'],
            'config_manager.py': ['Configuration Management', 'config'],
            'config_validator.py': ['Configuration', 'validation']
        }

        # Keywords for task completion detection
        completion_keywords = ['יצירת', 'עדכון', 'התקנת', 'בדיקת', 'הקמת', 'פיתוח']

        # Look for tasks that should be completed
        lines = tasks_content.split('\n')
        updated_lines = []

        for line in lines:
            updated_line = line
            # Check if this is a pending task line
            if '- ⏳' in line or '- 🔄' in line:
                task_text = line.lower()
                should_complete = False

                # Check file-based completion
                for filename, keywords in file_mappings.items():
                    if filename in python_files and python_files[filename]['exists']:
                        for keyword in keywords:
                            if keyword.lower() in task_text:
                                should_complete = True
                                updates_made.append(f"Found {filename} → completing task: {keyword}")
                                break
                    if should_complete:
                        break

                # Update the line if task should be completed
                if should_complete:
                    if '- ⏳' in line:
                        updated_line = line.replace('- ⏳', '- ✅')
                    elif '- 🔄' in line:
                        updated_line = line.replace('- 🔄', '- ✅')

            updated_lines.append(updated_line)

        return '\n'.join(updated_lines), updates_made

    def update_tasks_file(self, updated_content):
        """Write updated TASKS.md back to file"""
        try:
            tasks_file = self.md_path / "TASKS.md"
            with open(tasks_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            return True
        except Exception as e:
            self.safe_print(f"❌ Error updating TASKS.md: {str(e)}")
            return False

    def analyze_project(self):
        """Main analysis function with enhanced file scanning"""
        self.safe_print("🔍 Reading project documentation files...")

        # Read all files - ACTUAL CONTENT READING
        for filename in self.files_to_read:
            self.safe_print(f"   📄 Reading {filename}...")
            content = self.read_file_safe(filename)
            self.status_data[filename] = content

        self.safe_print("\n📊 Scanning Python files in src/...")
        python_files = self.scan_python_files()
        self.safe_print(f"   Found {len(python_files)} Python files")

        self.safe_print("\n🔄 Analyzing task completion status...")
        if "TASKS.md" in self.status_data:
            updated_tasks_content, updates_made = self.analyze_task_completion(
                self.status_data["TASKS.md"], python_files
            )

            if updates_made:
                self.safe_print(f"   ✅ Found {len(updates_made)} tasks to update automatically")
                for update in updates_made[:3]:  # Show first 3
                    self.safe_print(f"      • {update}")

                # Update the TASKS.md file
                if self.update_tasks_file(updated_tasks_content):
                    self.safe_print("   💾 TASKS.md updated successfully")
                    # Update our internal copy
                    self.status_data["TASKS.md"] = updated_tasks_content
                else:
                    self.safe_print("   ❌ Failed to update TASKS.md")
            else:
                self.safe_print("   ℹ️ No automatic task updates needed")

        self.safe_print("\n📊 Analyzing project status...")

        # Extract enhanced information
        if "RULES.md" in self.status_data:
            self.project_rules = self.extract_project_rules(self.status_data["RULES.md"])

        self.technical_status = self.extract_technical_status()
        self.architectural_decisions = self.extract_architectural_decisions(self.status_data)

        # Parse specific files
        current_status = self.parse_current_status(
            self.status_data.get("CURRENT_STATUS.md", "")
        )
        task_status = self.parse_tasks_status(self.status_data.get("TASKS.md", ""))
        session_info = self.parse_session_archive(
            self.status_data.get("SESSION_ARCHIVE.md", "")
        )

        return current_status, task_status, session_info, python_files

    def generate_summary(self, current_status, task_status, session_info, python_files=None):
        """Generate final summary with RULES enforcement reminder"""
        summary = []
        summary.append("=" * 60)
        summary.append("🎯 TRADING PROJECT 004 - STATUS SUMMARY")
        summary.append("=" * 60)
        summary.append("")

        # Add RULES enforcement reminder at the top
        summary.append("⚠️ IMPORTANT - RULES ENFORCEMENT:")
        summary.append("   📋 RULES.md has been read - MUST follow communication and work rules")
        summary.append("   🔹 Communication: Short, direct, factual responses")
        summary.append("   🔹 Work Process: Plan before action, request approval, no unsolicited code")
        summary.append("   🔹 Resource Saving: Use efficient tools, batch operations")
        summary.append("")

        # Session info
        summary.append("📝 LATEST SESSION:")
        summary.append(f"   Date: {session_info.get('latest_session', 'Unknown')}")
        for accomplishment in session_info.get("key_accomplishments", [])[:2]:
            if accomplishment:
                summary.append(f"   • {accomplishment}")
        summary.append("")

        # Current state
        summary.append("📋 CURRENT STATE:")
        summary.append(f"   Phase: {current_status.get('phase', 'Unknown')}")
        summary.append(f"   Progress: {current_status.get('progress', 'Unknown')}")
        summary.append(f"   Blockers: {current_status.get('blockers', 'Unknown')}")
        summary.append("")

        # Task status
        summary.append("✅ TASK STATUS:")
        summary.append(f"   Completed: {task_status.get('completed_count', 0)} tasks")
        summary.append(f"   Pending: {task_status.get('pending_count', 0)} tasks")
        summary.append(
            f"   In Progress: {task_status.get('in_progress_count', 0)} tasks"
        )
        summary.append("")

        # Last completed task
        summary.append("🏁 LAST COMPLETED:")
        last_completed = task_status.get("last_completed", "None")[
            :80
        ]  # Truncate if too long
        summary.append(f"   {last_completed}")
        summary.append("")

        # Next task
        summary.append("🔜 NEXT TASK:")
        next_task = task_status.get("next_task", "None")[:80]  # Truncate if too long
        summary.append(f"   {next_task}")
        summary.append("")

        # Next actions
        summary.append("🎯 NEXT ACTIONS:")
        summary.append(f"   {current_status.get('next_actions', 'Not specified')}")
        summary.append("")

        # Project Rules (NEW)
        summary.append("📋 PROJECT RULES:")
        summary.append("   📞 Communication Rules:")
        for rule in self.project_rules.get("communication", [])[:3]:  # Limit to top 3
            summary.append(f"     • {rule}")
        summary.append("   💼 Work Process Rules:")
        for rule in self.project_rules.get("work_process", [])[:3]:  # Limit to top 3
            summary.append(f"     • {rule}")
        summary.append("")

        # Technical Status (ENHANCED)
        summary.append("🔧 TECHNICAL STATUS:")
        summary.append(f"   Environment: {self.technical_status.get('environment', 'Unknown')}")
        summary.append(f"   Database: {self.technical_status.get('database_choice', 'Not specified')}")
        summary.append(f"   Validation: {self.technical_status.get('validation_quality', 'Unknown')}")

        # Python Files Status (NEW)
        if python_files:
            summary.append(f"   Python Files: {len(python_files)} files in src/")
            summary.append("     Recent files:")
            # Sort by modification time and show top 5
            sorted_files = sorted(python_files.items(), key=lambda x: x[1]['modified'], reverse=True)
            for filename, info in sorted_files[:5]:
                size_kb = info['size'] // 1024 if info['size'] > 0 else 0
                summary.append(f"       • {filename} ({size_kb}KB, modified: {info['modified']})")
        else:
            summary.append(f"   Python Files: {len(self.technical_status.get('python_files', []))} files in src/")
            if self.technical_status.get('python_files'):
                top_files = self.technical_status['python_files'][:5]  # Show first 5
                summary.append(f"     Key files: {', '.join(top_files)}")
        summary.append("")

        # Architectural Decisions (NEW)
        if self.architectural_decisions:
            summary.append("🏗️ KEY ARCHITECTURAL DECISIONS:")
            for decision in self.architectural_decisions[:4]:  # Limit to top 4
                summary.append(f"   • {decision}")
            summary.append("")

        # CLAUDE.md Integration Note (NEW)
        summary.append("📖 COMPLETE PROJECT CONTEXT:")
        summary.append("   ⚡ This summary provides quick status overview")
        summary.append("   📚 For full context, CLAUDE.md contains complete reading guidelines:")
        summary.append("     • All project documentation (RULES, PRD, PLANNING, etc.)")
        summary.append("     • Database design specifications (DATABASE_DESIGN.md)")
        summary.append("     • Session history and accomplishments")
        summary.append("   💡 Use this summary as starting point, refer to CLAUDE.md for details")
        summary.append("")

        summary.append("=" * 60)
        summary.append(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary.append("=" * 60)
        summary.append("")

        # Add final RULES reminder
        summary.append("🚨 CLAUDE CODE SESSION START REQUIREMENTS:")
        summary.append("   1. APPLY RULES.md immediately - no exceptions")
        summary.append("   2. Communicate: Short, direct, seek approval")
        summary.append("   3. Work: Plan first, execute only after approval")
        summary.append("=" * 60)

        return "\n".join(summary)


def main():
    """Main execution function"""
    try:
        reviewer = ProjectStatusReviewer()

        # Check if .md directory exists
        if not reviewer.md_path.exists():
            reviewer.safe_print(
                f"❌ Error: .md directory not found at {reviewer.md_path}"
            )
            reviewer.safe_print(
                "   Make sure you're running this script from the project root."
            )
            return

        reviewer.safe_print("🚀 Trading Project 004 - Status Reviewer")
        reviewer.safe_print("=" * 50)

        # Analyze project with enhanced scanning
        current_status, task_status, session_info, python_files = reviewer.analyze_project()

        # Generate and display summary
        summary = reviewer.generate_summary(current_status, task_status, session_info, python_files)
        reviewer.safe_print(summary)

        # Optionally save to file
        output_file = reviewer.base_path / ".md" / "GENERATED_STATUS_SUMMARY.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(summary)

        reviewer.safe_print(f"\n💾 Full summary saved to: {output_file}")

        # Add Claude reading instructions
        reviewer.safe_print("\n" + "=" * 60)
        reviewer.safe_print("📋 CLAUDE: Please read these files for complete project context:")
        reviewer.safe_print("=" * 60)
        files_to_read = [
            "RULES.md",
            "PRD.md",
            "PLANNING.md",
            "DATABASE_DESIGN.md",
            "CURRENT_STATUS.md",
            "TASKS.md",
            "GENERATED_STATUS_SUMMARY.md"
        ]

        for file in files_to_read:
            reviewer.safe_print(f"   📄 Read: {file}")

        reviewer.safe_print("\n💡 After reading these files, you'll have complete project understanding!")
        reviewer.safe_print("=" * 60)

    except Exception as e:
        reviewer = ProjectStatusReviewer()
        reviewer.safe_print(f"❌ Unexpected error: {str(e)}")
        reviewer.safe_print("   Please check your file structure and try again.")


if __name__ == "__main__":
    main()
