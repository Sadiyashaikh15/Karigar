/* ServiceConnect – vanilla JS single page app (no build step needed) */
const S = { access: localStorage.getItem("access"), refresh: localStorage.getItem("refresh"),
            user: JSON.parse(localStorage.getItem("user") || "null"), cats: [], pos: null, ws: null };
const $ = (s, el = document) => el.querySelector(s);
const app = () => $("#app");
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = (n) => "₹" + Number(n).toLocaleString("en-IN");
const fmt = (iso) => new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
const stars = (r) => `<span class="stars">${"★".repeat(Math.round(r))}${"☆".repeat(5 - Math.round(r))}</span> ${Number(r).toFixed(1)}`;

function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2600); }
function openModal(html) { $("#modalBox").innerHTML = html; $("#modal").classList.remove("hidden"); }
function closeModal() { $("#modal").classList.add("hidden"); if (S.ws) { S.ws.close(); S.ws = null; } }
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });

async function api(path, { method = "GET", body, auth = true } = {}, retry = true) {
  const headers = { "Content-Type": "application/json" };
  if (auth && S.access) headers.Authorization = "Bearer " + S.access;
  const res = await fetch("/api" + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (res.status === 401 && auth && S.refresh && retry) {
    const r = await fetch("/api/auth/refresh/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh: S.refresh }) });
    if (r.ok) { S.access = (await r.json()).access; localStorage.setItem("access", S.access); return api(path, { method, body, auth }, false); }
    logout(); throw new Error("Session expired. Please log in again.");
  }
  let data = null; try { data = await res.json(); } catch (e) {}
  if (!res.ok) {
    let msg = data && (data.detail || Object.entries(data).map(([k, v]) => `${k}: ${[].concat(v).join(" ")}`).join(" | ")) || "Request failed";
    const err = new Error(msg); err.status = res.status; throw err;
  }
  return data;
}
const safe = (fn) => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message); } };

function logout() { S.access = S.refresh = S.user = null; localStorage.clear(); renderNav(); go("home"); }

function renderNav() {
  const u = S.user, n = $("#nav");
  if (!u) { n.innerHTML = `<button class="ghost" onclick="go('home')">Find services</button><button onclick="go('auth')">Login / Sign up</button>`; return; }
  n.innerHTML = `<button class="ghost" onclick="go('home')">Find services</button>
    <button class="ghost" onclick="go('bookings')">My bookings</button>
    ${u.role === "provider" ? `<button class="ghost" onclick="go('dashboard')">My dashboard</button>` : ""}
    ${u.role === "admin" ? `<a class="btn" href="/admin/" target="_blank">Admin panel</a>` : ""}
    <span class="muted">${esc(u.username)} (${u.role})</span><button class="ghost" onclick="logout()">Logout</button>`;
}

function go(view, arg) {
  ({ home: viewHome, auth: viewAuth, bookings: viewBookings, dashboard: viewDashboard }[view] || viewHome)(arg);
  window.scrollTo(0, 0);
}

