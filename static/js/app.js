/* =====================================================================
   NOVA — frontend application
   Handles: product catalog (fetch/API), search + filter + sort, cart
   (localStorage), checkout modal (API order), theme toggle, toasts.
   ===================================================================== */
(() => {
  "use strict";


  const API = "/api/products";
  const ORDER_API = "/api/orders";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // Two-step real-image fallback: Unsplash -> loremflickr -> hide (emoji shows).
  window.useImg = (img) => {
    const alt = img.getAttribute("data-alt");
    if (alt && img.src.indexOf(alt) === -1) {
      img.setAttribute("data-alt", "");
      img.onerror = () => window.useImg(img);
      img.src = alt;
    } else {
      img.style.display = "none";
    }
  };

  /* ---------------- State ---------------- */
  const state = {
    products: [],
    categories: ["All"],
    activeCategory: "All",
    query: "",
    sort: "featured",
    cart: loadCart(), // { [productId]: qty }
  };

  /* ---------------- Theme ---------------- */
  const THEME_KEY = "nova-theme";
  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = saved ? saved : (prefersDark ? "dark" : "light");
  }
  function toggleTheme() {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem(THEME_KEY, next);
  }

  /* ---------------- Cart (localStorage) ---------------- */
  const CART_KEY = "nova-cart";
  function loadCart() {
    try { return JSON.parse(localStorage.getItem(CART_KEY)) || {}; }
    catch { return {}; }
  }
  function saveCart() {
    localStorage.setItem(CART_KEY, JSON.stringify(state.cart));
    renderCartBadge();
  }
  function cartCount() { return Object.values(state.cart).reduce((a, b) => a + b, 0); }
  function findProduct(id) { return state.products.find(p => p.id === id); }

  /* ---------------- Toast ---------------- */
  let toastTimer;
  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
  }

  /* ---------------- Loading ---------------- */
  const loading = {
    show() { $("#loadingBar").hidden = false; },
    hide() { $("#loadingBar").hidden = true; },
  };

  /* ---------------- Helpers ---------------- */
  function money(n) {
    return "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function stars(rating) {
    const full = Math.round(rating);
    let s = "";
    for (let i = 0; i < 5; i++) s += i < full ? "★" : "☆";
    return s;
  }
  function stockTag(p) {
    if (p.stock === 0) return '<span class="stock-tag out">Out of stock</span>';
    if (p.stock <= 10) return `<span class="stock-tag low">Only ${p.stock} left</span>`;
    return '<span class="stock-tag in">In stock</span>';
  }
  function discountPct(p) {
    if (!p.old_price) return null;
    return Math.round((1 - p.price / p.old_price) * 100);
  }
  function cardTemplate(p) {
    const disc = discountPct(p);
    const save = disc ? `<span class="price-save">-${disc}%</span>` : "";
    const old = p.old_price ? `<span class="price-old">${money(p.old_price)}</span>` : "";
    return `
      <article class="card" data-open="${p.id}" data-id="${p.id}" style="animation-delay:0s">
        <div class="card-media" style="background:linear-gradient(135deg,${p.gradient[0]},${p.gradient[1]})">
          <img class="card-img" src="${p.img_url || p.img_url2}" data-alt="${p.img_url2 || ''}" alt="${p.name}" loading="lazy" onerror="useImg(this)">
          ${p.badge ? `<span class="badge">${p.badge}</span>` : ""}
          <span class="card-emoji">${p.emoji}</span>
          <button class="quick-view" data-view="${p.id}" aria-label="View ${p.name}" title="View product">👁</button>
          <button class="quick-add" data-add="${p.id}" aria-label="Add ${p.name} to cart" title="Add to cart">＋</button>
        </div>
        <div class="card-body">
          <span class="card-cat">${p.category}</span>
          <h3 class="card-title">${p.name}</h3>
          <p class="card-desc">${p.description}</p>
          <div class="stars"><span class="star">${stars(p.rating)}</span><span class="rating-num">${p.rating.toFixed(1)}</span><span style="color:var(--muted)">(${p.rating.toLocaleString()})</span></div>
          <div class="card-foot">
            <div class="price-wrap"><span class="price">${money(p.price)}</span>${old}${save}</div>
            ${stockTag(p)}
          </div>
          <button class="btn-add" data-add="${p.id}" ${p.stock === 0 ? "disabled style='opacity:.5;cursor:not-allowed'" : ""}>
            ${p.stock === 0 ? "Unavailable" : "Add to cart"}
          </button>
        </div>
      </article>`;
  }

  /* ---------------- Render catalog ---------------- */
  function renderChips() {
    const wrap = $("#categoryChips");
    wrap.innerHTML = state.categories.map(c =>
      `<button class="chip ${c === state.activeCategory ? "is-active" : ""}" data-cat="${c}">${c}</button>`
    ).join("");
  }

  function renderProducts() {
    const grid = $("#productGrid");
    const empty = $("#emptyState");
    const countLabel = $("#resultCount");

    if (!state.products.length) {
      grid.innerHTML = "";
      empty.hidden = false;
      countLabel.textContent = "0 products";
      return;
    }
    empty.hidden = true;
    grid.innerHTML = state.products.map(cardTemplate).join("");
    countLabel.textContent = `${state.products.length} product${state.products.length > 1 ? "s" : ""} · ${state.activeCategory} · ${state.sort.replace("-", " ")}`;
  }

  async function fetchProducts() {
    loading.show();
    try {
      const params = new URLSearchParams();
      if (state.query) params.set("q", state.query);
      if (state.activeCategory !== "All") params.set("category", state.activeCategory);
      params.set("sort", state.sort);
      const res = await fetch(`${API}?${params}`);
      if (!res.ok) throw new Error("Request failed");
      const data = await res.json();
      state.products = data.products;
      state.categories = data.categories;
      renderChips();
      renderProducts();
      renderRail();
    } catch (err) {
      $("#productGrid").innerHTML = "";
      $("#emptyState").hidden = false;
      $("#resultCount").textContent = "Couldn't load products.";
      console.error(err);
    } finally {
      loading.hide();
    }
  }

  let productsSig = "";
  async function pollProducts() {
    try {
      const params = new URLSearchParams();
      if (state.query) params.set("q", state.query);
      if (state.activeCategory !== "All") params.set("category", state.activeCategory);
      params.set("sort", state.sort);
      const res = await fetch(`${API}?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      const sig = JSON.stringify(data.products.map(p => p.id + "|" + p.stock + "|" + p.price));
      if (sig !== productsSig) {
        productsSig = sig;
        state.products = data.products;
        state.categories = data.categories;
        renderChips();
        renderProducts();
        renderRail();
      }
    } catch (e) { /* silent */ }
  }

  /* ---------------- Cart render / actions ---------------- */
  function renderCart() {
    const wrap = $("#cartItems");
    const empty = $("#cartEmpty");
    const foot = $("#cartFoot");
    const ids = Object.keys(state.cart);

    wrap.innerHTML = "";
    let subtotal = 0;

    for (const id of ids) {
      const p = findProduct(id);
      const qty = state.cart[id];
      if (!p) continue;
      const line = p.price * qty;
      subtotal += line;
      wrap.insertAdjacentHTML("beforeend", `
        <div class="cart-line" data-line="${p.id}">
          <div class="cart-line-thumb" style="background:linear-gradient(135deg,${p.gradient[0]},${p.gradient[1]})">${p.emoji}</div>
          <div class="cart-line-info">
            <div class="cart-line-name">${p.name}</div>
            <div class="cart-line-price">${money(p.price)} each</div>
            <div class="qty-row">
              <button class="qty-btn" data-qty="dec" data-id="${p.id}">−</button>
              <span class="qty-val">${qty}</span>
              <button class="qty-btn" data-qty="inc" data-id="${p.id}">＋</button>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
            <span class="cart-line-sub">${money(line)}</span>
            <button class="remove-line" data-remove="${p.id}" aria-label="Remove ${p.name}">✕</button>
          </div>
        </div>`);
    }

    const hasItems = ids.length > 0;
    empty.hidden = hasItems;
    foot.hidden = !hasItems;

    if (hasItems) {
      const shipping = subtotal >= 5000 ? 0 : 299;
      const total = subtotal + shipping;
      $("#cartSubtotal").textContent = money(subtotal);
      $("#cartShipping").textContent = shipping === 0 ? "Free" : money(shipping);
      $("#cartTotal").textContent = money(total);
    }
  }

  function addToCart(id, qty = 1) {
    const p = findProduct(id);
    if (!p) return;
    if (p.stock === 0) { toast("This item is out of stock."); return; }
    const cur = state.cart[id] || 0;
    if (cur + qty > p.stock) { toast(`Only ${p.stock} left of ${p.name}.`); state.cart[id] = p.stock; saveCart(); renderCart(); return; }
    state.cart[id] = cur + qty;
    saveCart();
    renderCart();
    toast(`${p.name} added to cart ✓`);
  }

  function changeQty(id, delta) {
    const cur = state.cart[id] || 0;
    const next = cur + delta;
    if (next <= 0) { delete state.cart[id]; }
    else { state.cart[id] = next; }
    saveCart();
    renderCart();
  }

  function removeFromCart(id) {
    delete state.cart[id];
    saveCart();
    renderCart();
  }

  function renderCartBadge() {
    const count = cartCount();
    const badge = $("#cartCount");
    badge.hidden = count === 0;
    badge.textContent = count > 99 ? "99+" : count;
  }

  /* ---------------- Drawer ---------------- */
  function openCart() { renderCart(); $("#overlay").hidden = false; $("#cartDrawer").hidden = false; document.body.style.overflow = "hidden"; }
  function closeCart() { $("#overlay").hidden = true; $("#cartDrawer").hidden = true; document.body.style.overflow = ""; }

  /* ---------------- Checkout ---------------- */
  function openCheckout() {
    const ids = Object.keys(state.cart);
    if (!ids.length) { toast("Your cart is empty."); return; }

    const subtotal = ids.reduce((acc, id) => {
      const p = findProduct(id);
      return acc + (p ? p.price * state.cart[id] : 0);
    }, 0);
    const shipping = subtotal >= 5000 ? 0 : 299;
    const tax = subtotal * 0.18;
    const total = subtotal + shipping + tax;

    $("#coSubtotal").textContent = money(subtotal);
    $("#coShipping").textContent = money(shipping);
    $("#coTax").textContent = money(tax);
    $("#coTotal").textContent = money(total);
    $("#placeOrderAmt").textContent = money(total);

    // Always ensure the place-order button is enabled & clickable.
    const ob = $("#placeOrderBtn");
    ob.disabled = false;

    $("#checkoutForm").reset();
    $("#formMsg").hidden = true;
    $$(".invalid", $("#checkoutForm")).forEach(i => i.classList.remove("invalid"));
    $("#checkoutBackdrop").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeCheckout() { $("#checkoutBackdrop").hidden = true; document.body.style.overflow = ""; }

  function showFormError(msg) {
    const el = $("#formMsg");
    el.textContent = msg;
    el.hidden = false;
  }

  let submitting = false;
  async function placeOrder(e) {
    if (e && e.type === "submit") e.preventDefault();
    if (submitting) return;
    submitting = true;

    const form = $("#checkoutForm");
    const btn = $("#placeOrderBtn");
    const amt = $("#placeOrderAmt");
    const ctrl = new AbortController();
    let timer = null;
    try {
      const name = $("#coName").value.trim();
      const email = $("#coEmail").value.trim();
      let address = $("#coAddress").value.trim();
      const city = $("#coCity").value.trim();
      const stName = $("#coState").value.trim();
      const zip = $("#coZip").value.trim();
      const payment = (form.querySelector('input[name="payment"]:checked') || {}).value;

      // Validate all required fields — text inputs AND the state field.
      let valid = true;
      $$("[required]", form).forEach(el => {
        const val = (el.value || "").trim();
        el.classList.toggle("invalid", !val);
        if (!val) valid = false;
      });
      if (!valid) { showFormError("Please fill in every delivery field (including state)."); return; }
      if (!/^\d{6}$/.test(zip)) {
        $("#coZip").classList.add("invalid");
        showFormError("Enter a valid 6-digit Indian PIN code.");
        return;
      }
      address = (address + ", " + stName).trim();
      if (!/^[\w.+-]+@[\w-]+\.[\w.-]+$/.test(email)) {
        $("#coEmail").classList.add("invalid");
        showFormError("That email address doesn't look right.");
        return;
      }

      const items = Object.entries(state.cart).map(([id, qty]) => ({ id, qty }));
      if (!items.length) { toast("Your cart is empty."); return; }

      timer = setTimeout(() => ctrl.abort(), 15000);
      btn.disabled = true;
      btn.textContent = "Placing order…";

      const res = await fetch(ORDER_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, address, city, zip, payment, items }),
        signal: ctrl.signal,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong.");

      // success
      $("#successName").textContent = name;
      $("#successEmail").textContent = email;
      $("#successOrderId").textContent = data.order.id;
      closeCheckout();
      $("#successBackdrop").hidden = false;
      recordOrder({ id: data.order.id, email, date: new Date().toISOString(), total: data.order.total, status: "confirmed" });

      state.cart = {};
      saveCart();
      renderCart();
      toast(`Order ${data.order.id} confirmed 🎉`);
    } catch (err) {
      console.error("placeOrder:", err);
      showFormError(err.name === "AbortError" ? "Request timed out — please try again." : (err.message || "Could not place your order."));
    } finally {
      if (timer) clearTimeout(timer);
      btn.disabled = false;
      btn.textContent = "Place order — ";
      btn.appendChild(amt);
      submitting = false;
    }
  }

  function closeSuccess() {
    $("#successBackdrop").hidden = true;
    document.body.style.overflow = "";
    closeCart();
  }

  /* ---------------- Hero slider ---------------- */
  function initHeroSlider() {
    const track = $("#heroTrack");
    const dotsWrap = $("#heroDots");
    if (!track || !dotsWrap) return;
    const slides = Array.from(track.children);
    if (!slides.length) return;

    slides.forEach((_, i) => {
      const d = document.createElement("button");
      d.className = "dot";
      d.type = "button";
      d.setAttribute("aria-label", `Go to slide ${i + 1}`);
      d.addEventListener("click", () => { goTo(i); restart(); });
      dotsWrap.appendChild(d);
    });
    const dots = Array.from(dotsWrap.children);

    let cur = 0;
    let timer = null;

    function goTo(i) {
      cur = (i + slides.length) % slides.length;
      track.style.transform = `translateX(-${cur * 100}%)`;
      slides.forEach((s, k) => s.classList.toggle("is-active", k === cur));
      dots.forEach((d, k) => d.classList.toggle("active", k === cur));
    }

    function restart() {
      clearInterval(timer);
      timer = setInterval(() => goTo(cur + 1), 5200);
    }

    $("#heroPrev").addEventListener("click", () => { goTo(cur - 1); restart(); });
    $("#heroNext").addEventListener("click", () => { goTo(cur + 1); restart(); });

    const hero = $("#heroSlider");
    hero.addEventListener("mouseenter", () => clearInterval(timer));
    hero.addEventListener("mouseleave", restart);

    restart();
  }

  /* ---------------- Trending rail ---------------- */
  function renderRail() {
    const track = $("#railTrack");
    if (!track) return;
    const picks = state.products.slice(0, 8);
    if (!picks.length) { track.innerHTML = ""; return; }
    track.innerHTML = picks.map(cardTemplate).join("");
  }

  /* ---------------- Auth (demo, localStorage) ---------------- */
  const USERS_KEY = "nova-users";
  const SESSION_KEY = "nova-session";

  function loadUsers() { try { return JSON.parse(localStorage.getItem(USERS_KEY)) || []; } catch { return []; } }
  function saveUsers(u) { localStorage.setItem(USERS_KEY, JSON.stringify(u)); }
  function currentUser() { try { return JSON.parse(localStorage.getItem(SESSION_KEY)) || null; } catch { return null; } }
  function setSession(u) { if (u) localStorage.setItem(SESSION_KEY, JSON.stringify(u)); else localStorage.removeItem(SESSION_KEY); }

  function setAuthUI() {
    const u = currentUser();
    const btn = $("#accountBtn");
    if (u) {
      btn.innerHTML = '<span class="mini-avatar">' + (u.name ? u.name[0].toUpperCase() : "?") + "</span>";
      btn.title = u.name;
    } else {
      btn.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/></svg>';
      btn.title = "Account";
    }
  }

  function openAuth(mode) {
    const register = (mode || "login") === "register";
    $("#tabLogin").classList.toggle("is-active", !register);
    $("#tabRegister").classList.toggle("is-active", register);
    $("#authTitle").textContent = register ? "Create account" : "Login";
    $("#authSubmitBtn").textContent = register ? "Create account" : "Login";
    $("#authNameField").hidden = !register;
    $("#authMsg").hidden = true;
    $("#authForm").reset();
    $("#authBackdrop").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeAuth() { $("#authBackdrop").hidden = true; document.body.style.overflow = ""; }

  function handleAuthSubmit(e) {
    e.preventDefault();
    const msg = $("#authMsg");
    const email = $("#authEmail").value.trim().toLowerCase();
    const pass = $("#authPass").value;
    const register = !$("#authNameField").hidden;
    if (!/^[\w.+-]+@[\w-]+\.[\w.-]+$/.test(email)) { msg.textContent = "Please enter a valid email."; msg.hidden = false; return; }
    if (pass.length < 4) { msg.textContent = "Password must be at least 4 characters."; msg.hidden = false; return; }
    const users = loadUsers();
    if (register) {
      const name = $("#authName").value.trim();
      if (!name) { msg.textContent = "Please enter your name."; msg.hidden = false; return; }
      if (users.some(u => u.email === email)) { msg.textContent = "An account with that email already exists — please login."; msg.hidden = false; return; }
      const u = { name, email, pass };
      users.push(u); saveUsers(users); setSession({ name, email });
      toast(`Welcome, ${name}! 🎉`);
    } else {
      const u = users.find(x => x.email === email && x.pass === pass);
      if (!u) { msg.textContent = "Wrong email or password."; msg.hidden = false; return; }
      setSession({ name: u.name, email });
      toast(`Welcome back, ${u.name}! 👋`);
    }
    setAuthUI(); closeAuth();
  }

  /* ---------------- Chat ---------------- */
  function openChat() {
    const p = $("#chatPanel");
    p.hidden = false;
    if (!p.dataset.booted) {
      p.dataset.booted = "1";
      appendMsg("bot", "Hi! I'm NOVA Assistant 🤖 I can help you track orders, check shipping & returns, or recommend products. What do you need?");
    }
    setTimeout(() => $("#chatText").focus(), 60);
  }
  function closeChat() { $("#chatPanel").hidden = true; }
  function appendMsg(who, text) {
    const body = $("#chatBody");
    const div = document.createElement("div");
    div.className = "msg " + who;
    div.textContent = text;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
  }
  async function sendChat(text) {
    text = (text || "").trim();
    if (!text) return;
    appendMsg("user", text);
    const body = $("#chatBody");
    const t = document.createElement("div");
    t.className = "msg bot typing"; t.textContent = "…";
    body.appendChild(t); body.scrollTop = body.scrollHeight;
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [{ role: "user", content: text }] }),
      });
      const data = await res.json();
      t.remove();
      appendMsg("bot", data.reply || "Sorry, I couldn't process that.");
    } catch (err) {
      t.remove();
      appendMsg("bot", "Sorry, I'm having trouble connecting right now. Please try again in a moment.");
    }
  }

  /* ---------------- Product angle viewer ---------------- */
  let angleProduct = null;
  const ANGLE_VIEWS = [
    { label: "Front", tf: "rotateY(0deg) scale(1)" },
    { label: "Tilt", tf: "rotateY(-18deg) rotateX(6deg) scale(1.06)" },
    { label: "Side", tf: "rotateY(70deg) scale(.95)" },
  ];
  const ANGLE_ICONS = ["🧿", "🌀", "🔄"];

  function openAngles(id) {
    angleProduct = findProduct(id);
    if (!angleProduct) return;
    const p = angleProduct;
    $("#anglesName").textContent = p.name;
    $("#anglesCat").textContent = p.category;
    $("#anglesPrice").textContent = money(p.price);
    $("#anglesThumbs").innerHTML = ANGLE_VIEWS.map((v, i) =>
      `<button type="button" data-angle="${i}" aria-label="${v.label}">${ANGLE_ICONS[i]}</button>`
    ).join("");
    selectAngle(0);
    $("#anglesBackdrop").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function selectAngle(i) {
    const stage = $("#anglesStage");
    const p = angleProduct;
    if (!p) return;
    const v = ANGLE_VIEWS[i];
    stage.style.background = `linear-gradient(135deg, ${p.gradient[0]}, ${p.gradient[1]})`;
    stage.innerHTML = `<span class="big-emoji" style="transform:${v.tf}">${p.emoji}</span>`;
    $$("#anglesThumbs button").forEach(b => b.classList.toggle("is-active", +b.dataset.angle === i));
  }
  function closeAngles() { angleProduct = null; $("#anglesBackdrop").hidden = true; document.body.style.overflow = ""; }

  /* ---------------- Profile / orders / tracking ---------------- */
  const ORDERS_KEY = "nova-orders";
  function loadMyOrders() { try { return JSON.parse(localStorage.getItem(ORDERS_KEY)) || []; } catch { return []; } }
  function recordOrder(o) { const arr = loadMyOrders(); arr.push(o); localStorage.setItem(ORDERS_KEY, JSON.stringify(arr)); }

  function openProfile() {
    const u = currentUser();
    if (!u) { openAuth("login"); return; }
    $("#profileName").textContent = u.name;
    $("#profileAvatar").textContent = u.name ? u.name[0].toUpperCase() : "🧑";
    $("#profileEmail").textContent = u.email;
    renderProfileOrders();
    $("#profileBackdrop").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeProfile() { $("#profileBackdrop").hidden = true; document.body.style.overflow = ""; }
  function renderProfileOrders() {
    const u = currentUser();
    const wrap = $("#orderList");
    const panel = $("#profileOrders");
    if (!u) { panel.hidden = true; return; }
    const mine = loadMyOrders().filter(o => o.email === u.email);
    panel.hidden = false;
    if (!mine.length) { wrap.innerHTML = '<small style="color:var(--muted)">No orders yet.</small>'; return; }
    wrap.innerHTML = mine.slice().reverse().map(o =>
      `<div class="order-row" data-track="${o.id}"><div><b>${o.id}</b><small>${new Date(o.date).toLocaleDateString()} · ${money(o.total)}</small></div><small style="color:var(--brand)">${o.status}</small></div>`
    ).join("");
  }

  function openTrack() {
    $("#trackForm").reset(); $("#trackMsg").hidden = true; $("#trackResult").hidden = true;
    $("#trackBackdrop").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeTrack() { $("#trackBackdrop").hidden = true; document.body.style.overflow = ""; }
  function renderTracker(tracking) {
    const cur = tracking.findIndex(t => !t.done);
    const html = tracking.map((t, i) => {
      const cls = t.done ? "done" : (i === cur ? "current" : "");
      return `<div class="st ${cls}"><span class="dot"></span><small>${t.label}</small></div>`;
    }).join("");
    return `<div class="tracker">${html}</div>`;
  }

  async function doTrack(e) {
    e.preventDefault();
    const id = $("#trackId").value.trim();
    const msg = $("#trackMsg");
    const res = $("#trackResult");
    if (!id) { msg.textContent = "Please enter an order number."; msg.hidden = false; return; }
    msg.hidden = true;
    try {
      const r = await fetch("/api/orders/" + encodeURIComponent(id));
      const data = await r.json();
      if (!r.ok || !data.order) { msg.textContent = data.error || "Order not found."; msg.hidden = false; res.hidden = true; return; }
      const o = data.order;
      const steps = (o.tracking && o.tracking.length) ? renderTracker(o.tracking) : "";
      const items = o.items.map(it => `<div class="row"><span>${it.name} × ${it.qty}</span><span>${money(it.line_total)}</span></div>`).join("");
      res.innerHTML =
        `<span class="track-status">● ${o.status}</span>` +
        steps +
        `<div class="track-order-items">${items}</div>` +
        `<div class="row" style="margin-top:10px"><span>Subtotal</span><span>${money(o.subtotal)}</span></div>` +
        `<div class="row"><span>Shipping</span><span>${o.shipping_cost ? money(o.shipping_cost) : "Free"}</span></div>` +
        `<div class="row"><span>Tax</span><span>${money(o.tax)}</span></div>` +
        `<div class="row total-row"><span>Total</span><span>${money(o.total)}</span></div>`;
      res.hidden = false;
    } catch (err) {
      msg.textContent = "Couldn't reach the tracking service."; msg.hidden = false; res.hidden = true;
    }
  }

  /* ---------------- Dedicated product page /--------------- */
  let ppId = null, ppQty = 1, ppAngle = 0, ppProduct = null;

  const PP_VIEWS = [
    { ang: "Full", pos: "50% 50%", zoom: 1 },
    { ang: "Zoom left", pos: "15% 50%", zoom: 1.45 },
    { ang: "Zoom right", pos: "85% 50%", zoom: 1.45 },
  ];

  function renderPpAngles(p) {
    const src = p.img_url || p.img_url2 || "";
    $("#ppAngles").innerHTML = PP_VIEWS.map((v, i) =>
      `<button class="at-img ${i === ppAngle ? "on" : ""}" data-a="${i}" aria-label="${v.ang}" title="${v.ang}">
         <img src="${src}" alt="${v.ang}" loading="lazy" style="object-fit:cover;object-position:${v.pos}">
       </button>`
    ).join("");
  }

  function setPpAngle(i) {
    ppAngle = i;
    const v = PP_VIEWS[i];
    const img = $("#ppImg");
    img.style.transition = "transform .45s ease, object-position .45s ease";
    img.style.objectPosition = v.pos;
    img.style.transform = `scale(${v.zoom})`;
    if (img.complete && img.naturalWidth) {
      img.style.display = "block";
      $("#ppFallback").style.display = "none";
    }
    $$("#ppAngles .at-img").forEach((b, idx) => b.classList.toggle("on", idx === i));
  }

  function renderPp(p) {
    ppId = p.id; ppQty = 1; ppAngle = 0; ppProduct = p;
    $("#ppCat").textContent = p.category;
    $("#ppName").textContent = p.name;
    $("#ppDesc").textContent = p.description;
    $("#ppPrice").innerHTML = (p.old_price ? `<span class="price-old">${money(p.old_price)}</span>` : "") + `<span class="price">${money(p.price)}</span>`;
    $("#ppRating").innerHTML = `<span class="star">${stars(p.rating)}</span> <strong>${p.rating.toFixed(1)}</strong> · ${p.reviews.toLocaleString()} reviews`;
    const st = $("#ppStock");
    st.textContent = p.stock > 0 ? `In stock — ${p.stock} available` : "Out of stock";
    st.className = "pp-stock " + (p.stock > 0 ? "ok" : "low");
    const badge = $("#ppBadge");
    badge.textContent = p.badge || "";
    badge.hidden = !p.badge;
    const media = $("#ppMedia");
    media.style.background = `linear-gradient(140deg, ${p.gradient[0]}, ${p.gradient[1]})`;
    const img = $("#ppImg"), fb = $("#ppFallback");
    fb.textContent = p.emoji; fb.style.display = "grid"; img.style.display = "none";
    img.setAttribute("data-alt", p.img_url2 || "");
    img.src = p.img_url || p.img_url2 || "";
    img.onload = () => { img.style.display = "block"; fb.style.display = "none"; };
    img.onerror = () => window.useImg(img);
    renderPpAngles(p);
    setPpAngle(0);
    $("#ppQty").textContent = "1";
    $("#productPage").hidden = false;
    document.body.classList.add("lock-scroll");
  }

  function openProductPage(id) {
    const p = findProduct(id);
    if (p) { renderPp(p); return; }
    fetch("/api/products/" + encodeURIComponent(id))
      .then((res) => res.json())
      .then((d) => { if (d.product) renderPp(d.product); })
      .catch(() => {});
  }

  function closeProductPage() {
    $("#productPage").hidden = true;
    document.body.classList.remove("lock-scroll");
  }

  function handleRoute() {
    const m = location.hash.match(/^#\/product\/([A-Za-z0-9_-]+)/);
    if (m) openProductPage(m[1]); else closeProductPage();
  }

  /* ---------------- Events ---------------- */
  function bindEvents() {
    // theme
    $("#themeToggle").addEventListener("click", toggleTheme);

    // account / auth
    $("#accountBtn").addEventListener("click", () => { if (currentUser()) openProfile(); else openAuth("login"); });
    $("#tabLogin").addEventListener("click", () => openAuth("login"));
    $("#tabRegister").addEventListener("click", () => openAuth("register"));
    $("#authForm").addEventListener("submit", handleAuthSubmit);
    $("#closeAuth").addEventListener("click", closeAuth);
    $("#authBackdrop").addEventListener("click", (e) => { if (e.target === e.currentTarget) closeAuth(); });

    // chat
    $("#chatFab").addEventListener("click", () => {
      const p = $("#chatPanel");
      if (p.hidden) openChat(); else closeChat();
    });
    $("#chatClose").addEventListener("click", closeChat);
    $("#chatForm").addEventListener("submit", (e) => {
      e.preventDefault();
      sendChat($("#chatText").value);
      $("#chatText").value = "";
    });
    $("#chatQuick").addEventListener("click", (e) => {
      const b = e.target.closest("[data-q]");
      if (b) sendChat(b.dataset.q);
    });

    // product angles
    $("#closeAngles").addEventListener("click", closeAngles);
    $("#anglesBackdrop").addEventListener("click", (e) => { if (e.target === e.currentTarget) closeAngles(); });
    $("#anglesThumbs").addEventListener("click", (e) => {
      const b = e.target.closest("[data-angle]");
      if (b) selectAngle(+b.dataset.angle);
    });
    $("#anglesAdd").addEventListener("click", () => {
      if (angleProduct) { addToCart(angleProduct.id); closeAngles(); }
    });

    // profile
    $("#profileOrdersBtn").addEventListener("click", renderProfileOrders);
    $("#trackBtn").addEventListener("click", openTrack);
    $("#logoutBtn").addEventListener("click", () => {
      setSession(null); setAuthUI(); closeProfile(); toast("You've been logged out.");
    });
    $("#closeProfile").addEventListener("click", closeProfile);
    $("#profileBackdrop").addEventListener("click", (e) => { if (e.target === e.currentTarget) closeProfile(); });
    $("#orderList").addEventListener("click", (e) => {
      const row = e.target.closest("[data-track]");
      if (row) {
        openTrack();
        $("#trackId").value = row.dataset.track;
        doTrack(new Event("submit"));
      }
    });

    // order tracking
    $("#trackForm").addEventListener("submit", doTrack);
    $("#closeTrack").addEventListener("click", closeTrack);
    $("#trackBackdrop").addEventListener("click", (e) => { if (e.target === e.currentTarget) closeTrack(); });

    // nav mobile activate on scroll (simple)
    const navLinks = $$(".nav-link");
    const spySections = ["shop", "categories", "featured", "about"];
    const spy = new IntersectionObserver((entries) => {
      entries.forEach(en => {
        if (!en.isIntersecting) return;
        const id = en.target.id;
        navLinks.forEach(l => l.classList.toggle("is-active", l.getAttribute("href") === `#${id}`));
      });
    }, { threshold: 0.4 });

    // categories
    $("#categoryChips").addEventListener("click", (e) => {
      const chip = e.target.closest("[data-cat]");
      if (!chip) return;
      state.activeCategory = chip.dataset.cat;
      fetchProducts();
    });

    // search (debounced)
    let debounce;
    $("#searchInput").addEventListener("input", (e) => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        state.query = e.target.value.trim();
        fetchProducts();
      }, 300);
    });

    // sort
    $("#sortSelect").addEventListener("change", (e) => {
      state.sort = e.target.value;
      fetchProducts();
    });

    // clear filters
    $("#clearFilters").addEventListener("click", () => {
      state.query = "";
      state.activeCategory = "All";
      $("#searchInput").value = "";
      $("#sortSelect").value = "featured";
      state.sort = "featured";
      fetchProducts();
    });

    // product grid interactions — click card -> dedicated product page
    $("#productGrid").addEventListener("click", (e) => {
      const addBtn = e.target.closest("[data-add]");
      if (addBtn) { addToCart(addBtn.dataset.add); return; }
      const card = e.target.closest("[data-open]");
      if (card) { location.hash = "#/product/" + card.dataset.open; }
    });

    // trending rail
    const railTrack = $("#railTrack");
    if (railTrack) {
      railTrack.addEventListener("click", (e) => {
        const addBtn = e.target.closest("[data-add]");
        if (addBtn) { addToCart(addBtn.dataset.add); return; }
        const card = e.target.closest("[data-open]");
        if (card) { openProductPage(card.dataset.open); }
      });
      $("#railPrev").addEventListener("click", () => railTrack.scrollBy({ left: -320, behavior: "smooth" }));
      $("#railNext").addEventListener("click", () => railTrack.scrollBy({ left: 320, behavior: "smooth" }));
    }

    // cart
    $("#cartBtn").addEventListener("click", openCart);
    $("#closeCart").addEventListener("click", closeCart);
    $("#overlay").addEventListener("click", closeCart);
    $("#continueShopping").addEventListener("click", closeCart);
    $("#checkoutBtn").addEventListener("click", openCheckout);

    $("#cartItems").addEventListener("click", (e) => {
      const inc = e.target.closest('[data-qty="inc"]');
      const dec = e.target.closest('[data-qty="dec"]');
      const rem = e.target.closest("[data-remove]");
      if (inc) changeQty(inc.dataset.id, 1);
      else if (dec) changeQty(dec.dataset.id, -1);
      else if (rem) removeFromCart(rem.dataset.remove);
    });

    // checkout modal
    $("#closeCheckout").addEventListener("click", closeCheckout);
    $("#checkoutBackdrop").addEventListener("click", (e) => { if (e.target === e.currentTarget) closeCheckout(); });
    $("#checkoutForm").addEventListener("submit", placeOrder);
    $("#placeOrderBtn").addEventListener("click", placeOrder);
    $("#checkoutForm").addEventListener("input", (e) => {
      const el = e.target.closest("[required]");
      if (el && (el.value || "").trim()) el.classList.remove("invalid");
    });

    // success modal
    $("#successDone").addEventListener("click", closeSuccess);
    $("#successBackdrop").addEventListener("click", (e) => { if (e.target === e.currentTarget) closeSuccess(); });

    // escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!$("#successBackdrop").hidden) closeSuccess();
        else if (!$("#checkoutBackdrop").hidden) closeCheckout();
        else if (!$("#cartDrawer").hidden) closeCart();
        else if (!$("#anglesBackdrop").hidden) closeAngles();
        else if (!$("#authBackdrop").hidden) closeAuth();
        else if (!$("#profileBackdrop").hidden) closeProfile();
        else if (!$("#trackBackdrop").hidden) closeTrack();
        else if (!$("#chatPanel").hidden) closeChat();
      }
    });

    // newsletter fake submit
    $("#newsletterForm").addEventListener("submit", (e) => {
      e.preventDefault();
      e.target.reset();
      toast("You're subscribed! Check your inbox for 10% off.");
    });

    // dedicated product page controls
    $("#ppBack").addEventListener("click", () => {
      if (window.history.length > 1) { history.back(); } else { location.hash = ""; }
    });
    $("#ppCart").addEventListener("click", openCart);
    $("#ppMinus").addEventListener("click", () => {
      if (ppId && ppQty > 1) { ppQty--; $("#ppQty").textContent = ppQty; }
    });
    $("#ppPlus").addEventListener("click", () => {
      const p = findProduct(ppId);
      if (p && ppQty < Math.max(1, p.stock)) { ppQty++; $("#ppQty").textContent = ppQty; }
    });
    $("#ppAdd").addEventListener("click", () => { if (ppId) addToCart(ppId, ppQty); });
    $("#ppAngles").addEventListener("click", (e) => {
      const b = e.target.closest("[data-a]");
      if (b) setPpAngle(+b.dataset.a);
    });
    window.addEventListener("hashchange", handleRoute);

    // sticky header shadow
    window.addEventListener("scroll", () => {
      $("#siteHeader").style.boxShadow = window.scrollY > 10 ? "var(--shadow-sm)" : "none";
    }, { passive: true });
  }
  /* ---------------- Boot ---------------- */
  function boot() {
    $("#year").textContent = new Date().getFullYear();
    initTheme();
    bindEvents();
    initHeroSlider();
    setAuthUI();
    handleRoute();
    renderCartBadge();
    renderCart();
    fetchProducts();
    pollProducts();                 // live refresh: new products appear automatically
    setInterval(pollProducts, 15000);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
