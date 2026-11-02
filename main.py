"""
NOVA — A fully functional ecommerce web app with a real SQLite database.

Backend: Flask serves the static UI + JSON REST API. Dynamic data (users,
products stock, orders, order items, tracking events) is stored in SQLite
(data/nova.db), seeded from a built-in catalog.
Run:    python main.py   ->  http://127.0.0.1:5000
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "data", "nova.db")
LEGACY_ORDERS = os.path.join(BASE_DIR, "data", "orders.json")

DB_LOCK = threading.RLock()  # reentrant: nested DB helpers acquire it again

# --------------------------------------------------------------------------
# Catalog (seed data). Each product carries a gradient + emoji fallback plus
# a generated internet image URL.
# --------------------------------------------------------------------------
CATALOG = [
    dict(id="p1", name="Aurora Wireless Headphones", category="Audio", price=149.00,
         old_price=199.00, rating=4.8, reviews=1241, stock=32, emoji="🎧",
         gradient=["#6a11cb", "#2575fc"], badge="Best Seller", img_key="headphones",
         description="Over-ear headphones with adaptive noise cancelling, 40h battery and studio-grade sound."),
    dict(id="p2", name="Pulse Ultra Smartwatch", category="Wearables", price=229.00,
         old_price=279.00, rating=4.7, reviews=863, stock=21, emoji="⌚",
         gradient=["#fc466b", "#3f5efb"], badge="New", img_key="smartwatch",
         description="AMOLED display, 12-day battery, heart-rate + sleep + SpO2 tracking."),
    dict(id="p3", name="Vertex Mechanical Keyboard", category="Gaming", price=119.00,
         old_price=None, rating=4.9, reviews=2104, stock=58, emoji="⌨️",
         gradient=["#11998e", "#38ef7d"], badge=None, img_key="keyboard",
         description="Hot-swappable RGB switches, gasket mount and aluminium frame."),
    dict(id="p4", name="Nebula 27\" 4K Monitor", category="Gaming", price=449.00,
         old_price=529.00, rating=4.6, reviews=520, stock=14, emoji="🖥️",
         gradient=["#141e30", "#243b55"], badge="Limited", img_key="monitor",
         description="IPS panel, 144Hz, HDR600 and 98% DCI-P3 for creators and gamers."),
    dict(id="p5", name="Orbit Mechanical Mouse", category="Gaming", price=69.00,
         old_price=89.00, rating=4.7, reviews=689, stock=77, emoji="🖱️",
         gradient=["#f953c6", "#b91d73"], badge=None, img_key="computer-mouse",
         description="Ultra-light 58g, 26K DPI sensor and 8 programmable buttons."),
    dict(id="p6", name="Sonic Portable Bluetooth Speaker", category="Audio", price=79.00,
         old_price=99.00, rating=4.5, reviews=431, stock=65, emoji="🔊",
         gradient=["#f7971e", "#ffd200"], badge=None, img_key="bluetooth-speaker",
         description="360° sound, IPX7 waterproof and 18h of playtime."),
    dict(id="p7", name="Lumen LED Desk Lamp", category="Home", price=59.00,
         old_price=None, rating=4.6, reviews=312, stock=90, emoji="💡",
         gradient=["#43cea2", "#185a9d"], badge=None, img_key="desk-lamp",
         description="Touch dimming, 5 colour temperatures and USB-C charging port."),
    dict(id="p8", name="Nordic Wooden Desk Shelf", category="Home", price=34.00,
         old_price=44.00, rating=4.4, reviews=198, stock=44, emoji="🪵",
         gradient=["#b79891", "#94716b"], badge=None, img_key="wooden-shelf",
         description="Bamboo organiser with phone groove and cable channel."),
    dict(id="p9", name="Zen Ceramic Pour-Over Set", category="Home", price=49.00,
         old_price=62.00, rating=4.8, reviews=540, stock=27, emoji="☕",
         gradient=["#59282f", "#b2765a"], badge=None, img_key="coffee",
         description="Hand-thrown dripper + carafe, dishwasher safe."),
    dict(id="p10", name="Trail Lightweight Backpack", category="Fashion", price=89.00,
         old_price=119.00, rating=4.7, reviews=731, stock=38, emoji="🎒",
         gradient=["#0f2027", "#2c5364"], badge="Trending", img_key="backpack",
         description="25L water-resistant pack with laptop sleeve and breathable back."),
    dict(id="p11", name="Aether Minimalist Wallet", category="Fashion", price=39.00,
         old_price=None, rating=4.5, reviews=402, stock=112, emoji="👝",
         gradient=["#c31432", "#240b36"], badge=None, img_key="wallet",
         description="RFID-blocking, holds 12 cards, fits in any pocket."),
    dict(id="p12", name="Terra Water Bottle 1L", category="Lifestyle", price=29.00,
         old_price=36.00, rating=4.6, reviews=980, stock=140, emoji="🍶",
         gradient=["#45b649", "#dce35b"], badge=None, img_key="water-bottle",
         description="Insulated stainless steel, keeps drinks cold 24h / hot 12h."),
]

CATEGORIES = ["All", "Audio", "Wearables", "Gaming", "Home", "Fashion", "Lifestyle"]

# --------------------------------------------------------------------------
# Currency + shipping (India)
# --------------------------------------------------------------------------
USD_TO_INR = 83.0          # used at seed time to convert catalog prices to ₹
SHIP_FREE_ABOVE = 5000.0   # free shipping above ₹5,000
SHIP_RATE = 299.0
TAX_RATE = 0.18            # GST


# --------------------------------------------------------------------------
# Image URLs — curated real photos (Unsplash) with a keyword-photo fallback
# (loremflickr). Both are real internet images; the browser falls back to the
# gradient/emoji only if the network is unreachable.
# --------------------------------------------------------------------------
UNSPLASH = {
    "headphones": "1505740420928-5e560c06d30e",
    "smartwatch": "1523275335684-37898b6baf30",
    "keyboard": "1587829741301-dc798b83add3",
    "monitor": "1527443224154-c4a3942d3acf",
    "computer-mouse": "1527864550417-2fd1fcb958c9",
    "bluetooth-speaker": "1545454675-3531b543be5d",
    "desk-lamp": "1507473885765-e6ed057f782c",
    "wooden-shelf": "1518455027359-f3f8164ba6bd",
    "coffee": "1495474472287-4d71bcdd2085",
    "backpack": "1553062407-98eeb64c6a62",
    "wallet": "1554224155-6726b3ff858f",
    "water-bottle": "1602143407151-7111542de6e8",
}


def _img_url(pid: str, key: str) -> str:
    photo = UNSPLASH.get(key)
    if photo:
        return f"https://images.unsplash.com/photo-{photo}?auto=format&fit=crop&w=1200&q=80"
    return _img_url2(pid, key)


def _img_url2(pid: str, key: str) -> str:
    lock = sum(ord(c) for c in pid)
    return f"https://loremflickr.com/1200/1200/{key}?lock={lock}"


_PLACEHOLDER_IMG = "https://images.unsplash.com/photo-1523275335684-37898b6baf30"


def _angle_urls(product_id: str, name: str, primary: str) -> list[str]:
    """Three real image URLs — the primary photo plus two alternate compositions
    of the same product (Different crop anchors so the thumbnails are distinct)."""
    base = (primary or _PLACEHOLDER_IMG).split("?", 1)[0] + "?auto=format&fit=crop&q=80"
    return [
        base + "&w=1200&h=1200&crop=entropy",
        base + "&w=1200&h=1200&crop=left",
        base + "&w=1200&h=1200&crop=right",
    ]


# --------------------------------------------------------------------------
# SQLite schema + init
# --------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  pw_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL,
  old_price REAL, rating REAL NOT NULL, reviews INTEGER NOT NULL,
  stock INTEGER NOT NULL, emoji TEXT NOT NULL,
  gradient0 TEXT NOT NULL, gradient1 TEXT NOT NULL,
  badge TEXT, description TEXT NOT NULL, img_url TEXT, img_url2 TEXT
);
CREATE TABLE IF NOT EXISTS orders(
  id TEXT PRIMARY KEY,
  email TEXT, name TEXT, address TEXT, city TEXT, zip TEXT, payment TEXT,
  subtotal REAL, shipping REAL, tax REAL, total REAL,
  status TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT NOT NULL REFERENCES orders(id),
  product_id TEXT, name TEXT, price REAL, qty INTEGER, line_total REAL
);
CREATE TABLE IF NOT EXISTS tracking_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT NOT NULL REFERENCES orders(id),
  stage TEXT NOT NULL, label TEXT NOT NULL, note TEXT, at TEXT NOT NULL
);
"""

