# Person Rating Platform

A Django-based web platform where users can rate and discuss about people, similar to IMDB's rating system.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   `pip install -r requirements.txt`
3. Copy env template:
   `cp .env.example .env`
4. Run migrations:
   `python manage.py migrate`
5. Start development server:
   `python manage.py runserver`

Default runtime mode is `development`. To run production settings, set:
`PERSONMETER_ENV=production`

## Configuration

Environment variables are documented in `.env.example`.

Important groups:
- Django runtime: `PERSONMETER_ENV`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- Development DB: `SQLITE_NAME`
- Production DB: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- Production storage: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`
- Production security: `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`, `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`, `DJANGO_SECURE_HSTS_PRELOAD`, `DJANGO_SECURE_CONTENT_TYPE_NOSNIFF`, `DJANGO_X_FRAME_OPTIONS`
- Upload limits: `PERSONMETER_MAX_IMAGE_UPLOAD_MB`, `PERSONMETER_MAX_IMAGE_PIXELS`, `PERSONMETER_ALLOWED_IMAGE_*`

## Production Deployment

This project uses:
- `gunicorn` as the WSGI server
- `whitenoise` for static file serving in production

Typical deploy sequence:
1. Install dependencies:
   `pip install -r requirements.txt`
2. Apply migrations:
   `python manage.py migrate`
3. Build static assets:
   `python manage.py collectstatic --noinput`
4. Run app:
   `gunicorn personmeter.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120`

## Quality Checks

- Run tests: `python manage.py test`
- Run Django system checks: `python manage.py check`

## Features

### Person Pages
- Basic information about the person (name and short description)
- Rating system (1-10)
- Average rating and total number of ratings
- Comment section
- Users can add new persons to the platform
- Statistics section showing:
  - Rating distribution
  - Demographics of raters
  - Rating trends over time
  - Similar persons based on user ratings

### Search
- Global search functionality for persons and collections
- Advanced filters:
  - By rating range
  - By number of ratings
  - By categories/tags
  - By date added
- Auto-complete suggestions
- Search within collections

### User Profiles
- Personal information and preferences
- Activity feed
- Lists of:
  - Favorite persons
  - Rated persons
  - Created collections
  - Collection ratings and reviews
- Rating statistics and history
- Customizable privacy settings

### Homepage
- Currently trending persons
- Recently added persons
- Featured collections
- Weekly top rated persons

### Top 250
- List of highest-rated persons
- Minimum rating requirement (100 ratings)
- Sortable by rating and number of votes

### Collections
- Groups of similar persons
- Users can create and manage their own collections
- Collection description and title
- Browse public collections
- Rate and review collections

### Favorites
- Add persons to personal favorites list
- Organize favorites into custom categories
- Share favorite lists with other users
- Get notifications about updates to favorite persons

## Tech Stack
- Django 5.1.x
- Bootstrap 5.x
- SQLite (default) / PostgreSQL (production)
