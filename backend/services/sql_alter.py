"""
SQL ALTER Script Generator for the Refactoring Workbench.

Detects SQL object types (Table, TableType, View, StoredProcedure, Function)
from .sql file content and generates safe ALTER/sp_rename scripts that
preserve data and permissions.
"""

import re
import os
from typing import Optional, List, Tuple


# ============== SQL Object Type Detection ==============

# Ordered by specificity — more specific patterns checked first
_SQL_TYPE_PATTERNS = [
    # Table Type (must check before TABLE — "CREATE TYPE ... AS TABLE")
    (
        r'CREATE\s+TYPE\s+',
        'TABLE_TYPE'
    ),
    # View
    (
        r'(?:CREATE|ALTER)\s+VIEW\s+',
        'VIEW'
    ),
    # Stored Procedure
    (
        r'(?:CREATE|ALTER)\s+(?:PROCEDURE|PROC)\s+',
        'STORED_PROCEDURE'
    ),
    # Function
    (
        r'(?:CREATE|ALTER)\s+FUNCTION\s+',
        'FUNCTION'
    ),
    # Table (plain CREATE TABLE — checked last since other types contain TABLE keyword)
    (
        r'CREATE\s+TABLE\s+',
        'TABLE'
    ),
]

# Pre-compile patterns for performance
_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE | re.MULTILINE), sql_type)
    for pattern, sql_type in _SQL_TYPE_PATTERNS
]


def detect_sql_type(content: str, file_path: str = '') -> str:
    """
    Detect the SQL object type from file content.

    Checks content against known DDL patterns in priority order.
    Falls back to filename heuristics if content doesn't match.

    Returns one of: TABLE, TABLE_TYPE, VIEW, STORED_PROCEDURE, FUNCTION, UNKNOWN
    """
    # Content-based detection (most reliable)
    for compiled_re, sql_type in _COMPILED_PATTERNS:
        if compiled_re.search(content):
            return sql_type

    # Filename-based heuristic fallback
    if file_path:
        basename = os.path.basename(file_path).lower()
        if basename.startswith('sp') or basename.startswith('usp'):
            return 'STORED_PROCEDURE'
        if basename.startswith('vw') or basename.startswith('view'):
            return 'VIEW'
        if basename.startswith('fn') or basename.startswith('ufn'):
            return 'FUNCTION'
        if basename.startswith('tbl') or basename.startswith('table'):
            return 'TABLE'

    return 'UNKNOWN'


# ============== Object Name Extraction ==============

def _extract_object_name(content: str, sql_type: str) -> Optional[str]:
    """
    Extract the fully-qualified object name from SQL DDL.
    Returns the name including schema prefix if present (e.g., "dbo.EmployeeView").
    """
    patterns = {
        'TABLE': r'CREATE\s+TABLE\s+([\[\].\w]+)',
        'TABLE_TYPE': r'CREATE\s+TYPE\s+([\[\].\w]+)',
        'VIEW': r'(?:CREATE|ALTER)\s+VIEW\s+([\[\].\w]+)',
        'STORED_PROCEDURE': r'(?:CREATE|ALTER)\s+(?:PROCEDURE|PROC)\s+([\[\].\w]+)',
        'FUNCTION': r'(?:CREATE|ALTER)\s+FUNCTION\s+([\[\].\w]+)',
    }

    pattern = patterns.get(sql_type)
    if not pattern:
        return None

    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _strip_brackets(name: str) -> str:
    """Remove SQL bracket notation: [dbo].[MyTable] -> dbo.MyTable"""
    return name.replace('[', '').replace(']', '')


def _get_short_name(full_name: str) -> str:
    """Get the object name without schema: dbo.MyTable -> MyTable"""
    stripped = _strip_brackets(full_name)
    parts = stripped.split('.')
    return parts[-1] if parts else stripped


# ============== ALTER SQL Generation ==============

