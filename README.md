# Personal Documents Expiry Tracker —

A beginner-friendly Flask + SQLite project with authentication, document CRUD, expiry status, automated tests, database indexes, and responsive UI.

## 1. Requirements
- Windows 10/11
- Python 3.10 or newer
- VS Code (recommended)

## 2. Run in VS Code
Open this folder in VS Code, then open **Terminal → New Terminal**.

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your laptop browser. Register an account and add a sample document. SQLite database is created automatically in `instance/documents.db`.

## 3. Run automated tests
Stop the server if it is running, then run:

```bash
python -m unittest discover -s tests -v
```

The tests cover expiry calculation, invalid input, login protection, API CRUD, and user data isolation.

## 4. Open on your mobile (same Wi-Fi)
For local-network testing only:
1. Change the final line in `app.py` to `app.run(host="0.0.0.0", port=5000, debug=False)`.
2. Find laptop IPv4 using `ipconfig`.
3. Allow Python through Windows Firewall on your **private network** if Windows asks.
4. On mobile Chrome (same Wi-Fi), open `http://LAPTOP-IP:5000`, for example `http://192.168.1.5:5000`.
5. When finished, stop the server and restore `127.0.0.1`. Do not expose the development server to the public internet.

## 5. Expiry rules
- Expired: expiry date is before today.
- Expiring Soon: today through 30 days from today.
- Valid: more than 30 days away.

## 6. API endpoints
All API endpoints require a logged-in session.
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/documents` | List the logged-in user's documents |
| POST | `/api/documents` | Add a document (JSON) |
| GET | `/api/documents/<id>` | Get one document |
| PUT | `/api/documents/<id>` | Update a document (JSON) |
| DELETE | `/api/documents/<id>` | Delete a document |
| GET | `/api/expiry-status/<YYYY-MM-DD>` | Calculate expiry status |

Example JSON for POST/PUT:
```json
{
  "title": "Passport",
  "document_type": "Identity",
  "expiry_date": "2027-05-30",
  "notes": "Keep a copy"
}
```

## 8. Security and project limitations
This is an educational prototype. Use a strong `SECRET_KEY` environment variable before deployment. Do not store actual identity document numbers, scans, or sensitive personal data in a classroom demo. For production, add CSRF protection, rate limiting, HTTPS, secure cookie settings, password reset, backups, and a production WSGI server.