/* ---------------- AUTH ---------------- */
function viewAuth() {
  app().innerHTML = `<div class="grid g2">
   <div class="card"><h2>Login</h2>
     <label>Username</label><input id="lu"><label>Password</label><input id="lp" type="password">
     <p><button onclick="doLogin()">Login</button></p>
     <p class="muted">Demo: <b>customer</b>/demo123 · <b>ramesh_elec</b>/demo123 (provider)</p></div>
   <div class="card"><h2>Sign up</h2>
     <label>I am a</label><select id="rr"><option value="customer">Customer (I need a service)</option><option value="provider">Provider (I offer a service)</option></select>
     <label>Username</label><input id="ru"><label>Full name</label><input id="rn"><label>Email</label><input id="re" type="email">
     <label>Phone</label><input id="rph"><label>Password (min 6)</label><input id="rp" type="password">
     <p><button onclick="doRegister()">Create account</button></p></div></div>`;
}
const doLogin = safe(async () => {
  const d = await api("/auth/login/", { method: "POST", auth: false, body: { username: $("#lu").value.trim(), password: $("#lp").value } });
  saveSession(d); toast("Welcome back!"); go(d.user.role === "provider" ? "dashboard" : "home");
});
const doRegister = safe(async () => {
  const [first, ...rest] = $("#rn").value.trim().split(" ");
  const body = { username: $("#ru").value.trim(), email: $("#re").value.trim(), password: $("#rp").value,
                 first_name: first || "", last_name: rest.join(" "), phone: $("#rph").value.trim(), role: $("#rr").value };
  await api("/auth/register/", { method: "POST", auth: false, body });
  const d = await api("/auth/login/", { method: "POST", auth: false, body: { username: body.username, password: body.password } });
  saveSession(d); toast("Account created!"); go(d.user.role === "provider" ? "dashboard" : "home");
});
function saveSession(d) {
  S.access = d.access; S.refresh = d.refresh; S.user = d.user;
  localStorage.setItem("access", d.access); localStorage.setItem("refresh", d.refresh); localStorage.setItem("user", JSON.stringify(d.user));
  renderNav();
}

/* ---------------- HOME / SEARCH ---------------- */
let filters = { category: "", q: "", radius: 15, sort: "", verified: "" };
const viewHome = safe(async () => {
  if (!S.cats.length) S.cats = await api("/categories/", { auth: false });
  app().innerHTML = `<div class="hero"><h1>Trusted local help, at your doorstep</h1>
    <p class="muted">Electricians, tutors, tailors, mechanics – verified, reviewed, bookable in minutes.</p></div>
    <div class="card"><div class="row"><input id="q" style="flex:1;min-width:180px" placeholder="Search e.g. AC repair, maths tutor..." value="${esc(filters.q)}">
      <button onclick="doSearch()">Search</button><button class="ghost" onclick="useLocation()">📍 Near me${S.pos ? " ✓" : ""}</button></div>
      <div class="row" style="margin-top:8px"><select id="sort" style="width:auto"><option value="">Best match</option><option value="rating">Top rated</option><option value="price">Lowest price</option><option value="distance">Nearest</option></select>
      <select id="radius" style="width:auto">${[5, 10, 15, 30].map((r) => `<option value="${r}" ${filters.radius == r ? "selected" : ""}>${r} km</option>`).join("")}</select>
      <label style="margin:0"><input type="checkbox" id="ver" style="width:auto" ${filters.verified ? "checked" : ""}> Verified only</label></div></div>
    <div class="chips"><button class="chip ${filters.category ? "" : "on"}" onclick="setCat('')">All</button>
      ${S.cats.map((c) => `<button class="chip ${filters.category === c.slug ? "on" : ""}" onclick="setCat('${c.slug}')">${c.icon} ${esc(c.name)}</button>`).join("")}</div>
    <div id="results" class="grid g3"></div>`;
  $("#sort").value = filters.sort;
  await doSearch();
});
function setCat(slug) { filters.category = slug; viewHome(); }
function useLocation() {
  if (!navigator.geolocation) return toast("Geolocation not supported");
  navigator.geolocation.getCurrentPosition((p) => { S.pos = { lat: p.coords.latitude, lng: p.coords.longitude }; toast("Location set"); viewHome(); },
    () => { S.pos = { lat: 18.5204, lng: 73.8567 }; toast("Using demo location: Pune centre"); viewHome(); });
}
const doSearch = safe(async () => {
  filters.q = $("#q").value; filters.sort = $("#sort").value; filters.radius = $("#radius").value; filters.verified = $("#ver").checked ? "1" : "";
  const p = new URLSearchParams();
  if (filters.category) p.set("category", filters.category);
  if (filters.q) p.set("q", filters.q);
  if (filters.sort) p.set("sort", filters.sort);
  if (filters.verified) p.set("verified", "1");
  if (S.pos) { p.set("lat", S.pos.lat); p.set("lng", S.pos.lng); p.set("radius", filters.radius); }
  const d = await api("/providers/?" + p, { auth: false });
  $("#results").innerHTML = d.results.length ? d.results.map((r) => `
    <div class="card"><div class="row spread"><h3>${esc(r.name)}</h3>${r.is_verified ? '<span class="badge ver">✔ Verified</span>' : ""}</div>
      <div>${r.rating_count ? stars(r.avg_rating) + ` <span class="muted">(${r.rating_count})</span>` : '<span class="muted">New</span>'}</div>
      <div class="muted">📍 ${esc(r.city || "—")} ${r.distance_km != null ? "· " + r.distance_km + " km away" : ""} · ${r.experience_years} yrs exp</div>
      <p class="muted">${esc((r.bio || "").slice(0, 90))}</p>
      ${r.services.slice(0, 2).map((s) => `<div class="row spread"><span>${esc(s.title)}</span><span class="price">${inr(s.price)}</span></div>`).join("")}
      <p><button onclick="openProvider(${r.id})">View & book</button></p></div>`).join("")
    : `<div class="card muted">No providers found. Try a bigger radius or another category.</div>`;
});