def generate_alter_sql(
    content: str,
    sql_type: str,
    search_pattern: str,
    replacement_text: str,
    file_path: str = ''
) -> dict:
    """
    Generate safe ALTER/RENAME SQL based on the detected object type.

    Strategy:
    - TABLE & TABLE_TYPE: sp_rename for renaming (preserves data)
    - VIEW, SP, FUNCTION: ALTER statement (preserves permissions)

    Returns dict with:
        sql_type: str
        alter_sql: str
        warnings: List[str]
    """
    warnings = []

    if sql_type == 'UNKNOWN':
        sql_type = detect_sql_type(content, file_path)

    object_name = _extract_object_name(content, sql_type)
    if not object_name:
        object_name = '<object_name>'
        warnings.append('Could not auto-detect object name from DDL. Please replace <object_name> manually.')

    if sql_type == 'TABLE':
        alter_sql = _generate_table_alter(content, object_name, search_pattern, replacement_text, warnings)
    elif sql_type == 'TABLE_TYPE':
        alter_sql = _generate_table_type_alter(content, object_name, search_pattern, replacement_text, warnings)
    elif sql_type == 'VIEW':
        alter_sql = _generate_view_alter(content, object_name, search_pattern, replacement_text, warnings)
    elif sql_type == 'STORED_PROCEDURE':
        alter_sql = _generate_sp_alter(content, object_name, search_pattern, replacement_text, warnings)
    elif sql_type == 'FUNCTION':
        alter_sql = _generate_function_alter(content, object_name, search_pattern, replacement_text, warnings)
    else:
        alter_sql = f"-- Could not determine SQL object type for this file.\n-- Please review manually.\n"
        warnings.append('Unknown SQL object type. Manual review recommended.')

    return {
        'sql_type': sql_type,
        'alter_sql': alter_sql.strip(),
        'warnings': warnings,
    }


def _generate_table_alter(
    content: str,
    object_name: str,
    search: str,
    replace: str,
    warnings: List[str]
) -> str:
    """
    Generate ALTER statements for TABLE objects.
    Uses sp_rename for column/table name changes to preserve data.
    """
    clean_name = _strip_brackets(object_name)
    short_name = _get_short_name(object_name)
    lines = []

    lines.append(f"-- ==============================================")
    lines.append(f"-- ALTER Script for TABLE: {clean_name}")
    lines.append(f"-- Keyword: '{search}' → '{replace}'")
    lines.append(f"-- Strategy: sp_rename (preserves data)")
    lines.append(f"-- ==============================================")
    lines.append(f"")

    # Check if the table name itself contains the search pattern
    if _contains_pattern(short_name, search):
        new_table_name = _apply_replacement(short_name, search, replace)
        lines.append(f"-- Rename the table itself")
        lines.append(f"EXEC sp_rename '{clean_name}', '{new_table_name}';")
        lines.append(f"GO")
        lines.append(f"")
        warnings.append(f'Table rename: {clean_name} → {new_table_name}. Update all references (views, SPs, code) accordingly.')

    # Find columns that match the search pattern
    column_names = _extract_column_names(content)
    matching_columns = [col for col in column_names if _contains_pattern(col, search)]

    if matching_columns:
        # Use the potentially-renamed table name for column renames
        effective_table = clean_name
        if _contains_pattern(short_name, search):
            # If table was renamed, use the schema + new name
            parts = clean_name.split('.')
            if len(parts) > 1:
                effective_table = f"{'.'.join(parts[:-1])}.{_apply_replacement(parts[-1], search, replace)}"
            else:
                effective_table = _apply_replacement(clean_name, search, replace)

        lines.append(f"-- Rename columns containing '{search}'")
        for col in matching_columns:
            new_col = _apply_replacement(col, search, replace)
            lines.append(f"EXEC sp_rename '{effective_table}.{col}', '{new_col}', 'COLUMN';")
            lines.append(f"GO")

        lines.append(f"")

    # Check for constraints, indexes, defaults that might reference the keyword
    constraint_names = _extract_constraint_names(content)
    matching_constraints = [c for c in constraint_names if _contains_pattern(c, search)]
    if matching_constraints:
        lines.append(f"-- Rename constraints/indexes containing '{search}'")
        for c_name in matching_constraints:
            new_c_name = _apply_replacement(c_name, search, replace)
            lines.append(f"EXEC sp_rename '{c_name}', '{new_c_name}', 'OBJECT';")
            lines.append(f"GO")
        lines.append(f"")
        warnings.append(f'Found {len(matching_constraints)} constraint(s)/index(es) referencing the keyword.')

    if not matching_columns and not _contains_pattern(short_name, search) and not matching_constraints:
        lines.append(f"-- No table/column/constraint names found matching '{search}'.")
        lines.append(f"-- The keyword may appear in comments or default values only.")
        lines.append(f"-- Review the file manually if needed.")

    return '\n'.join(lines)


