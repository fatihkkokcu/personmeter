from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg, Count, F, Q, ExpressionWrapper, fields
from django.utils import timezone
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from datetime import timedelta
import logging
from PIL import Image, UnidentifiedImageError
import os
from .utils import get_s3_presigned_url
from io import BytesIO
from django.core.files import File

# Create your models here.

logger = logging.getLogger(__name__)

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name

class Person(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='person_images/', blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='persons')
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_hidden = models.BooleanField(default=False)
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=255, blank=True)

    def average_rating(self):
        return self.ratings.aggregate(Avg('score'))['score__avg'] or 0.0

    def total_ratings(self):
        return self.ratings.count()

    def get_tags_list(self):
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    def get_rating_distribution(self):
        distribution = self.ratings.values('score').annotate(
            count=Count('id')
        ).order_by('score')
        
        total = self.total_ratings()
        if total > 0:
            return {
                item['score']: {
                    'count': item['count'],
                    'percentage': (item['count'] / total) * 100
                }
                for item in distribution
            }
        return {}

    def get_rating_trend(self, days=30):
        start_date = timezone.now() - timedelta(days=days)
        ratings = self.ratings.filter(
            created_at__gte=start_date
        ).values('created_at__date').annotate(
            avg_score=Avg('score'),
            count=Count('id')
        ).order_by('created_at__date')
        return list(ratings)

    def get_demographics(self):
        return {
            'age_groups': self.ratings.exclude(
                user__profile__birth_date__isnull=True
            ).annotate(
                age=ExpressionWrapper(
                    (timezone.now().date() - F('user__profile__birth_date')),
                    output_field=fields.DurationField()
                )
            ).values('age').annotate(
                count=Count('id'),
                avg_rating=Avg('score')
            ),
            'locations': self.ratings.exclude(
                user__profile__location=''
            ).values(
                'user__profile__location'
            ).annotate(
                count=Count('id'),
                avg_rating=Avg('score')
            ).order_by('-count')[:10]
        }

    def get_similar_persons(self, limit=5):
        """Find similar persons based on common raters and ratings"""
        person_ratings = self.ratings.values_list('user_id', 'score')
        person_raters = set(uid for uid, _ in person_ratings)
        
        # Get persons rated by the same users
        similar_persons = Person.objects.exclude(pk=self.pk).filter(
            ratings__user_id__in=person_raters
        ).annotate(
            common_raters=Count('ratings__user_id', filter=Q(ratings__user_id__in=person_raters)),
            avg_rating=Avg('ratings__score')
        ).filter(
            common_raters__gt=0
        ).order_by('-common_raters', '-avg_rating')[:limit]
        
        return similar_persons

    def get_stats_summary(self):
        """Get a comprehensive statistics summary"""
        return {
            'total_ratings': self.total_ratings(),
            'average_rating': self.average_rating(),
            'rating_distribution': self.get_rating_distribution(),
            'total_comments': self.comments.count(),
            'total_favorites': self.favorited_by.count(),
            'total_collections': self.collections.filter(is_public=True).count(),
            'recent_activity': {
                'ratings': self.ratings.order_by('-created_at')[:5],
                'comments': self.comments.order_by('-created_at')[:5],
                'collections': self.collections.filter(is_public=True).order_by('-created_at')[:5]
            }
        }

    def get_image_url(self):
        """Get a presigned URL for the image using boto3"""
        if self.image:
            return get_s3_presigned_url(self.image.name)
        return None

    def hide(self, reason):
        self.is_hidden = True
        self.hidden_reason = reason
        self.hidden_at = timezone.now()
        self.save(update_fields=["is_hidden", "hidden_reason", "hidden_at"])

    def unhide(self):
        self.is_hidden = False
        self.hidden_reason = ""
        self.hidden_at = None
        self.save(update_fields=["is_hidden", "hidden_reason", "hidden_at"])

    def __str__(self):
        return self.name

