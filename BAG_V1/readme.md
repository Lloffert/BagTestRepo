
# Bag (Flask) — Semester-Based Financial Pacing App

This is a working Flask + SQLite prototype for the **Bag** capstone project.

## Features (Option B: MVP + 100% grade extras)
- Register / Login / Logout (hashed passwords, sessions)
- Profile (name, school, default semester weeks)
- Semester create + select (active semester stored in session)
- Aid awards (lump-sum entries like FAFSA / GI Bill / Scholarship, etc.)
- Transactions (income + expenses) with categories
- Dashboard:
  - Week X of N
  - % semester elapsed vs % funds spent
  - Safe-to-spend this week
  - Supportive pacing message + alerts (75/90/100% thresholds)
  - Category totals
  - Run-out week projection (based on avg weekly spending)

## Tech
- Flask + Jinja templates
- SQLite (local persistence)
- No external services required

---

## Quickstart

### 1) Create and Activate Virtual Environment

#### Windows (PowerShell)

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

#### Mac/Linux

```
python3 -m venv .venv
source .venv/bin/activate
```

You should now see:

```
(.venv)
```

at the beginning of your terminal.

---

### 2) Install Dependencies

```
pip install -r requirements.txt
```

### 3) Initialize Database

#### Windows (PowerShell)

```powershell
$env:FLASK_APP="app"
flask init-db
```

#### Mac/Linux
```
export FLASK_APP=app
flask init-db
```
### 4) Run the app
```
flask run
```

Open: http://127.0.0.1:5000

---

## Demo Flow (what to show your instructor)
1. Register a new account
2. Create your Profile
3. Create a Semester + select it
4. Add Aid (lump sum)
5. Add a few Expenses (Food / Housing / etc.)
6. Open Dashboard and explain:
   - Safe-to-spend this week recalculates
   - Status changes when spending gets ahead of semester pace
   - Alerts show at 75/90/100%
   - Projection shows estimated run-out week

---

## Tests
```bash
pytest -q
```

---

## Notes
- Currency is stored as **cents** in the database.
- “Active semester” is stored in `session['active_semester_id']`.
