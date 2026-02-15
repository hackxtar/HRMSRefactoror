"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============== Project Schemas ==============

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    root_path: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = "main"
    is_active: bool = True


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    root_path: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = None
    is_active: Optional[bool] = None


class ProjectResponse(ProjectBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== Scan Config Schemas ==============

class ScanConfigBase(BaseModel):
    include_extensions: str = ".cs,.ts,.tsx,.js,.jsx,.sql,.cshtml,.razor,.html,.css,.scss"
    exclude_extensions: str = ".dll,.exe,.pdb,.cache"
    exclude_folders: str = ".git,.vs,bin,obj,node_modules,packages,.idea,dist,build"


class ScanConfigUpdate(BaseModel):
    include_extensions: Optional[str] = None
    exclude_extensions: Optional[str] = None
    exclude_folders: Optional[str] = None


class ScanConfigResponse(ScanConfigBase):
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== Replacement Rule Schemas ==============

class RuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    search_pattern: str = Field(..., min_length=1)
    replacement_text: str
    is_regex: bool = False
    case_sensitive: bool = True
    target_extensions: Optional[str] = None  # e.g., ".cs,.sql"
    is_active: bool = True


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    search_pattern: Optional[str] = None
    replacement_text: Optional[str] = None
    is_regex: Optional[bool] = None
    case_sensitive: Optional[bool] = None
    target_extensions: Optional[str] = None
    is_active: Optional[bool] = None


class RuleResponse(RuleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RuleExportItem(RuleBase):
    """Single rule for import/export."""
    pass


class RuleBulkExport(BaseModel):
    """Bulk export wrapper."""
    exported_at: datetime
    count: int
    rules: List[RuleExportItem]


# ============== Dry Run / Scan Schemas ==============

class FileDiff(BaseModel):
    """Represents a single file with its diff preview."""
    file_path: str
    relative_path: str
    match_count: int
    diff_html: str  # HTML-formatted diff for display
    selected: bool = True  # Whether to include in execution


class DryRunRequest(BaseModel):
    """Request to scan files with given rules."""
    rule_ids: List[int]  # IDs of rules to apply
    project_ids: Optional[List[int]] = None  # If None, scan all active projects


class DryRunResponse(BaseModel):
    """Response from dry run scan."""
    total_files_scanned: int
    total_matches: int
    files: List[FileDiff]
    errors: List[str] = []


# ============== Execution Schemas ==============

class ExecuteRequest(BaseModel):
    """Request to execute replacements."""
    rule_ids: List[int]
    file_paths: List[str]  # Specific files to modify (from dry run selection)


class ExecuteResponse(BaseModel):
    """Response from execution."""
    execution_id: int
    total_files_modified: int
    total_replacements: int
    status: str
    errors: List[str] = []


# ============== History Schemas ==============

class ModifiedFileResponse(BaseModel):
    id: int
    file_path: str
    backup_path: Optional[str] = None
    replacements_count: int

    class Config:
        from_attributes = True


class HistoryResponse(BaseModel):
    id: int
    rule_id: int
    rule_name: Optional[str] = None
    executed_at: datetime
    total_files_scanned: int
    total_files_modified: int
    total_replacements: int
    status: str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class HistoryDetailResponse(HistoryResponse):
    modified_files: List[ModifiedFileResponse] = []

    class Config:
        from_attributes = True


# ============== Dashboard Schemas ==============

class DashboardStats(BaseModel):
    """Aggregate statistics for the dashboard."""
    total_projects: int
    active_projects: int
    total_rules: int
    active_rules: int
    total_executions: int
    total_replacements: int
    total_files_modified: int
    recent_executions: List[HistoryResponse] = []


# ============== Keyword Tracking Schemas ==============

class TrackingEntry(BaseModel):
    id: int
    execution_id: int
    rule_id: int
    rule_name: Optional[str] = None
    file_path: str
    line_number: int
    original_text: str
    replacement_text: str
    context_snippet: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TrackingResponse(BaseModel):
    total: int
    entries: List[TrackingEntry]


# ============== Git Schemas ==============

class GitStatusResponse(BaseModel):
    is_repo: bool
    branch: Optional[str] = None
    modified_files: List[dict] = []
    modified_count: int = 0
    ahead: int = 0
    behind: int = 0
    error: Optional[str] = None


class GitPullResponse(BaseModel):
    success: bool
    message: str


class AutoMergeResult(BaseModel):
    """Result of auto-merge for a single project."""
    project_name: str
    pull_success: bool
    pull_message: str
    rules_applied: int = 0
    replacements_made: int = 0


class AutoMergeResponse(BaseModel):
    """Overall auto-merge response."""
    results: List[AutoMergeResult]
    total_projects: int
    successful_pulls: int
    total_replacements: int


# ============== Deep Search Schemas ==============

class DeepSearchRequest(BaseModel):
    """Request for Deep Search variant generation."""
    rule_ids: List[int]


class DeepSearchSuggestion(BaseModel):
    """A single Deep Search suggestion."""
    original: str
    suggestion: str
    replacement: str
    category: str
    selected: bool = True
    source_rule: str = ""
    source_rule_id: Optional[int] = None


class DeepSearchResponse(BaseModel):
    """Response from Deep Search."""
    total: int
    suggestions: List[DeepSearchSuggestion]


class CustomScanRule(BaseModel):
    """An inline rule for custom scan."""
    search_pattern: str
    replacement_text: str
    case_sensitive: bool = False


class CustomScanRequest(BaseModel):
    """Request to scan with ad-hoc rules."""
    rules: List[CustomScanRule]
    project_ids: Optional[List[int]] = None


class DeepSearchPreviewFile(BaseModel):
    """A file found during deep search preview."""
    file_path: str
    relative_path: str
    match_count: int


class DeepSearchPatternResult(BaseModel):
    """Result for a single pattern during preview."""
    original: str
    replacement: str
    file_count: int
    total_matches: int
    files: List[DeepSearchPreviewFile] = []


class DeepSearchPreviewRequest(BaseModel):
    """Request for deep search preview scan."""
    patterns: List[CustomScanRule]
    project_ids: Optional[List[int]] = None


class DeepSearchPreviewResponse(BaseModel):
    """Response from deep search preview."""
    results: List[DeepSearchPatternResult]


class DeepSearchDiffRequest(BaseModel):
    """Request for on-demand diff generation."""
    file_path: str
    search_pattern: str
    replacement_text: str
    case_sensitive: bool = False


class DeepSearchDiffResponse(BaseModel):
    """Response with generated diff HTML."""
    diff_html: str


# ============== Rollback Schemas ==============

class RollbackResponse(BaseModel):
    execution_id: int
    files_restored: int
    files_failed: int
    errors: List[str] = []


# ============== ALTER SQL Schemas ==============

class AlterSqlRequest(BaseModel):
    """Request to generate ALTER SQL for a .sql file."""
    file_path: str
    search_pattern: str
    replacement_text: str
    sql_type: Optional[str] = None  # Auto-detect if not provided


class AlterSqlResponse(BaseModel):
    """Response with generated ALTER SQL script."""
    sql_type: str
    alter_sql: str
    warnings: List[str] = []