TRACKING_STAGES = [
    ("placed", "Order placed", "We've received your order.", 0),
    ("confirmed", "Confirmed", "Payment confirmed — thanks!", 60),
    ("packed", "Packed", "Your items are being packed.", 120),
    ("shipped", "Shipped", "Shipped — on its way.", 300),
    ("out", "Out for delivery", "Out for delivery today.", 420),
    ("delivered", "Delivered", "Delivered! Enjoy 🎉", 600),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _order_exists(conn: sqlite3.Connection, order_id: str) -> bool:
    return conn.execute("SELECT 1 FROM orders WHERE id=?", (order_id,)).fetchone() is not None


def _insert_order_from_dict(conn: sqlite3.Connection, o: dict) -> None:
    """Insert a pre-existing order dict (used to migrate legacy orders.json).

    Uses the caller's connection so it joins the same transaction.
    """
    created = o.get("created_at") or _now()
    conn.execute(
        "INSERT INTO orders(id,email,name,address,city,zip,payment,subtotal,shipping,tax,total,status,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (o["id"], o.get("customer", {}).get("email"), o.get("customer", {}).get("name"),
         o.get("shipping", {}).get("address"), o.get("shipping", {}).get("city"),
         o.get("shipping", {}).get("zip"), o.get("payment"), o.get("subtotal"),
         o.get("shipping_cost"), o.get("tax"), o.get("total"), o.get("status", "confirmed"), created),
    )
    for it in o.get("items", []):
        conn.execute(
            "INSERT INTO order_items(order_id,product_id,name,price,qty,line_total) VALUES(?,?,?,?,?,?)",
            (o["id"], it.get("id"), it.get("name"), it.get("price"), it.get("qty"), it.get("line_total")),
        )
    created_dt = datetime.fromisoformat(created)
    for stage, label, note, offset in TRACKING_STAGES:
        conn.execute(
            "INSERT INTO tracking_events(order_id,stage,label,note,at) VALUES(?,?,?,?,?)",
            (o["id"], stage, label, note, (created_dt + timedelta(seconds=offset)).isoformat()),
        )


