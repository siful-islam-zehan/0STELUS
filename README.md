# STELUS Store (Python / Flask)

Anime-streetwear storefront + admin dashboard. Backend: Flask + SQLite. Frontend: plain HTML/CSS/JS in `public/`.

## Run
```bash
python -m venv venv
venv\Scripts\activate        # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```
- Store: http://localhost:3000
- Admin: http://localhost:3000/admin.html  (`admin` / `StelusDemo2026!`)

## Before going live
Set your own credentials on the FIRST run (before `stelus.db` exists):
```powershell
$env:ADMIN_USER="you"; $env:ADMIN_PASSWORD="long-unique-password"; $env:SESSION_SECRET="long-random-secret"
python app.py
```
For production use `pip install waitress` then `waitress-serve --port=3000 app:app`, behind HTTPS.

## Features
- Product filters, bag, size select, checkout with stock validation + deduction
- Admin: login (rate-limited), revenue chart, product CRUD + image upload, size stock, order status updates
- 8 demo orders seeded on first run (delete `stelus.db` to reset)

## Notes
Demo art is original placeholder illustration. No payment gateway, email/SMS or customer accounts yet. Add CSRF protection before public launch.
