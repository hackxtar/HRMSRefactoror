"""
File scanner service for the Refactoring Workbench.
Handles directory traversal, file filtering, and diff generation.
"""

import os
import re
import difflib
from typing import List, Tuple, Optional, Set
from html import escape


class FileScanner:
    """
    Scans directories for files matching patterns and generates diffs.
    """

    # Always exclude these folders (safety)
    ALWAYS_EXCLUDE_FOLDERS = {'.git', '.vs', '.idea', '__pycache__', '.svn', '.hg'}

    def __init__(
        self,
        include_extensions: str = ".cs,.ts,.tsx,.js,.jsx,.sql",
        exclude_extensions: str = ".dll,.exe,.pdb",
        exclude_folders: str = "bin,obj,node_modules,packages,dist,build"
    ):
        # Parse comma-separated lists into sets
        self.include_extensions = self._parse_extensions(include_extensions)
        self.exclude_extensions = self._parse_extensions(exclude_extensions)
        self.exclude_folders = self._parse_folders(exclude_folders)
        # Add always-excluded folders
        self.exclude_folders.update(self.ALWAYS_EXCLUDE_FOLDERS)

    def _parse_extensions(self, ext_string: str) -> Set[str]:
        """Parse comma-separated extension string into a set."""
        if not ext_string:
            return set()
        extensions = set()
        for ext in ext_string.split(','):
            ext = ext.strip().lower()
            if ext and not ext.startswith('.'):
                ext = '.' + ext
            if ext:
                extensions.add(ext)
        return extensions

    def _parse_folders(self, folder_string: str) -> Set[str]:
        """Parse comma-separated folder string into a set."""
        if not folder_string:
            return set()
        return {f.strip().lower() for f in folder_string.split(',') if f.strip()}

    def should_include_file(self, file_path: str) -> bool:
        """Check if a file should be included in scanning."""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # Check extension exclusions first
        if ext in self.exclude_extensions:
            return False

        # Check extension inclusions
        if self.include_extensions:
            return ext in self.include_extensions

        return True

    def should_exclude_folder(self, folder_name: str) -> bool:
        """Check if a folder should be excluded from scanning."""
        return folder_name.lower() in self.exclude_folders

    def scan_directory(self, root_path: str) -> List[str]:
        """
        Recursively scan a directory for matching files.
        Returns a list of absolute file paths.
        """
        matching_files = []

        if not os.path.isdir(root_path):
            return matching_files

        for dirpath, dirnames, filenames in os.walk(root_path):
            # Filter out excluded directories (modify in place to prevent descent)
            dirnames[:] = [
                d for d in dirnames
                if not self.should_exclude_folder(d) and not d.startswith('.')
            ]

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if self.should_include_file(file_path):
                    matching_files.append(file_path)

        return matching_files

    def find_matches(
        self,
        content: str,
        search_pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = True
    ) -> List[Tuple[int, int, str]]:
        """
        Find all matches of a pattern in content.
        Returns list of (start, end, matched_text) tuples.
        """
        matches = []

        if is_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                for match in re.finditer(search_pattern, content, flags):
                    matches.append((match.start(), match.end(), match.group()))
            except re.error:
                pass  # Invalid regex, return empty
        else:
            # Plain text search
            search_text = search_pattern
            search_content = content

            if not case_sensitive:
                search_text = search_pattern.lower()
                search_content = content.lower()

            start = 0
            while True:
                pos = search_content.find(search_text, start)
                if pos == -1:
                    break
                # Get the actual matched text (preserving original case)
                matched = content[pos:pos + len(search_pattern)]
                matches.append((pos, pos + len(search_pattern), matched))
                start = pos + 1

        return matches

    def find_matches_with_context(
        self,
        content: str,
        search_pattern: str,
        replacement_text: str,
        is_regex: bool = False,
        case_sensitive: bool = True,
        context_lines: int = 1
    ) -> List[dict]:
        """
        Find all matches with line numbers and surrounding context.
        Returns a list of dicts with line_number, original_text, context_snippet.
        """
        matches = self.find_matches(content, search_pattern, is_regex, case_sensitive)
        if not matches:
            return []

        lines = content.split('\n')
        # Build a mapping from character offset to line number
        line_starts = [0]
        for line in lines:
            line_starts.append(line_starts[-1] + len(line) + 1)  # +1 for \n

        results = []
        for start_pos, end_pos, matched_text in matches:
            # Find line number (0-indexed)
            line_num = 0
            for i, ls in enumerate(line_starts):
                if ls > start_pos:
                    line_num = i - 1
                    break
            else:
                line_num = len(lines) - 1

            # Get context lines
            ctx_start = max(0, line_num - context_lines)
            ctx_end = min(len(lines), line_num + context_lines + 1)
            context = '\n'.join(lines[ctx_start:ctx_end])

            results.append({
                'line_number': line_num + 1,  # 1-indexed
                'original_text': matched_text,
                'replacement_text': replacement_text,
                'context_snippet': context,
            })

        return results

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
            except re.error:
                return content, 0
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

    def generate_diff_html(
        self,
        original: str,
        modified: str,
        file_path: str,
        context_lines: int = 3
    ) -> str:
        """
        Generate an HTML diff between original and modified content.
        Returns HTML string for display.
        """
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{os.path.basename(file_path)}",
            tofile=f"b/{os.path.basename(file_path)}",
            n=context_lines
        )

        # Convert diff to HTML with syntax highlighting
        html_lines = ['<div class="diff-container">']

        for line in diff:
            escaped_line = escape(line.rstrip('\n\r'))

            if line.startswith('+++') or line.startswith('---'):
                html_lines.append(f'<div class="diff-header">{escaped_line}</div>')
            elif line.startswith('@@'):
                html_lines.append(f'<div class="diff-hunk">{escaped_line}</div>')
            elif line.startswith('+'):
                html_lines.append(f'<div class="diff-add">{escaped_line}</div>')
            elif line.startswith('-'):
                html_lines.append(f'<div class="diff-remove">{escaped_line}</div>')
            else:
                html_lines.append(f'<div class="diff-context">{escaped_line}</div>')

        html_lines.append('</div>')
        return '\n'.join(html_lines)


