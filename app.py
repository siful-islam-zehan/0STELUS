"""STELUS storefront + admin dashboard — Flask / SQLite backend."""
import json, os, secrets, sqlite3, time, uuid
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).parent
DB_PATH = os.environ.get("DB_PATH", str(BASE / "stelus.db"))
SIZES = ["M", "L", "XL", "XXL"]
STATUSES = ["Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"]
ALLOWED_IMG = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__, static_folder="public", static_url_path="")
app.config.update(
    SECRET_KEY=os.environ.get("SESSION_SECRET") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=8 * 3600,
    MAX_CONTENT_LENGTH=3 * 1024 * 1024,
)

# ---------- database ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()

SCHEMA = """
CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT,
  description TEXT, price INTEGER, wholesale_price INTEGER, tag TEXT, image TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS sizes(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, size TEXT, stock INTEGER,
  UNIQUE(product_id,size), FOREIGN KEY(product_id) REFERENCES products(id));
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, customer_name TEXT, phone TEXT, address TEXT,
  source TEXT, status TEXT DEFAULT 'Pending', total INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, product_id INTEGER,
  product_name TEXT, size TEXT, qty INTEGER, price INTEGER, FOREIGN KEY(order_id) REFERENCES orders(id));
"""

SEED_PRODUCTS = [
    ("After Dark Graphic Tee", "streetwear", "Heavyweight everyday statement tee.", 450, 140, "BESTSELLER", "/img/after-dark.svg"),
    ("Cursed Energy Tee", "anime", "Anime-inspired concept graphic tee.", 450, 140, "FAN FAVOURITE", "/img/cursed-energy.svg"),
    ("Purple Haze Oversized", "streetwear", "Relaxed drop-shoulder fit.", 450, 140, "NEW DROP", "/img/purple-haze.svg"),
    ("Your Art Custom Tee", "custom", "Custom print enquiry listing.", 375, 0, "CUSTOM PRINT", "/img/custom.svg"),
]
DEMO_NAMES = ["Rafi Ahmed", "Nusrat Jahan", "Tanvir Hasan", "Maisha Khan", "Sakib Islam", "Tasnia Rahman", "Arif Hossain", "Sadia Noor"]
DEMO_STATUS = ["Delivered", "Delivered", "Shipped", "Confirmed", "Delivered", "Pending", "Delivered", "Pending"]

def init_db(seed_demo=True):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM admins").fetchone():
        conn.execute("INSERT INTO admins(username,password_hash) VALUES(?,?)", (
            os.environ.get("ADMIN_USER", "admin"),
            generate_password_hash(os.environ.get("ADMIN_PASSWORD", "StelusDemo2026!"))))
    if seed_demo and not conn.execute("SELECT 1 FROM products").fetchone():
        for p in SEED_PRODUCTS:
            pid = conn.execute("INSERT INTO products(name,category,description,price,wholesale_price,tag,image) VALUES(?,?,?,?,?,?,?)", p).lastrowid
            conn.executemany("INSERT INTO sizes(product_id,size,stock) VALUES(?,?,8)", [(pid, s) for s in SIZES])
        prods = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
        for i, name in enumerate(DEMO_NAMES):
            p, qty = prods[i % len(prods)], 1 + i % 3
            oid = conn.execute(
                "INSERT INTO orders(customer_name,phone,address,source,status,total,created_at) VALUES(?,?,?,?,?,?,datetime('now',?))",
                (name, f"017{10000000 + i * 1234567}", "Demo address, Dhaka", "messenger" if i % 3 == 2 else "website",
                 DEMO_STATUS[i], p["price"] * qty, f"-{i % 7} days")).lastrowid
            conn.execute("INSERT INTO order_items(order_id,product_id,product_name,size,qty,price) VALUES(?,?,?,?,?,?)",
                         (oid, p["id"], p["name"], ["M", "L", "XL"][i % 3], qty, p["price"]))
    conn.commit(); conn.close()

# ---------- helpers ----------
def err(msg, code=400):
    return jsonify(error=msg), code

