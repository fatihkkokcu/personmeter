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

## Documentation

- [Guide to Adding People](docs/ADDING_PEOPLE.md) - Learn how to properly add people to the platform, including image requirements, description guidelines, and tag usage.

## Tech Stack
- Django 4.x
- Bootstrap 5.x
- SQLite (default) / PostgreSQL (production)
