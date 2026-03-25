from django.db import migrations, models
from django.utils.text import slugify


def populate_person_slugs(apps, schema_editor):
    Person = apps.get_model("core", "Person")

    existing_slugs = set(
        Person.objects.exclude(slug__isnull=True).exclude(slug="").values_list("slug", flat=True)
    )

    for person in Person.objects.all().order_by("id"):
        if person.slug:
            continue

        base_slug = slugify(person.name)[:230] or "person"
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
        ("core", "0010_person_ratings_average_cached_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="slug",
            field=models.SlugField(blank=True, db_index=True, max_length=230, null=True),
        ),
        migrations.RunPython(populate_person_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="person",
            name="slug",
            field=models.SlugField(blank=True, db_index=True, max_length=230, unique=True),
        ),
    ]
