"""
Main FastAPI application for the Refactoring Workbench.
Provides REST API endpoints for managing projects, rules, executing refactors,
keyword tracking, Git integration, and dashboard statistics.
"""

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func as sqla_func
from typing import List, Optional
from datetime import datetime
import json
import os

from .database import get_db, init_db, engine, Base
from . import models, schemas
from .services.scanner import FileScanner, scan_files_with_rules
from .services.refactor import RefactorExecutor, restore_from_backup
from .services import git_service

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Refactoring Workbench",
    description="A tool to safely find, replace, and track keyword changes across legacy repositories.",
    version="2.0.0"
)

# Get the directory of this file to serve frontend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Default project seed data
DEFAULT_PROJECTS = [
    {"name": "ESS Legacy (ASP.NET)", "root_path": r"C:\Users\SAIF\Desktop\Projects\HRMS\Payroll-Web-Payroll\Payroll Web Payroll", "description": "Legacy ASP.NET Web Forms application"},
    {"name": "ESS API (Core API)", "root_path": r"C:\Users\SAIF\Desktop\Projects\HRMS\Payroll-Web-Payroll\CoreAPI", "description": ".NET Core REST API for ESS"},
    {"name": "ESS Logic", "root_path": r"C:\Users\SAIF\Desktop\Projects\HRMS\Payroll-Web-Payroll\Logic", "description": "Shared C# business logic library for ESS"},
    {"name": "ESS Angular", "root_path": r"C:\Users\SAIF\Desktop\Projects\HRMS\ESS_Angular\src", "description": "Angular frontend SPA"},
    {"name": "HRMS Windows (WinForms)", "root_path": r"C:\Users\SAIF\Desktop\Projects\HRMS\HRMS-Windows\Payroll", "description": "Windows desktop .NET WinForms application"},
    {"name": "HRMS API (Core API)", "root_path": r"C:\Users\SAIF\Desktop\Projects\HRMS\HRMS-Windows\CoreAPI", "description": ".NET Core REST API for HRMS"},
    {"name": "HRMS Logic", "root_path": r"C:\Users\SAIF\Desktop\Projects\HRMS\HRMS-Windows\Logic", "description": "Shared C# business logic library for HRMS"},
    {"name": "Database (SP/Views/Tables)", "root_path": r"C:\Users\SAIF\Desktop\Projects\HRMS\Payroll-Web-Payroll\DB", "description": "SQL stored procedures, views, tables, functions"},
]


# ============== Startup Event ==============

@app.on_event("startup")
async def startup_event():
    """Initialize database and seed data on startup."""
    init_db()

    db = next(get_db())
    try:
        # Create default scan config if not exists
        config = db.query(models.ScanConfig).first()
        if not config:
            config = models.ScanConfig()
            db.add(config)
            db.commit()

        # Seed default projects if table is empty
        project_count = db.query(models.Project).count()
        if project_count == 0:
            for proj_data in DEFAULT_PROJECTS:
                project = models.Project(**proj_data)
                db.add(project)
            db.commit()
    finally:
        db.close()


# ============== Dashboard Endpoint ==============

@app.get("/api/dashboard", response_model=schemas.DashboardStats)
def get_dashboard(db: Session = Depends(get_db)):
    """Get aggregate statistics for the dashboard."""
    total_projects = db.query(models.Project).count()
    active_projects = db.query(models.Project).filter(models.Project.is_active == True).count()
    total_rules = db.query(models.ReplacementRule).count()
    active_rules = db.query(models.ReplacementRule).filter(models.ReplacementRule.is_active == True).count()
    total_executions = db.query(models.ExecutionHistory).count()

    agg = db.query(
        sqla_func.coalesce(sqla_func.sum(models.ExecutionHistory.total_replacements), 0),
        sqla_func.coalesce(sqla_func.sum(models.ExecutionHistory.total_files_modified), 0),
    ).first()
    total_replacements = int(agg[0])
    total_files_modified = int(agg[1])

    # Recent executions
    recent = db.query(models.ExecutionHistory).order_by(
        models.ExecutionHistory.executed_at.desc()
    ).limit(5).all()

    recent_list = []
    for ex in recent:
        resp = schemas.HistoryResponse.model_validate(ex)
        if ex.rule:
            resp.rule_name = ex.rule.name
        recent_list.append(resp)

    return schemas.DashboardStats(
        total_projects=total_projects,
        active_projects=active_projects,
        total_rules=total_rules,
        active_rules=active_rules,
        total_executions=total_executions,
        total_replacements=total_replacements,
        total_files_modified=total_files_modified,
        recent_executions=recent_list,
    )


