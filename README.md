# Person Rating Platform

A Django-based web platform where users can rate and discuss about people, similar to IMDB's rating system.

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

## Local Development

The committed `personmeter/settings.py` targets production (PostgreSQL, S3, `DEBUG=False`).
For local work use `personmeter/settings_local.py`, which overrides it with SQLite and
filesystem media storage — no `.env`, database server or AWS credentials needed.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate --settings=personmeter.settings_local
python manage.py seed_demo --settings=personmeter.settings_local
python manage.py runserver --settings=personmeter.settings_local
```

Then open http://127.0.0.1:8000/.

### Demo data

`seed_demo` loads `core/fixtures/demo_people.json` (8 categories, 32 well-known people)
and generates ratings, comments, favourites and collections on top of it, so the feed and
statistics pages are not empty on a fresh clone. It is safe to re-run — the random
generator is seeded and every object is created against a fixed key, so nothing duplicates.

Accounts it creates:

| Username | Password | Notes |
| --- | --- | --- |
| `admin` | `admin123` | Superuser, for `/admin/` |
| `demo` | `demo123` | Regular account; owns the demo collections and favourites |
| `rater001` … `rater130` | `demo1234` | Only exist to produce ratings and comments |

These credentials are deliberately trivial and are for local use only.

The rater accounts exist because ratings are unique per `(person, user)` pair: the only
way to give someone the 100+ ratings that `/top-rated/` requires is to have more than 100
accounts. Lower the count with `--raters 40` for a lighter dataset — `/top-rated/` will
then be empty, since nobody clears the threshold.

Use `--reset` whenever you change `--raters`. Re-running with the same arguments is
harmless, but switching pool sizes without a reset leaves the previous run's ratings
behind.

### Person images

Photographs come from the subjects' English Wikipedia pages. `core/fixtures/demo_image_sources.json`
holds the resolved image URL, source page, licence and credit for each of the 32 people;
`seed_demo` downloads them, converts them to 800px JPEGs and stores them under `MEDIA_ROOT`,
so no binaries live in the repository. Every image is public domain or CC-licensed.

Downloads are cached in `.demo_image_cache/` (git-ignored), so only the first run hits
Wikimedia — later runs finish in about a second. Use `--no-images` to skip downloading
entirely; the interface falls back to coloured initial tiles.

## Tech Stack
- Django 4.x
- Bootstrap 5.x
- SQLite (default) / PostgreSQL (production)
