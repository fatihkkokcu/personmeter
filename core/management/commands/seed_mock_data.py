import hashlib
from io import BytesIO
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from core.models import Category, Collection, CollectionItem, Comment, Favorite, Person, Rating


CELEBRITIES = [
    {
        "name": "Leonardo DiCaprio",
        "category": "Actors",
        "description": "Award-winning actor known for ambitious dramatic performances and global box office hits.",
        "tags": "actor,hollywood,award-winning,film",
    },
    {
        "name": "Scarlett Johansson",
        "category": "Actors",
        "description": "Versatile actor recognized for blockbuster franchises and character-driven films.",
        "tags": "actor,hollywood,marvel,film",
    },
    {
        "name": "Zendaya",
        "category": "Actors",
        "description": "Actor and performer with a strong presence across television, film, and fashion.",
        "tags": "actor,television,film,fashion",
    },
    {
        "name": "Tom Hanks",
        "category": "Actors",
        "description": "Beloved actor associated with classic dramas, comedies, and long-running audience appeal.",
        "tags": "actor,hollywood,classics,film",
    },
    {
        "name": "Taylor Swift",
        "category": "Musicians",
        "description": "Singer-songwriter known for stadium tours, chart success, and a large global fan base.",
        "tags": "musician,pop,songwriter,touring",
    },
    {
        "name": "Beyonce",
        "category": "Musicians",
        "description": "Global pop and R&B performer known for influential live shows and cultural reach.",
        "tags": "musician,pop,rnb,performer",
    },
    {
        "name": "The Weeknd",
        "category": "Musicians",
        "description": "Chart-topping artist known for moody pop production and major streaming success.",
        "tags": "musician,pop,rnb,streaming",
    },
    {
        "name": "Drake",
        "category": "Musicians",
        "description": "Commercially dominant artist with a broad catalog spanning rap, pop, and R&B.",
        "tags": "musician,rap,pop,streaming",
    },
    {
        "name": "Lionel Messi",
        "category": "Athletes",
        "description": "Football icon celebrated for elite playmaking, consistency, and major international success.",
        "tags": "athlete,football,goat,argentina",
    },
    {
        "name": "Cristiano Ronaldo",
        "category": "Athletes",
        "description": "Football superstar known for longevity, scoring records, and global brand power.",
        "tags": "athlete,football,goat,portugal",
    },
    {
        "name": "Serena Williams",
        "category": "Athletes",
        "description": "Tennis legend with a dominant competitive record and major influence beyond sport.",
        "tags": "athlete,tennis,legend,champion",
    },
    {
        "name": "LeBron James",
        "category": "Athletes",
        "description": "Basketball star known for elite longevity, championships, and off-court business impact.",
        "tags": "athlete,basketball,nba,legend",
    },
    {
        "name": "Elon Musk",
        "category": "Public Figures",
        "description": "High-profile entrepreneur associated with electric vehicles, space ventures, and internet discourse.",
        "tags": "entrepreneur,technology,space,business",
    },
    {
        "name": "Bill Gates",
        "category": "Public Figures",
        "description": "Technology entrepreneur and philanthropist with long-standing global name recognition.",
        "tags": "entrepreneur,technology,philanthropy,business",
    },
    {
        "name": "Oprah Winfrey",
        "category": "Public Figures",
        "description": "Media executive and presenter with lasting cultural influence across television and publishing.",
        "tags": "media,television,entrepreneur,culture",
    },
    {
        "name": "MrBeast",
        "category": "Creators",
        "description": "Digital creator known for large-scale challenge videos and audience-driven internet reach.",
        "tags": "creator,youtube,digital,entertainment",
    },
    {
        "name": "Keanu Reeves",
        "category": "Actors",
        "description": "Actor widely recognized for action franchises and a consistently positive public image.",
        "tags": "actor,action,hollywood,film",
    },
    {
        "name": "Emma Stone",
        "category": "Actors",
        "description": "Award-winning actor known for charismatic performances across comedy and drama.",
        "tags": "actor,hollywood,award-winning,film",
    },
    {
        "name": "Ryan Gosling",
        "category": "Actors",
        "description": "Film actor known for stylish lead roles across romance, drama, and comedy.",
        "tags": "actor,hollywood,drama,film",
    },
    {
        "name": "Angelina Jolie",
        "category": "Actors",
        "description": "Global film star associated with major franchises, drama roles, and humanitarian visibility.",
        "tags": "actor,hollywood,global,film",
    },
    {
        "name": "Dua Lipa",
        "category": "Musicians",
        "description": "Pop performer known for dance-floor hits, strong visuals, and global touring appeal.",
        "tags": "musician,pop,performer,touring",
    },
    {
        "name": "Adele",
        "category": "Musicians",
        "description": "Singer-songwriter recognized for ballads, vocal power, and massive album sales.",
        "tags": "musician,pop,soul,vocals",
    },
    {
        "name": "Ed Sheeran",
        "category": "Musicians",
        "description": "Singer-songwriter known for radio success, songwriting range, and stadium performances.",
        "tags": "musician,pop,songwriter,acoustic",
    },
    {
        "name": "Bad Bunny",
        "category": "Musicians",
        "description": "International music star with major streaming presence and crossover cultural impact.",
        "tags": "musician,latin,streaming,global",
    },
    {
        "name": "Novak Djokovic",
        "category": "Athletes",
        "description": "Tennis champion known for elite consistency, physical resilience, and record-setting success.",
        "tags": "athlete,tennis,champion,records",
    },
    {
        "name": "Roger Federer",
        "category": "Athletes",
        "description": "Tennis legend associated with longevity, elegance, and broad global popularity.",
        "tags": "athlete,tennis,legend,global",
    },
    {
        "name": "Kylian Mbappé",
        "category": "Athletes",
        "description": "Football star known for explosive pace, elite finishing, and major tournament visibility.",
        "tags": "athlete,football,forward,france",
    },
    {
        "name": "Michael Jordan",
        "category": "Athletes",
        "description": "Basketball icon whose competitive legacy remains a benchmark for greatness.",
        "tags": "athlete,basketball,legend,nba",
    },
    {
        "name": "Kim Kardashian",
        "category": "Public Figures",
        "description": "Media personality and business figure with major influence in fashion and lifestyle culture.",
        "tags": "media,fashion,business,culture",
    },
    {
        "name": "David Beckham",
        "category": "Public Figures",
        "description": "Former football star and global media figure known for brand and lifestyle appeal.",
        "tags": "football,media,brand,style",
    },
    {
        "name": "PewDiePie",
        "category": "Creators",
        "description": "Digital creator recognized for long-running internet fame and gaming-focused content.",
        "tags": "creator,youtube,gaming,internet",
    },
    {
        "name": "Rihanna",
        "category": "Public Figures",
        "description": "Music and beauty entrepreneur with strong influence across pop culture and business.",
        "tags": "musician,business,beauty,pop-culture",
    },
    {
        "name": "Şah Rukh Khan",
        "category": "Actors",
        "description": "Globally recognized film star associated with major audience reach and enduring fame.",
        "tags": "actor,film,global,cinema",
    },
    {
        "name": "Priyanka Chopra",
        "category": "Actors",
        "description": "Actor and producer with visibility across film, television, and international media.",
        "tags": "actor,producer,television,global",
    },
    {
        "name": "Tarkan",
        "category": "Musicians",
        "description": "Turkish pop icon known for crossover hits, stage presence, and long-term popularity.",
        "tags": "musician,turkish,pop,icon",
    },
    {
        "name": "Barış Manço",
        "category": "Musicians",
        "description": "Beloved Turkish music legend remembered for songs, television work, and cultural influence.",
        "tags": "musician,turkish,legend,culture",
    },
    {
        "name": "Cem Yılmaz",
        "category": "Public Figures",
        "description": "Turkish comedian and filmmaker known for stand-up, films, and strong mainstream recognition.",
        "tags": "comedian,turkish,film,stand-up",
    },
    {
        "name": "Kıvanç Tatlıtuğ",
        "category": "Actors",
        "description": "Turkish actor associated with high-profile television dramas and strong screen presence.",
        "tags": "actor,turkish,television,drama",
    },
    {
        "name": "Aras Bulut İynemli",
        "category": "Actors",
        "description": "Turkish actor known for emotionally intense television and film performances.",
        "tags": "actor,turkish,television,film",
    },
    {
        "name": "Hande Erçel",
        "category": "Actors",
        "description": "Turkish actor and model with strong digital popularity and mainstream television reach.",
        "tags": "actor,turkish,model,television",
    },
    {
        "name": "Serenay Sarıkaya",
        "category": "Actors",
        "description": "Turkish actor recognized for television leads, fashion visibility, and broad audience appeal.",
        "tags": "actor,turkish,television,fashion",
    },
    {
        "name": "Demet Özdemir",
        "category": "Actors",
        "description": "Turkish actor and performer with popular romantic drama and comedy projects.",
        "tags": "actor,turkish,romance,television",
    },
    {
        "name": "Kenan İmirzalıoğlu",
        "category": "Actors",
        "description": "Turkish actor known for long-running series and a steady mainstream profile.",
        "tags": "actor,turkish,television,series",
    },
    {
        "name": "Hadise",
        "category": "Musicians",
        "description": "Turkish-Belgian pop singer with mainstream hits and television presence.",
        "tags": "musician,turkish,pop,television",
    },
    {
        "name": "Ajda Pekkan",
        "category": "Musicians",
        "description": "Turkish pop legend whose long career made her one of the country's iconic performers.",
        "tags": "musician,turkish,legend,pop",
    },
    {
        "name": "Edis",
        "category": "Musicians",
        "description": "Turkish pop performer known for polished visuals, upbeat singles, and live appeal.",
        "tags": "musician,turkish,pop,performer",
    },
    {
        "name": "Mert Demir",
        "category": "Musicians",
        "description": "Turkish singer-songwriter with contemporary pop success and growing mainstream visibility.",
        "tags": "musician,turkish,pop,songwriter",
    },
    {
        "name": "Ezhel",
        "category": "Musicians",
        "description": "Turkish artist known for rap and genre crossover with strong youth recognition.",
        "tags": "musician,turkish,rap,urban",
    },
    {
        "name": "Haluk Levent",
        "category": "Public Figures",
        "description": "Turkish rock musician and public figure known for music and visible social solidarity work.",
        "tags": "musician,turkish,rock,public-figure",
    },
    {
        "name": "Arda Güler",
        "category": "Athletes",
        "description": "Turkish football talent known for technical creativity and fast-rising international attention.",
        "tags": "athlete,turkish,football,young-star",
    },
    {
        "name": "Hakan Çalhanoğlu",
        "category": "Athletes",
        "description": "Turkish midfielder recognized for technical passing, set pieces, and top-level club football.",
        "tags": "athlete,turkish,football,midfielder",
    },
    {
        "name": "Naim Süleymanoğlu",
        "category": "Athletes",
        "description": "Turkish weightlifting legend remembered for remarkable strength and international medals.",
        "tags": "athlete,turkish,legend,olympics",
    },
    {
        "name": "Acun Ilıcalı",
        "category": "Public Figures",
        "description": "Turkish media entrepreneur known for television formats and broad entertainment influence.",
        "tags": "media,turkish,entrepreneur,television",
    },
]