def init_db() -> None:
    with DB_LOCK:
        conn = get_conn()
        try:
            conn.executescript(_SCHEMA)

            # Migration for existing DBs: ensure img_url2 column exists.
            cols = [r[1] for r in conn.execute("PRAGMA table_info(products)")]
            if "img_url2" not in cols:
                conn.execute("ALTER TABLE products ADD COLUMN img_url2 TEXT")
            # Migration: created_at tracks newest products (live/upcoming).
            if "created_at" not in cols:
                conn.execute("ALTER TABLE products ADD COLUMN created_at TEXT")
                from datetime import datetime as _dt, timezone as _tz
                base = _dt.now(tz=_tz.utc)
                _rows = conn.execute("SELECT id FROM products ORDER BY ROWID ASC").fetchall()
                for i, r in enumerate(_rows):
                    ts = base.replace(second=max(0, base.second - i)).isoformat()
                    conn.execute("UPDATE products SET created_at=? WHERE id=?", (ts, r["id"]))
            # Backfill any products missing an image with the placeholder.
            conn.execute("UPDATE products SET img_url=? WHERE img_url IS NULL OR img_url=''", (_PLACEHOLDER_IMG,))

            if conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"] == 0:
                for p in CATALOG:
                    conn.execute(
                        "INSERT INTO products(id,name,category,price,old_price,rating,reviews,stock,emoji,gradient0,gradient1,badge,description,img_url,img_url2) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (p["id"], p["name"], p["category"], round(p["price"] * USD_TO_INR),
                         round(p["old_price"] * USD_TO_INR) if p.get("old_price") else None,
                         p["rating"], p["reviews"], p["stock"], p["emoji"],
                         p["gradient"][0], p["gradient"][1], p.get("badge"),
                         p["description"], _img_url(p["id"], p["img_key"]),
                         _img_url2(p["id"], p["img_key"])),
                    )
            else:
                # Re-apply INR prices + image URLs to existing rows.
                for p in CATALOG:
                    conn.execute(
                        "UPDATE products SET price=?, old_price=?, img_url=?, img_url2=? WHERE id=?",
                        (round(p["price"] * USD_TO_INR),
                         round(p["old_price"] * USD_TO_INR) if p.get("old_price") else None,
                         _img_url(p["id"], p["img_key"]),
                         _img_url2(p["id"], p["img_key"]),
                         p["id"]),
                    )
            if os.path.exists(LEGACY_ORDERS):
                with open(LEGACY_ORDERS, encoding="utf-8") as fh:
                    legacy = json.load(fh)
                for o in legacy:
                    if not _order_exists(conn, o["id"]):
                        _insert_order_from_dict(conn, o)

            # Default manager account (used to log in on /manage).
            if not conn.execute("SELECT 1 FROM users WHERE email=?", ("sahilbadarkhe@gmail.com",)).fetchone():
                conn.execute("INSERT INTO users(name,email,pw_hash,created_at) VALUES(?,?,?,?)",
                             ("Sahil", "sahilbadarkhe@gmail.com", _hash_pw("sahil321"), _now()))
            conn.commit()
        finally:
            conn.close()


