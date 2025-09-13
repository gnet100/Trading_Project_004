#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix encoding issues in TASKS.md - specifically Milestone 3.2 icons
"""

import os
from pathlib import Path

def fix_tasks_encoding():
    """Fix the encoding issues with checkmarks in TASKS.md"""

    tasks_file = Path(r"C:\Users\Golan\Claude-Code\Trading Project\Trading Project 004\.md\TASKS.md")

    # Read with explicit UTF-8 encoding
    with open(tasks_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Define replacements for Milestone 3.2
    replacements = [
        ("⏳ 🔥 התקנת database libraries:", "✅ 🟢 התקנת database libraries:"),
        ("⏳ 🔥 יצירת Database Models:", "✅ 🟢 יצירת Database Models:"),
        ("⏳ 🔥 יצירת Database Manager class:", "✅ 🟢 יצירת Database Manager class:"),
        ("⏳ 🔥 מערכת migrations עם Alembic", "✅ 🟢 מערכת migrations עם Alembic")
    ]

    # Apply replacements
    changes_made = 0
    for old_text, new_text in replacements:
        if old_text in content:
            content = content.replace(old_text, new_text)
            changes_made += 1
            print(f"Replaced: {old_text}")

    # Write back with explicit UTF-8 encoding
    with open(tasks_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Fixed {changes_made} items in TASKS.md!")
    return True

if __name__ == "__main__":
    try:
        success = fix_tasks_encoding()
        if success:
            print("✅ Encoding fix completed successfully!")
        else:
            print("❌ Encoding fix failed!")
    except Exception as e:
        print(f"Error: {e}")