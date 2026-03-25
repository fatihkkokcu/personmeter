from io import BytesIO
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .forms import PersonForm
from .models import (
    Category,
    Comment,
    Collection,
    CollectionItem,
    Favorite,
    ModerationLog,
    Person,
    Rating,
    Report,
    UserProfile,
    compress_image,
)


def build_test_image(
    name="test.jpg",
    image_format="JPEG",
    size=(40, 40),
    color=(220, 60, 90),
    content_type="image/jpeg",
):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class SearchViewTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(username="owner", password="pass12345")
        rater_one = User.objects.create_user(username="rater1", password="pass12345")
        rater_two = User.objects.create_user(username="rater2", password="pass12345")

        category = Category.objects.create(name="Actors", description="Actor profiles")

        self.high_person = Person.objects.create(
            name="High Rated",
            description="High score person",
            category=category,
            created_by=owner,
        )
        self.low_person = Person.objects.create(
            name="Low Rated",
            description="Lower score person",
            category=category,
            created_by=owner,
        )

        Rating.objects.create(person=self.high_person, user=rater_one, score=9)
        Rating.objects.create(person=self.high_person, user=rater_two, score=8)
        Rating.objects.create(person=self.low_person, user=rater_one, score=4)

    def test_search_filters_by_rating_range(self):
        response = self.client.get(
            reverse("search"),
            {"min_rating": 8, "max_rating": 9},
        )

        results = list(response.context["page_obj"].object_list)
        self.assertIn(self.high_person, results)
        self.assertNotIn(self.low_person, results)

    def test_search_filters_by_min_ratings_count(self):
        response = self.client.get(reverse("search"), {"min_ratings_count": 2})

        results = list(response.context["page_obj"].object_list)
        self.assertIn(self.high_person, results)
        self.assertNotIn(self.low_person, results)


class InteractionFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="member", password="pass12345")
        category = Category.objects.create(name="Singers", description="Singer profiles")
        self.person = Person.objects.create(
            name="Favorite Person",
            description="Test profile",
            category=category,
            created_by=self.user,
        )

    def test_rate_person_creates_and_updates_rating(self):
        self.client.login(username="member", password="pass12345")

        rate_url = reverse("rate_person", kwargs={"slug": self.person.slug})
        self.client.post(rate_url, {"score": "7"})
        self.client.post(rate_url, {"score": "9"})

        rating = Rating.objects.get(person=self.person, user=self.user)
        self.assertEqual(rating.score, 9)
        self.assertEqual(
            Rating.objects.filter(person=self.person, user=self.user).count(),
            1,
        )

    def test_toggle_favorite_adds_then_removes(self):
        self.client.login(username="member", password="pass12345")

        favorite_url = reverse("toggle_favorite", kwargs={"slug": self.person.slug})
        add_response = self.client.post(favorite_url)
        remove_response = self.client.post(favorite_url)

        self.assertEqual(add_response.status_code, 200)
        self.assertTrue(add_response.json()["is_favorite"])
        self.assertEqual(remove_response.status_code, 200)
        self.assertFalse(remove_response.json()["is_favorite"])
        self.assertEqual(
            Favorite.objects.filter(
                user_profile=self.user.profile,
                person=self.person,
            ).count(),
            0,
        )


class ReportFlowTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(username="reporter", password="pass12345")
        self.author = User.objects.create_user(username="author", password="pass12345")
        self.staff = User.objects.create_user(
            username="moderator",
            password="pass12345",
            is_staff=True,
        )
        category = Category.objects.create(name="Comedians", description="Comedian profiles")
        self.person = Person.objects.create(
            name="Reported Person",
            description="Profile under test",
            category=category,
            created_by=self.author,
        )
        self.comment = Comment.objects.create(
            person=self.person,
            user=self.author,
            content="Problematic comment",
        )

    def test_report_person_creates_report(self):
        self.client.login(username="reporter", password="pass12345")
        response = self.client.post(
            reverse("report_person", kwargs={"slug": self.person.slug}),
            {"reason": Report.REASON_SPAM, "details": "Spam links"},
        )

        self.assertEqual(response.status_code, 302)
        report = Report.objects.get(reporter=self.reporter, person=self.person)
        self.assertEqual(report.reason, Report.REASON_SPAM)
        self.assertEqual(report.status, Report.STATUS_PENDING)

    def test_report_comment_creates_report(self):
        self.client.login(username="reporter", password="pass12345")
        response = self.client.post(
            reverse("report_comment", kwargs={"pk": self.comment.pk}),
            {"reason": Report.REASON_HARASSMENT, "details": "Insulting language"},
        )

        self.assertEqual(response.status_code, 302)
        report = Report.objects.get(reporter=self.reporter, comment=self.comment)
        self.assertEqual(report.reason, Report.REASON_HARASSMENT)

    def test_staff_can_update_report_status(self):
        report = Report.objects.create(
            reporter=self.reporter,
            person=self.person,
            reason=Report.REASON_OTHER,
            details="Initial report",
        )
        self.client.login(username="moderator", password="pass12345")

        response = self.client.post(
            reverse("report_status_update", kwargs={"pk": report.pk}),
            {"status": Report.STATUS_ACTIONED, "resolution_notes": "Removed content"},
        )

        self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.STATUS_ACTIONED)
        self.assertEqual(report.reviewed_by, self.staff)
        self.assertEqual(report.resolution_notes, "Removed content")
        self.assertIsNotNone(report.reviewed_at)

    def test_auto_hide_comment_after_threshold_reports(self):
        extra_one = User.objects.create_user(username="r_extra_1", password="pass12345")
        extra_two = User.objects.create_user(username="r_extra_2", password="pass12345")

        for reporter in [self.reporter, extra_one, extra_two]:
            self.client.login(username=reporter.username, password="pass12345")
            self.client.post(
                reverse("report_comment", kwargs={"pk": self.comment.pk}),
                {"reason": Report.REASON_SPAM, "details": "Spam"},
            )

        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_hidden)
        self.assertIn("Auto-hidden", self.comment.hidden_reason)
        self.assertTrue(
            ModerationLog.objects.filter(
                action=ModerationLog.ACTION_TARGET_AUTO_HIDDEN,
                comment=self.comment,
            ).exists()
        )

    def test_escalating_sanctions_warn_mute_suspend_ban(self):
        reporters = [
            self.reporter,
            User.objects.create_user(username="rep_2", password="pass12345"),
            User.objects.create_user(username="rep_3", password="pass12345"),
            User.objects.create_user(username="rep_4", password="pass12345"),
        ]

        expected_statuses = [
            UserProfile.STATUS_WARNED,
            UserProfile.STATUS_MUTED,
            UserProfile.STATUS_SUSPENDED,
            UserProfile.STATUS_BANNED,
        ]

        for index, reporter in enumerate(reporters):
            target_person = Person.objects.create(
                name=f"Escalation Target {index}",
                description="Escalation profile",
                category=self.person.category,
                created_by=self.author,
            )
            self.client.login(username=reporter.username, password="pass12345")
            self.client.post(
                reverse("report_person", kwargs={"slug": target_person.slug}),
                {"reason": Report.REASON_OTHER, "details": f"Violation {index}"},
            )
            report = Report.objects.get(reporter=reporter, person=target_person)

            self.client.login(username="moderator", password="pass12345")
            self.client.post(
                reverse("report_status_update", kwargs={"pk": report.pk}),
                {"status": Report.STATUS_ACTIONED, "resolution_notes": "Confirmed"},
            )

            self.author.profile.refresh_from_db()
            self.assertEqual(self.author.profile.moderation_status, expected_statuses[index])

        self.assertEqual(self.author.profile.strike_count, 4)
        self.assertIsNotNone(self.author.profile.banned_at)
        self.assertTrue(
            ModerationLog.objects.filter(
                target_user=self.author,
                action=ModerationLog.ACTION_SANCTION_BAN,
            ).exists()
        )

    def test_report_status_update_creates_audit_log(self):
        report = Report.objects.create(
            reporter=self.reporter,
            comment=self.comment,
            reason=Report.REASON_HARASSMENT,
            details="Audit test",
        )
        self.client.login(username="moderator", password="pass12345")
        self.client.post(
            reverse("report_status_update", kwargs={"pk": report.pk}),
            {"status": Report.STATUS_REVIEWED, "resolution_notes": "Checked"},
        )

        self.assertTrue(
            ModerationLog.objects.filter(
                action=ModerationLog.ACTION_REPORT_STATUS_CHANGED,
                report=report,
            ).exists()
        )


class AbuseProtectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="abuse_user", password="pass12345")
        category = Category.objects.create(name="Writers", description="Writer profiles")
        self.person = Person.objects.create(
            name="Abuse Target",
            description="Testing anti spam",
            category=category,
            created_by=self.user,
        )

    def test_comment_honeypot_blocks_submission(self):
        self.client.login(username="abuse_user", password="pass12345")
        response = self.client.post(
            reverse("add_comment", kwargs={"slug": self.person.slug}),
            {"content": "Should be blocked", "website": "bot-filled"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 0)

    def test_comment_rate_limit_blocks_second_post(self):
        self.client.login(username="abuse_user", password="pass12345")
        with patch("core.views.COMMENT_RATE_LIMIT", (1, 300)):
            self.client.post(
                reverse("add_comment", kwargs={"slug": self.person.slug}),
                {"content": "First message"},
            )
            response = self.client.post(
                reverse("add_comment", kwargs={"slug": self.person.slug}),
                {"content": "Second message"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 1)

    def test_duplicate_rating_flood_blocked(self):
        self.client.login(username="abuse_user", password="pass12345")
        rate_url = reverse("rate_person", kwargs={"slug": self.person.slug})

        self.client.post(rate_url, {"score": "8"})
        response = self.client.post(rate_url, {"score": "8"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Rating.objects.filter(person=self.person, user=self.user).count(), 1)
        self.assertEqual(Rating.objects.get(person=self.person, user=self.user).score, 8)

    def test_hidden_person_not_accessible_for_regular_user(self):
        self.person.is_hidden = True
        self.person.hidden_reason = "Auto-hidden after moderation"
        self.person.save(update_fields=["is_hidden", "hidden_reason"])

        response = self.client.get(reverse("person_detail", kwargs={"slug": self.person.slug}))
        self.assertEqual(response.status_code, 404)


class ImageUploadHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="image_owner", password="pass12345")
        self.category = Category.objects.create(name="Image Cat", description="Image tests")

    def _person_form_data(self):
        return {
            "name": "Image Person",
            "description": "Image description",
            "category": self.category.pk,
            "tags": "one,two",
        }

    def test_person_form_rejects_oversized_image(self):
        oversized = SimpleUploadedFile(
            "oversized.jpg",
            b"a" * (PersonForm.MAX_IMAGE_BYTES + 1),
            content_type="image/jpeg",
        )
        form = PersonForm(data=self._person_form_data(), files={"image": oversized})

        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_person_form_rejects_invalid_image_payload(self):
        invalid_file = SimpleUploadedFile(
            "fake.jpg",
            b"not-a-real-image",
            content_type="image/jpeg",
        )
        form = PersonForm(data=self._person_form_data(), files={"image": invalid_file})

        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_person_form_rejects_unsupported_extension(self):
        valid_png_content = build_test_image(
            name="bad.bmp",
            image_format="PNG",
            content_type="image/png",
        ).read()
        invalid_extension_file = SimpleUploadedFile(
            "bad.bmp",
            valid_png_content,
            content_type="image/png",
        )
        form = PersonForm(
            data=self._person_form_data(),
            files={"image": invalid_extension_file},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_person_form_rejects_unsupported_image_format(self):
        bmp_bytes = build_test_image(
            name="avatar.png",
            image_format="BMP",
            content_type="image/png",
        ).read()
        invalid_type_file = SimpleUploadedFile(
            "avatar.png",
            bmp_bytes,
            content_type="image/png",
        )
        form = PersonForm(
            data=self._person_form_data(),
            files={"image": invalid_type_file},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_person_form_rejects_high_pixel_image(self):
        high_pixel_image = build_test_image(
            name="large.png",
            image_format="PNG",
            size=(40, 40),
            content_type="image/png",
        )
        with patch.object(PersonForm, "MAX_IMAGE_PIXELS", 100):
            form = PersonForm(
                data=self._person_form_data(),
                files={"image": high_pixel_image},
            )
            self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_compress_image_returns_original_file_when_invalid(self):
        invalid_file = SimpleUploadedFile(
            "broken.jpg",
            b"invalid",
            content_type="image/jpeg",
        )
        result = compress_image(invalid_file)

        self.assertIs(result, invalid_file)

    def test_compress_image_returns_jpeg_file_for_valid_input(self):
        valid_file = build_test_image(name="avatar.png", image_format="PNG", content_type="image/png")
        result = compress_image(valid_file)

        self.assertTrue(result.name.endswith(".jpg"))

    def test_compress_image_returns_original_for_high_pixel_image(self):
        large_file = build_test_image(
            name="very_large.png",
            image_format="PNG",
            size=(40, 40),
            content_type="image/png",
        )
        with self.settings(PERSONMETER_MAX_IMAGE_PIXELS=100):
            result = compress_image(large_file)

        self.assertIs(result, large_file)


class PersonSlugTests(TestCase):
    def test_turkish_name_generates_readable_slug(self):
        owner = User.objects.create_user(username="slug_owner", password="pass12345")
        category = Category.objects.create(name="Slug Cat", description="Slug tests")

        person = Person.objects.create(
            name="Kıvanç Tatlıtuğ",
            description="Slug profile",
            category=category,
            created_by=owner,
        )

        self.assertEqual(person.slug, "kivanc-tatlitug")


class SeedMockDataCommandTests(TestCase):
    def test_seed_mock_data_is_idempotent(self):
        out = StringIO()

        call_command("seed_mock_data", fan_count=12, stdout=out)

        celebrity_count = Person.objects.count()
        comment_count = Comment.objects.count()
        rating_count = Rating.objects.count()
        favorite_count = Favorite.objects.count()
        collection_count = Collection.objects.count()
        collection_item_count = CollectionItem.objects.count()

        self.assertGreaterEqual(celebrity_count, 50)
        self.assertEqual(User.objects.filter(username__startswith="demo_fan_").count(), 12)
        self.assertTrue(Person.objects.filter(name="Taylor Swift").exists())
        self.assertTrue(Person.objects.filter(ratings_count_cached__gt=0).exists())
        self.assertTrue(collection_count > 0)

        call_command("seed_mock_data", fan_count=12, stdout=out)

        self.assertEqual(Person.objects.count(), celebrity_count)
        self.assertEqual(Comment.objects.count(), comment_count)
        self.assertEqual(Rating.objects.count(), rating_count)
        self.assertEqual(Favorite.objects.count(), favorite_count)
        self.assertEqual(Collection.objects.count(), collection_count)
        self.assertEqual(CollectionItem.objects.count(), collection_item_count)