# --------------------------------------------------------------------------
# DB accessors
# --------------------------------------------------------------------------
def _product_row_to_dict(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "name": r["name"], "category": r["category"],
        "price": r["price"], "old_price": r["old_price"], "rating": r["rating"],
        "reviews": r["reviews"], "stock": r["stock"], "emoji": r["emoji"],
        "gradient": [r["gradient0"], r["gradient1"]], "badge": r["badge"],
        "description": r["description"], "img_url": r["img_url"] or _PLACEHOLDER_IMG,
        "img_url2": r["img_url2"] or None,
        "angles": _angle_urls(r["id"], r["name"], r["img_url"]),
    }


def _list_products(q: str, cat: str, sort: str) -> list[dict]:
    with DB_LOCK:
        conn = get_conn()
        try:
            sql = "SELECT * FROM products WHERE 1=1"
            args = []
            if q:
                sql += " AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ?)"
                like = f"%{q}%"
                args += [like, like]
            if cat != "All":
                sql += " AND category=?"
                args.append(cat)
            if sort == "price-asc":
                sql += " ORDER BY price ASC"
            elif sort == "price-desc":
                sql += " ORDER BY price DESC"
            elif sort == "rating":
                sql += " ORDER BY rating DESC"
            else:
                sql += " ORDER BY created_at DESC, ROWID DESC"
            rows = conn.execute(sql, args).fetchall()
            return [_product_row_to_dict(r) for r in rows]
        finally:
            conn.close()


def _get_product(product_id: str) -> dict | None:
    with DB_LOCK:
        conn = get_conn()
        try:
            r = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
            return _product_row_to_dict(r) if r else None
        finally:
            conn.close()


def _hash_pw(pw: str) -> str:
    salt = uuid.uuid4().hex[:16]
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120000).hex()
    return f"{salt}${digest}"


def _check_pw(pw: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120000).hex() == digest


def _create_session(conn: sqlite3.Connection, email: str) -> str:
    token = uuid.uuid4().hex
    conn.execute("INSERT INTO sessions(token,email,created_at) VALUES(?,?,?)", (token, email, _now()))
    return token


def _insert_order(conn: sqlite3.Connection, order: dict, items: list[dict], track: bool = True) -> None:
    conn.execute(
        "INSERT INTO orders(id,email,name,address,city,zip,payment,subtotal,shipping,tax,total,status,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (order["id"], order["customer"]["email"], order["customer"]["name"],
         order["shipping"]["address"], order["shipping"]["city"], order["shipping"]["zip"],
         order["payment"], order["subtotal"], order["shipping_cost"], order["tax"],
         order["total"], order["status"], order["created_at"]),
    )
    for it in items:
        conn.execute(
            "INSERT INTO order_items(order_id,product_id,name,price,qty,line_total) VALUES(?,?,?,?,?,?)",
            (order["id"], it["id"], it["name"], it["price"], it["qty"], it["line_total"]),
        )
    if track:
        created_dt = datetime.fromisoformat(order["created_at"])
        for stage, label, note, offset in TRACKING_STAGES:
            conn.execute(
                "INSERT INTO tracking_events(order_id,stage,label,note,at) VALUES(?,?,?,?,?)",
                (order["id"], stage, label, note, (created_dt + timedelta(seconds=offset)).isoformat()),
            )


