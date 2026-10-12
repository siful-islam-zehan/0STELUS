# STELUS Store

A streetwear storefront and admin dashboard built with **Flask, SQLite, HTML, CSS, and vanilla JavaScript**.

## Project structure

```text
STELUS_GitHub_Ready/
├── app.py                 # Flask API and server
├── requirements.txt
├── .env.example           # Environment variable template
├── .gitignore
├── public/
│   ├── index.html          # Storefront
│   ├── admin.html          # Admin dashboard
│   ├── styles.css
│   ├── store.js
│   ├── admin.js
│   ├── img/                # Store graphics
│   └── uploads/            # Uploaded product images
└── README.md
```

## Run locally (Windows)

1. Install Python 3.10 or newer.
2. Open a terminal in this project folder.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

4. Install packages and start the server:

   ```powershell
   python -m pip install -r requirements.txt
   python app.py
   ```

5. Open the storefront at http://127.0.0.1:3000 and the admin page at http://127.0.0.1:3000/admin.html.

On first local run, the demo admin login is `admin` / `StelusDemo2026!`. **Change these before any public deployment.** The app creates `stelus.db` automatically; the database is intentionally excluded from this repository.

## Configure environment variables

Set these variables in your terminal or hosting provider's secret/environment settings:

- `ADMIN_USER` — your private admin username
- `ADMIN_PASSWORD` — a long, unique admin password
- `SESSION_SECRET` — a long random secret used to sign sessions
- `PORT` — hosting provider's port (the app defaults to `3000`)
- `DB_PATH` — optional path to the SQLite database file

See `.env.example` for a template. Do not commit real credentials or `.env` files.

## Publish the source to GitHub

GitHub stores the code, but **GitHub Pages cannot run this Flask/Python backend**. Publish this repository to GitHub, then deploy the Flask app to a Python-capable host (for example, Render or Railway) and set the environment variables there.

Typical Git commands:

```bash
git init
git add .
git commit -m "Prepare STELUS store for GitHub"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Install `waitress` for a production WSGI server and run `waitress-serve --host=0.0.0.0 --port=$PORT app:app` where supported. Some Windows shells require a different way to reference `PORT`.

## Important before accepting real orders

- Add CSRF protection and review security settings before public launch.
- Use HTTPS and strong unique admin credentials.
- SQLite files and uploaded images may be lost on hosts with ephemeral storage. Configure persistent storage or move to a managed database and persistent media storage for production.
- This demo does not integrate a payment gateway, email/SMS notifications, or customer accounts.
- Seeded demo orders are for development only; do not use demo data for real business reporting.
