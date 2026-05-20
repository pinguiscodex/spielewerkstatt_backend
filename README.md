# Spielewerkstatt Backend

Django REST Framework backend for the Spielewerkstatt platform. Maps the existing Spielewerkstatt database with Django ORM and exposes JWT-protected APIs for games, uploads, voting, wishlists, newsletter, data folders, admin tools, and Minecraft events.

## Tech Stack

- **Framework**: Django 5.2+
- **API**: Django REST Framework 3.16+
- **Auth**: djangorestframework-simplejwt (JWT)
- **Database**: MySQL / MariaDB (via PyMySQL)
- **Password Hashing**: Argon2
- **Image Processing**: Pillow

## Architecture

```
spielewerkstatt_backend/
├── spielewerkstatt/        # Django project settings
│   ├── settings.py         # Configuration (env-driven)
│   ├── urls.py             # Root URL routing
│   └── wsgi.py / asgi.py   # Server entry points
├── api/                    # Main Django app
│   ├── models.py           # Django ORM models (legacy tables)
│   ├── serializers.py      # DRF serializers
│   ├── views.py            # API viewsets & views
│   ├── urls.py             # API URL routing
│   └── uploading.py        # File upload handling
├── deploy/                 # Gunicorn and systemd examples
├── manage.py               # Django management script
├── passenger_wsgi.py       # Passenger/WSGI hosting entry point
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build
├── .env.example            # Environment template
└── sql_legacy_compatibility.sql  # Existing DB compatibility SQL
```

## Getting Started

### Prerequisites

- Python 3.12+
- MySQL / MariaDB running

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database credentials
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DJANGO_DEBUG` | Debug mode (true/false) |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated CSRF trusted origins |
| `DJANGO_CORS_ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `DJANGO_SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS behind a proxy |
| `DJANGO_COOKIE_SECURE` | Mark cookies as HTTPS-only |
| `DB_ENGINE` | Database engine |
| `DB_NAME` | Database name |
| `DB_USER` | Database user |
| `DB_PASSWORD` | Database password |
| `DB_HOST` | Database host |
| `DB_PORT` | Database port |
| `MEDIA_ROOT` | Media files directory |
| `LEGACY_UPLOAD_ROOT` | Path to legacy upload root |

### Existing Database Migration

For an existing database, run `sql_legacy_compatibility.sql` first, then run Django migrations with care. On a database that already contains all application tables:

```bash
python manage.py migrate --fake-initial
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login/` | Login, returns JWT tokens |
| POST | `/api/auth/refresh/` | Refresh access token |
| POST | `/api/auth/logout/` | Invalidate tokens |

### Games

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/backend/games/` | List all games |
| GET | `/api/backend/games/{id}/` | Get game details |
| POST | `/api/backend/games/` | Create game (auth required) |
| PUT | `/api/backend/games/{id}/` | Update game (auth required) |
| DELETE | `/api/backend/games/{id}/` | Delete game (auth required) |

### Voting

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backend/votes/` | Vote for a game |
| GET | `/api/backend/votes/` | Get voting results |

### Uploads

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backend/upload/` | Upload game files |
| GET | `/api/backend/upload/{id}/` | Download game file |

### Wishlist

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backend/wishlist/` | Add game to wishlist |
| DELETE | `/api/backend/wishlist/{id}/` | Remove from wishlist |
| GET | `/api/backend/wishlist/` | Get user's wishlist |

### Newsletter

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backend/newsletter/` | Subscribe to newsletter |
| POST | `/api/backend/newsletter/unsubscribe/` | Unsubscribe |

### Data Folders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/backend/data-folders/` | List user's data folders |
| POST | `/api/backend/data-folders/` | Create data folder |
| GET | `/api/backend/data-folders/{id}/` | Get folder contents |

### Minecraft

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/backend/minecraft/events/` | List Minecraft events |
| POST | `/api/backend/minecraft/events/` | Create event (admin) |

## File Uploads

New media is stored under `MEDIA_ROOT/uploads/...`. Existing relative paths such as `uploads/thumbnails/...` are resolved through `LEGACY_UPLOAD_ROOT` when present.

Supported game upload types include executables (`.exe`, `.AppImage`, `.dmg`), archives (`.zip`, `.tar.gz`), and standard project bundles validated by `api/uploading.py`.

## Deployment

Native deployment examples are included in `deploy/`:

- `deploy/gunicorn.conf.py` for Gunicorn
- `deploy/spielewerkstatt-backend.service` for systemd
- `passenger_wsgi.py` for Passenger/WSGI hosts
- `../deploy/nginx/spielewerkstatt.conf` for Nginx reverse proxying

Container deployment is available from the repository root with `docker compose up --build`.

## Development

```bash
# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver 127.0.0.1:8000

# Run tests
python manage.py test
```

## Related

- [Frontend](../spielewerkstatt_frontend/) — Next.js 14 frontend
- [Deployment Guide](../deploy/README.md)
