"""
SQLAlchemy ORM models for the Refactoring Workbench.
Defines the database schema for projects, rules, and execution history.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Project(Base):
    """
    Stores configuration for each sub-application/project.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # e.g., "ASP.NET Legacy", "Angular Frontend"
    root_path = Column(String(500), nullable=False)  # e.g., "C:\\Projects\\LegacyApp"
    description = Column(Text, nullable=True)
    git_repo_url = Column(String(500), nullable=True)  # e.g., "https://github.com/org/repo.git"
    git_branch = Column(String(100), nullable=True, default="main")  # e.g., "main", "develop"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ScanConfig(Base):
    """
    Global scan configuration for file filtering.
    """
    __tablename__ = "scan_config"

    id = Column(Integer, primary_key=True, index=True)
    include_extensions = Column(Text, default=".cs,.ts,.tsx,.js,.jsx,.sql,.cshtml,.razor,.html,.css,.scss")
    exclude_extensions = Column(Text, default=".dll,.exe,.pdb,.cache")
    exclude_folders = Column(Text, default=".git,.vs,bin,obj,node_modules,packages,.idea,dist,build")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ReplacementRule(Base):
    """
    The Rule Engine: stores search/replace patterns.
    These rules persist and can be re-applied when new code is pulled.
    """
    __tablename__ = "replacement_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)  # e.g., "CNIC to NationalID"
    description = Column(Text, nullable=True)
    search_pattern = Column(Text, nullable=False)  # The pattern to find
    replacement_text = Column(Text, nullable=False)  # What to replace with
    is_regex = Column(Boolean, default=False)  # True for regex, False for plain text
    case_sensitive = Column(Boolean, default=True)
    target_extensions = Column(Text, nullable=True)  # Comma-separated, e.g., ".cs,.sql" (null = all)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to execution history
    executions = relationship("ExecutionHistory", back_populates="rule")
    tracking_entries = relationship("KeywordTrackingEntry", back_populates="rule")


class ExecutionHistory(Base):
    """
    Audit trail: logs every refactoring execution.
    """
    __tablename__ = "execution_history"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("replacement_rules.id"), nullable=False)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
    total_files_scanned = Column(Integer, default=0)
    total_files_modified = Column(Integer, default=0)
    total_replacements = Column(Integer, default=0)
    projects_included = Column(Text, nullable=True)  # JSON array of project IDs
    status = Column(String(50), default="completed")  # completed, failed, partial
    error_message = Column(Text, nullable=True)

    # Relationships
    rule = relationship("ReplacementRule", back_populates="executions")
    modified_files = relationship("ModifiedFile", back_populates="execution", cascade="all, delete-orphan")
    tracking_entries = relationship("KeywordTrackingEntry", back_populates="execution", cascade="all, delete-orphan")


class ModifiedFile(Base):
    """
    Tracks individual files modified in each execution.
    Enables granular audit and potential rollback.
    """
    __tablename__ = "modified_files"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("execution_history.id"), nullable=False)
    file_path = Column(String(1000), nullable=False)
    backup_path = Column(String(1000), nullable=True)  # Path to .bak file
    replacements_count = Column(Integer, default=0)
    original_content_hash = Column(String(64), nullable=True)  # SHA-256 for verification

    # Relationship
    execution = relationship("ExecutionHistory", back_populates="modified_files")


class KeywordTrackingEntry(Base):
    """
    Granular audit: one row per individual replacement occurrence.
    Tracks exactly what was replaced, where, and by which rule.
    """
    __tablename__ = "keyword_tracking"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("execution_history.id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("replacement_rules.id"), nullable=False)
    file_path = Column(String(1000), nullable=False)
    line_number = Column(Integer, nullable=False)
    original_text = Column(Text, nullable=False)  # The matched text
    replacement_text = Column(Text, nullable=False)  # What it was replaced with
    context_snippet = Column(Text, nullable=True)  # Surrounding lines for context
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    execution = relationship("ExecutionHistory", back_populates="tracking_entries")
    rule = relationship("ReplacementRule", back_populates="tracking_entries")
