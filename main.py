import hashlib
import secrets
import sqlite3
from datetime import datetime
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="WhistleDrop")

# Moderators must send this key in the "x-api-key" header to use moderator endpoints.
MODERATOR_KEY = "mod-secret-123"

Category = Literal["SECURITY", "HARASSMENT", "CORRUPTION", "TECHNICAL", "OTHER"]
Status = Literal["SUBMITTED", "UNDER_REVIEW", "RESOLVED", "DISMISSED"]

# The workflow: from each status, which statuses are allowed next?
NEXT_STATUS = {
    "SUBMITTED": ["UNDER_REVIEW"],
    "UNDER_REVIEW": ["RESOLVED", "DISMISSED"],
    "RESOLVED": [],
    "DISMISSED": [],
}


# ---------- Database ----------
def connect():
    conn = sqlite3.connect("whistledrop.db")
    conn.row_factory = sqlite3.Row  # lets us read columns by name
    return conn


def setup_database():
    conn = connect()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_code_hash TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            evidence_url TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()


setup_database()


# ---------- What data we accept ----------
class NewReport(BaseModel):
    category: Category
    description: str = Field(min_length=10, max_length=5000)
    evidence_url: Optional[str] = Field(default=None, pattern=r"^https?://")


class StatusChange(BaseModel):
    status: Status
    message: Optional[str] = Field(default=None, max_length=300)


# ---------- Small helpers ----------
def hash_code(case_code):
    # One-way scramble: we save this instead of the real case code.
    return hashlib.sha256(case_code.encode()).hexdigest()


def check_moderator(x_api_key):
    if x_api_key != MODERATOR_KEY:
        raise HTTPException(status_code=401, detail="Wrong or missing moderator key.")


# ---------- Reporter endpoints (no login needed) ----------
@app.get("/")
def home():
    return {"message": "WhistleDrop is running"}


@app.post("/reports", status_code=201)
def submit_report(report: NewReport):
    case_code = secrets.token_urlsafe(16)  # long random code, impossible to guess
    now = datetime.now().isoformat()

    conn = connect()
    cursor = conn.execute(
        "INSERT INTO reports (case_code_hash, category, description, evidence_url, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (hash_code(case_code), report.category, report.description, report.evidence_url, "SUBMITTED", now),
    )
    conn.execute(
        "INSERT INTO updates (report_id, status, message, created_at) VALUES (?, ?, ?, ?)",
        (cursor.lastrowid, "SUBMITTED", "Report received.", now),
    )
    conn.commit()
    conn.close()

    return {"case_code": case_code, "status": "SUBMITTED", "note": "Save this code. It cannot be shown again."}


@app.get("/reports/{case_code}")
def check_report(case_code: str):
    conn = connect()
    report = conn.execute(
        "SELECT * FROM reports WHERE case_code_hash = ?", (hash_code(case_code),)
    ).fetchone()
    if report is None:
        conn.close()
        raise HTTPException(status_code=404, detail="No report found for this case code.")

    updates = conn.execute(
        "SELECT status, message, created_at FROM updates WHERE report_id = ? ORDER BY id", (report["id"],)
    ).fetchall()
    conn.close()

    return {
        "category": report["category"],
        "status": report["status"],
        "updates": [dict(u) for u in updates],
    }


# ---------- Moderator endpoints (need the key) ----------
@app.get("/moderator/reports")
def list_reports(
    status: Optional[Status] = None,
    category: Optional[Category] = None,
    x_api_key: Optional[str] = Header(default=None),
):
    check_moderator(x_api_key)

    query = "SELECT id, category, description, evidence_url, status, created_at FROM reports WHERE 1=1"
    values = []
    if status:
        query += " AND status = ?"
        values.append(status)
    if category:
        query += " AND category = ?"
        values.append(category)
    query += " ORDER BY id DESC"

    conn = connect()
    rows = conn.execute(query, values).fetchall()
    conn.close()
    return {"count": len(rows), "reports": [dict(r) for r in rows]}


@app.patch("/moderator/reports/{report_id}/status")
def change_status(report_id: int, change: StatusChange, x_api_key: Optional[str] = Header(default=None)):
    check_moderator(x_api_key)

    conn = connect()
    report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if report is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Report not found.")

    allowed = NEXT_STATUS[report["status"]]
    if change.status not in allowed:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot change from {report['status']} to {change.status}. Allowed next: {allowed}",
        )

    conn.execute("UPDATE reports SET status = ? WHERE id = ?", (change.status, report_id))
    conn.execute(
        "INSERT INTO updates (report_id, status, message, created_at) VALUES (?, ?, ?, ?)",
        (report_id, change.status, change.message, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"id": report_id, "status": change.status, "message": change.message}