COLLECTIONS = [
    ("Award-Winning Actors", ["Leonardo DiCaprio", "Scarlett Johansson", "Zendaya", "Tom Hanks"]),
    ("Global Pop Icons", ["Taylor Swift", "Beyonce", "The Weeknd", "Drake"]),
    ("Legends of Sport", ["Lionel Messi", "Cristiano Ronaldo", "Serena Williams", "LeBron James"]),
    ("Internet and Media Powerhouses", ["Oprah Winfrey", "MrBeast", "Bill Gates", "Elon Musk"]),
    ("Turkish Screen Stars", ["Kıvanç Tatlıtuğ", "Aras Bulut İynemli", "Hande Erçel", "Serenay Sarıkaya"]),
    ("Turkish Music Icons", ["Tarkan", "Barış Manço", "Ajda Pekkan", "Hadise"]),
    ("Turkish Spotlight", ["Cem Yılmaz", "Acun Ilıcalı", "Arda Güler", "Hakan Çalhanoğlu"]),
]

LOCATIONS = [
    "Istanbul",
    "Ankara",
    "Izmir",
    "London",
    "New York",
    "Berlin",
    "Paris",
    "Los Angeles",
    "Toronto",
    "Dubai",
]

COMMENT_TEMPLATES = [
    "Strong public image and consistently interesting profile.",
    "Very recognizable name and a useful benchmark entry for the app.",
    "This profile feels like solid demo content for ratings and comments.",
    "A good example of a celebrity page with clear category fit.",
]