def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return err("Please log in.", 401)
        return fn(*a, **kw)
    return wrapper

def products_query(active_only):
    where = "WHERE p.active=1" if active_only else ""
    return db().execute(f"""SELECT p.*, (SELECT COALESCE(SUM(stock),0) FROM sizes s WHERE s.product_id=p.id) stock,
        (SELECT json_group_object(size,stock) FROM sizes s WHERE s.product_id=p.id) sizes
        FROM products p {where} ORDER BY p.id DESC""").fetchall()

def clean_sizes(raw):
    raw = raw or {}
    out = {}
    for s in SIZES:
        try: out[s] = max(0, int(raw.get(s, 0) or 0))
        except (TypeError, ValueError): out[s] = 0
    return out

_login_hits = {}
def login_blocked(ip):
    now = time.time()
    hits = [t for t in _login_hits.get(ip, []) if now - t < 300]
    _login_hits[ip] = hits
    return len(hits) >= 8

# ---------- public API ----------
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/api/products")
def api_products():
    return jsonify([dict(r) for r in products_query(True)])

@app.post("/api/orders")
def api_create_order():
    b = request.get_json(silent=True) or {}
    items = b.get("items")
    if not (b.get("customer_name") and b.get("phone") and b.get("address") and isinstance(items, list) and items):
        return err("Name, phone, address and items are required.")
    conn, rows, total = db(), [], 0
    for it in items:
        try: pid, qty = int(it.get("product_id")), int(it.get("qty"))
        except (TypeError, ValueError, AttributeError): return err("Invalid item.")
        size = str(it.get("size") or "L").upper()
        p = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
        s = p and conn.execute("SELECT stock FROM sizes WHERE product_id=? AND size=?", (pid, size)).fetchone()
        if not p or not s or not 1 <= qty <= 20 or s["stock"] < qty:
            return err(f"Invalid item or insufficient stock for {p['name'] if p else 'product'}.")
        rows.append((p, qty, size)); total += p["price"] * qty
    with conn:
        oid = conn.execute("INSERT INTO orders(customer_name,phone,address,source,total) VALUES(?,?,?,?,?)", (
            str(b["customer_name"])[:100], str(b["phone"])[:40], str(b["address"])[:500],
            "messenger" if b.get("source") == "messenger" else "website", total)).lastrowid
        for p, qty, size in rows:
            conn.execute("INSERT INTO order_items(order_id,product_id,product_name,size,qty,price) VALUES(?,?,?,?,?,?)",
                         (oid, p["id"], p["name"], size, qty, p["price"]))
            conn.execute("UPDATE sizes SET stock=stock-? WHERE product_id=? AND size=?", (qty, p["id"], size))
    return jsonify(ok=True, order_id=oid, total=total), 201

# ---------- admin auth ----------
@app.post("/api/admin/login")
def admin_login():
    ip = request.remote_addr or "?"
    if login_blocked(ip):
        return err("Too many attempts. Try again in a few minutes.", 429)
    b = request.get_json(silent=True) or {}
    u = db().execute("SELECT * FROM admins WHERE username=?", (str(b.get("username", "")),)).fetchone()
    if not u or not check_password_hash(u["password_hash"], str(b.get("password", ""))):
        _login_hits[ip].append(time.time())
        return err("Incorrect username or password.", 401)
    session.clear(); session.permanent = True
    session["admin"] = {"id": u["id"], "username": u["username"]}
    return jsonify(ok=True, username=u["username"])

@app.get("/api/admin/me")
def admin_me():
    a = session.get("admin")
    return (jsonify(ok=True, username=a["username"]) if a else (jsonify(ok=False), 401))

