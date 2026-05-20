# Spielewerkstatt Backend — Agent Instructions

## Project Overview

Spielewerkstatt backend is a Django REST Framework application that provides JWT-protected APIs for the Spielewerkstatt platform. It maps the existing Spielewerkstatt database with Django ORM.

## Tech Stack

- **Django 5.2+**
- **Django REST Framework 3.16+**
- **djangorestframework-simplejwt** (JWT authentication)
- **django-cors-headers** (CORS handling)
- **PyMySQL** (MySQL database driver)
- **Argon2** (password hashing)
- **Pillow** (image processing)

## Project Structure

```
spielewerkstatt_backend/
├── spielewerkstatt/        # Django project package
│   ├── settings.py         # Settings (env-driven)
│   ├── urls.py             # Root URL configuration
│   ├── wsgi.py             # WSGI entry point
│   └── asgi.py             # ASGI entry point
├── api/                    # Main Django app
│   ├── models.py           # ORM models (legacy tables)
│   ├── serializers.py      # DRF serializers
│   ├── views.py            # ViewSets and API views
│   ├── urls.py             # URL routing
│   ├── uploading.py        # File upload logic
│   └── admin.py            # Django admin configuration
├── manage.py               # Django management script
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
└── sql_legacy_compatibility.sql  # Existing DB compatibility SQL
```

## Coding Conventions

### Python

- Follow PEP 8
- Use type hints for function signatures
- Use docstrings for classes and public methods
- Prefer descriptive variable names
- Use `snake_case` for variables and functions, `PascalCase` for classes

### Django Models

- Models map to legacy database tables — use `db_table` Meta option
- Define `__str__` methods for all models
- Use appropriate field types and constraints
- Add `related_name` to ForeignKey and ManyToManyField

### DRF Serializers

- Use `ModelSerializer` as base class
- Define explicit fields list (avoid `__all__` in production)
- Add validation methods (`validate_<field>`, `validate`)
- Include helpful error messages

### Views

- Use `ModelViewSet` for standard CRUD endpoints
- Use `APIView` for custom logic
- Apply appropriate permission classes
- Use `@action` decorator for custom ViewSet actions

### URLs

- Use routers for ViewSet registration
- Keep URL patterns consistent
- Use descriptive names for URL patterns

## Key Patterns

### Authentication

- JWT tokens via `djangorestframework-simplejwt`
- Access tokens in Authorization header
- Refresh tokens for token renewal
- Custom auth views for login/logout with cookie storage

### File Uploads

- Uploads stored in `MEDIA_ROOT/uploads/`
- Legacy paths resolved via `LEGACY_UPLOAD_ROOT`
- File type validation in `uploading.py`
- gzip compression for supported file types

### CORS

- Configured via `django-cors-headers`
- Allowed origins from `DJANGO_CORS_ALLOWED_ORIGINS` env var
- Credentials enabled for cookie-based auth

## Commands

```bash
python manage.py migrate          # Run migrations
python manage.py makemigrations   # Create migrations
python manage.py createsuperuser  # Create admin user
python manage.py runserver        # Development server
python manage.py test             # Run tests
python manage.py shell            # Django shell
```

## Environment

All configuration is driven by environment variables. See `.env.example` for required variables. Never hardcode secrets or database credentials.

## Database

- MySQL / MariaDB via PyMySQL
- Legacy tables mapped with `db_table` Meta option
- Use `migrate --fake-initial` for existing databases with legacy tables
- Run `sql_legacy_compatibility.sql` before first migration on legacy DB

## Important Notes

- Models map to existing legacy tables — be careful with migrations
- The `LEGACY_UPLOAD_ROOT` setting resolves old upload paths
- CORS must include the frontend origin (`http://localhost:3000` in dev)
- Always use prepared statements (Django ORM handles this)
- Password hashing uses Argon2 — do not change without migration plan
