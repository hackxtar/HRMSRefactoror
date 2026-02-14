# Refactoring Workbench

A local web application for safely managing find-replace operations across legacy multi-technology repositories.

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the application:**
```bash
python -m uvicorn backend.main:app --reload --port 8000
```

3. **Open in browser:**
```
http://localhost:8000
```

## Features

- **Project Configuration**: Manage paths for ASP.NET, .NET Core, WinForms, and Angular projects
- **Rule Engine**: Create/Edit/Delete replacement rules with regex or plain text support
- **Dry Run**: Preview all changes with diff view before applying
- **Safe Execution**: Automatic `.bak` backups before any modification
- **Audit Trail**: Complete history of all refactoring operations

## Safety Features

- Automatic backup of files before modification (`.bak` extension)
- Hidden folders excluded (`.git`, `.vs`, `bin`, `obj`, `node_modules`)
- Dry run preview with file-by-file selection
- Execution history with rollback information

## API Documentation

After starting the server, visit `http://localhost:8000/docs` for interactive API documentation.