def _tracking_for(order_id: str) -> list[dict]:
    with DB_LOCK:
        conn = get_conn()
        try:
            events = conn.execute(
                "SELECT stage,label,note,at FROM tracking_events WHERE order_id=? ORDER BY id", (order_id,)
            ).fetchall()
        finally:
            conn.close()
    now = _utcnow()
    out = []
    for e in events:
        scheduled = datetime.fromisoformat(e["at"])
        done = now >= scheduled
        out.append({
            "stage": e["stage"], "label": e["label"], "note": e["note"],
            "at": e["at"], "done": done,
        })
    return out


def _order_json(order_id: str) -> dict | None:
    with DB_LOCK:
        conn = get_conn()
        try:
            r = conn.execute("SELECT * FROM orders WHERE LOWER(id)=LOWER(?)", (order_id,)).fetchone()
            if not r:
                return None
            items = conn.execute(
                "SELECT product_id id,name,price,qty,line_total FROM order_items WHERE order_id=? ORDER BY id", (order_id,)
            ).fetchall()
        finally:
            conn.close()
    items = [dict(it) for it in items]
    tracking = _tracking_for(order_id)
    done_count = sum(1 for t in tracking if t["done"])
    status = tracking[-1]["label"] if tracking and done_count == len(tracking) else (tracking[done_count - 1]["label"] if done_count else "Order placed")
    return {
        "id": r["id"],
        "created_at": r["created_at"],
        "customer": {"name": r["name"], "email": r["email"]},
        "shipping": {"address": r["address"], "city": r["city"], "zip": r["zip"]},
        "payment": r["payment"],
        "items": items,
        "subtotal": r["subtotal"],
        "shipping_cost": r["shipping"],
        "tax": r["tax"],
        "total": r["total"],
        "status": status,
        "tracking": tracking,
    }


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)
app.config["JSON_SORT_KEYS"] = False
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1MB
app.config["TEMPLATES_AUTO_RELOAD"] = True  # pick up template edits without restart

init_db()


def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[\w.+-]+@[\w-]+\.[\w.-]+$", email))


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
@app.get("/api/products")
def list_products():
    q = (request.args.get("q") or "").strip().lower()
    cat = request.args.get("category") or "All"
    sort = request.args.get("sort") or "featured"
    payload = _list_products(q, cat, sort)
    return jsonify({"products": payload, "categories": CATEGORIES, "count": len(payload)})


@app.get("/api/products/<product_id>")
def get_product(product_id: str):
    p = _get_product(product_id)
    if not p:
        return jsonify({"error": "Product not found."}), 404
    return jsonify({"product": p})


@app.patch("/api/products/<product_id>")
def update_product(product_id: str):
    if not _manager_email():
        return jsonify({"error": "Manager login required."}), 401
    body = request.get_json(silent=True) or {}
    with DB_LOCK:
        conn = get_conn()
        try:
            row = conn.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone()
            if not row:
                return jsonify({"error": "Product not found."}), 404
            sets, vals = [], []
            if "price" in body:
                price = float(body["price"])
                if price < 0:
                    return jsonify({"error": "Price cannot be negative."}), 400
                sets.append("price=?"); vals.append(round(price, 2))
            if "old_price" in body:
                op = body["old_price"]
                sets.append("old_price=?"); vals.append(round(float(op), 2) if op not in (None, "") else None)
            if "stock" in body:
                stock = int(body["stock"])
                if stock < 0:
                    return jsonify({"error": "Stock cannot be negative."}), 400
                sets.append("stock=?"); vals.append(stock)
            if not sets:
                return jsonify({"error": "Nothing to update."}), 400
            vals.append(product_id)
            conn.execute(f"UPDATE products SET {', '.join(sets)} WHERE id=?", (*vals,))
            conn.commit()
            row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        finally:
            conn.close()
    return jsonify({"product": _product_row_to_dict(row)})


def _manager_email() -> str | None:
    """Return the logged-in manager email from a Bearer token, or None."""
    hdr = request.headers.get("Authorization", "")
    if not hdr.startswith("Bearer "):
        return None
    token = hdr[7:].strip()
    with DB_LOCK:
        conn = get_conn()
        try:
            row = conn.execute("SELECT email FROM sessions WHERE token=?", (token,)).fetchone()
            return row["email"] if row else None
        finally:
            conn.close()


def _clean_text(s: str) -> str:
    """HTML-encode user-supplied text so it can never execute as markup."""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#39;"))


