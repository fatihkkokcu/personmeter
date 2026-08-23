"""Yerel demo verisini yükler: kişiler, hesaplar, oylar, yorumlar, koleksiyonlar.

Repoyu yeni çeken birinin boş bir siteyle karşılaşmaması için var. Üretimde
çalıştırılmak üzere tasarlanmadı; hesap şifreleri kasıtlı olarak basit.

    python manage.py seed_demo --settings=personmeter.settings_local

Komut yeniden çalıştırılabilir: her nesne sabit bir anahtarla oluşturulur ve
random üreteci sabit tohumla çalışır, yani ikinci çalıştırma kopya üretmez.
"""

import json
import random
import time
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image

from core.models import (
    Category,
    Collection,
    CollectionItem,
    Comment,
    Favorite,
    Person,
    Rating,
)

SEED = 42

# Kişi görselleri Wikipedia sayfa görsellerinden geliyor. URL'ler ayrı bir JSON'da
# tutuluyor ve dosyalar seed sırasında indiriliyor; böylece repoda binary durmuyor.
IMAGE_SOURCES = Path(__file__).resolve().parents[2] / 'fixtures' / 'demo_image_sources.json'
# Wikimedia'nın robot politikası iletişim bilgisi içeren bir User-Agent istiyor;
# genel bir UA ile istekler 429 dönüyor.
USER_AGENT = 'personmeter-demo-seed/1.0 (https://github.com/fatihkkokcu/personmeter) Python-urllib'
# İstekler arası bekleme. Peş peşe atılan 32 istek hız sınırına takılıyor.
REQUEST_DELAY = 0.5
DOWNLOAD_ATTEMPTS = 3
MAX_IMAGE_SIZE = 800
# İndirilen görseller burada saklanıyor. MEDIA_ROOT yeterli değil: loaddata,
# kişileri güncellerken delete_old_image sinyalini tetikliyor ve dosyaları
# siliyor; önbellek olmasa komut her çalıştığında 32 görseli yeniden indirirdi.
IMAGE_CACHE = Path(settings.BASE_DIR) / '.demo_image_cache'

# Giriş için kullanılacak iki hesap.
ADMIN = {'username': 'admin', 'email': 'admin@example.com', 'password': 'admin123'}
DEMO = {'username': 'demo', 'email': 'demo@example.com', 'password': 'demo123'}

# Oyları üretmek için açılan hesaplar. Şifreleri ortak; amaçları veri üretmek.
# 130 seçildi çünkü /top-rated/ yalnızca 100'den fazla oy almış kişileri listeliyor
# ve Rating (person, user) çifti tekil: eşiği aşmanın tek yolu oylayıcı sayısı.
RATER_COUNT = 130
RATER_PASSWORD = 'demo1234'

LOCATIONS = [
    'Istanbul', 'Ankara', 'Izmir', 'Berlin', 'Lisbon', 'Toronto',
    'Nairobi', 'Osaka', 'Sao Paulo', 'Manchester', 'Austin', 'Delhi',
]

COMMENTS = [
    "Kept coming back to this one. The body of work holds up better than the reputation suggests.",
    "Underrated here, honestly. Would put them a couple of points higher.",
    "Rated high, but the ceiling was even higher than what actually got made.",
    "The influence is easier to see in everyone who came after than in the work itself.",
    "First encountered this as a teenager and it rearranged what I thought was possible.",
    "Consistency over decades is the part people skip when they talk about this one.",
    "Strong start, uneven middle, and then a late run nobody saw coming.",
    "Hard to separate the myth from the actual output at this point.",
    "The technical side gets all the attention, but the judgement was the rare part.",
    "Would rank differently depending on which decade you ask about.",
    "Read three biographies and still not sure I understand the decision-making.",
    "Overexposed, which is a strange thing to hold against someone.",
    "The early work is the interesting work. The famous stuff came later.",
    "Placement feels about right. Not a stretch in either direction.",
    "People forget how much of this was done without the tools we take for granted.",
    "Gave this a 9 and felt like I was being stingy.",
    "Respect the achievement, never connected with it personally.",
    "Every field has one of these: the person the specialists point to first.",
    "The contemporaries who were considered equals at the time have not aged the same way.",
    "Watched a documentary last month and bumped my rating up two points.",
]

