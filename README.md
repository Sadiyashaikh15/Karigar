# 🛠️ Karigar – Hyperlocal Services Marketplace

> Find trusted local electricians, tutors, tailors, mechanics and more. Book a time slot, pay securely, chat live and leave reviews.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-5.1-green)
![DRF](https://img.shields.io/badge/DRF-REST_API-red)
![WebSockets](https://img.shields.io/badge/Django_Channels-WebSockets-orange)
![Tests](https://img.shields.io/badge/tests-15_passing-brightgreen)

**Live demo:** _add your link here after deploying_ · **Demo video:** _add link here_

## 🎯 The Problem
Finding a reliable plumber, tutor or tailor nearby usually depends on word of mouth. There is no way to check
trust, prices are unclear, availability is a guess, and there is no accountability if the work is bad.
Small local providers also have no online presence or proof of reputation.

## 💡 The Solution
Karigar connects customers with **verified local providers**. Customers search by category and distance,
see real reviews, book an available slot, pay online and chat in-app. Providers manage their own services and
schedule. Admins verify providers and moderate reviews.

## ✨ Features

**Customers**
- Search by category, keyword, rating, price and "near me" distance
- Smart ranking (distance + rating + completion rate + verified badge)
- Real-time slot availability and booking
- Secure online payment (Razorpay) with refund on cancellation
- Live chat with the provider, with typing, online and seen indicators
- Reviews and ratings after a completed job

**Providers**
- Profile, location, services with price and duration
- Weekly availability and days off
- Accept or reject requests, start and complete jobs

**Admin**
- Verify or suspend providers
- Moderate reported reviews
- View all bookings and payments

## 🧠 Engineering Highlights
| Challenge | Solution |
|---|---|
| Two users booking the same slot | Database transaction with row-level lock (`select_for_update`), slot re-checked inside the lock; API returns `409 Conflict` |
| Trusting the payment from the browser | Razorpay signature verified **server-side** (HMAC-SHA256) |
| Duplicate payment webhooks | Idempotent handling using a stored event id |
| Holding money until the job is done | Escrow-style flow: `paid` → `released` on completion, `refunded` on cancel |
| "Near me" search | Bounding-box DB filter + Haversine distance |
| Real-time chat security | JWT-authenticated WebSocket, only booking participants can join |
| Fake or abusive reviews | Only completed bookings, one review per booking, profanity filter, rate limiting, report and moderation queue |
| Unpaid bookings blocking slots | Auto-cancel command (`expire_bookings`) |

## 🧰 Tech Stack
**Backend:** Python, Django, Django REST Framework, SimpleJWT, Django Channels (WebSockets)
**Database:** SQLite (default) / PostgreSQL (Docker)
**Cache and realtime layer:** In-memory / Redis (Docker)
**Payments:** Razorpay (with a built-in mock mode)
**Frontend:** HTML, CSS, vanilla JavaScript
**DevOps:** Docker, Docker Compose, GitHub Actions CI
**Docs:** Swagger / OpenAPI (drf-spectacular)

## 📸 Screenshots
| Search | Booking | Chat |
|---|---|---|
| ![search](screenshots/search.png) | ![booking](screenshots/booking.png) | ![chat](screenshots/chat.png) |

_Create a `screenshots/` folder and add your images._

## 🚀 Getting Started

**Requirements:** Python 3.10+

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open **http://127.0.0.1:8000**

### Demo accounts
| Role | Username | Password |
|---|---|---|
| Customer | `customer` | `demo123` |
| Provider | `ramesh_elec` | `demo123` |
| Admin | `admin` | `admin123` (at `/admin/`) |

API documentation: **http://127.0.0.1:8000/api/docs/**

## 🧪 Try the Full Flow
Use two browser windows (one normal, one incognito).
1. **Customer:** click *Near me*, open a provider, pick a slot, request booking
2. **Provider:** open *My bookings*, click *Accept*
3. **Customer:** click *Pay* (mock mode, no real money)
4. **Both:** open *Chat* and send messages
5. **Provider:** *Start job*, then *Mark completed*
6. **Customer:** leave a review

## ⚙️ Configuration (optional)
Copy `.env.example` to `.env`. The app runs without it.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key (required in production) |
| `DATABASE_URL` | PostgreSQL URL (default is SQLite) |
| `REDIS_URL` | Redis for scaling chat across servers |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | Real Razorpay test payments (empty means mock mode) |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook verification |
| `COMMISSION_PERCENT` | Platform commission (default 10) |

## 🐳 Run with Docker
```bash
docker compose up --build
```
Starts the app with PostgreSQL and Redis at http://localhost:8000

## ✅ Running Tests
```bash
python manage.py test apps
```
Covers authentication, geo search, double-booking prevention, payments, webhook idempotency, reviews and WebSocket chat.

## 📁 Project Structure
```
config/          settings, URLs, ASGI (HTTP + WebSocket)
apps/users/      custom user with roles, JWT auth
apps/providers/  categories, profiles, services, availability, search
apps/bookings/   booking model, slot generation, status flow
apps/payments/   Razorpay integration, verification, webhooks
apps/chat/       messages and WebSocket consumer
apps/reviews/    ratings and moderation
templates/ static/   frontend
```

## 🔌 API Overview
| Endpoint | Description |
|---|---|
| `POST /api/auth/register/`, `/login/` | Sign up and log in |
| `GET /api/providers/?lat=&lng=&radius=&category=` | Search providers |
| `GET /api/providers/{id}/slots/?service=&date=` | Free time slots |
| `POST /api/bookings/` | Create a booking |
| `POST /api/bookings/{id}/accept\|reject\|start\|complete\|cancel/` | Booking lifecycle |
| `POST /api/payments/create-order/`, `/verify/`, `/webhook/` | Payments |
| `WS /ws/chat/{booking_id}/?token=` | Real-time chat |
| `POST /api/reviews/` | Submit a review |

Full interactive docs are available at `/api/docs/`.

## 🔮 Future Improvements
- PostGIS for database-level geospatial queries
- React / Next.js frontend
- Celery for reminders, email and SMS notifications
- Image uploads for provider portfolios and ID verification
- Multi-language support (English, Hindi, Marathi)
- Recurring bookings and an instant "need help now" mode

## 👤 Author
**Your Name**
[LinkedIn] www.linkedin.com/in/sadiyashaikh15 · [GitHub] https://github.com/Sadiyashaikh15 sadiyashaikh9371@gmail.com