@app.post("/api/products")
def create_product():
    if not _manager_email():
        return jsonify({"error": "Manager login required."}), 401
    body = request.get_json(silent=True) or {}
    name = _clean_text(str(body.get("name", "")).strip())
    category = _clean_text(str(body.get("category", "")).strip())
    price = body.get("price")
    stock = body.get("stock", 0)
    if not name or not category or price is None:
        return jsonify({"error": "Name, category and price are required."}), 400
    try:
        price = round(float(price), 2)
        stock = int(stock)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid price or stock."}), 400
    if price < 0 or stock < 0:
        return jsonify({"error": "Price/stock cannot be negative."}), 400

    description = _clean_text(str(body.get("description", "")).strip()) or "A brand-new product."
    old_price = body.get("old_price")
    old_price = round(float(old_price), 2) if old_price not in (None, "") else None
    emoji = _clean_text(str(body.get("emoji", "")).strip()) or "📦"
    grad0 = str(body.get("gradient0", "")).strip() or "#4f46e5"
    grad1 = str(body.get("gradient1", "")).strip() or "#a855f7"
    badge = _clean_text(str(body.get("badge", "")).strip()) or None
    try:
        rating = float(body.get("rating", 4.5))
        reviews = int(body.get("reviews", 0))
    except (TypeError, ValueError):
        rating, reviews = 4.5, 0
    img_url = str(body.get("img_url", "")).strip() or None
    img_url2 = str(body.get("img_url2", "")).strip() or None
    if img_url and not img_url.startswith(("http://", "https://")):
        img_url = None
    if img_url2 and not img_url2.startswith(("http://", "https://")):
        img_url2 = None
    if not img_url:
        img_url = _PLACEHOLDER_IMG

    pid = "p" + uuid.uuid4().hex[:8]
    with DB_LOCK:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO products(id,name,category,price,old_price,rating,reviews,stock,emoji,gradient0,gradient1,badge,description,img_url,img_url2,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, name, category, price, old_price, rating, reviews, stock, emoji,
                 grad0, grad1, badge, description, img_url, img_url2, _now()),
            )
            conn.commit()
        finally:
            conn.close()
    return jsonify({"product": _get_product(pid)}), 201


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
@app.post("/api/register")
def register():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    email = str(body.get("email", "")).strip().lower()
    pw = str(body.get("password", ""))
    if not name or not email or len(pw) < 4:
        return jsonify({"error": "Please fill in all fields (password 4+ chars)."}), 400
    if not _validate_email(email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    with DB_LOCK:
        conn = get_conn()
        try:
            if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                return jsonify({"error": "An account with that email already exists."}), 409
            conn.execute("INSERT INTO users(name,email,pw_hash,created_at) VALUES(?,?,?,?)",
                         (name, email, _hash_pw(pw), _now()))
            token = _create_session(conn, email)
            conn.commit()
            return jsonify({"token": token, "user": {"name": name, "email": email}}), 201
        finally:
            conn.close()


@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email", "")).strip().lower()
    pw = str(body.get("password", ""))
    with DB_LOCK:
        conn = get_conn()
        try:
            row = conn.execute("SELECT name,email,pw_hash FROM users WHERE email=?", (email,)).fetchone()
            if not row or not _check_pw(pw, row["pw_hash"]):
                return jsonify({"error": "Wrong email or password."}), 401
            token = _create_session(conn, email)
            conn.commit()
            return jsonify({"token": token, "user": {"name": row["name"], "email": row["email"]}})
        finally:
            conn.close()


# --------------------------------------------------------------------------
# Orders
# --------------------------------------------------------------------------
@app.post("/api/orders")
def create_order():
    body = request.get_json(silent=True) or {}
    items = body.get("items", [])
    if not items:
        return jsonify({"error": "Your cart is empty."}), 400

    name = str(body.get("name", "")).strip()
    email = str(body.get("email", "")).strip()
    address = str(body.get("address", "")).strip()
    city = str(body.get("city", "")).strip()
    zipcode = str(body.get("zip", "")).strip()
    payment = str(body.get("payment", "")).strip()

    if not name or not email or not address or not city or not zipcode:
        return jsonify({"error": "Please fill in every delivery field."}), 400
    if not _validate_email(email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if payment not in {"card", "paypal", "cod"}:
        return jsonify({"error": "Please choose a payment method."}), 400

    state = str(body.get("state", "")).strip()
    if state and state not in address:
        address = f"{address}, {state}"

    with DB_LOCK:
        conn = get_conn()
        try:
            # Decrement stock first.
            for line in items:
                pid = str(line.get("id", ""))
                try:
                    qty = int(line.get("qty", 0))
                except (TypeError, ValueError):
                    qty = 0
                row = conn.execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()
                if row is None or qty <= 0 or qty > 99:
                    return jsonify({"error": "One of the cart items is invalid."}), 400
                if qty > row["stock"]:
                    return jsonify({"error": "One of the cart items is out of stock."}), 400
            for line in items:
                pid = str(line.get("id", ""))
                qty = int(line.get("qty", 0))
                conn.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, pid))

            order_id = "NV-" + uuid.uuid4().hex[:10].upper()
            created = _now()
            line_items = []
            subtotal = 0.0
            for line in items:
                pid = str(line.get("id", ""))
                qty = int(line.get("qty", 0))
                row = conn.execute("SELECT name,price FROM products WHERE id=?", (pid,)).fetchone()
                line_total = round(row["price"] * qty, 2)
                subtotal += line_total
                line_items.append({"id": pid, "name": row["name"], "price": row["price"],
                                   "qty": qty, "line_total": line_total})
            subtotal = round(subtotal, 2)
            shipping = 0.0 if subtotal >= SHIP_FREE_ABOVE else SHIP_RATE
            tax = round(subtotal * TAX_RATE, 2)
            total = round(subtotal + shipping + tax, 2)
            order = {
                "id": order_id, "created_at": created,
                "customer": {"name": name, "email": email},
                "shipping": {"address": address, "city": city, "zip": zipcode},
                "payment": payment, "items": line_items,
                "subtotal": subtotal, "shipping_cost": shipping, "tax": tax,
                "total": total, "status": "Order placed",
            }
            _insert_order(conn, order, line_items)
            conn.commit()
            order["tracking"] = _tracking_for(order_id)
            return jsonify({"order": order}), 201
        finally:
            conn.close()


