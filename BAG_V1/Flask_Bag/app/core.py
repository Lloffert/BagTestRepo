from __future__ import annotations
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from .db import get_db
from .auth import login_required
from .pacing import compute_pace, safe_to_spend, runout_week_projection

bp = Blueprint("core", __name__, url_prefix="")

DEFAULT_CATEGORIES = ["Housing", "Food", "Transportation", "Textbooks", "Personal", "Health", "School Supplies", "Other"]

def _user_id() -> int:
    return int(session["user_id"])

def _active_semester_id() -> int | None:
    sid = session.get("active_semester_id")
    return int(sid) if sid is not None else None

def _ensure_default_categories(db, user_id: int):
    # seed defaults once per user (idempotent)
    for name in DEFAULT_CATEGORIES:
        db.execute(
            "INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)",
            (user_id, name),
        )
    db.commit()

def _money_to_cents(s: str) -> int | None:
    try:
        v = float(s)
    except Exception:
        return None
    if v < 0:
        return None
    return int(round(v * 100))

def _cents_to_money(cents: int) -> float:
    return (cents or 0) / 100.0

@bp.route("/")
def home():
    if session.get("user_id") is None:
        return redirect(url_for("auth.login"))
    return redirect(url_for("core.dashboard"))

@bp.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    db = get_db()
    uid = _user_id()
    row = db.execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone()

    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        school = (request.form.get("school") or "").strip()
        weeks = request.form.get("default_semester_weeks") or "16"
        try:
            weeks_i = int(weeks)
        except Exception:
            weeks_i = 16
        if weeks_i < 8 or weeks_i > 26:
            flash("Default semester weeks must be between 8 and 26.")
            return render_template("profile.html", profile=row)

        db.execute(
            "INSERT INTO profiles (user_id, display_name, school, default_semester_weeks) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name, school=excluded.school, default_semester_weeks=excluded.default_semester_weeks",
            (uid, display_name, school, weeks_i),
        )
        db.commit()
        flash("Profile saved.")
        return redirect(url_for("core.dashboard"))

    return render_template("profile.html", profile=row)

@bp.route("/semesters", methods=["GET"])
@login_required
def semesters():
    db = get_db()
    uid = _user_id()
    prof = db.execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone()
    sems = db.execute("SELECT * FROM semesters WHERE user_id = ? ORDER BY created_at DESC", (uid,)).fetchall()
    active = _active_semester_id()
    return render_template("semesters.html", semesters=sems, active_semester_id=active, profile=prof)

@bp.route("/semester/new", methods=["GET","POST"])
@login_required
def semester_new():
    db = get_db()
    uid = _user_id()
    prof = db.execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone()
    default_weeks = int(prof["default_semester_weeks"]) if prof else 16

    if request.method == "POST":
        name = (request.form.get("name") or "").strip() or "My Semester"
        start_date = (request.form.get("start_date") or "").strip()
        end_date = (request.form.get("end_date") or "").strip()
        weeks = request.form.get("weeks") or str(default_weeks)

        if not start_date or not end_date:
            flash("Start date and end date are required.")
            return render_template("semester_new.html", default_weeks=default_weeks)

        # validate dates
        try:
            sd = date.fromisoformat(start_date)
            ed = date.fromisoformat(end_date)
        except Exception:
            flash("Invalid date format.")
            return render_template("semester_new.html", default_weeks=default_weeks)
        if ed <= sd:
            flash("End date must be after start date.")
            return render_template("semester_new.html", default_weeks=default_weeks)

        try:
            weeks_i = int(weeks)
        except Exception:
            weeks_i = default_weeks
        if weeks_i < 8 or weeks_i > 26:
            flash("Weeks must be between 8 and 26.")
            return render_template("semester_new.html", default_weeks=default_weeks)

        db.execute(
            "INSERT INTO semesters (user_id, name, start_date, end_date, weeks) VALUES (?, ?, ?, ?, ?)",
            (uid, name, start_date, end_date, weeks_i),
        )
        db.commit()

        # set newly created semester active
        new_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        session["active_semester_id"] = int(new_id)

        flash("Semester created and selected.")
        return redirect(url_for("core.dashboard"))

    return render_template("semester_new.html", default_weeks=default_weeks)