/* ---------------- PROVIDER DETAIL + BOOKING ---------------- */
let pick = { svc: null, slot: null, prov: null };
const openProvider = safe(async (id) => {
  const p = await api(`/providers/${id}/`, { auth: false });
  pick = { svc: p.services[0]?.id, slot: null, prov: p };
  const today = new Date(); today.setDate(today.getDate() + 1);
  const iso = today.toISOString().slice(0, 10);
  openModal(`<div class="row spread"><h2>${esc(p.name)} ${p.is_verified ? '<span class="badge ver">✔</span>' : ""}</h2><button class="ghost" onclick="closeModal()">✕</button></div>
    <div>${p.rating_count ? stars(p.avg_rating) + ` (${p.rating_count} reviews)` : "No reviews yet"} · ${p.completed_jobs} jobs done</div>
    <p class="muted">${esc(p.bio)}</p>
    <label>Service</label><select id="svc" onchange="pick.svc=this.value;loadSlots()">${p.services.map((s) => `<option value="${s.id}">${esc(s.title)} – ${inr(s.price)} (${s.duration_minutes} min)</option>`).join("")}</select>
    <label>Date</label><input type="date" id="bdate" value="${iso}" min="${iso}" onchange="loadSlots()">
    <div id="slots" class="slots"></div>
    <label>Your address</label><input id="addr" placeholder="Flat no, building, area">
    <label>Notes (optional)</label><textarea id="notes" rows="2"></textarea>
    <p><button id="bookBtn" onclick="doBook()">Request booking</button> ${S.user ? "" : '<span class="muted">Login required</span>'}</p>
    <h3>Reviews</h3>${p.reviews.length ? p.reviews.map((r) => `<div class="muted"><span class="stars">${"★".repeat(r.rating)}</span> ${esc(r.comment)} — ${esc(r.customer)}</div>`).join("") : '<div class="muted">No reviews yet</div>'}`);
  loadSlots();
});
const loadSlots = safe(async () => {
  pick.svc = $("#svc").value; pick.slot = null;
  const d = await api(`/providers/${pick.prov.id}/slots/?service=${pick.svc}&date=${$("#bdate").value}`, { auth: false });
  $("#slots").innerHTML = d.slots.length ? d.slots.map((s) => `<button class="slot" onclick="selSlot(this,'${s}')">${new Date(s).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</button>`).join("") : '<span class="muted">No free slots on this day</span>';
});
function selSlot(el, iso) { document.querySelectorAll(".slot").forEach((b) => b.classList.remove("sel")); el.classList.add("sel"); pick.slot = iso; }
const doBook = safe(async () => {
  if (!S.user) { closeModal(); return go("auth"); }
  if (!pick.slot) return toast("Pick a time slot");
  if (!$("#addr").value.trim()) return toast("Enter your address");
  try {
    await api("/bookings/", { method: "POST", body: { service: +pick.svc, start: pick.slot, address: $("#addr").value, notes: $("#notes").value } });
  } catch (e) { if (e.status === 409) { toast(e.message); return loadSlots(); } throw e; }
  closeModal(); toast("Request sent! Pay after provider accepts."); go("bookings");
});