@app.post("/api/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return jsonify(ok=True)

# ---------- admin data ----------
@app.get("/api/admin/summary")
@admin_required
def admin_summary():
    q = lambda sql: db().execute(sql).fetchone()[0]
    return jsonify(
        products=q("SELECT COUNT(*) FROM products WHERE active=1"),
        orders=q("SELECT COUNT(*) FROM orders"),
        revenue=q("SELECT COALESCE(SUM(total),0) FROM orders WHERE status='Delivered'"),
        pending=q("SELECT COUNT(*) FROM orders WHERE status IN ('Pending','Confirmed')"),
        recent=[dict(r) for r in db().execute("SELECT * FROM orders ORDER BY id DESC LIMIT 8")],
        daily=[dict(r) for r in db().execute(
            "SELECT substr(created_at,1,10) day, SUM(total) revenue FROM orders "
            "WHERE created_at>=datetime('now','-6 days') GROUP BY day")])

@app.get("/api/admin/products")
@admin_required
def admin_products():
    return jsonify([dict(r) for r in products_query(False)])

def product_fields(b, base=None):
    base = base or {}
    pick = lambda k, d="": b.get(k, base.get(k, d))
    try: price, wholesale = int(float(pick("price", 0))), int(float(pick("wholesale_price", 0) or 0))
    except (TypeError, ValueError): return None
    if not str(pick("name")).strip() or price < 0 or wholesale < 0: return None
    return (str(pick("name")).strip()[:150], pick("category", "streetwear"), str(pick("description"))[:1000],
            price, wholesale, str(pick("tag", "NEW DROP"))[:40], str(pick("image"))[:500])

@app.post("/api/admin/products")
@admin_required
def admin_add_product():
    f = product_fields(request.get_json(silent=True) or {})
    if not f: return err("Product name and valid price required.")
    sizes = clean_sizes((request.get_json(silent=True) or {}).get("sizes"))
    with db() as conn:
        pid = conn.execute("INSERT INTO products(name,category,description,price,wholesale_price,tag,image) VALUES(?,?,?,?,?,?,?)", f).lastrowid
        conn.executemany("INSERT INTO sizes(product_id,size,stock) VALUES(?,?,?)", [(pid, s, n) for s, n in sizes.items()])
    return jsonify(ok=True, id=pid), 201

@app.put("/api/admin/products/<int:pid>")
@admin_required
def admin_edit_product(pid):
    p = db().execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p: return err("Product not found.", 404)
    b = request.get_json(silent=True) or {}
    f = product_fields(b, dict(p))
    if not f: return err("Product name and valid price required.")
    with db() as conn:
        conn.execute("UPDATE products SET name=?,category=?,description=?,price=?,wholesale_price=?,tag=?,image=?,active=1 WHERE id=?", (*f, pid))
        if b.get("sizes"):
            for s, n in clean_sizes(b["sizes"]).items():
                conn.execute("INSERT INTO sizes(product_id,size,stock) VALUES(?,?,?) ON CONFLICT(product_id,size) DO UPDATE SET stock=excluded.stock", (pid, s, n))
    return jsonify(ok=True)

@app.delete("/api/admin/products/<int:pid>")
@admin_required
def admin_archive_product(pid):
    with db() as conn:
        n = conn.execute("UPDATE products SET active=0 WHERE id=?", (pid,)).rowcount
    return jsonify(ok=bool(n))

@app.post("/api/admin/upload")
@admin_required
def admin_upload():
    f = request.files.get("file")
    ext = (f.filename.rsplit(".", 1)[-1].lower() if f and "." in f.filename else "")
    if ext not in ALLOWED_IMG: return err("Upload a png, jpg, webp or gif image.")
    name = f"{uuid.uuid4().hex}.{ext}"
    f.save(BASE / "public" / "uploads" / name)
    return jsonify(ok=True, url=f"/uploads/{name}")

@app.get("/api/admin/orders")
@admin_required
def admin_orders():
    out = []
    for o in db().execute("SELECT * FROM orders ORDER BY id DESC"):
        d = dict(o)
        d["items"] = [dict(i) for i in db().execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],))]
        out.append(d)
    return jsonify(out)

@app.patch("/api/admin/orders/<int:oid>")
@admin_required
def admin_order_status(oid):
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in STATUSES: return err("Invalid status.")
    with db() as conn:
        n = conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid)).rowcount
    return jsonify(ok=bool(n))

init_db()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print(f"STELUS running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG") == "1")
