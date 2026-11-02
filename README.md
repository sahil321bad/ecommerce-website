# NOVA · Premium Gadget Store

A fully functional e-commerce web application — real SQLite database, REST API,
manager dashboard, delivery-partner dashboard, live product publishing, and an AI
customer chat assistant. Built with Flask + vanilla JavaScript.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)

---

## ✨ Features

### For shoppers (main store)
- **Product catalog** with real internet images, categories, search, filter, and sort
- **Product cards** with price, old price, discount %, stock badges, and rating
- **Quick add / quick view** — add to cart or open a product modal without leaving the page
- **Shopping cart** in `localStorage` with quantity controls and grand totals (incl. shipping + 18% GST)
- **Checkout** with full delivery form (name, email, address, state, PIN), payment method (Card / PayPal / COD)
- **Order confirmation** modal with live order number
- **Responsive dark/light theme** toggle (persisted)
- **AI chatbot** — answers customer questions via an LLM API (OmniRoute-compatible)

### For store managers (`/manage`)
- **Add new product** — name, category, price, old price, stock, emoji, description, image URL
- **Publish live** — new products appear at the top of the store in real time
- **Edit price / old price / stock** inline
- **Recent orders** feed
- **Password-protected** — only logged-in managers can create/edit products

### For delivery partners (`/partner`)
- Live view of all orders with customer details
- **Update order status** (e.g. → *Packed* → *Out for delivery* → *Delivered*)
- Auto-refreshing list

### Under the hood
- Real **SQLite** storage: users, sessions, products, orders, order items, tracking events
- REST API with auth (Bearer tokens), input validation, and **XSS sanitization** of user content
- Auto-seeded catalog and default manager account
- 17 passing API tests

---

## 🚀 Getting started

### Prerequisites
- Python 3.10+
- (Optional) An LLM API key for the customer chatbot

### 1. Clone
```bash
git clone https://github.com/<your-user>/nova-store.git
cd nova-store
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run
```bash
python main.py
```
Then open **http://127.0.0.1:5000/** in your browser.

> **With chatbot API key (optional):**
> ```bash
> python main.py --api-key YOUR_KEY --model "GPT 6 Luna"
> ```

### 4. Use it
| Page | URL |
|---|---|
| Store | http://127.0.0.1:5000/ |
| Store Manager | http://127.0.0.1:5000/manage |
| Partner dashboard | http://127.0.0.1:5000/partner |

**Default manager login** (for `/manage`):
```
email:    sahilbadarkhe@gmail.com
password: sahil321
```

---

## 📁 Project structure

```
.
├── main.py              # Flask app: routes, DB, auth, API
├── requirements.txt     # Python dependencies
├── test_api.py          # Pytest-style smoke tests (17 checks)
├── templates/
│   ├── index.html       # Main store
│   ├── manage.html      # Store manager dashboard
│   └── partner.html     # Delivery partner dashboard
├── static/
│   ├── css/style.css    # All styling (themes, modals, responsive)
│   └── js/app.js        # Frontend logic (cart, checkout, theme, chatbot, polling)
└── data/
    ├── nova.db          # SQLite database (created at runtime)
    └── orders.json      # Legacy seed orders (imported on first boot)
```

---

## 📡 API overview

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/health` | Health check + counts | — |
| GET | `/api/products` | List products (`?q=&category=&sort=`) | — |
| GET | `/api/products/<id>` | Single product | — |
| POST | `/api/products` | Create product | 🔑 Manager |
| PATCH | `/api/products/<id>` | Update price/stock | 🔑 Manager |
| POST | `/api/register` | Register a manager account | — |
| POST | `/api/login` | Log in → token | — |
| POST | `/api/orders` | Place an order | — |
| GET | `/api/orders/<id>` | Fetch an order | — |
| GET | `/api/orders/list` | All orders (partner/manager) | — |
| PATCH | `/api/orders/<id>/status` | Update order status | — |
| POST | `/api/chat` | Chat with the AI assistant | — |

---

## 🧪 Running tests

```bash
python test_api.py
```
Expected result: **17 passed, 0 failed**.

---

## 🔒 Security notes

- Manager actions (`POST`/`PATCH /api/products`) require a Bearer token.
- Passwords are hashed with **PBKDF2-SHA256** (120k iterations).
- User-supplied text is HTML-encoded at the input boundary (prevents stored XSS).
- Image URLs are restricted to `http(s)://`.

> ⚠️ This is a demo. For production, place it behind a real WSGI server (e.g. Gunicorn),
> serve over HTTPS, add rate limiting, and put the dashboards behind full session auth.

---

## 📄 License

Demo project — free to use and modify for learning purposes.
