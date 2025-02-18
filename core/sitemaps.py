from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Person, Collection

class PersonSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Person.objects.all()

    def lastmod(self, obj):
        return obj.updated_at

class CollectionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Collection.objects.filter(is_public=True)

    def lastmod(self, obj):
        return obj.updated_at

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = "daily"

    def items(self):
        return ['home', 'search', 'top_rated']

    def location(self, item):
        return reverse(item) 