def _generate_table_type_alter(
    content: str,
    object_name: str,
    search: str,
    replace: str,
    warnings: List[str]
) -> str:
    """
    Generate ALTER statements for TABLE TYPE (user-defined table type).
    Uses sp_rename for the type name.
    """
    clean_name = _strip_brackets(object_name)
    short_name = _get_short_name(object_name)
    lines = []

    lines.append(f"-- ==============================================")
    lines.append(f"-- ALTER Script for TABLE TYPE: {clean_name}")
    lines.append(f"-- Keyword: '{search}' → '{replace}'")
    lines.append(f"-- Strategy: sp_rename (preserves type)")
    lines.append(f"-- ==============================================")
    lines.append(f"")

    if _contains_pattern(short_name, search):
        new_type_name = _apply_replacement(short_name, search, replace)
        lines.append(f"-- Rename the table type")
        lines.append(f"EXEC sp_rename '{clean_name}', '{new_type_name}', 'USERDATATYPE';")
        lines.append(f"GO")
        lines.append(f"")
        warnings.append(f'Table type rename: {clean_name} → {new_type_name}. Update all SP parameters referencing this type.')

    # Also check column names inside the type definition
    column_names = _extract_column_names(content)
    matching_columns = [col for col in column_names if _contains_pattern(col, search)]

    if matching_columns:
        lines.append(f"-- ⚠️ Table Types do NOT support column rename via sp_rename.")
        lines.append(f"-- You must DROP and re-CREATE the type to rename columns.")
        lines.append(f"-- Below is the re-created type with replacements applied:")
        lines.append(f"")
        # Generate the full DROP/CREATE with replacements
        new_content = _case_insensitive_replace(content, search, replace)
        lines.append(f"-- First, check dependencies:")
        lines.append(f"-- SELECT * FROM sys.dm_sql_referencing_entities('{clean_name}', 'TYPE');")
        lines.append(f"")
        lines.append(f"-- DROP TYPE {clean_name};")
        lines.append(f"-- GO")
        lines.append(f"")
        lines.append(new_content.strip())
        lines.append(f"GO")
        warnings.append(f'Table type column rename requires DROP/CREATE. Check dependencies first!')

    if not matching_columns and not _contains_pattern(short_name, search):
        lines.append(f"-- No type/column names found matching '{search}'.")
        lines.append(f"-- Review the file manually if needed.")

    return '\n'.join(lines)


def _generate_view_alter(
    content: str,
    object_name: str,
    search: str,
    replace: str,
    warnings: List[str]
) -> str:
    """
    Generate ALTER VIEW statement.
    Replaces CREATE VIEW with ALTER VIEW and applies keyword replacements.
    Preserves permissions.
    """
    clean_name = _strip_brackets(object_name)
    lines = []

    lines.append(f"-- ==============================================")
    lines.append(f"-- ALTER Script for VIEW: {clean_name}")
    lines.append(f"-- Keyword: '{search}' → '{replace}'")
    lines.append(f"-- Strategy: ALTER VIEW (preserves permissions)")
    lines.append(f"-- ==============================================")
    lines.append(f"")

    # Replace CREATE with ALTER and apply keyword replacements
    altered = _replace_create_with_alter(content, 'VIEW')
    altered = _case_insensitive_replace(altered, search, replace)

    lines.append(altered.strip())
    lines.append(f"GO")

    warnings.append('Review the ALTER VIEW output to ensure column aliases and references are correct.')
    return '\n'.join(lines)


def _generate_sp_alter(
    content: str,
    object_name: str,
    search: str,
    replace: str,
    warnings: List[str]
) -> str:
    """
    Generate ALTER PROCEDURE statement.
    Replaces CREATE with ALTER and applies keyword replacements.
    Preserves permissions.
    """
    clean_name = _strip_brackets(object_name)
    lines = []

    lines.append(f"-- ==============================================")
    lines.append(f"-- ALTER Script for STORED PROCEDURE: {clean_name}")
    lines.append(f"-- Keyword: '{search}' → '{replace}'")
    lines.append(f"-- Strategy: ALTER PROCEDURE (preserves permissions)")
    lines.append(f"-- ==============================================")
    lines.append(f"")

    # Replace CREATE with ALTER and apply keyword replacements
    altered = _replace_create_with_alter(content, 'PROCEDURE')
    # Also handle CREATE PROC shorthand
    altered = _replace_create_with_alter(altered, 'PROC')
    altered = _case_insensitive_replace(altered, search, replace)

    lines.append(altered.strip())
    lines.append(f"GO")

    warnings.append('Review parameter names and internal references after replacement.')
    return '\n'.join(lines)


def _generate_function_alter(
    content: str,
    object_name: str,
    search: str,
    replace: str,
    warnings: List[str]
) -> str:
    """
    Generate ALTER FUNCTION statement.
    Replaces CREATE with ALTER and applies keyword replacements.
    Preserves permissions.
    """
    clean_name = _strip_brackets(object_name)
    lines = []

    lines.append(f"-- ==============================================")
    lines.append(f"-- ALTER Script for FUNCTION: {clean_name}")
    lines.append(f"-- Keyword: '{search}' → '{replace}'")
    lines.append(f"-- Strategy: ALTER FUNCTION (preserves permissions)")
    lines.append(f"-- ==============================================")
    lines.append(f"")

    altered = _replace_create_with_alter(content, 'FUNCTION')
    altered = _case_insensitive_replace(altered, search, replace)

    lines.append(altered.strip())
    lines.append(f"GO")

    warnings.append('Review return types and internal table references after replacement.')
    return '\n'.join(lines)


