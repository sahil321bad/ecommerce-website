"""Lightweight smoke test for the NOVA store API."""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5000"
passed = 0
failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return r.status, json.load(r)


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


print("== Health ==")
s, body = get("/api/health")
check("health 200", s == 200 and body["status"] == "ok")

print("\n== Products ==")
s, body = get("/api/products")
check("products 200", s == 200)
check("has products", body["count"] >= 8)
check("has categories", "Gaming" in body["categories"])
first = body["products"][0]
check("product schema", all(k in first for k in ("id", "name", "price", "category", "stock", "gradient", "emoji")))

s, body = get("/api/products?category=Audio")
check("filter category", all(p["category"] == "Audio" for p in body["products"]))

s, body = get("/api/products?q=headphones")
check("search q", any("headphones" in p["name"].lower() for p in body["products"]))

s, body = get("/api/products?sort=price-asc")
prices = [p["price"] for p in body["products"]]
check("sort price asc", prices == sorted(prices))

print("\n== Orders ==")
payload = {
    "name": "Test User",
    "email": "test@example.com",
    "address": "1 Test St",
    "city": "Testville",
    "zip": "12345",
    "payment": "card",
    "items": [{"id": first["id"], "qty": 2}],
}
s, body = post("/api/orders", payload)
check("order created 201", s == 201)
order = body.get("order", {})
check("order has id", order.get("id", "").startswith("NV-"))
expected_total = round(first["price"] * 2 + round(first["price"] * 2 * 0.18, 2), 2)
check("order total math", abs(order.get("total", -1) - expected_total) < 0.01)
check("item line computed", order["items"][0]["line_total"] == round(first["price"] * 2, 2))

s, body = get(f"/api/orders/{order['id']}")
check("fetch order 200", s == 200 and body["order"]["id"] == order["id"])

s, body = post("/api/orders", {})
check("empty cart rejected 400", s == 400)

s, body = post("/api/orders", {**payload, "email": "not-an-email"})
check("bad email rejected 400", s == 400)

s, body = post("/api/orders", {**payload, "items": [{"id": "nope", "qty": 1}]})
check("bad product rejected 400", s == 400)

s, body = post("/api/orders", {**payload, "items": [{"id": first["id"], "qty": 9999}]})
check("oversell rejected 400", s == 400)

print(f"\nRESULT: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