def scan_files_with_rules(
    root_paths: List[str],
    rules: List[dict],
    scanner: FileScanner
):
    """
    Scan multiple directories with multiple rules.
    Yields progress and match results.
    """
    files_to_scan = []
    
    # First, collect all files to scan
    for root_path in root_paths:
        if not os.path.isdir(root_path):
            continue
        files = scanner.scan_directory(root_path)
        files_to_scan.extend([(f, root_path) for f in files])

    total_files = len(files_to_scan)
    seen_files = set()
    
    for idx, (file_path, root_path) in enumerate(files_to_scan):
        if file_path in seen_files:
            continue
        seen_files.add(file_path)

        # Yield progress
        yield {
            'type': 'progress',
            'scanned': idx + 1,
            'total': total_files,
            'current_file': os.path.basename(file_path),
            'full_path': file_path
        }

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                original_content = f.read()
        except Exception:
            continue

        # Apply all rules to get final content
        modified_content = original_content
        match_count = 0
        matches_found = False

        for rule in rules:
            # Check if this rule applies to this file type
            target_exts = rule.get('target_extensions')
            if target_exts:
                _, file_ext = os.path.splitext(file_path)
                allowed_exts = {e.strip().lower() for e in target_exts.split(',')}
                if file_ext.lower() not in allowed_exts:
                    continue

            # We use a temporary content to check for matches without modifying the 'modified_content' yet
            # Actually, to show cumulative diffs, we should modify 'modified_content'
            new_content, count = scanner.apply_replacement(
                modified_content,
                rule['search_pattern'],
                rule['replacement_text'],
                rule.get('is_regex', False),
                rule.get('case_sensitive', True)
            )
            
            if count > 0:
                modified_content = new_content
                match_count += count
                matches_found = True

        if matches_found:
            diff_html = scanner.generate_diff_html(
                original_content, modified_content, file_path
            )

            relative_path = os.path.relpath(file_path, root_path)
            
            # Identify project name or root (simplification)
            project_root = root_path

            yield {
                'type': 'match',
                'file_path': file_path,
                'relative_path': relative_path,
                'project_root': project_root,
                'match_count': match_count,
                'diff_html': diff_html,
                'selected': True,
                'extension': os.path.splitext(file_path)[1].lower()
            }

