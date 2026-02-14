"""
Refactor execution service for the Refactoring Workbench.
Handles backup creation, file modification, and per-match tracking.
"""

import os
import shutil
import hashlib
import re
from typing import List, Tuple, Optional
from datetime import datetime
from .scanner import FileScanner, _normalize_ext_set


class RefactorExecutor:
    """
    Executes refactoring operations with safety measures and tracking.
    """

    def __init__(self, create_backups: bool = True):
        self.create_backups = create_backups
        self._scanner = FileScanner()  # Used for context-aware matching

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""

    def create_backup(self, file_path: str) -> Optional[str]:
        """
        Create a backup of a file before modification.
        Returns the backup file path or None if failed.
        """
        if not self.create_backups:
            return None

        try:
            # Simple backup path, overwriting any existing
            simple_backup = f"{file_path}.bak"
            shutil.copy2(file_path, simple_backup)
            return simple_backup
        except Exception as e:
            print(f"Failed to create backup for {file_path}: {e}")
            return None

    def apply_replacement(
        self,
        content: str,
        search_pattern: str,
        replacement_text: str,
        is_regex: bool = False,
        case_sensitive: bool = True
    ) -> Tuple[str, int]:
        """
        Apply a replacement to content.
        Returns (new_content, replacement_count).
        """
        if is_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                new_content, count = re.subn(search_pattern, replacement_text, content, flags=flags)
                return new_content, count
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        else:
            if case_sensitive:
                count = content.count(search_pattern)
                new_content = content.replace(search_pattern, replacement_text)
            else:
                # Case-insensitive plain text replacement
                pattern = re.escape(search_pattern)
                new_content, count = re.subn(
                    pattern, replacement_text, content, flags=re.IGNORECASE
                )
            return new_content, count

    def execute_replacement(
        self,
        file_path: str,
        rules: List[dict]
    ) -> dict:
        """
        Execute replacements on a single file.
        Returns dict with execution results and tracking data.
        """
        result = {
            'file_path': file_path,
            'backup_path': None,
            'original_hash': None,
            'replacements_count': 0,
            'success': False,
            'error': None,
            'tracking': []  # Per-match tracking entries
        }

        try:
            # Read original content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                original_content = f.read()

            result['original_hash'] = self.calculate_file_hash(file_path)

            # Apply all rules and collect tracking
            modified_content = original_content
            total_replacements = 0

            _, file_ext = os.path.splitext(file_path)

            for rule in rules:
                # Check if this rule applies to this file type (normalized)
                target_exts = rule.get('target_extensions')
                if target_exts:
                    allowed_exts = _normalize_ext_set(target_exts)
                    if file_ext.lower() not in allowed_exts:
                        continue

                # Collect tracking data BEFORE applying replacement
                tracking_matches = self._scanner.find_matches_with_context(
                    modified_content,
                    rule['search_pattern'],
                    rule['replacement_text'],
                    rule.get('is_regex', False),
                    rule.get('case_sensitive', True)
                )

                for match in tracking_matches:
                    match['rule_id'] = rule.get('rule_id')
                    match['file_path'] = file_path
                    result['tracking'].append(match)

                modified_content, count = self.apply_replacement(
                    modified_content,
                    rule['search_pattern'],
                    rule['replacement_text'],
                    rule.get('is_regex', False),
                    rule.get('case_sensitive', True)
                )
                total_replacements += count

            # If no changes, skip
            if total_replacements == 0:
                result['success'] = True
                return result

            # Create backup before modifying
            backup_path = self.create_backup(file_path)
            result['backup_path'] = backup_path

            # Write modified content
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                f.write(modified_content)

            result['replacements_count'] = total_replacements
            result['success'] = True

        except Exception as e:
            result['error'] = str(e)

        return result

    def execute_batch(
        self,
        file_paths: List[str],
        rules: List[dict]
    ) -> dict:
        """
        Execute replacements on multiple files.
        Returns dict with summary, per-file results, and tracking.
        """
        summary = {
            'total_files': len(file_paths),
            'files_modified': 0,
            'total_replacements': 0,
            'files': [],
            'errors': [],
            'tracking': []  # Aggregated tracking entries
        }

        for file_path in file_paths:
            result = self.execute_replacement(file_path, rules)
            summary['files'].append(result)

            if result['success'] and result['replacements_count'] > 0:
                summary['files_modified'] += 1
                summary['total_replacements'] += result['replacements_count']

            if result['error']:
                summary['errors'].append(f"{file_path}: {result['error']}")

            # Aggregate tracking data
            summary['tracking'].extend(result.get('tracking', []))

        return summary


def restore_from_backup(file_path: str) -> bool:
    """
    Restore a file from its backup.
    Returns True if successful.
    """
    backup_path = f"{file_path}.bak"

    if not os.path.exists(backup_path):
        return False

    try:
        shutil.copy2(backup_path, file_path)
        return True
    except Exception:
        return False


def cleanup_backups(directory: str, recursive: bool = True) -> int:
    """
    Remove all .bak files from a directory.
    Returns the number of files removed.
    """
    removed = 0

    if recursive:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith('.bak'):
                    try:
                        os.remove(os.path.join(root, filename))
                        removed += 1
                    except Exception:
                        pass
    else:
        for filename in os.listdir(directory):
            if filename.endswith('.bak'):
                try:
                    os.remove(os.path.join(directory, filename))
                    removed += 1
                except Exception:
                    pass

    return removed
