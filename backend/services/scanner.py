"""
File scanner service for the Refactoring Workbench.
Handles directory traversal, file filtering, and diff generation.

Performance-optimized version:
- Generator-based directory scanning (no full list in memory)
- Non-overlapping match counting (matches VS/BS Studio behavior)
- Pre-compiled regex patterns for case-insensitive search
- Extension normalization to prevent .sql/.cs filtering bugs
"""

import os
import re
import difflib
from typing import List, Tuple, Optional, Set, Generator
from html import escape


def _normalize_ext(ext: str) -> str:
    """Normalize a file extension to always have a leading dot, lowercase."""
    ext = ext.strip().lower()
    if ext and not ext.startswith('.'):
        ext = '.' + ext
    return ext


def _normalize_ext_set(ext_string: str) -> Set[str]:
    """Parse comma-separated extension string into a normalized set."""
    if not ext_string:
        return set()
    result = set()
    for ext in ext_string.split(','):
        normed = _normalize_ext(ext)
        if normed:
            result.add(normed)
    return result


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
        # Parse comma-separated lists into normalized sets
        self.include_extensions = _normalize_ext_set(include_extensions)
        self.exclude_extensions = _normalize_ext_set(exclude_extensions)
        self.exclude_folders = self._parse_folders(exclude_folders)
        # Add always-excluded folders
        self.exclude_folders.update(self.ALWAYS_EXCLUDE_FOLDERS)

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

    def scan_directory(self, root_path: str) -> Generator[str, None, None]:
        """
        Recursively scan a directory for matching files.
        Yields absolute file paths (generator - no full list in memory).
        """
        if not os.path.isdir(root_path):
            return

        for dirpath, dirnames, filenames in os.walk(root_path):
            # Filter out excluded directories (modify in place to prevent descent)
            dirnames[:] = [
                d for d in dirnames
                if not self.should_exclude_folder(d) and not d.startswith('.')
            ]

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if self.should_include_file(file_path):
                    yield file_path

    def find_matches(
        self,
        content: str,
        search_pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = True
    ) -> List[Tuple[int, int, str]]:
        """
        Find all NON-OVERLAPPING matches of a pattern in content.
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
            # Plain text search — non-overlapping
            search_text = search_pattern
            search_content = content

            if not case_sensitive:
                search_text = search_pattern.lower()
                search_content = content.lower()

            pattern_len = len(search_pattern)
            start = 0
            while True:
                pos = search_content.find(search_text, start)
                if pos == -1:
                    break
                # Get the actual matched text (preserving original case)
                matched = content[pos:pos + pattern_len]
                matches.append((pos, pos + pattern_len, matched))
                # Advance past this match (non-overlapping)
                start = pos + pattern_len

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
        # Build a mapping from character offset to line number using bisect for speed
        line_starts = [0]
        for line in lines:
            line_starts.append(line_starts[-1] + len(line) + 1)  # +1 for \n

        results = []
        for start_pos, end_pos, matched_text in matches:
            # Binary search for line number (faster than linear scan)
            lo, hi = 0, len(line_starts) - 1
            while lo < hi:
                mid = (lo + hi) // 2
                if line_starts[mid] > start_pos:
                    hi = mid
                else:
                    lo = mid + 1
            line_num = lo - 1

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
        case_sensitive: bool = True,
        _compiled_pattern: 're.Pattern | None' = None,
    ) -> Tuple[str, int]:
        """
        Apply a replacement to content.
        Returns (new_content, replacement_count).
        Accepts optional _compiled_pattern for pre-compiled regex reuse.
        """
        if is_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                pat = _compiled_pattern or re.compile(search_pattern, flags)
                new_content, count = pat.subn(replacement_text, content)
                return new_content, count
            except re.error:
                return content, 0
        else:
            if case_sensitive:
                count = content.count(search_pattern)
                new_content = content.replace(search_pattern, replacement_text)
            else:
                # Use pre-compiled if available, else compile
                if _compiled_pattern:
                    new_content, count = _compiled_pattern.subn(replacement_text, content)
                else:
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

    Optimizations:
    - Pre-compiles regex patterns per rule
    - Normalizes target_extensions once per rule
    - Uses generator-based directory traversal
    - Deduplicates files across overlapping project roots
    """
    # Pre-process rules: normalize extensions and compile patterns
    processed_rules = []
    for rule in rules:
        compiled = None
        if rule.get('is_regex'):
            flags = 0 if rule.get('case_sensitive', True) else re.IGNORECASE
            try:
                compiled = re.compile(rule['search_pattern'], flags)
            except re.error:
                pass
        elif not rule.get('case_sensitive', True):
            # Pre-compile escaped pattern for case-insensitive plain text
            compiled = re.compile(re.escape(rule['search_pattern']), re.IGNORECASE)

        # Normalize target extensions
        target_exts = rule.get('target_extensions')
        normalized_exts = None
        if target_exts:
            normalized_exts = _normalize_ext_set(target_exts)

        processed_rules.append({
            **rule,
            '_compiled': compiled,
            '_normalized_exts': normalized_exts,
        })

    # Collect all files to scan (needed for total count in progress reporting)
    files_to_scan = []
    for root_path in root_paths:
        if not os.path.isdir(root_path):
            continue
        for file_path in scanner.scan_directory(root_path):
            files_to_scan.append((file_path, root_path))

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

        # Get the file extension once
        _, file_ext = os.path.splitext(file_path)
        file_ext_lower = file_ext.lower()

        # Apply all rules to get final content
        modified_content = original_content
        match_count = 0
        matches_found = False

        for prule in processed_rules:
            # Check if this rule applies to this file type (normalized comparison)
            normed_exts = prule['_normalized_exts']
            if normed_exts and file_ext_lower not in normed_exts:
                continue

            # Use pre-compiled pattern if available
            new_content, count = scanner.apply_replacement(
                modified_content,
                prule['search_pattern'],
                prule['replacement_text'],
                prule.get('is_regex', False),
                prule.get('case_sensitive', True),
                prule['_compiled'],
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
                'extension': file_ext_lower
            }
