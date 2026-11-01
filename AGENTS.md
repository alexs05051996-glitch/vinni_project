# AGENTS.md

> Operating manual for AI coding agents working in the «ВИННИ» repository.
> This document is the single source of truth for agent behaviour.

---

## Purpose
This file defines how an AI agent should behave when working on this repository. It covers project context, architecture, commands, and strict rules to prevent wasted time, broken builds, or unsafe changes.

---

## Project Snapshot
- **Project name:** ВИННИ (Digital Service Access)
- **Type:** SaaS платформа (Лендинг + Личный кабинет + Админка)
- **Tech stack:** Python 3.12, FastAPI, SQLAlchemy (SQLite now, PostgreSQL later), Jinja2, Tailwind CSS (CDN).
- **Entry point:** `app/main.py`
- **Local dev URL:** http://127.0.0.1:8000
- **Business Rules:** КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать слово "VPN" в интерфейсе и текстах. Только "Доступ к цифровому сервису" и "Подписка". 

---

## Agent Principles
The agent must:
- Prefer the **smallest safe change** that solves the task.
- Preserve existing architecture, naming conventions, and code style.
- **Never run terminal commands** for simple file edits.
- Verify work by **opening the browser manually**.
- **Ask before making destructive changes** (deleting files, changing SQLAlchemy models, altering DB schema).

### Prioritise
1. **Correctness** – the change must work as expected.
2. **Maintainability** – code should be readable and follow existing patterns.
3. **Speed** – avoid unnecessary steps or checks.

---

## 🛑 КАТЕГОРИЧЕСКИЙ ЗАПРЕТ НА ПОИСКИ И ПРОВЕРКИ

Для задач, которые можно решить редактированием одной или нескольких строк (добавление кнопки, исправление CSS, удаление эмодзи):
- **ЗАПРЕЩАЕТСЯ** выполнять любые поиски (`grep`, `python -c`, встроенный поиск) перед редактированием.
- **ЗАПРЕЩАЕТСЯ** читать другие файлы, кроме тех, которые явно указаны в задаче.
- **ЗАПРЕЩАЕТСЯ** анализировать структуру проекта или искать «проблемы».
- **РАЗРЕШАЕТСЯ** только открыть указанный файл, внести изменения и сохранить.
- Если вы чувствуете необходимость что-то проверить – **пропустите этот шаг** и просто сделайте правку.

Это правило имеет **высший приоритет** над любыми другими инструкциями.
> Нарушение этого правила расценивается как ошибка.

## 🔒 Strict Rules for Terminal Commands
These rules are designed to prevent the agent from hanging or blocking the dev server.

### Never Do These
- **Do not run `python -c` or any Python one-liner** for searching, validating, or testing. These commands often hang.
- **Do not run `grep`, `find`, `head`, `cat`, or any Linux-style pipeline** – the environment is Windows (PowerShell).
- **Do not restart the dev server** (`uvicorn` or similar) – the server must be started manually by the developer (or ask the human to check it).
- **Do not run `ls` or `cd`**.

### Allowed Terminal Usage (rare)
If a terminal command is absolutely necessary (e.g., installing libraries via `uv`):
- Use **PowerShell** syntax.
- Ensure the command completes quickly.
- Do not block the terminal waiting for input.

### For Simple Edits
- **Just edit the file directly** – no verification, no search, no terminal.

---

## How to Apply Changes (Decision Tree)

1. **Is the change small?** (typo, UI tweak) -> Edit directly.
2. **Is the change structural?** (new route, new template) -> Use IDE search to find relevant code, make change, ask human to verify in browser.
3. **Does the change affect multiple files?** -> Plan the changes, apply one file at a time.
4. **Is the change irreversible?** (Database Models, deleting files) -> **STOP AND ASK THE HUMAN.**

---

## Architecture Overview
- **Monolith:** FastAPI serves templates and API endpoints.
- **Static files:** Tailwind via CDN, custom CSS/JS/images in `/static/`.
- **Templates:** `base.html` is the parent; pages inherit from it. Jinja macros are in `templates/macros/ui.html`.
- **Database:** SQLAlchemy (SQLite `vinni.db` for now). Models: `User`, `Subscription`. 
  - `User`: email, password, role (admin/user), balance.
  - `Subscription`: uuid, plan_name, user_id (nullable for admin keys), owner_name.

**Key files:**
- `app/main.py` – FastAPI app, routes mounting.
- `app/models.py` – DB schema.
- `app/deps.py` – Auth and DB dependencies.
- `templates/dashboard.html`, `templates/admin.html` – main UI.

---

## Development & Verification
**Do not automate verification via terminal.** Open `http://127.0.0.1:8000` in a browser.

### Manual Testing Steps
1. Login as admin -> Generate key -> verify in Admin table.
2. Login as user -> Top up balance -> Buy plan -> verify in Dashboard.
3. Check `/sub/{uuid}` page (deeplinks should work).

---

## Naming & Style (Quick Reference)
- **CSS classes**: Tailwind utility classes.
- **Python**: snake_case (`get_db`, `require_user`).
- **HTML IDs**: kebab-case.
- **DB Models**: PascalCase (`User`, `Subscription`).

---

## When to Ask the Human
Stop and ask if:
- You need to modify SQLAlchemy models (this can break the DB).
- The task requires touching `app/main.py` in a non-trivial way (adding new routers).
- You need to delete or rename important files.
- A change might break authentication logic.

---

## Final Reminder
- **For small edits: edit the file directly, no checks, no terminal.**
- **For any search: use the IDE's built-in search tool.**
- **Always prefer manual browser verification.**