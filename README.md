# 🛠️ ServiceConnect – Hyperlocal Skill & Service Marketplace

Django + DRF + Channels (WebSockets) full-stack app. Customers find **verified local providers**
(electrician, tutor, tailor, mechanic…), book a **conflict-free slot**, **pay securely**, **chat in real time**
and leave **reviews**. Providers manage services & availability; admins verify/moderate via Django admin.

## ▶ Run in 4 commands (no Docker, no PostgreSQL needed)

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo && python manage.py runserver
```
Open **http://127.0.0.1:8000**

| Role | Login |
|---|---|
| Customer | `customer` / `demo123` |
| Provider | `ramesh_elec` / `demo123` (also `sunita_tutor`, `meena_tailor`, `anil_ac` …) |
| Admin | `admin` / `admin123` → http://127.0.0.1:8000/admin/ |

API docs (Swagger): http://127.0.0.1:8000/api/docs/

## 🧪 Try the full flow (2 browser windows – one normal, one incognito)
1. Window A – login as **customer** → click **📍 Near me** → open a provider → pick date + slot → *Request booking*
2. Window B – login as **ramesh_elec** (provider) → *My bookings* → **Accept**
3. Window A – **Pay** (mock mode) → status becomes *paid*
4. Both windows – **💬 Chat** (live messages, typing, online, seen)
5. Window B – **Start job** → **Mark completed** (payment released to provider minus 10% commission)
6. Window A – **★ Leave review** → provider rating updates

Try booking the same slot from a second customer → **409 Conflict** (no double booking).

## ✅ Tests
```bash
python manage.py test apps      # 15 tests: auth, geo search, double-booking, payments, webhooks, reviews, WebSocket chat
```

## 💳 Real Razorpay (optional)
Without keys the app runs in **mock payment mode**. For real test payments copy `.env.example` → `.env` and set
`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (and `RAZORPAY_WEBHOOK_SECRET`; webhook URL: `/api/payments/webhook/`,
events `payment.captured`, `payment.failed`).

## 🐳 Docker (PostgreSQL + Redis)
```bash
docker compose up --build        # http://localhost:8000
```

## 🏗️ Architecture / interview talking points
| Topic | Where | How |
|---|---|---|
| Role-based auth | `apps/users` | JWT (SimpleJWT) access+refresh, `IsProvider` / `IsCustomer` permissions |
| Geo "near me" search | `apps/providers/views.py`, `geo.py` | Bounding-box DB pre-filter + Haversine; smart ranking (distance, rating, completion rate, verified) |
| Double-booking prevention | `apps/bookings/services.py` | `transaction.atomic` + `select_for_update` on provider row, re-checks free slots inside the lock |
| Slot generation | `apps/bookings/slots.py` | availability windows → slots, minus bookings, time-off and past times |
| Payments | `apps/payments` | Razorpay order → **server-side HMAC signature verify**, **idempotent webhooks** (`WebhookEvent`), escrow (`paid` → `released`), refund on cancel |
| Real-time chat | `apps/chat` | Django Channels consumer, JWT in query string, participant-only access, typing / presence / read receipts, Redis layer when `REDIS_URL` set |
| Reviews & abuse prevention | `apps/reviews` | only completed bookings, 1 per booking, profanity filter, rate-limit, report → admin moderation, recency-weighted rating |
| Admin | Django admin | verify/suspend providers, hide reviews, view payments |
| Background cleanup | `manage.py expire_bookings` | cancels unpaid (15 min) / unanswered (24 h) bookings; run via cron or Celery beat |

## 📁 Structure
```
config/        settings, urls, asgi (HTTP + WebSocket)
apps/users     custom User (role), register/login/me
apps/providers categories, profiles, services, availability, search
apps/bookings  booking model, slot logic, status machine
apps/payments  Razorpay (+mock), verify, webhook
apps/chat      Message model + WebSocket consumer
apps/reviews   ratings, moderation
templates/ static/   single-page frontend (vanilla JS, no build step)
```

## 🚀 Extend it (resume boosters)
- Swap lat/lng for **PostGIS** (GeoDjango `PointField`, `D(km=)` queries, GiST index)
- Celery + Redis for reminders/emails/SMS instead of the cron command
- Replace vanilla JS with **React/Next.js** (the REST API is ready)
- Image uploads (Cloudinary/S3) for portfolio + ID documents
- Multi-language UI (English / Hindi / Marathi), PWA, recurring bookings
- Deploy on Render/Railway; add live link + demo video to your resume
