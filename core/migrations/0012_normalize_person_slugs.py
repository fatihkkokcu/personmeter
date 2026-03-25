from django.db import migrations
from django.utils.text import slugify


SLUG_TRANSLATION_TABLE = str.maketrans(
    {
        "ç": "c",
        "Ç": "C",
        "ğ": "g",
        "Ğ": "G",
        "ı": "i",
        "İ": "I",
        "ö": "o",
        "Ö": "O",
        "ş": "s",
        "Ş": "S",
        "ü": "u",
        "Ü": "U",
    }
)


def normalize_slug_source(value):
    return value.translate(SLUG_TRANSLATION_TABLE)


def repopulate_person_slugs(apps, schema_editor):
    Person = apps.get_model("core", "Person")
    existing_slugs = set()

    for person in Person.objects.all().order_by("id"):
        base_slug = slugify(normalize_slug_source(person.name))[:230] or "person"
        slug = base_slug
        counter = 2

        while slug in existing_slugs:
            suffix = f"-{counter}"
            slug = f"{base_slug[: 230 - len(suffix)]}{suffix}"
            counter += 1

        person.slug = slug
        person.save(update_fields=["slug"])
        existing_slugs.add(slug)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_person_slug"),
    ]

    operations = [
        migrations.RunPython(repopulate_person_slugs, migrations.RunPython.noop),
    ]