# (koleksiyon başlığı, açıklama, kişi adları)
COLLECTIONS = [
    (
        'Minds that changed the rules',
        'People whose work forced everyone else in their field to start over.',
        ['Marie Curie', 'Albert Einstein', 'Ada Lovelace', 'Alan Turing',
         'Charles Darwin', 'Grace Hopper'],
    ),
    (
        'Screen and sound',
        'A short list for anyone arguing about the 20th century in film and music.',
        ['Akira Kurosawa', 'Hayao Miyazaki', 'Meryl Streep', 'Freddie Mercury',
         'Nina Simone', 'Beyonce Knowles'],
    ),
    (
        'The long game',
        'Careers measured in decades, not seasons.',
        ['Serena Williams', 'Muhammad Ali', 'Nelson Mandela', 'Pele',
         'Rosa Parks', 'Yayoi Kusama'],
    ),
]


class Command(BaseCommand):
    help = 'Yerel geliştirme için demo verisi yükler (kişiler, hesaplar, oylar, yorumlar).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--raters',
            type=int,
            default=RATER_COUNT,
            help=f'Oy üretmek için açılacak hesap sayısı (varsayılan {RATER_COUNT}).',
        )
        parser.add_argument(
            '--no-images',
            action='store_true',
            help='Wikipedia görsellerini indirmeyi atlar (çevrimdışı çalışmak için).',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Önceki demo verisini silip sıfırdan üretir. Farklı --raters '
                 'değerleriyle çalıştırırken gerekli: aksi halde eski oylar kalır.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(SEED)
        now = timezone.now()

        if options['reset']:
            self._reset()

        call_command('loaddata', 'demo_people', verbosity=0)
        people = list(Person.objects.order_by('pk'))
        self.stdout.write(f'Kişi: {len(people)}')

        admin, demo = self._create_login_users()
        raters = self._create_raters(options['raters'], rng)
        self.stdout.write(f'Hesap: {admin.username}, {demo.username} + {len(raters)} oylayıcı')

        self._assign_authors(people, raters + [demo], rng)

        if not options['no_images']:
            self._download_images(people)

        self._spread_person_dates(people, now, rng)
        rating_count = self._create_ratings(people, raters + [demo], now, rng)
        comment_count = self._create_comments(people, raters + [demo], now, rng)
        self._create_favorites(demo, people, rng)
        collection_count = self._create_collections(demo)

        self.stdout.write(
            f'Oy: {rating_count}  Yorum: {comment_count}  Koleksiyon: {collection_count}'
        )
        self.stdout.write(self.style.SUCCESS(
            f"\nHazır. Giriş: {ADMIN['username']}/{ADMIN['password']} (admin), "
            f"{DEMO['username']}/{DEMO['password']}"
        ))

    def _reset(self):
        """Demo verisini siler.

        Aynı parametrelerle tekrar çalıştırmak zaten kopya üretmiyor; bu, --raters
        değiştiğinde eski hesapların oylarının geride kalmasını engellemek için.
        Kişi ve kategoriler silinince oy, yorum ve koleksiyon kayıtları da
        cascade ile gidiyor.
        """
        raters = User.objects.filter(username__startswith='rater')
        counts = (Person.objects.count(), raters.count())
        Collection.objects.filter(created_by__username=DEMO['username']).delete()
        Person.objects.all().delete()
        Category.objects.all().delete()
        raters.delete()
        self.stdout.write(f'Sıfırlandı: {counts[0]} kişi, {counts[1]} oylayıcı silindi')

    def _create_login_users(self):
        admin, _ = User.objects.get_or_create(
            username=ADMIN['username'],
            defaults={'email': ADMIN['email'], 'is_staff': True, 'is_superuser': True},
        )
        admin.email = ADMIN['email']
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password(ADMIN['password'])
        admin.save()

        demo, _ = User.objects.get_or_create(
            username=DEMO['username'], defaults={'email': DEMO['email']}
        )
        demo.email = DEMO['email']
        demo.set_password(DEMO['password'])
        demo.save()

        demo.profile.bio = 'Local demo account. Rates too generously.'
        demo.profile.location = 'Istanbul'
        demo.profile.birth_date = date(1994, 6, 12)
        demo.profile.save()

        return admin, demo

    def _create_raters(self, count, rng):
        """Oy ve yorum üretmek için hesaplar.

        Profillere şehir ve doğum tarihi yazılıyor: kişi sayfasındaki demografi
        bölümü bu iki alan boşsa hiçbir şey göstermiyor.
        """
        raters = []
        for i in range(1, count + 1):
            username = f'rater{i:03d}'
            user, created = User.objects.get_or_create(
                username=username, defaults={'email': f'{username}@example.com'}
            )
            if created:
                user.set_password(RATER_PASSWORD)
                user.save()

            profile = user.profile
            profile.location = LOCATIONS[i % len(LOCATIONS)]
            profile.birth_date = date(
                rng.randint(1960, 2004), rng.randint(1, 12), rng.randint(1, 28)
            )
            profile.save()
            raters.append(user)
        return raters

    def _download_images(self, people):
        """Wikipedia sayfa görsellerini indirip Person.image alanına yazar.

        Ağ yoksa sessizce vazgeçiyor: görselsiz demo, yarım kalmış bir seed'den
        iyi. Zaten inmiş dosyalar tekrar indirilmiyor.
        """
        sources = {row['name']: row for row in json.loads(IMAGE_SOURCES.read_text())}
        IMAGE_CACHE.mkdir(exist_ok=True)
        downloaded = cached = failed = 0

        for person in people:
            row = sources.get(person.name)
            if row is None:
                continue

            slug = slugify(person.name)
            cache_file = IMAGE_CACHE / f'{slug}.jpg'

            if cache_file.exists():
                jpeg = cache_file.read_bytes()
                cached += 1
            else:
                data = self._fetch(row['image_url'])
                if data is None:
                    failed += 1
                    continue
                try:
                    jpeg = self._to_jpeg(data)
                except OSError:
                    failed += 1
                    continue
                cache_file.write_bytes(jpeg)
                downloaded += 1
                time.sleep(REQUEST_DELAY)

            # Dosya doğrudan depolamaya yazılıp alan update() ile işaretleniyor.
            # person.image.save() kullanılsaydı modeldeki compress_image sinyali
            # dosyayı ikinci kez, üstelik person_images/person_images/ altına
            # yazıyor ve ilk kopya sahipsiz kalıyor.
            target = f'person_images/{slug}.jpg'
            if default_storage.exists(target):
                default_storage.delete(target)
            name = default_storage.save(target, ContentFile(jpeg))
            Person.objects.filter(pk=person.pk).update(image=name)
            person.image = name

        self.stdout.write(
            f'Görsel: {downloaded} indirildi, {cached} önbellekten, {failed} başarısız'
        )
        if failed:
            self.stdout.write(self.style.WARNING(
                'Bazı görseller inmedi. Ağ bağlantısını kontrol edip komutu tekrar '
                'çalıştırın; eksik olanlar tamamlanır.'
            ))

    def _fetch(self, url):
        """Görseli indirir, 429'da Retry-After'a uyarak tekrar dener.

        Wikimedia hız sınırını hızlı çeker; tek denemede 32 görselin çoğu düşüyor.
        Başarısızlıkta None döner, çağıran sayacı artırır.
        """
        for attempt in range(DOWNLOAD_ATTEMPTS):
            try:
                request = Request(url, headers={'User-Agent': USER_AGENT})
                with urlopen(request, timeout=30) as response:
                    return response.read()
            except HTTPError as exc:
                if exc.code != 429 or attempt == DOWNLOAD_ATTEMPTS - 1:
                    return None
                retry_after = exc.headers.get('Retry-After')
                wait = int(retry_after) if retry_after and retry_after.isdigit() else 2 * (attempt + 1)
                time.sleep(wait)
            except (URLError, TimeoutError, OSError):
                return None
        return None

    def _to_jpeg(self, data):
        """Görseli RGB JPEG'e çevirip 800 pikselin altına küçültür.

        Boyut sınırı modeldeki compress_image ile aynı; kaynak dosyalar
        sıkıştırılmadan 13 MB'a yaklaşıyordu.
        """
        image = Image.open(BytesIO(data))
        if image.mode != 'RGB':
            image = image.convert('RGB')

        ratio = min(MAX_IMAGE_SIZE / image.width, MAX_IMAGE_SIZE / image.height, 1)
        if ratio < 1:
            image = image.resize(
                (int(image.width * ratio), int(image.height * ratio)),
                Image.Resampling.LANCZOS,
            )

        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=85, optimize=True)
        return buffer.getvalue()

    def _assign_authors(self, people, users, rng):
        """Kişileri ekleyen kullanıcıyı atar.

        Fixture created_by'ı boş bırakıyor (hesaplardan bağımsız olsun diye) ve
        arayüz bunu 'added by unknown' diye gösteriyor.
        """
        for person in people:
            author = rng.choice(users)
            Person.objects.filter(pk=person.pk).update(created_by=author)

    def _spread_person_dates(self, people, now, rng):
        """Ekleme tarihlerini son ~6 aya yayar.

        Fixture'daki sabit tarih tek başına kullanılsa 'new' sıralaması anlamsız
        kalır ve kayıtlar zamanla eskir. update() ile yazılıyor çünkü alanlar
        auto_now_add/auto_now ve save() üzerinden değiştirilemiyor.
        """
        for person in people:
            added = now - timedelta(days=rng.randint(1, 180), hours=rng.randint(0, 23))
            Person.objects.filter(pk=person.pk).update(
                created_at=added, updated_at=added
            )

    def _create_ratings(self, people, voters, now, rng):
        """Kişilere oy dağıtır.

        Kişilerin yarısı 'popüler' sayılıp havuzun neredeyse tamamından oy alıyor,
        kalanı çok daha az. Düz bir dağılımda 100 oy eşiğini (Top 250'nin şartı)
        yalnızca birkaç kişi geçiyordu; bu ayrım hem o sayfayı dolduruyor hem de
        listelerde popüler/yeni ayrımını görünür kılıyor. Her kişinin ayrıca gizli
        bir 'kalite' değeri var ve oylar bunun etrafında dağılıyor, böylece
        ortalamalar da birbirinden ayrışıyor.
        """
        by_offset = {}
        total = 0

        for person in people:
            quality = rng.uniform(5.5, 9.3)
            if rng.random() < 0.5:
                voter_count = rng.randint(int(len(voters) * 0.8), len(voters))
            else:
                voter_count = rng.randint(5, max(5, int(len(voters) * 0.5)))
            for voter in rng.sample(voters, voter_count):
                score = round(rng.gauss(quality, 1.4))
                score = max(1, min(10, score))
                rating, _ = Rating.objects.update_or_create(
                    person=person, user=voter, defaults={'score': score}
                )
                by_offset.setdefault(rng.randint(0, 60), []).append(rating.pk)
                total += 1

        self._backdate(Rating, by_offset, now)
        return total

    def _create_comments(self, people, authors, now, rng):
        by_offset = {}
        total = 0

        for person in people:
            for text in rng.sample(COMMENTS, rng.randint(1, 5)):
                comment, _ = Comment.objects.get_or_create(
                    person=person, user=rng.choice(authors), content=text
                )
                by_offset.setdefault(rng.randint(0, 45), []).append(comment.pk)
                total += 1

        self._backdate(Comment, by_offset, now)
        return total

    def _backdate(self, model, pks_by_day_offset, now):
        """created_at'i geçmişe yayar, gün başına tek UPDATE ile."""
        for offset, pks in pks_by_day_offset.items():
            model.objects.filter(pk__in=pks).update(created_at=now - timedelta(days=offset))

    def _create_favorites(self, user, people, rng):
        for person in rng.sample(people, 6):
            Favorite.objects.get_or_create(user_profile=user.profile, person=person)

    def _create_collections(self, owner):
        for title, description, names in COLLECTIONS:
            collection, _ = Collection.objects.get_or_create(
                title=title,
                created_by=owner,
                defaults={'description': description, 'is_public': True},
            )
            for order, name in enumerate(names):
                person = Person.objects.filter(name=name).first()
                if person:
                    CollectionItem.objects.get_or_create(
                        collection=collection, person=person, defaults={'order': order}
                    )
        return len(COLLECTIONS)