@receiver(post_delete, sender=Person)
def delete_image_file(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(False)

def compress_image(image):
    """Compress the image while maintaining aspect ratio and quality"""
    if not image:
        return None

    try:
        img = Image.open(image)
    except (UnidentifiedImageError, OSError, ValueError):
        logger.warning("Skipping compression for invalid image upload: %s", image.name)
        if hasattr(image, "seek"):
            image.seek(0)
        return image
    except Exception:
        logger.exception("Unexpected image open error for file: %s", image.name)
        if hasattr(image, "seek"):
            image.seek(0)
        return image

    try:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")

        max_width = 800
        max_height = 800
        ratio = min(1.0, max_width / img.width, max_height / img.height)
        new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

        output = BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)
        output.seek(0)

        base_name, _ = os.path.splitext(image.name)
        return File(output, name=f"{base_name}.jpg")
    except (OSError, ValueError):
        logger.warning("Skipping compression for problematic image: %s", image.name)
        if hasattr(image, "seek"):
            image.seek(0)
        return image
    except Exception:
        logger.exception("Unexpected image compression error for file: %s", image.name)
        if hasattr(image, "seek"):
            image.seek(0)
        return image

@receiver(pre_save, sender=Person)
def delete_old_image(sender, instance, **kwargs):
    if instance.pk:  # Only for existing objects
        try:
            old_instance = Person.objects.get(pk=instance.pk)
            if old_instance.image and old_instance.image != instance.image:
                old_instance.image.delete(False)
        except Person.DoesNotExist:
            pass
    
    # Compress new image if it exists
    if instance.image:
        instance.image = compress_image(instance.image)

class Rating(models.Model):
    person = models.ForeignKey(Person, related_name='ratings', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['person', 'user']

    def __str__(self):
        return f"{self.user.username}'s rating for {self.person.name}"

class Comment(models.Model):
    person = models.ForeignKey(Person, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_hidden = models.BooleanField(default=False)
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.person.name}"

    def hide(self, reason):
        self.is_hidden = True
        self.hidden_reason = reason
        self.hidden_at = timezone.now()
        self.save(update_fields=["is_hidden", "hidden_reason", "hidden_at"])

    def unhide(self):
        self.is_hidden = False
        self.hidden_reason = ""
        self.hidden_at = None
        self.save(update_fields=["is_hidden", "hidden_reason", "hidden_at"])


class Report(models.Model):
    REASON_SPAM = "spam"
    REASON_HARASSMENT = "harassment"
    REASON_HATE = "hate_speech"
    REASON_VIOLENCE = "violence"
    REASON_MISINFORMATION = "misinformation"
    REASON_OTHER = "other"

    REASON_CHOICES = [
        (REASON_SPAM, "Spam or scam"),
        (REASON_HARASSMENT, "Harassment"),
        (REASON_HATE, "Hate speech"),
        (REASON_VIOLENCE, "Violence or threat"),
        (REASON_MISINFORMATION, "Misinformation"),
        (REASON_OTHER, "Other"),
    ]

    STATUS_PENDING = "pending"
    STATUS_REVIEWED = "reviewed"
    STATUS_DISMISSED = "dismissed"
    STATUS_ACTIONED = "actioned"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_REVIEWED, "Reviewed"),
        (STATUS_DISMISSED, "Dismissed"),
        (STATUS_ACTIONED, "Actioned"),
    ]

    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="submitted_reports",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
    )
    reason = models.CharField(max_length=32, choices=REASON_CHOICES)
    details = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(person__isnull=False) & Q(comment__isnull=True))
                    | (Q(person__isnull=True) & Q(comment__isnull=False))
                ),
                name="report_single_target",
            ),
            models.UniqueConstraint(
                fields=["reporter", "person"],
                condition=Q(person__isnull=False),
                name="unique_person_report_per_user",
            ),
            models.UniqueConstraint(
                fields=["reporter", "comment"],
                condition=Q(comment__isnull=False),
                name="unique_comment_report_per_user",
            ),
        ]

    @property
    def target_type(self):
        return "comment" if self.comment_id else "person"

    @property
    def target_display(self):
        if self.comment_id:
            return f"Comment #{self.comment_id}"
        if self.person_id:
            return self.person.name
        return "-"

    def clean(self):
        if bool(self.person_id) == bool(self.comment_id):
            raise ValidationError("Report must target either a person or a comment.")

    def __str__(self):
        return f"Report #{self.pk} by {self.reporter.username}"