@app.get("/api/orders/<order_id>")
def get_order(order_id: str):
    o = _order_json(order_id)
    if not o:
        return jsonify({"error": "Order not found."}), 404
    return jsonify({"order": o})


@app.get("/api/orders/list")
def list_orders():
    """All orders (newest first) — powers the partner & management dashboards."""
    with DB_LOCK:
        conn = get_conn()
        try:
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM orders ORDER BY created_at DESC LIMIT 200"
            ).fetchall()]
        finally:
            conn.close()
    return jsonify({"orders": [_order_json(i) for i in ids]})


@app.patch("/api/orders/<order_id>/status")
def update_order_status(order_id: str):
    """Advance an order to a delivery stage (immediately done)."""
    body = request.get_json(silent=True) or {}
    stage = str(body.get("stage", "")).strip()
    allowed = {s for s, _l, _n, _d in TRACKING_STAGES}
    if stage not in allowed:
        return jsonify({"error": "Invalid status."}), 400
    with DB_LOCK:
        conn = get_conn()
        try:
            exists = conn.execute("SELECT id FROM orders WHERE LOWER(id)=LOWER(?)", (order_id,)).fetchone()
            if not exists:
                return jsonify({"error": "Order not found."}), 404
            idx = next(i for i, (s, _l, _n, _d) in enumerate(TRACKING_STAGES) if s == stage)
            # Mark every stage up to the target as done now (the store pre-schedules
            # future stages, so advancing a delivery must override those timestamps).
            conn.execute("DELETE FROM tracking_events WHERE order_id=?", (order_id,))
            for s, l, n, _d in TRACKING_STAGES[:idx + 1]:
                conn.execute(
                    "INSERT INTO tracking_events(order_id,stage,label,note,at) VALUES(?,?,?,?,?)",
                    (order_id, s, l, n, _now()),
                )
            conn.commit()
        finally:
            conn.close()
    return jsonify({"order": _order_json(order_id)})


@app.get("/api/health")
def health():
    with DB_LOCK:
        conn = get_conn()
        try:
            n = conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
        finally:
            conn.close()
    return jsonify({"status": "ok", "time": _now(), "products": n})


# --------------------------------------------------------------------------
# Chat assistant (VyceAi OpenAI-compatible endpoint, live DB context)
# --------------------------------------------------------------------------
VYCEAI_BASE = os.environ.get("VYCEAI_BASE_URL", "https://vyceai.com/v1")
VYCEAI_MODEL = os.environ.get("VYCEAI_MODEL", "auto")