/* ---------------- BOOKINGS ---------------- */
const viewBookings = safe(async () => {
  if (!S.user) return go("auth");
  const list = await api("/bookings/");
  const isP = S.user.role === "provider";
  app().innerHTML = `<h2>My bookings</h2>` + (list.length ? list.map((b) => `
    <div class="card"><div class="row spread"><h3>${esc(b.service_title)}</h3><span class="badge ${b.status}">${b.status.replace("_", " ")}</span></div>
     <div class="muted">${isP ? "Customer: " + esc(b.customer_name) : "Provider: " + esc(b.provider_name)} · ${fmt(b.start)}</div>
     <div class="muted">📍 ${esc(b.address)}</div>
     <div class="row spread"><span class="price">${inr(b.amount)}</span><span class="muted">${b.payment_status ? "payment: " + b.payment_status : ""}</span></div>
     <div class="row" style="margin-top:8px">${actions(b, isP)}<button class="ghost" onclick="openChat(${b.id})">💬 Chat</button></div></div>`).join("")
    : `<div class="card muted">No bookings yet.</div>`);
});
function actions(b, isP) {
  const out = [];
  if (isP) {
    if (b.status === "requested") out.push(`<button class="ok" onclick="act('accept',${b.id})">Accept</button>`, `<button class="bad" onclick="act('reject',${b.id})">Reject</button>`);
    if (b.status === "paid") out.push(`<button onclick="act('start',${b.id})">Start job</button>`);
    if (b.status === "in_progress") out.push(`<button class="ok" onclick="act('complete',${b.id})">Mark completed</button>`);
  } else {
    if (b.status === "accepted") out.push(`<button class="ok" onclick="pay(${b.id})">Pay ${inr(b.amount)}</button>`);
    if (b.status === "completed" && !b.has_review) out.push(`<button class="warn" onclick="reviewForm(${b.id})">★ Leave review</button>`);
  }
  if (["requested", "accepted", "paid"].includes(b.status)) out.push(`<button class="ghost" onclick="act('cancel',${b.id})">Cancel</button>`);
  return out.join("");
}
const act = safe(async (action, id) => {
  if (action === "cancel" && !confirm("Cancel this booking? Paid amounts are refunded.")) return;
  await api(`/bookings/${id}/${action}/`, { method: "POST" }); toast("Done: " + action); viewBookings();
});

/* ---------------- PAYMENT (Razorpay or MOCK) ---------------- */
const pay = safe(async (id) => {
  const o = await api("/payments/create-order/", { method: "POST", body: { booking_id: id } });
  const verify = async (r) => { await api("/payments/verify/", { method: "POST", body: r }); toast("Payment successful ✔"); viewBookings(); };
  if (o.mock) {
    if (!confirm(`MOCK PAYMENT MODE (no Razorpay keys set).\nPay ₹${o.amount / 100} now?`)) return;
    return verify({ razorpay_order_id: o.order_id, razorpay_payment_id: "pay_mock_" + Date.now(), razorpay_signature: "mock_signature" });
  }
  await loadScript("https://checkout.razorpay.com/v1/checkout.js");
  new Razorpay({ key: o.key, amount: o.amount, currency: o.currency, order_id: o.order_id, name: "ServiceConnect",
    prefill: { email: S.user.email }, theme: { color: "#4f46e5" }, handler: (r) => safe(verify)(r) }).open();
});
const loadScript = (src) => new Promise((res, rej) => { const s = document.createElement("script"); s.src = src; s.onload = res; s.onerror = rej; document.head.appendChild(s); });