class ModerationLog(models.Model):
    ACTION_REPORT_STATUS_CHANGED = "report_status_changed"
    ACTION_TARGET_AUTO_HIDDEN = "target_auto_hidden"
    ACTION_TARGET_UNHIDDEN = "target_unhidden"
    ACTION_TARGET_HIDDEN_ACTIONED = "target_hidden_actioned"
    ACTION_SANCTION_WARN = "sanction_warn"
    ACTION_SANCTION_MUTE = "sanction_mute"
    ACTION_SANCTION_SUSPEND = "sanction_suspend"
    ACTION_SANCTION_BAN = "sanction_ban"

    ACTION_CHOICES = [
        (ACTION_REPORT_STATUS_CHANGED, "Report status changed"),
        (ACTION_TARGET_AUTO_HIDDEN, "Target auto hidden"),
        (ACTION_TARGET_UNHIDDEN, "Target unhidden"),
        (ACTION_TARGET_HIDDEN_ACTIONED, "Target hidden by moderation"),
        (ACTION_SANCTION_WARN, "User warned"),
        (ACTION_SANCTION_MUTE, "User muted"),
        (ACTION_SANCTION_SUSPEND, "User suspended"),
        (ACTION_SANCTION_BAN, "User banned"),
    ]

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_logs",
    )
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    report = models.ForeignKey(
        Report,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_logs",
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_logs",
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_actions_received",
    )
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} #{self.pk}"


class UserProfile(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_WARNED = "warned"
    STATUS_MUTED = "muted"
    STATUS_SUSPENDED = "suspended"
    STATUS_BANNED = "banned"

    MODERATION_STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_WARNED, "Warned"),
        (STATUS_MUTED, "Muted"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_BANNED, "Banned"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    favorite_persons = models.ManyToManyField(Person, through='Favorite', related_name='favorited_by')
    moderation_status = models.CharField(
        max_length=16,
        choices=MODERATION_STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    warning_count = models.PositiveIntegerField(default=0)
    strike_count = models.PositiveIntegerField(default=0)
    muted_until = models.DateTimeField(null=True, blank=True)
    suspended_until = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    def total_ratings(self):
        return self.user.rating_set.count()

    def recent_ratings(self):
        return self.user.rating_set.order_by('-created_at')[:5]

    def recent_comments(self):
        return self.user.comment_set.order_by('-created_at')[:5]

    def normalize_moderation_state(self):
        now = timezone.now()
        changed = False

        if self.moderation_status == self.STATUS_MUTED and self.muted_until and self.muted_until <= now:
            self.moderation_status = self.STATUS_ACTIVE
            self.muted_until = None
            changed = True

        if self.moderation_status == self.STATUS_SUSPENDED and self.suspended_until and self.suspended_until <= now:
            self.moderation_status = self.STATUS_ACTIVE
            self.suspended_until = None
            changed = True

        if changed:
            self.save(update_fields=["moderation_status", "muted_until", "suspended_until"])

    def is_banned(self):
        return self.moderation_status == self.STATUS_BANNED

    def is_suspended(self):
        self.normalize_moderation_state()
        return self.moderation_status == self.STATUS_SUSPENDED

    def is_muted(self):
        self.normalize_moderation_state()
        return self.moderation_status == self.STATUS_MUTED

class Favorite(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user_profile', 'person']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_profile.user.username}'s favorite: {self.person.name}"

class Collection(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collections')
    persons = models.ManyToManyField(Person, through='CollectionItem', related_name='collections')
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def total_items(self):
        return self.persons.count()

    def total_ratings(self):
        return Rating.objects.filter(person__in=self.persons.all()).count()

    def average_rating(self):
        return Rating.objects.filter(person__in=self.persons.all()).aggregate(Avg('score'))['score__avg'] or 0.0

class CollectionItem(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        unique_together = ['collection', 'person']

    def __str__(self):
        return f"{self.person.name} in {self.collection.title}"