# ============== Helper Functions ==============

def _contains_pattern(text: str, pattern: str) -> bool:
    """Case-insensitive check if text contains pattern."""
    return pattern.lower() in text.lower()


def _apply_replacement(text: str, search: str, replace: str) -> str:
    """Case-insensitive replacement preserving original casing style."""
    result = re.sub(re.escape(search), replace, text, flags=re.IGNORECASE)
    return result


def _case_insensitive_replace(content: str, search: str, replace: str) -> str:
    """Apply case-insensitive find-replace across full content."""
    return re.sub(re.escape(search), replace, content, flags=re.IGNORECASE)


def _replace_create_with_alter(content: str, object_keyword: str) -> str:
    """
    Replace 'CREATE <keyword>' with 'ALTER <keyword>' in SQL content.
    Handles optional OR ALTER syntax: CREATE OR ALTER -> ALTER
    """
    # First handle CREATE OR ALTER -> ALTER
    content = re.sub(
        r'CREATE\s+OR\s+ALTER\s+' + object_keyword,
        f'ALTER {object_keyword}',
        content,
        count=1,
        flags=re.IGNORECASE
    )
    # Then handle plain CREATE -> ALTER
    content = re.sub(
        r'CREATE\s+' + object_keyword,
        f'ALTER {object_keyword}',
        content,
        count=1,
        flags=re.IGNORECASE
    )
    return content


def _extract_column_names(content: str) -> List[str]:
    """
    Extract column names from CREATE TABLE / CREATE TYPE definitions.
    Matches patterns like:
        ColumnName INT,
        [ColumnName] NVARCHAR(50),
        @ColumnName INT  (for table type parameters)
    """
    columns = []

    # Find the column definition block (between first ( and matching ))
    # Look for the block after CREATE TABLE/TYPE ... AS TABLE (
    paren_match = re.search(r'\(\s*\n', content)
    if not paren_match:
        paren_match = re.search(r'\(', content)
    if not paren_match:
        return columns

    start = paren_match.end()
    depth = 1
    end = start
    for i in range(start, len(content)):
        if content[i] == '(':
            depth += 1
        elif content[i] == ')':
            depth -= 1
            if depth == 0:
                end = i
                break

    block = content[start:end]

    # Match column definitions — column name followed by a data type
    # Handles: ColumnName, [ColumnName], @ColumnName
    col_pattern = re.compile(
        r'^\s*[\[@]?(\w+)[\]]?\s+(?:INT|BIGINT|SMALLINT|TINYINT|BIT|DECIMAL|NUMERIC|FLOAT|REAL|'
        r'MONEY|SMALLMONEY|DATE|DATETIME|DATETIME2|DATETIMEOFFSET|SMALLDATETIME|TIME|'
        r'CHAR|VARCHAR|NCHAR|NVARCHAR|TEXT|NTEXT|BINARY|VARBINARY|IMAGE|'
        r'UNIQUEIDENTIFIER|XML|SQL_VARIANT|HIERARCHYID|GEOGRAPHY|GEOMETRY|TABLE)',
        re.IGNORECASE | re.MULTILINE
    )

    for match in col_pattern.finditer(block):
        col_name = match.group(1)
        # Exclude SQL keywords that might false-match
        if col_name.upper() not in ('CONSTRAINT', 'PRIMARY', 'FOREIGN', 'UNIQUE', 'INDEX',
                                     'CHECK', 'DEFAULT', 'KEY', 'REFERENCES', 'CLUSTERED',
                                     'NONCLUSTERED', 'ASC', 'DESC', 'WITH', 'ON', 'NOT',
                                     'NULL', 'IDENTITY', 'AS', 'BEGIN', 'END', 'RETURN',
                                     'DECLARE', 'SET', 'IF', 'ELSE', 'WHILE', 'GO'):
            columns.append(col_name)

    return columns


def _extract_constraint_names(content: str) -> List[str]:
    """
    Extract named constraints, indexes, and defaults from SQL content.
    Matches patterns like: CONSTRAINT PK_TableName, INDEX IX_TableName
    """
    constraints = []

    patterns = [
        r'CONSTRAINT\s+([\[\]\w.]+)',
        r'INDEX\s+([\[\]\w.]+)',
        r'DEFAULT\s+.*?\s+FOR\s+.*?\s+--\s*DF_([\w]+)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            name = _strip_brackets(match.group(1))
            constraints.append(name)

    return constraints