@bp.route("/semester/select/<int:semester_id>")
@login_required
def semester_select(semester_id: int):
    db = get_db()
    uid = _user_id()
    row = db.execute("SELECT id FROM semesters WHERE id = ? AND user_id = ?", (semester_id, uid)).fetchone()
    if not row:
        flash("Semester not found.")
        return redirect(url_for("core.semesters"))
    session["active_semester_id"] = semester_id
    flash("Semester selected.")
    return redirect(url_for("core.dashboard"))

@bp.route("/aid/new", methods=["GET","POST"])
@login_required
def aid_new():
    db = get_db()
    uid = _user_id()
    sid = _active_semester_id()
    if sid is None:
        flash("Create and select a semester first.")
        return redirect(url_for("core.semester_new"))

    if request.method == "POST":
        source_type = (request.form.get("source_type") or "FAFSA").strip()
        label = (request.form.get("label") or "").strip() or source_type
        amount = _money_to_cents(request.form.get("amount") or "")
        disb = (request.form.get("disbursement_date") or "").strip()

        if amount is None:
            flash("Amount must be a non-negative number.")
            return render_template("aid_new.html")
        if not disb:
            flash("Disbursement date is required.")
            return render_template("aid_new.html")
        try:
            date.fromisoformat(disb)
        except Exception:
            flash("Invalid disbursement date.")
            return render_template("aid_new.html")

        # ensure semester belongs to user
        sem = db.execute("SELECT id FROM semesters WHERE id = ? AND user_id = ?", (sid, uid)).fetchone()
        if not sem:
            flash("Invalid active semester.")
            return redirect(url_for("core.semesters"))

        db.execute(
            "INSERT INTO aid_awards (semester_id, source_type, label, amount_cents, disbursement_date) VALUES (?, ?, ?, ?, ?)",
            (sid, source_type, label, amount, disb),
        )
        db.commit()
        flash("Aid saved.")
        return redirect(url_for("core.dashboard"))

    return render_template("aid_new.html")

@bp.route("/transaction/new", methods=["GET","POST"])
@login_required
def transaction_new():
    db = get_db()
    uid = _user_id()
    sid = _active_semester_id()
    if sid is None:
        flash("Create and select a semester first.")
        return redirect(url_for("core.semester_new"))

    _ensure_default_categories(db, uid)
    cats = db.execute("SELECT * FROM categories WHERE user_id = ? ORDER BY name ASC", (uid,)).fetchall()

    if request.method == "POST":
        ttype = (request.form.get("type") or "expense").strip()
        amount = _money_to_cents(request.form.get("amount") or "")
        tdate = (request.form.get("date") or "").strip()
        category_id = request.form.get("category_id") or None
        note = (request.form.get("note") or "").strip()

        if ttype not in ("income","expense"):
            flash("Invalid transaction type.")
            return render_template("transaction_new.html", categories=cats, today=date.today().isoformat())
        if amount is None or amount == 0:
            flash("Amount must be greater than 0.")
            return render_template("transaction_new.html", categories=cats, today=date.today().isoformat())
        if not tdate:
            flash("Date is required.")
            return render_template("transaction_new.html", categories=cats, today=date.today().isoformat())
        try:
            date.fromisoformat(tdate)
        except Exception:
            flash("Invalid date.")
            return render_template("transaction_new.html", categories=cats, today=date.today().isoformat())

        # only allow categories belonging to user
        cat_id = None
        if category_id:
            try:
                cid = int(category_id)
                ok = db.execute("SELECT id FROM categories WHERE id = ? AND user_id = ?", (cid, uid)).fetchone()
                if ok:
                    cat_id = cid
            except Exception:
                cat_id = None

        db.execute(
            "INSERT INTO transactions (user_id, semester_id, type, amount_cents, date, category_id, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, sid, ttype, amount, tdate, cat_id, note),
        )
        db.commit()
        flash("Transaction saved.")
        return redirect(url_for("core.dashboard"))

    return render_template("transaction_new.html", categories=cats, today=date.today().isoformat())

