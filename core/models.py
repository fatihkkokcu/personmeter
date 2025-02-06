from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg, Count, F, Q, ExpressionWrapper, fields
from django.utils import timezone
from datetime import timedelta
from PIL import Image
import os

# Create your models here.

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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        if self.image:
            from django.core.files.storage import default_storage
            from django.core.files import File
            
            # Open the image using a temporary file
            with self.image.open('rb') as img_file:
                img = Image.open(img_file)
                
                # Convert RGBA/LA to RGB if necessary
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, 'WHITE')
                    background.paste(img, mask=img.split()[-1])
                    img = background
                
                # Save the processed image to a temporary file
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                try:
                    img.save(temp_file.name, 'JPEG', quality=100)
                    
                    # Save the processed image back to storage
                    with open(temp_file.name, 'rb') as processed_file:
                        self.image.save(
                            self.image.name,
                            File(processed_file),
                            save=False
                        )
                finally:
                    temp_file.close()
                    import os
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)

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

    def __str__(self):
        return self.name

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

    def __str__(self):
        return f"Comment by {self.user.username} on {self.person.name}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    favorite_persons = models.ManyToManyField(Person, through='Favorite', related_name='favorited_by')
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
