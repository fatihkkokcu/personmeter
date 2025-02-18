from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class PersonSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return ['person_list']

    def location(self, item):
        return reverse(item)

class CollectionSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7

    def items(self):
        return ['collection_list']

    def location(self, item):
        return reverse(item)

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = "daily"

    def items(self):
        return ['home', 'search', 'top_rated']

    def location(self, item):
        return reverse(item) 