@bp.route("/categories", methods=["GET","POST"])
@login_required
def categories():
    db = get_db()
    uid = _user_id()
    _ensure_default_categories(db, uid)

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Category name is required.")
        else:
            db.execute("INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)", (uid, name))
            db.commit()
            flash("Category saved.")
        return redirect(url_for("core.categories"))

    cats = db.execute("SELECT * FROM categories WHERE user_id = ? ORDER BY name ASC", (uid,)).fetchall()
    return render_template("categories.html", categories=cats)

@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    uid = _user_id()
    sid = _active_semester_id()

    prof = db.execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone()
    if sid is None:
        sems = db.execute("SELECT * FROM semesters WHERE user_id = ? ORDER BY created_at DESC", (uid,)).fetchall()
        return render_template("dashboard_empty.html", semesters=sems, profile=prof)

    sem = db.execute("SELECT * FROM semesters WHERE id = ? AND user_id = ?", (sid, uid)).fetchone()
    if not sem:
        session.pop("active_semester_id", None)
        flash("Active semester not found. Please select a semester.")
        return redirect(url_for("core.semesters"))

    # totals
    aid_total_cents = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS s FROM aid_awards WHERE semester_id = ?",
        (sid,),
    ).fetchone()["s"]
    income_total_cents = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS s FROM transactions WHERE semester_id = ? AND user_id = ? AND type='income'",
        (sid, uid),
    ).fetchone()["s"]
    expense_total_cents = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS s FROM transactions WHERE semester_id = ? AND user_id = ? AND type='expense'",
        (sid, uid),
    ).fetchone()["s"]

    total_funds_cents = int(aid_total_cents) + int(income_total_cents)  # aid + any income
    spent_cents = int(expense_total_cents)

    total_funds = _cents_to_money(total_funds_cents)
    spent = _cents_to_money(spent_cents)
    remaining = max(0.0, total_funds - spent)

    pace = compute_pace(
        start_iso=sem["start_date"],
        end_iso=sem["end_date"],
        weeks_total=int(sem["weeks"]),
        today=date.today(),
        funds_spent=spent,
        total_funds=total_funds,
    )
    safe_weekly = safe_to_spend(remaining, pace.week_now, pace.weeks_total)

    # threshold alerts (based on % of funds used)
    alerts = []
    if total_funds > 0:
        if pace.funds_spent_pct >= 100:
            alerts.append("You’ve reached 100% of your funds. Time to pause spending and reassess.")
        elif pace.funds_spent_pct >= 90:
            alerts.append("You’ve used 90% of your funds. Consider tightening spending until the semester ends.")
        elif pace.funds_spent_pct >= 75:
            alerts.append("You’ve used 75% of your funds. Keep an eye on your pace this week.")

    # category totals
    cat_rows = db.execute(
        """SELECT c.name AS category, COALESCE(SUM(t.amount_cents),0) AS total_cents
             FROM categories c
             LEFT JOIN transactions t
               ON t.category_id = c.id AND t.type='expense' AND t.semester_id=? AND t.user_id=?
             WHERE c.user_id=?
             GROUP BY c.id
             HAVING total_cents > 0
             ORDER BY total_cents DESC""",
        (sid, uid, uid),
    ).fetchall()

    # projection
    proj = runout_week_projection(remaining=remaining, spent_so_far=spent, week_now=pace.week_now)

    # recent transactions
    recent = db.execute(
        """SELECT t.*, COALESCE(c.name,'') AS category_name
             FROM transactions t
             LEFT JOIN categories c ON c.id = t.category_id
             WHERE t.user_id=? AND t.semester_id=?
             ORDER BY t.date DESC, t.id DESC
             LIMIT 10""",
        (uid, sid),
    ).fetchall()

    aid_list = db.execute(
        "SELECT * FROM aid_awards WHERE semester_id=? ORDER BY disbursement_date DESC, id DESC",
        (sid,),
    ).fetchall()

    return render_template(
        "dashboard.html",
        profile=prof,
        semester=sem,
        pace=pace,
        total_funds=total_funds,
        spent=spent,
        remaining=remaining,
        safe_weekly=safe_weekly,
        alerts=alerts,
        categories=cat_rows,
        projection_week=proj,
        recent=recent,
        aid_list=aid_list,
    )
