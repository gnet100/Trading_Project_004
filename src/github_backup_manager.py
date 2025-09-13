#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Backup Manager - Trading Project 004
Handles automated backup of project files to GitHub repository

Usage:
    manager = GitHubBackupManager()
    manager.backup_md_files()
"""

import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# Fix Windows console encoding issues
if sys.platform.startswith("win"):
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


class GitHubBackupManager:
    def __init__(self):
        """Initialize GitHub Backup Manager"""
        self.base_path = Path(__file__).parent.parent
        self.md_path = self.base_path / ".md"

        # Load configuration
        self.github_token = self._load_github_token()
        self.repo_owner = "gnet100"
        self.repo_name = "Trading_Project_004"

        # GitHub API settings
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

        # Track backup results
        self.backup_results = []

    def safe_print(self, text):
        """Print text safely handling encoding issues"""
        try:
            print(text)
        except UnicodeEncodeError:
            import re

            clean_text = re.sub(r"[^\x00-\x7F]+", "?", text)
            print(clean_text)

    def _load_github_token(self) -> Optional[str]:
        """Load GitHub token from environment or .env file"""
        # Try environment variable first
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            return token

        # Try .env file
        env_file = self.base_path / ".env"
        if env_file.exists():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GITHUB_TOKEN="):
                            return line.split("=", 1)[1].strip()
            except Exception as e:
                self.safe_print(f"❌ Error reading .env file: {e}")

        return None

    def _make_api_request(
        self, method: str, endpoint: str, data: dict = None
    ) -> Tuple[bool, dict]:
        """Make GitHub API request with error handling"""
        url = f"{self.api_base}{endpoint}"

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, verify=False)
            elif method.upper() == "PUT":
                response = requests.put(
                    url, headers=self.headers, json=data, verify=False
                )
            elif method.upper() == "POST":
                response = requests.post(
                    url, headers=self.headers, json=data, verify=False
                )
            else:
                return False, {"error": f"Unsupported method: {method}"}

            if response.status_code in [200, 201]:
                return True, response.json()
            else:
                return False, {
                    "error": f"API request failed: {response.status_code}",
                    "message": response.text,
                }

        except requests.RequestException as e:
            return False, {"error": f"Request exception: {str(e)}"}

    def _get_file_sha(self, file_path: str) -> Optional[str]:
        """Get SHA hash of existing file in repository"""
        endpoint = f"/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
        success, response = self._make_api_request("GET", endpoint)

        if success:
            return response.get("sha")
        return None

    def _encode_file_content(self, file_path: Path) -> str:
        """Encode file content to base64 for GitHub API"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return base64.b64encode(content.encode("utf-8")).decode("ascii")
        except Exception as e:
            self.safe_print(f"❌ Error encoding file {file_path}: {e}")
            return ""

    def upload_file(
        self, local_file_path: Path, repo_path: str, commit_message: str = None
    ) -> bool:
        """Upload single file to GitHub repository"""
        if not self.github_token:
            self.safe_print("❌ GitHub token not found")
            return False

        if not local_file_path.exists():
            self.safe_print(f"❌ File not found: {local_file_path}")
            return False

        # Encode file content
        encoded_content = self._encode_file_content(local_file_path)
        if not encoded_content:
            return False

        # Check if file exists and get SHA
        sha = self._get_file_sha(repo_path)

        # Prepare API data
        if not commit_message:
            commit_message = f"Update {repo_path}"

        api_data = {"message": commit_message, "content": encoded_content}

        if sha:  # File exists, need SHA for update
            api_data["sha"] = sha

        # Upload file
        endpoint = f"/repos/{self.repo_owner}/{self.repo_name}/contents/{repo_path}"
        success, response = self._make_api_request("PUT", endpoint, api_data)

        if success:
            self.safe_print(f"✅ Uploaded: {repo_path}")
            self.backup_results.append(
                {
                    "file": repo_path,
                    "status": "success",
                    "message": "File uploaded successfully",
                }
            )
            return True
        else:
            self.safe_print(
                f"❌ Failed to upload {repo_path}: {response.get('error', 'Unknown error')}"
            )
            self.backup_results.append(
                {
                    "file": repo_path,
                    "status": "failed",
                    "message": response.get("error", "Unknown error"),
                }
            )
            return False

    def backup_md_files(self) -> bool:
        """Backup all .md files to GitHub"""
        if not self.github_token:
            self.safe_print("❌ GitHub token not configured")
            return False

        self.safe_print("📤 Starting backup of .md files to GitHub...")

        # Get all .md files
        md_files = list(self.md_path.glob("*.md"))
        if not md_files:
            self.safe_print("ℹ️ No .md files found to backup")
            return True

        self.safe_print(f"📁 Found {len(md_files)} .md files to backup")

        # Upload each file
        success_count = 0
        for md_file in md_files:
            repo_path = f".md/{md_file.name}"
            commit_message = (
                f"Backup {md_file.name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            if self.upload_file(md_file, repo_path, commit_message):
                success_count += 1

        # Report results
        self.safe_print(
            f"✅ Backup completed: {success_count}/{len(md_files)} files uploaded"
        )

        return success_count == len(md_files)

    def backup_py_files(self) -> bool:
        """Backup .py automation files to GitHub"""
        if not self.github_token:
            self.safe_print("❌ GitHub token not configured")
            return False

        self.safe_print("📤 Starting backup of .py files to GitHub...")

        # Get .py files from .py directory
        py_dir = self.base_path / ".py"
        if not py_dir.exists():
            self.safe_print("ℹ️ No .py directory found")
            return True

        py_files = list(py_dir.glob("*.py"))
        if not py_files:
            self.safe_print("ℹ️ No .py files found to backup")
            return True

        self.safe_print(f"📁 Found {len(py_files)} .py files to backup")

        # Upload each file
        success_count = 0
        for py_file in py_files:
            repo_path = f".py/{py_file.name}"
            commit_message = (
                f"Backup {py_file.name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            if self.upload_file(py_file, repo_path, commit_message):
                success_count += 1

        self.safe_print(
            f"✅ Backup completed: {success_count}/{len(py_files)} files uploaded"
        )
        return success_count == len(py_files)

    def backup_config_files(self) -> bool:
        """Backup critical config files (excluding sensitive ones)"""
        if not self.github_token:
            return False

        self.safe_print("📤 Starting backup of config files...")

        config_files = [
            (self.base_path / "config" / "config.yaml", "config/config.yaml"),
            (self.base_path / "config" / ".env.template", "config/.env.template"),
            (self.base_path / "README.md", "README.md"),
            (self.base_path / ".gitignore", ".gitignore"),
        ]

        success_count = 0
        actual_files = 0

        for local_path, repo_path in config_files:
            if local_path.exists():
                actual_files += 1
                commit_message = (
                    f"Backup {repo_path} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                if self.upload_file(local_path, repo_path, commit_message):
                    success_count += 1

        if actual_files > 0:
            self.safe_print(
                f"✅ Config backup completed: {success_count}/{actual_files} files uploaded"
            )
        else:
            self.safe_print("ℹ️ No config files found to backup")

        return success_count == actual_files

    def full_backup(self) -> bool:
        """Perform full backup of all critical files"""
        self.safe_print("🚀 Starting full project backup to GitHub...")
        self.backup_results = []

        results = []
        results.append(self.backup_md_files())
        results.append(self.backup_py_files())
        results.append(self.backup_config_files())

        success = all(results)

        if success:
            self.safe_print("🎉 Full backup completed successfully!")
        else:
            self.safe_print("⚠️ Backup completed with some errors")

        return success

    def get_backup_summary(self) -> dict:
        """Get summary of backup results"""
        success_count = len(
            [r for r in self.backup_results if r["status"] == "success"]
        )
        failed_count = len([r for r in self.backup_results if r["status"] == "failed"])

        return {
            "total_files": len(self.backup_results),
            "successful": success_count,
            "failed": failed_count,
            "success_rate": (success_count / len(self.backup_results) * 100)
            if self.backup_results
            else 0,
            "results": self.backup_results,
        }


def main():
    """Main execution function for testing"""
    try:
        manager = GitHubBackupManager()

        if not manager.github_token:
            manager.safe_print("❌ GitHub token not found!")
            manager.safe_print(
                "Set GITHUB_TOKEN environment variable or create .env file"
            )
            return

        manager.safe_print("🔧 Trading Project 004 - GitHub Backup Manager")
        manager.safe_print("=" * 50)

        # Test connection
        success, response = manager._make_api_request("GET", "/user")
        if not success:
            manager.safe_print("❌ Failed to connect to GitHub API")
            return

        manager.safe_print(
            f"✅ Connected to GitHub as: {response.get('login', 'Unknown')}"
        )

        # Perform full backup
        manager.full_backup()

        # Show summary
        summary = manager.get_backup_summary()
        manager.safe_print(f"\n📊 Backup Summary:")
        manager.safe_print(f"   Total files: {summary['total_files']}")
        manager.safe_print(f"   Successful: {summary['successful']}")
        manager.safe_print(f"   Failed: {summary['failed']}")
        manager.safe_print(f"   Success rate: {summary['success_rate']:.1f}%")

    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