class Command(BaseCommand):
    help = "Seed the database with celebrity-focused demo content."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fan-count",
            type=int,
            default=120,
            help="How many demo fan users to create. Use 100+ if you want Top 250 entries.",
        )
        parser.add_argument(
            "--password",
            default="DemoPass123!",
            help="Password assigned to demo users that are created by this command.",
        )
        parser.add_argument(
            "--without-images",
            action="store_true",
            help="Skip generating poster-style profile images for demo people.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        fan_count = max(1, options["fan_count"])
        password = options["password"]
        with_images = not options["without_images"]

        categories = self._seed_categories()
        curator = self._get_or_create_user(
            username="mock_curator",
            email="mock_curator@example.com",
            password=password,
            location="Istanbul",
            bio="Curates demo celebrity content for local testing.",
        )
        fans = self._seed_fans(fan_count=fan_count, password=password)
        people, created_people, created_images = self._seed_people(
            categories=categories,
            curator=curator,
            with_images=with_images,
        )
        created_ratings = self._seed_ratings(people=people, fans=fans)
        created_comments = self._seed_comments(people=people, fans=fans)
        created_favorites = self._seed_favorites(people=people, fans=fans)
        created_collections = self._seed_collections(people=people, curator=curator)

        for person in people:
            person.refresh_rating_metrics()

        self.stdout.write(self.style.SUCCESS("Celebrity mock data is ready."))
        self.stdout.write(f"People created: {created_people}")
        self.stdout.write(f"Images created: {created_images}")
        self.stdout.write(f"Ratings created: {created_ratings}")
        self.stdout.write(f"Comments created: {created_comments}")
        self.stdout.write(f"Favorites created: {created_favorites}")
        self.stdout.write(f"Collections created: {created_collections}")
        self.stdout.write(f"Demo user password: {password}")
        self.stdout.write("Primary demo accounts: mock_curator and demo_fan_001 ...")

    def _seed_categories(self):
        categories = {}
        for name in sorted({item["category"] for item in CELEBRITIES}):
            category, _ = Category.objects.get_or_create(
                name=name,
                defaults={"description": f"Demo category for {name.lower()}."},
            )
            categories[name] = category
        return categories

    def _seed_people(self, categories, curator, with_images):
        created_count = 0
        image_count = 0
        people = []
        for item in CELEBRITIES:
            person, created = Person.objects.get_or_create(
                name=item["name"],
                defaults={
                    "description": item["description"],
                    "category": categories[item["category"]],
                    "tags": item["tags"],
                    "created_by": curator,
                },
            )
            if created:
                created_count += 1
            has_seed_image = person.image and Path(person.image.name).name.startswith("seed_")
            if with_images and (not person.image or has_seed_image):
                if has_seed_image:
                    person.image.delete(save=False)
                person.image.save(
                    self._build_image_filename(item["name"]),
                    ContentFile(self._build_person_portrait(item)),
                    save=True,
                )
                image_count += 1
            people.append(person)
        return people, created_count, image_count

    def _seed_fans(self, fan_count, password):
        fans = []
        for index in range(1, fan_count + 1):
            user = self._get_or_create_user(
                username=f"demo_fan_{index:03d}",
                email=f"demo_fan_{index:03d}@example.com",
                password=password,
                location=LOCATIONS[(index - 1) % len(LOCATIONS)],
                bio=f"Demo fan account #{index} for local load and UI testing.",
            )
            fans.append(user)
        return fans

    def _get_or_create_user(self, username, email, password, location, bio):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        if created:
            user.email = email
            user.set_password(password)
            user.save(update_fields=["email", "password"])

        profile = user.profile
        changed_fields = []
        if profile.location != location:
            profile.location = location
            changed_fields.append("location")
        if profile.bio != bio:
            profile.bio = bio
            changed_fields.append("bio")
        if changed_fields:
            profile.save(update_fields=changed_fields)

        return user

    def _seed_ratings(self, people, fans):
        existing_pairs = set(
            Rating.objects.filter(person__in=people, user__in=fans).values_list("person_id", "user_id")
        )
        created_count = 0
        now = timezone.now()
        pending_ratings = []

        for person_index, person in enumerate(people):
            for fan_index, fan in enumerate(fans):
                pair = (person.pk, fan.pk)
                if pair in existing_pairs:
                    continue

                score = 6 + ((person_index * 5 + fan_index * 3) % 5)
                created_at = now - timedelta(days=(person_index + fan_index) % 30)
                pending_ratings.append(
                    Rating(
                        person=person,
                        user=fan,
                        score=score,
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )

        if pending_ratings:
            Rating.objects.bulk_create(pending_ratings, batch_size=500)
            created_count = len(pending_ratings)

        return created_count

    def _seed_comments(self, people, fans):
        comment_users = fans[: min(8, len(fans))]
        existing_triples = set(
            Comment.objects.filter(person__in=people, user__in=comment_users).values_list(
                "person_id",
                "user_id",
                "content",
            )
        )
        created_count = 0

        for person_index, person in enumerate(people):
            for fan_index, fan in enumerate(comment_users):
                content = COMMENT_TEMPLATES[(person_index + fan_index) % len(COMMENT_TEMPLATES)]
                triple = (person.pk, fan.pk, content)
                if triple in existing_triples:
                    continue

                Comment.objects.create(
                    person=person,
                    user=fan,
                    content=content,
                )
                created_count += 1

        return created_count

    def _seed_favorites(self, people, fans):
        existing_pairs = set(
            Favorite.objects.filter(person__in=people, user_profile__user__in=fans).values_list(
                "person_id",
                "user_profile__user_id",
            )
        )
        pending_favorites = []

        for fan_index, fan in enumerate(fans):
            favorite_targets = [people[(fan_index + offset) % len(people)] for offset in range(3)]
            for person in favorite_targets:
                pair = (person.pk, fan.pk)
                if pair in existing_pairs:
                    continue
                pending_favorites.append(
                    Favorite(
                        user_profile=fan.profile,
                        person=person,
                    )
                )

        if pending_favorites:
            Favorite.objects.bulk_create(pending_favorites, ignore_conflicts=True, batch_size=500)

        return len(pending_favorites)

    def _seed_collections(self, people, curator):
        people_by_name = {person.name: person for person in people}
        created_collections = 0

        for title, names in COLLECTIONS:
            collection, created = Collection.objects.get_or_create(
                title=title,
                created_by=curator,
                defaults={
                    "description": f"Demo collection: {title}.",
                    "is_public": True,
                },
            )
            if created:
                created_collections += 1

            for order, name in enumerate(names):
                person = people_by_name[name]
                CollectionItem.objects.get_or_create(
                    collection=collection,
                    person=person,
                    defaults={"order": order},
                )

        return created_collections

    def _build_image_filename(self, name):
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]
        return f"seed_portrait_{digest}.jpg"

    def _build_person_portrait(self, item):
        width, height = 900, 1200
        top_color, bottom_color, accent_color = self._palette_for_name(item["name"])
        skin_color = self._skin_tone_for_name(item["name"])
        hair_color = self._hair_tone_for_name(item["name"])
        clothing_color = self._clothing_tone_for_name(item["name"], accent_color)
        image = Image.new("RGB", (width, height), top_color)
        draw = ImageDraw.Draw(image)

        for y in range(height):
            ratio = y / max(height - 1, 1)
            line_color = tuple(
                int(top_color[index] + (bottom_color[index] - top_color[index]) * ratio)
                for index in range(3)
            )
            draw.line([(0, y), (width, y)], fill=line_color)

        for offset in range(6):
            alpha_color = tuple(min(255, channel + offset * 8) for channel in accent_color)
            left = -120 + offset * 110
            top = 90 + offset * 55
            draw.ellipse((left, top, left + 420, top + 420), fill=alpha_color, outline=None)

        bust_top = 610
        draw.rounded_rectangle(
            (120, bust_top, width - 120, height + 150),
            radius=120,
            fill=clothing_color,
        )
        draw.polygon(
            [(250, height), (450, 760), (650, height)],
            fill=tuple(max(0, channel - 25) for channel in clothing_color),
        )

        neck_left = width // 2 - 55
        neck_top = 500
        neck_bottom = 650
        draw.rounded_rectangle(
            (neck_left, neck_top, neck_left + 110, neck_bottom),
            radius=28,
            fill=skin_color,
        )

        head_box = (260, 180, 640, 620)
        draw.ellipse(head_box, fill=skin_color)

        ear_color = tuple(max(0, channel - 8) for channel in skin_color)
        draw.ellipse((235, 330, 300, 450), fill=ear_color)
        draw.ellipse((600, 330, 665, 450), fill=ear_color)

        draw.pieslice((220, 120, 680, 650), start=180, end=360, fill=hair_color)
        draw.rounded_rectangle(
            (260, 220, 325, 610),
            radius=32,
            fill=hair_color,
        )
        draw.rounded_rectangle(
            (575, 220, 640, 610),
            radius=32,
            fill=hair_color,
        )
        fringe_shift = self._feature_value(item["name"], 9, -30, 30)
        draw.polygon(
            [
                (285, 260),
                (360 + fringe_shift, 170),
                (470, 240),
                (560, 160),
                (620, 280),
                (620, 220),
                (285, 220),
            ],
            fill=hair_color,
        )

        eye_y = 370 + self._feature_value(item["name"], 10, -12, 12)
        eye_spacing = 105 + self._feature_value(item["name"], 11, -10, 14)
        eye_width = 66
        eye_height = 32
        left_eye_x = width // 2 - eye_spacing - eye_width // 2
        right_eye_x = width // 2 + eye_spacing - eye_width // 2
        iris_color = tuple(max(30, channel - 70) for channel in accent_color)

        for eye_x in (left_eye_x, right_eye_x):
            draw.ellipse((eye_x, eye_y, eye_x + eye_width, eye_y + eye_height), fill=(252, 252, 252))
            draw.ellipse((eye_x + 20, eye_y + 6, eye_x + 46, eye_y + 32), fill=iris_color)
            draw.ellipse((eye_x + 28, eye_y + 12, eye_x + 40, eye_y + 24), fill=(22, 22, 22))

        brow_y = eye_y - 28
        draw.line((left_eye_x - 4, brow_y, left_eye_x + eye_width + 4, brow_y - 6), fill=hair_color, width=8)
        draw.line((right_eye_x - 4, brow_y - 6, right_eye_x + eye_width + 4, brow_y), fill=hair_color, width=8)

        nose_top = eye_y + 36
        nose_bottom = nose_top + 95
        nose_x = width // 2 + self._feature_value(item["name"], 12, -8, 8)
        draw.line((nose_x, nose_top, nose_x - 10, nose_bottom), fill=tuple(max(0, channel - 25) for channel in skin_color), width=7)
        draw.arc((nose_x - 28, nose_bottom - 6, nose_x + 18, nose_bottom + 26), start=20, end=180, fill=tuple(max(0, channel - 40) for channel in skin_color), width=5)

        mouth_top = nose_bottom + 50
        mouth_width = 120 + self._feature_value(item["name"], 13, -20, 20)
        draw.arc(
            (
                width // 2 - mouth_width // 2,
                mouth_top,
                width // 2 + mouth_width // 2,
                mouth_top + 55,
            ),
            start=15,
            end=165,
            fill=(145, 50, 70),
            width=6,
        )

        draw.line((280, 740, 430, 640), fill=(238, 238, 238), width=8)
        draw.line((620, 740, 470, 640), fill=(238, 238, 238), width=8)
        draw.rounded_rectangle((388, 650, 512, 860), radius=24, outline=(240, 240, 240), width=4)

        output = BytesIO()
        image.save(output, format="JPEG", quality=90)
        return output.getvalue()

    def _palette_for_name(self, name):
        digest = hashlib.sha256(name.encode("utf-8")).digest()
        return (
            (40 + digest[0] % 80, 30 + digest[1] % 90, 70 + digest[2] % 100),
            (100 + digest[3] % 120, 50 + digest[4] % 100, 80 + digest[5] % 90),
            (160 + digest[6] % 80, 90 + digest[7] % 80, 120 + digest[8] % 80),
        )

    def _skin_tone_for_name(self, name):
        palette = [
            (244, 216, 188),
            (234, 197, 159),
            (210, 168, 130),
            (176, 126, 96),
            (126, 84, 60),
        ]
        return palette[self._feature_value(name, 0, 0, len(palette) - 1)]

    def _hair_tone_for_name(self, name):
        palette = [
            (32, 24, 22),
            (58, 37, 25),
            (90, 64, 40),
            (128, 97, 70),
            (42, 42, 48),
        ]
        return palette[self._feature_value(name, 1, 0, len(palette) - 1)]

    def _clothing_tone_for_name(self, name, accent_color):
        palettes = [
            (28, 34, 56),
            (36, 64, 74),
            (78, 48, 92),
            (70, 42, 44),
            tuple(max(0, channel - 55) for channel in accent_color),
        ]
        return palettes[self._feature_value(name, 2, 0, len(palettes) - 1)]

    def _feature_value(self, name, index, minimum, maximum):
        digest = hashlib.sha256(name.encode("utf-8")).digest()
        if minimum == maximum:
            return minimum
        span = maximum - minimum + 1
        return minimum + digest[index % len(digest)] % span