# ============== Project Endpoints ==============

@app.get("/api/projects", response_model=List[schemas.ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """List all configured projects."""
    return db.query(models.Project).order_by(models.Project.name).all()


@app.post("/api/projects", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project configuration."""
    db_project = models.Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@app.get("/api/projects/{project_id}", response_model=schemas.ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get a specific project by ID."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.put("/api/projects/{project_id}", response_model=schemas.ProjectResponse)
def update_project(project_id: int, project: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    """Update a project configuration."""
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)

    db.commit()
    db.refresh(db_project)
    return db_project


@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project configuration."""
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(db_project)
    db.commit()


# ============== Scan Config Endpoints ==============

@app.get("/api/config", response_model=schemas.ScanConfigResponse)
def get_scan_config(db: Session = Depends(get_db)):
    """Get the current scan configuration."""
    config = db.query(models.ScanConfig).first()
    if not config:
        config = models.ScanConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@app.put("/api/config", response_model=schemas.ScanConfigResponse)
def update_scan_config(config: schemas.ScanConfigUpdate, db: Session = Depends(get_db)):
    """Update the scan configuration."""
    db_config = db.query(models.ScanConfig).first()
    if not db_config:
        db_config = models.ScanConfig()
        db.add(db_config)

    update_data = config.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)

    db.commit()
    db.refresh(db_config)
    return db_config


# ============== Replacement Rule Endpoints ==============

@app.get("/api/rules", response_model=List[schemas.RuleResponse])
def list_rules(active_only: bool = False, db: Session = Depends(get_db)):
    """List all replacement rules."""
    query = db.query(models.ReplacementRule)
    if active_only:
        query = query.filter(models.ReplacementRule.is_active == True)
    return query.order_by(models.ReplacementRule.name).all()


@app.post("/api/rules", response_model=schemas.RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(rule: schemas.RuleCreate, db: Session = Depends(get_db)):
    """Create a new replacement rule."""
    db_rule = models.ReplacementRule(**rule.model_dump())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule


@app.get("/api/rules/{rule_id}", response_model=schemas.RuleResponse)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    """Get a specific rule by ID."""
    rule = db.query(models.ReplacementRule).filter(models.ReplacementRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@app.put("/api/rules/{rule_id}", response_model=schemas.RuleResponse)
def update_rule(rule_id: int, rule: schemas.RuleUpdate, db: Session = Depends(get_db)):
    """Update a replacement rule."""
    db_rule = db.query(models.ReplacementRule).filter(models.ReplacementRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = rule.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_rule, key, value)

    db.commit()
    db.refresh(db_rule)
    return db_rule


@app.delete("/api/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete a replacement rule."""
    db_rule = db.query(models.ReplacementRule).filter(models.ReplacementRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete(db_rule)
    db.commit()


# ============== Rule Import/Export ==============

@app.get("/api/rules/export")
def export_rules(db: Session = Depends(get_db)):
    """Export all rules as JSON."""
    rules = db.query(models.ReplacementRule).order_by(models.ReplacementRule.name).all()
    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "count": len(rules),
        "rules": [
            {
                "name": r.name,
                "description": r.description,
                "search_pattern": r.search_pattern,
                "replacement_text": r.replacement_text,
                "is_regex": r.is_regex,
                "case_sensitive": r.case_sensitive,
                "target_extensions": r.target_extensions,
                "is_active": r.is_active,
            }
            for r in rules
        ]
    }
    return JSONResponse(content=export_data)


@app.post("/api/rules/import", status_code=status.HTTP_201_CREATED)
def import_rules(data: schemas.RuleBulkExport, db: Session = Depends(get_db)):
    """Import rules from JSON. Creates new rules (does not overwrite existing)."""
    created = 0
    for rule_data in data.rules:
        db_rule = models.ReplacementRule(**rule_data.model_dump())
        db.add(db_rule)
        created += 1

    db.commit()
    return {"imported": created}


# ============== Dry Run / Scan Endpoint ==============

@app.post("/api/scan")
def dry_run_scan(request: schemas.DryRunRequest, db: Session = Depends(get_db)):
    """
    Perform a dry run scan (Streaming Response).
    Finds all matches and streams progress + results.
    """
    # Get scan config
    config = db.query(models.ScanConfig).first()
    if not config:
        config = models.ScanConfig()

    # Get rules
    rules = db.query(models.ReplacementRule).filter(
        models.ReplacementRule.id.in_(request.rule_ids),
        models.ReplacementRule.is_active == True
    ).all()

    if not rules:
        raise HTTPException(status_code=400, detail="No active rules found with the provided IDs")

    # Get project paths
    if request.project_ids:
        projects = db.query(models.Project).filter(
            models.Project.id.in_(request.project_ids),
            models.Project.is_active == True
        ).all()
    else:
        projects = db.query(models.Project).filter(models.Project.is_active == True).all()

    if not projects:
        raise HTTPException(status_code=400, detail="No active projects configured")

    # Create scanner with config
    scanner = FileScanner(
        include_extensions=config.include_extensions,
        exclude_extensions=config.exclude_extensions,
        exclude_folders=config.exclude_folders
    )

    # Prepare rules as dicts
    rule_dicts = [
        {
            'search_pattern': r.search_pattern,
            'replacement_text': r.replacement_text,
            'is_regex': r.is_regex,
            'case_sensitive': r.case_sensitive,
            'target_extensions': r.target_extensions
        }
        for r in rules
    ]

    root_paths = [p.root_path for p in projects]
    valid_paths = [p for p in root_paths if os.path.isdir(p)]

    # Generator for streaming response
    def event_generator():
        try:
            for item in scan_files_with_rules(valid_paths, rule_dicts, scanner):
                yield json.dumps(item) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


# ============== Execute Endpoint ==============

@app.post("/api/execute", response_model=schemas.ExecuteResponse)
def execute_refactor(request: schemas.ExecuteRequest, db: Session = Depends(get_db)):
    """
    Execute the refactoring on selected files.
    Creates backups, logs the execution, and saves keyword tracking data.
    """
    # Get rules
    rules = db.query(models.ReplacementRule).filter(
        models.ReplacementRule.id.in_(request.rule_ids),
        models.ReplacementRule.is_active == True
    ).all()

    if not rules:
        raise HTTPException(status_code=400, detail="No active rules found")

    if not request.file_paths:
        raise HTTPException(status_code=400, detail="No files selected for refactoring")

    # Validate all files exist
    for path in request.file_paths:
        if not os.path.isfile(path):
            raise HTTPException(status_code=400, detail=f"File not found: {path}")

    # Prepare rule dicts (include rule_id for tracking)
    rule_dicts = [
        {
            'rule_id': r.id,
            'search_pattern': r.search_pattern,
            'replacement_text': r.replacement_text,
            'is_regex': r.is_regex,
            'case_sensitive': r.case_sensitive,
            'target_extensions': r.target_extensions
        }
        for r in rules
    ]

    # Execute refactor
    executor = RefactorExecutor(create_backups=True)
    result = executor.execute_batch(request.file_paths, rule_dicts)

    # Create execution history record (use first rule for tracking)
    execution = models.ExecutionHistory(
        rule_id=rules[0].id,
        total_files_scanned=len(request.file_paths),
        total_files_modified=result['files_modified'],
        total_replacements=result['total_replacements'],
        projects_included=str([r.id for r in rules]),
        status="completed" if not result['errors'] else "partial"
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    # Add modified files to history
    for file_result in result['files']:
        if file_result['replacements_count'] > 0:
            mod_file = models.ModifiedFile(
                execution_id=execution.id,
                file_path=file_result['file_path'],
                backup_path=file_result['backup_path'],
                replacements_count=file_result['replacements_count'],
                original_content_hash=file_result['original_hash']
            )
            db.add(mod_file)

    # Save keyword tracking entries
    for entry in result.get('tracking', []):
        if entry.get('rule_id'):
            tracking = models.KeywordTrackingEntry(
                execution_id=execution.id,
                rule_id=entry['rule_id'],
                file_path=entry['file_path'],
                line_number=entry['line_number'],
                original_text=entry['original_text'],
                replacement_text=entry['replacement_text'],
                context_snippet=entry.get('context_snippet', ''),
            )
            db.add(tracking)

    db.commit()

    return schemas.ExecuteResponse(
        execution_id=execution.id,
        total_files_modified=result['files_modified'],
        total_replacements=result['total_replacements'],
        status=execution.status,
        errors=result['errors']
    )


# ============== Keyword Tracking Endpoints ==============

@app.get("/api/tracking", response_model=schemas.TrackingResponse)
def get_tracking(
    rule_id: Optional[int] = None,
    file_path: Optional[str] = None,
    execution_id: Optional[int] = None,
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get keyword tracking entries with optional filters."""
    query = db.query(models.KeywordTrackingEntry)

    if rule_id:
        query = query.filter(models.KeywordTrackingEntry.rule_id == rule_id)
    if execution_id:
        query = query.filter(models.KeywordTrackingEntry.execution_id == execution_id)
    if file_path:
        query = query.filter(models.KeywordTrackingEntry.file_path.contains(file_path))

    total = query.count()
    entries = query.order_by(models.KeywordTrackingEntry.id.desc()).offset(offset).limit(limit).all()

    entry_list = []
    for e in entries:
        resp = schemas.TrackingEntry.model_validate(e)
        if e.rule:
            resp.rule_name = e.rule.name
        entry_list.append(resp)

    return schemas.TrackingResponse(total=total, entries=entry_list)


@app.get("/api/tracking/export")
def export_tracking(
    rule_id: Optional[int] = None,
    execution_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Export tracking data as JSON."""
    query = db.query(models.KeywordTrackingEntry)

    if rule_id:
        query = query.filter(models.KeywordTrackingEntry.rule_id == rule_id)
    if execution_id:
        query = query.filter(models.KeywordTrackingEntry.execution_id == execution_id)

    entries = query.order_by(models.KeywordTrackingEntry.id).all()

    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "total": len(entries),
        "entries": [
            {
                "execution_id": e.execution_id,
                "rule_name": e.rule.name if e.rule else str(e.rule_id),
                "file_path": e.file_path,
                "line_number": e.line_number,
                "original_text": e.original_text,
                "replacement_text": e.replacement_text,
                "context_snippet": e.context_snippet,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]
    }
    return JSONResponse(content=export_data)


# ============== History Endpoints ==============

@app.get("/api/history", response_model=List[schemas.HistoryResponse])
def list_execution_history(limit: int = 50, db: Session = Depends(get_db)):
    """List execution history (most recent first)."""
    executions = db.query(models.ExecutionHistory).order_by(
        models.ExecutionHistory.executed_at.desc()
    ).limit(limit).all()

    result = []
    for exec in executions:
        response = schemas.HistoryResponse.model_validate(exec)
        if exec.rule:
            response.rule_name = exec.rule.name
        result.append(response)

    return result


@app.get("/api/history/{execution_id}", response_model=schemas.HistoryDetailResponse)
def get_execution_detail(execution_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific execution."""
    execution = db.query(models.ExecutionHistory).filter(
        models.ExecutionHistory.id == execution_id
    ).first()

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    response = schemas.HistoryDetailResponse.model_validate(execution)
    if execution.rule:
        response.rule_name = execution.rule.name

    return response


# ============== Rollback Endpoint ==============

@app.post("/api/rollback/{execution_id}", response_model=schemas.RollbackResponse)
def rollback_execution(execution_id: int, db: Session = Depends(get_db)):
    """Restore files from backups for a given execution."""
    execution = db.query(models.ExecutionHistory).filter(
        models.ExecutionHistory.id == execution_id
    ).first()

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    files_restored = 0
    files_failed = 0
    errors = []

    for mod_file in execution.modified_files:
        if mod_file.backup_path and os.path.exists(mod_file.backup_path):
            success = restore_from_backup(mod_file.file_path)
            if success:
                files_restored += 1
            else:
                files_failed += 1
                errors.append(f"Failed to restore: {mod_file.file_path}")
        else:
            files_failed += 1
            errors.append(f"Backup not found for: {mod_file.file_path}")

    return schemas.RollbackResponse(
        execution_id=execution_id,
        files_restored=files_restored,
        files_failed=files_failed,
        errors=errors
    )


# ============== Git Endpoints ==============

@app.post("/api/git/status/{project_id}", response_model=schemas.GitStatusResponse)
def git_status(project_id: int, db: Session = Depends(get_db)):
    """Get Git status for a project."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find the git root (may be a parent of root_path)
    git_root = git_service.find_git_root(project.root_path)
    if not git_root:
        return schemas.GitStatusResponse(is_repo=False, error="Not a Git repository")

    result = git_service.get_status(git_root)
    return schemas.GitStatusResponse(**result)


@app.post("/api/git/pull/{project_id}", response_model=schemas.GitPullResponse)
def git_pull(project_id: int, db: Session = Depends(get_db)):
    """Pull latest changes for a project."""
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    git_root = git_service.find_git_root(project.root_path)
    if not git_root:
        return schemas.GitPullResponse(success=False, message="Not a Git repository")

    result = git_service.pull(git_root)
    return schemas.GitPullResponse(**result)


@app.post("/api/git/auto-merge", response_model=schemas.AutoMergeResponse)
def auto_merge(db: Session = Depends(get_db)):
    """
    Auto-merge workflow: pull all projects, then re-apply active rules.
    This is the key CI integration feature.
    """
    projects = db.query(models.Project).filter(models.Project.is_active == True).all()
    active_rules = db.query(models.ReplacementRule).filter(
        models.ReplacementRule.is_active == True
    ).all()

    config = db.query(models.ScanConfig).first()
    if not config:
        config = models.ScanConfig()

    results = []
    total_replacements = 0
    successful_pulls = 0

    for project in projects:
        merge_result = schemas.AutoMergeResult(
            project_name=project.name,
            pull_success=False,
            pull_message="",
        )

        # Step 1: Pull latest code
        git_root = git_service.find_git_root(project.root_path)
        if git_root:
            pull_result = git_service.pull(git_root)
            merge_result.pull_success = pull_result["success"]
            merge_result.pull_message = pull_result["message"]
            if pull_result["success"]:
                successful_pulls += 1
        else:
            merge_result.pull_message = "Not a Git repository — skipped pull"
            merge_result.pull_success = True  # Not a failure if not a repo

        # Step 2: Re-apply active rules
        if active_rules and os.path.isdir(project.root_path):
            scanner = FileScanner(
                include_extensions=config.include_extensions,
                exclude_extensions=config.exclude_extensions,
                exclude_folders=config.exclude_folders
            )
            files = scanner.scan_directory(project.root_path)

            rule_dicts = [
                {
                    'rule_id': r.id,
                    'search_pattern': r.search_pattern,
                    'replacement_text': r.replacement_text,
                    'is_regex': r.is_regex,
                    'case_sensitive': r.case_sensitive,
                    'target_extensions': r.target_extensions
                }
                for r in active_rules
            ]

            executor = RefactorExecutor(create_backups=True)
            batch_result = executor.execute_batch(files, rule_dicts)

            merge_result.rules_applied = len(active_rules)
            merge_result.replacements_made = batch_result['total_replacements']
            total_replacements += batch_result['total_replacements']

            # Save tracking entries
            if batch_result['total_replacements'] > 0:
                execution = models.ExecutionHistory(
                    rule_id=active_rules[0].id,
                    total_files_scanned=len(files),
                    total_files_modified=batch_result['files_modified'],
                    total_replacements=batch_result['total_replacements'],
                    projects_included=str(project.id),
                    status="completed" if not batch_result['errors'] else "partial"
                )
                db.add(execution)
                db.commit()
                db.refresh(execution)

                for file_result in batch_result['files']:
                    if file_result['replacements_count'] > 0:
                        mod_file = models.ModifiedFile(
                            execution_id=execution.id,
                            file_path=file_result['file_path'],
                            backup_path=file_result['backup_path'],
                            replacements_count=file_result['replacements_count'],
                            original_content_hash=file_result['original_hash']
                        )
                        db.add(mod_file)

                for entry in batch_result.get('tracking', []):
                    if entry.get('rule_id'):
                        tracking = models.KeywordTrackingEntry(
                            execution_id=execution.id,
                            rule_id=entry['rule_id'],
                            file_path=entry['file_path'],
                            line_number=entry['line_number'],
                            original_text=entry['original_text'],
                            replacement_text=entry['replacement_text'],
                            context_snippet=entry.get('context_snippet', ''),
                        )
                        db.add(tracking)

                db.commit()

        results.append(merge_result)

    return schemas.AutoMergeResponse(
        results=results,
        total_projects=len(projects),
        successful_pulls=successful_pulls,
        total_replacements=total_replacements,
    )


# ============== Utilities ==============

@app.get("/api/utils/browse")
def browse_folder():
    """Open a native folder browser dialog."""
    import tkinter as tk
    from tkinter import filedialog
    
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder_path = filedialog.askdirectory()
        root.destroy()
        return {"path": folder_path}
    except Exception as e:
        return {"path": "", "error": str(e)}


# ============== Static Files & Frontend ==============

# Mount frontend static files
if os.path.isdir(FRONTEND_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


@app.get("/")
async def serve_frontend():
    """Serve the main frontend HTML file."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found. API is running at /docs"}


# Health check endpoint
@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "2.0.0"}
