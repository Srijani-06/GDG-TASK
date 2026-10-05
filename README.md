# GDG-TASK
My first backend project .


#TASK

A simple backend for anonymous reporting. Anyone can submit a report without an account, track it with a secret case code, and moderators can review reports without ever seeing who sent them.
Srijani Ghosh Id :CAND9103  | Reg No:RA2611003011197 | B.Tech CSE, 1st year, 

## AI assistance (honest disclosure)
I am a first-year student new to backend development. I used an AI assistant (Claude) heavily on this project: roughly 70% of the code was AI-generated. I have been studying it to understand how it works, and I am happy to explain or be tested on any part.

## Tech
Python, FastAPI, SQLite, Pydantic.

## Setup
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn main:app --reload --no-access-log



## Example
Submit:

    POST /reports
    {"category": "SECURITY", "description": "The server room door is left open at night."}

Response:

    {"case_code": "enpDCDt2hDL2SG4JVH4ALA", "status": "SUBMITTED", "note": "Save this code. It cannot be shown again."}

Invalid change (409):

    {"detail": "Cannot change from SUBMITTED to RESOLVED. Allowed next: ['UNDER_REVIEW']"}

## How anonymity is maintained
- No accounts, and no name, email or IP address is stored.
- The case code is long and random (`secrets.token_urlsafe`), so it cannot be guessed.
- Only a SHA-256 hash of the code is saved, so even a stolen database does not reveal codes.
- Moderators only see the report content, never any reporter details.
- Run with `--no-access-log` so the server does not print visitor IPs.

## Design decisions and limitations
- Moderator access uses one shared key. A real system would give each moderator their own login.
- The key is written in the code for simplicity; a real system would keep it in an environment variable.
- Status rules are enforced on the server, so steps cannot be skipped.
- A lost case code cannot be recovered, by design.
- No rate limiting, file upload, or automated tests yet.