/* ---------------- REVIEWS ---------------- */
function reviewForm(id) {
  openModal(`<h2>Rate your experience</h2><label>Rating</label>
    <select id="rv">${[5, 4, 3, 2, 1].map((n) => `<option value="${n}">${"★".repeat(n)}</option>`).join("")}</select>
    <label>Comment</label><textarea id="rc" rows="3"></textarea>
    <p><button onclick="sendReview(${id})">Submit</button> <button class="ghost" onclick="closeModal()">Cancel</button></p>`);
}
const sendReview = safe(async (id) => {
  await api("/reviews/", { method: "POST", body: { booking: id, rating: +$("#rv").value, comment: $("#rc").value } });
  closeModal(); toast("Thanks for your review!"); viewBookings();
});

/* ---------------- CHAT (WebSocket) ---------------- */
const openChat = safe(async (id) => {
  const hist = await api(`/chat/${id}/messages/`);
  openModal(`<div class="row spread"><h2>Chat · booking #${id}</h2><button class="ghost" onclick="closeModal()">✕</button></div>
    <div class="muted" id="cstat">connecting…</div><div class="chatbox" id="cbox"></div>
    <div class="row" style="margin-top:8px"><input id="cin" placeholder="Type a message…" style="flex:1"><button onclick="sendChat()">Send</button></div>`);
  hist.forEach(addMsg);
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/chat/${id}/?token=${S.access}`);
  S.ws = ws; let typingT;
  ws.onopen = () => { $("#cstat").textContent = "connected"; ws.send(JSON.stringify({ read: true })); };
  ws.onclose = () => { const e = $("#cstat"); if (e) e.textContent = "disconnected"; };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === "message") { addMsg(m); if (m.sender !== S.user.id) ws.send(JSON.stringify({ read: true })); }
    else if (m.type === "typing") $("#cstat").textContent = m.typing ? "typing…" : "connected";
    else if (m.type === "presence") $("#cstat").textContent = m.online ? "other person is online" : "other person left";
    else if (m.type === "read") $("#cstat").textContent = "seen ✓✓";
  };
  $("#cin").addEventListener("input", () => { ws.send(JSON.stringify({ typing: true })); clearTimeout(typingT); typingT = setTimeout(() => ws.readyState === 1 && ws.send(JSON.stringify({ typing: false })), 1200); });
  $("#cin").addEventListener("keydown", (e) => e.key === "Enter" && sendChat());
});
function addMsg(m) {
  const box = $("#cbox"); if (!box) return;
  const d = document.createElement("div"); d.className = "msg" + (m.sender === S.user.id ? " me" : "");
  d.innerHTML = `${esc(m.content)}<small>${esc(m.sender_name)} · ${new Date(m.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</small>`;
  box.appendChild(d); box.scrollTop = box.scrollHeight;
}
function sendChat() { const i = $("#cin"); if (!i.value.trim() || !S.ws) return; S.ws.send(JSON.stringify({ message: i.value })); i.value = ""; }

/* ---------------- PROVIDER DASHBOARD ---------------- */
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const viewDashboard = safe(async () => {
  if (!S.user || S.user.role !== "provider") return go("home");
  if (!S.cats.length) S.cats = await api("/categories/", { auth: false });
  const [prof, svcs, av, off] = await Promise.all([api("/me/profile/"), api("/me/services/"), api("/me/availability/"), api("/me/timeoff/")]);
  app().innerHTML = `<h2>Provider dashboard ${prof.is_verified ? '<span class="badge ver">✔ Verified</span>' : '<span class="badge">Pending admin verification</span>'}</h2>
   <div class="muted">Rating: ${prof.rating_count ? stars(prof.avg_rating) + ` (${prof.rating_count})` : "no reviews yet"} · Jobs done: ${prof.completed_jobs}</div>
   <div class="grid g2" style="margin-top:12px">
   <div class="card"><h3>Profile & location</h3>
     <label>Bio</label><textarea id="pb" rows="3">${esc(prof.bio)}</textarea>
     <label>City / area</label><input id="pc" value="${esc(prof.city)}">
     <div class="grid g2"><div><label>Latitude</label><input id="pla" value="${prof.latitude ?? ""}"></div><div><label>Longitude</label><input id="plo" value="${prof.longitude ?? ""}"></div></div>
     <div class="grid g2"><div><label>Experience (years)</label><input id="pe" type="number" value="${prof.experience_years}"></div><div><label>Service radius (km)</label><input id="pr" type="number" value="${prof.service_radius_km}"></div></div>
     <p class="row"><button onclick="saveProfile()">Save profile</button><button class="ghost" onclick="fillLoc()">📍 Use my location</button></p></div>
   <div class="card"><h3>My services</h3>
     ${svcs.map((s) => `<div class="row spread"><span>${esc(s.title)} · ${inr(s.price)} · ${s.duration_minutes}m ${s.is_active ? "" : "(off)"}</span><button class="ghost" onclick="delItem('services',${s.id})">✕</button></div>`).join("") || '<div class="muted">No services yet – add one!</div>'}
     <hr><label>Category</label><select id="sc">${S.cats.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select>
     <label>Title</label><input id="st"><div class="grid g2"><div><label>Price (₹)</label><input id="sp" type="number"></div><div><label>Duration (min)</label><input id="sd" type="number" value="60"></div></div>
     <p><button onclick="addService()">Add service</button></p></div>
   <div class="card"><h3>Weekly availability</h3>
     ${av.map((a) => `<div class="row spread"><span>${a.day_name} ${a.start_time.slice(0, 5)}–${a.end_time.slice(0, 5)}</span><button class="ghost" onclick="delItem('availability',${a.id})">✕</button></div>`).join("") || '<div class="muted">Add hours so customers can book you</div>'}
     <hr><div class="grid g3"><div><label>Day</label><select id="ad">${DAYS.map((d, i) => `<option value="${i}">${d}</option>`).join("")}</select></div><div><label>From</label><input id="af" type="time" value="09:00"></div><div><label>To</label><input id="at" type="time" value="18:00"></div></div>
     <p class="row"><button onclick="addAvail()">Add window</button><button class="ghost" onclick="addWeekdays()">Mon–Sat 9–6</button></p></div>
   <div class="card"><h3>Days off</h3>
     ${off.map((o) => `<div class="row spread"><span>${o.date} ${esc(o.reason)}</span><button class="ghost" onclick="delItem('timeoff',${o.id})">✕</button></div>`).join("") || '<div class="muted">None</div>'}
     <hr><label>Date</label><input id="od" type="date"><p><button onclick="addOff()">Block date</button></p></div></div>`;
});
const saveProfile = safe(async () => {
  const n = (v) => (v === "" ? null : Number(v));
  await api("/me/profile/", { method: "PATCH", body: { bio: $("#pb").value, city: $("#pc").value, latitude: n($("#pla").value), longitude: n($("#plo").value), experience_years: +$("#pe").value, service_radius_km: +$("#pr").value } });
  toast("Profile saved");
});
function fillLoc() { navigator.geolocation?.getCurrentPosition((p) => { $("#pla").value = p.coords.latitude.toFixed(5); $("#plo").value = p.coords.longitude.toFixed(5); }, () => toast("Location blocked")); }
const addService = safe(async () => { await api("/me/services/", { method: "POST", body: { category: +$("#sc").value, title: $("#st").value, price: $("#sp").value, duration_minutes: +$("#sd").value } }); viewDashboard(); });
const addAvail = safe(async () => { await api("/me/availability/", { method: "POST", body: { day_of_week: +$("#ad").value, start_time: $("#af").value, end_time: $("#at").value } }); viewDashboard(); });
const addWeekdays = safe(async () => { for (let d = 0; d < 6; d++) { try { await api("/me/availability/", { method: "POST", body: { day_of_week: d, start_time: "09:00", end_time: "18:00" } }); } catch (e) {} } viewDashboard(); });
const addOff = safe(async () => { await api("/me/timeoff/", { method: "POST", body: { date: $("#od").value } }); viewDashboard(); });
const delItem = safe(async (kind, id) => { await api(`/me/${kind}/${id}/`, { method: "DELETE" }); viewDashboard(); });

renderNav(); go("home");