def _vyceai_key() -> str | None:
    """Return the VyceAi API key from the environment only (never from files)."""
    return os.environ.get("VYCEAI_API_KEY") or None


SYSTEM_PROMPT = (
    "You are NOVA Assistant, the friendly support bot for the NOVA online store. "
    "You have live access to the store database, so answer with real, current data. "
    "Help with products (price, rating, stock), orders and delivery tracking. "
    "Order numbers look like NV-XXXXXXXXXX. Be concise, warm and helpful."
)


def _store_knowledge() -> str:
    products = _list_products("", "All", "featured")
    lines = [f"- {p['name']} ({p['category']}): ₹{p['price']:,.2f}, rating {p['rating']}, stock {p['stock']}" for p in products]
    return "Current catalog:\n" + "\n".join(lines)


def _tracking_text(order_id: str) -> str | None:
    o = _order_json(order_id)
    if not o:
        return None
    steps = " -> ".join(t["label"] for t in o["tracking"] if t["done"])
    return (f"Order {o['id']} status: {o['status']}. Progress: {steps}. "
            f"Items: {', '.join(i['name']+f' x{i['qty']}' for i in o['items'])}. Total ₹{o['total']:,.2f}.")


def _local_fallback(messages) -> str:
    text = " ".join((m.get("content", "") if isinstance(m, dict) else "") for m in messages).lower()
    m = re.search(r"\bNV-[A-Z0-9]{10}\b", text, re.I)
    if m:
        info = _tracking_text(m.group(0).upper())
        if info:
            return info
    if any(k in text for k in ("product", "recommend", "headphone", "watch", "keyboard", "monitor", "speaker", "what do you sell")):
        top = _list_products("", "All", "rating")[:3]
        s = ", ".join(f"{p['name']} (₹{p['price']:,.2f})" for p in top)
        return f"Our top-rated products right now: {s}. Browse the grid above for the full catalog."
    if any(k in text for k in ("shipping", "delivery", "free shipping")):
        return "We ship free on all orders over ₹5,000, dispatch within 24h, standard delivery 2–4 business days across India."
    if any(k in text for k in ("return", "refund")):
        return "You have 30 days for a no-quibble return. Reply with your order number and I'll start it."
    return ("I'm the NOVA assistant. I have live access to the store — I can check a product's "
            "price and stock, or look up an order (e.g. NV-FD6C4B235D) and tell you exactly where it is.")


@app.post("/api/chat")
def chat():
    body = request.get_json(silent=True) or {}
    messages = body.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "No messages provided."}), 400

    key = _vyceai_key()

    # Build live context.
    knowledge = _store_knowledge()
    last_user = messages[-1].get("content", "") if isinstance(messages[-1], dict) else ""
    ctx_extra = ""
    m = re.search(r"\bNV-[A-Z0-9]{10}\b", last_user, re.I)
    if m:
        info = _tracking_text(m.group(0).upper())
        ctx_extra = f"\nLive order lookup: {info}" if info else ""

    if not key:
        return jsonify({"reply": _local_fallback(messages), "fallback": True})

    import urllib.request
    import urllib.error

    system2 = SYSTEM_PROMPT + "\n\n" + knowledge + ctx_extra
    payload = {
        "model": VYCEAI_MODEL,
        "messages": [{"role": "system", "content": system2}] + messages[-8:],
        "stream": False,
        "max_tokens": 350,
    }
    url = VYCEAI_BASE.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.load(resp)
        reply = data["choices"][0]["message"]["content"]
        return jsonify({"reply": reply})
    except Exception:
        return jsonify({"reply": _local_fallback(messages), "fallback": True})


@app.get("/partner")
def partner_dashboard():
    return render_template("partner.html")


@app.get("/manage")
def manage_dashboard():
    return render_template("manage.html")


@app.get("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    import sys

    # Optional launch flags (kept out of any file):
    #   --api-key <key>   VyceAi API key (overrides nothing if VYCEAI_API_KEY set)
    #   --model <name>    chatbot model (overrides nothing if VYCEAI_MODEL set)
    for i, arg in enumerate(sys.argv):
        if arg == "--api-key" and i + 1 < len(sys.argv):
            os.environ.setdefault("VYCEAI_API_KEY", sys.argv[i + 1])
        if arg == "--model" and i + 1 < len(sys.argv):
            os.environ.setdefault("VYCEAI_MODEL", sys.argv[i + 1])

    print("  NOVA store running at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
