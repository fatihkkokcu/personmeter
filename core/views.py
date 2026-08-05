from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg, Q, OuterRef, Subquery, FloatField, IntegerField
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from .models import Person, Rating, Comment, UserProfile, Favorite, Collection, CollectionItem, Category
from django.contrib.auth import login, logout
from .forms import UserRegistrationForm, AdvancedSearchForm, CollectionForm, CollectionItemForm, PersonForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView, UpdateView, ListView, CreateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse

# Akıştaki sıralama seçenekleri. Anahtarlar URL'de ?sort= olarak görünür.
FEED_SORTS = {
    'hot': ('-comment_count', '-rating_count'),
    'new': ('-created_at',),
    'top': ('-avg_rating', '-rating_count'),
    'discussed': ('-comment_count', '-created_at'),
}
DEFAULT_SORT = 'hot'


def annotate_people(queryset):
    """Listelerin ihtiyaç duyduğu sayaçları tek sorguda ekler.

    Sayaçlar alt sorgu olarak yazıldı: dört ayrı çoklu JOIN yapılsaydı satırlar
    kartezyen çarpıma girip hem sayılar bozulur hem sorgu şişerdi.
    """
    ratings = Rating.objects.filter(person=OuterRef('pk')).values('person')
    comments = Comment.objects.filter(person=OuterRef('pk')).values('person')
    favorites = Favorite.objects.filter(person=OuterRef('pk')).values('person')

    return queryset.select_related('category', 'created_by').annotate(
        avg_rating=Subquery(
            ratings.annotate(value=Avg('score')).values('value'),
            output_field=FloatField(),
        ),
        rating_count=Coalesce(
            Subquery(ratings.annotate(value=Count('id')).values('value'), output_field=IntegerField()),
            0,
        ),
        comment_count=Coalesce(
            Subquery(comments.annotate(value=Count('id')).values('value'), output_field=IntegerField()),
            0,
        ),
        favorite_count=Coalesce(
            Subquery(favorites.annotate(value=Count('id')).values('value'), output_field=IntegerField()),
            0,
        ),
    )


def mark_favorites(request, people):
    """Oturum açmış kullanıcının favorilerini işaretler (tek sorgu)."""
    if not request.user.is_authenticated:
        return people

    favorite_ids = set(
        request.user.profile.favorite_set.values_list('person_id', flat=True)
    )
    for person in people:
        person.is_favorited_by_user = person.id in favorite_ids
    return people


def get_view_mode(request):
    """Liste / kart tercihi. URL'den gelirse oturuma yazılır ve kalıcı olur."""
    mode = request.GET.get('view')
    if mode in ('list', 'card'):
        request.session['person_view_mode'] = mode
        return mode
    return request.session.get('person_view_mode', 'list')


def sidebar_categories():
    return Category.objects.annotate(
        person_count=Count('persons')
    ).filter(person_count__gt=0).order_by('name')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('home')

def home(request):
    category_id = request.GET.get('category')
    selected_category = None

    people = annotate_people(Person.objects.all())
    if category_id:
        try:
            selected_category = int(category_id)
            people = people.filter(category_id=selected_category)
        except (ValueError, TypeError):
            pass

    sort = request.GET.get('sort', DEFAULT_SORT)
    if sort not in FEED_SORTS:
        sort = DEFAULT_SORT
    people = people.order_by(*FEED_SORTS[sort])

    paginator = Paginator(people, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    mark_favorites(request, page_obj.object_list)

    # Sağ ray: en yüksek puanlılar, en az 5 oy almış olanlar arasından.
    highest_rated = annotate_people(Person.objects.all()).filter(
        rating_count__gte=5
    ).order_by('-avg_rating')[:5]

    context = {
        'page_obj': page_obj,
        'categories': sidebar_categories(),
        'selected_category': selected_category,
        'sort': sort,
        'view_mode': get_view_mode(request),
        'highest_rated': highest_rated,
        'total_people': Person.objects.count(),
        'total_comments': Comment.objects.count(),
        'total_ratings': Rating.objects.count(),
        'total_members': UserProfile.objects.count(),
    }
    return render(request, 'core/home.html', context)

def person_list(request):
    people = annotate_people(Person.objects.all()).order_by('-created_at')

    paginator = Paginator(people, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    mark_favorites(request, page_obj.object_list)

    return render(request, 'core/person_list.html', {
        'page_obj': page_obj,
        'view_mode': get_view_mode(request),
        'categories': sidebar_categories(),
    })

def person_detail(request, pk):
    person = get_object_or_404(
        Person.objects.select_related('category', 'created_by'), pk=pk
    )

    user_rating = None
    is_favorited = False
    if request.user.is_authenticated:
        user_rating = Rating.objects.filter(person=person, user=request.user).first()
        is_favorited = Favorite.objects.filter(
            user_profile=request.user.profile, person=person
        ).exists()

    comments = person.comments.select_related('user', 'user__profile').order_by('-created_at')
    paginator = Paginator(comments, 20)
    comments_page = paginator.get_page(request.GET.get('page'))

    stats = person.get_stats_summary()
    distribution = person.get_rating_distribution()

    # Dağılımı 10'dan 1'e doğru, eksik puanlar sıfır olacak şekilde düzleştir.
    rating_rows = [
        {
            'score': score,
            'count': distribution.get(score, {}).get('count', 0),
            'percentage': distribution.get(score, {}).get('percentage', 0),
        }
        for score in range(10, 0, -1)
    ]

    context = {
        'person': person,
        'user_rating': user_rating,
        'is_favorited': is_favorited,
        'rating_choices': range(10, 0, -1),
        'comments_page': comments_page,
        'stats': stats,
        'rating_rows': rating_rows,
        'rating_trend': person.get_rating_trend(days=30),
        'demographics': person.get_demographics(),
        'similar_persons': person.get_similar_persons(limit=6),
    }
    return render(request, 'core/person_detail.html', context)

@login_required
def rate_person(request, pk):
    if request.method == 'POST':
        score = request.POST.get('score')
        if score and score.isdigit() and 1 <= int(score) <= 10:
            person = get_object_or_404(Person, pk=pk)
            rating, created = Rating.objects.update_or_create(
                person=person,
                user=request.user,
                defaults={'score': score}
            )
            messages.success(request, 'Rating submitted successfully!')
        else:
            messages.error(request, 'Invalid rating value!')
    return redirect('person_detail', pk=pk)

@login_required
def add_comment(request, pk):
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            person = get_object_or_404(Person, pk=pk)
            Comment.objects.create(
                person=person,
                user=request.user,
                content=content
            )
            messages.success(request, 'Comment added successfully!')
        else:
            messages.error(request, 'Comment cannot be empty!')
    return redirect('person_detail', pk=pk)

def top_rated(request):
    persons = annotate_people(Person.objects.all()).filter(
        rating_count__gt=100
    ).order_by('-avg_rating')[:250]

    return render(request, 'core/top_rated.html', {'persons': persons})

def search(request):
    query = request.GET.get('q', '')
    form = AdvancedSearchForm(request.GET)
    persons = annotate_people(Person.objects.all())

    if query:
        persons = persons.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )
    
    if form.is_valid():
        # Handle category filter
        category = form.cleaned_data.get('category')
        if category:
            persons = persons.filter(category=category)
            
        # Handle tags filter
        tags = form.cleaned_data.get('tags')
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            for tag in tag_list:
                persons = persons.filter(tags__icontains=tag)
        
        # Handle rating filters
        min_rating = form.cleaned_data.get('min_rating')
        max_rating = form.cleaned_data.get('max_rating')
        min_ratings = form.cleaned_data.get('min_ratings')
        
        if min_rating is not None:
            persons = persons.filter(avg_rating__gte=min_rating)
        if max_rating is not None:
            persons = persons.filter(avg_rating__lte=max_rating)
        if min_ratings is not None:
            persons = persons.filter(rating_count__gte=min_ratings)
        # Handle minimum ratings count
        min_ratings_count = form.cleaned_data.get('min_ratings_count')
        if min_ratings_count is not None:
            persons = persons.filter(rating_count__gte=min_ratings_count)
    # Order results
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by in ['-created_at', 'created_at', 'name', '-name', '-avg_rating', 'avg_rating', '-rating_count']:
        persons = persons.order_by(sort_by)
    
    paginator = Paginator(persons, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    mark_favorites(request, page_obj.object_list)

    context = {
        'query': query,
        'form': form,
        'page_obj': page_obj,
        'sort_by': sort_by,
        'view_mode': get_view_mode(request),
    }
    return render(request, 'core/search.html', context)

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful! Welcome to Personmeter!')
            return redirect('home')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'core/register.html', {'form': form})

class ProfileView(LoginRequiredMixin, DetailView):
    model = UserProfile
    template_name = 'core/profile.html'
    context_object_name = 'profile'

    def get_object(self):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ratings'] = self.request.user.rating_set.select_related('person').order_by('-created_at')[:10]
        context['comments'] = self.request.user.comment_set.select_related('person').order_by('-created_at')[:10]
        context['favorites'] = self.request.user.profile.favorite_set.select_related('person').order_by('-created_at')
        return context

class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    template_name = 'core/profile_edit.html'
    fields = ['bio', 'location', 'birth_date']
    success_url = reverse_lazy('profile')

    def get_object(self):
        return self.request.user.profile

class UserProfileView(DetailView):
    model = UserProfile
    template_name = 'core/profile.html'
    context_object_name = 'profile'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object().user
        context['ratings'] = user.rating_set.select_related('person').order_by('-created_at')[:10]
        context['comments'] = user.comment_set.select_related('person').order_by('-created_at')[:10]
        context['favorites'] = user.profile.favorite_set.select_related('person').order_by('-created_at')
        return context

@login_required
def toggle_favorite(request, pk):
    if request.method == 'POST':
        person = get_object_or_404(Person, pk=pk)
        favorite, created = Favorite.objects.get_or_create(
            user_profile=request.user.profile,
            person=person
        )
        
        if not created:
            favorite.delete()
            is_favorite = False
        else:
            is_favorite = True
        
        return JsonResponse({
            'is_favorite': is_favorite,
            'total_favorites': person.favorited_by.count()
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

class CollectionListView(ListView):
    model = Collection
    template_name = 'core/collection_list.html'
    context_object_name = 'collections'
    paginate_by = 12

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Collection.objects.filter(
                Q(is_public=True) | Q(created_by=self.request.user)
            ).distinct()
        return Collection.objects.filter(is_public=True)

class UserCollectionListView(LoginRequiredMixin, ListView):
    model = Collection
    template_name = 'core/user_collections.html'
    context_object_name = 'collections'
    paginate_by = 12

    def get_queryset(self):
        return Collection.objects.filter(created_by=self.request.user)

class CollectionDetailView(DetailView):
    model = Collection
    template_name = 'core/collection_detail.html'

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Collection.objects.filter(
                Q(is_public=True) | Q(created_by=self.request.user)
            )
        return Collection.objects.filter(is_public=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        collection = self.get_object()
        context['items'] = collection.collectionitem_set.select_related('person').all()
        return context

class CollectionCreateView(LoginRequiredMixin, CreateView):
    model = Collection
    form_class = CollectionForm
    template_name = 'core/collection_form.html'
    success_url = reverse_lazy('user_collections')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class CollectionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Collection
    form_class = CollectionForm
    template_name = 'core/collection_form.html'

    def test_func(self):
        collection = self.get_object()
        return collection.created_by == self.request.user

    def get_success_url(self):
        return reverse_lazy('collection_detail', kwargs={'pk': self.object.pk})

class CollectionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Collection
    template_name = 'core/collection_confirm_delete.html'
    success_url = reverse_lazy('user_collections')

    def test_func(self):
        collection = self.get_object()
        return collection.created_by == self.request.user

@login_required
def add_to_collection(request, person_pk):
    person = get_object_or_404(Person, pk=person_pk)
    
    if request.method == 'POST':
        collection_id = request.POST.get('collection')
        if collection_id:
            collection = get_object_or_404(Collection, pk=collection_id, created_by=request.user)
            CollectionItem.objects.get_or_create(
                collection=collection,
                person=person,
                defaults={'order': collection.collectionitem_set.count()}
            )
            messages.success(request, f'Added {person.name} to {collection.title}')
        else:
            messages.error(request, 'Please select a collection')
    
    return redirect('person_detail', pk=person_pk)

@login_required
def remove_from_collection(request, collection_pk, person_pk):
    collection = get_object_or_404(Collection, pk=collection_pk, created_by=request.user)
    CollectionItem.objects.filter(collection=collection, person_id=person_pk).delete()
    messages.success(request, 'Person removed from collection')
    return redirect('collection_detail', pk=collection_pk)

class PersonCreateView(LoginRequiredMixin, CreateView):
    model = Person
    form_class = PersonForm
    template_name = 'core/person_form.html'
    success_url = reverse_lazy('person_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Person added successfully!')
        return super().form_valid(form)

class PersonUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Person
    form_class = PersonForm
    template_name = 'core/person_form.html'

    def test_func(self):
        person = self.get_object()
        return self.request.user.is_superuser or person.created_by == self.request.user

    def get_success_url(self):
        return reverse_lazy('person_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, 'Person updated successfully!')
        return super().form_valid(form)

class CategoryListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Category
    template_name = 'core/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for category in context['categories']:
            category.person_count = category.persons.count()
        return context

class CategoryCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Category
    template_name = 'core/category_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('category_list')

    def test_func(self):
        return self.request.user.is_staff

    def form_valid(self, form):
        messages.success(self.request, 'Category created successfully!')
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Category
    template_name = 'core/category_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('category_list')

    def test_func(self):
        return self.request.user.is_staff

    def form_valid(self, form):
        messages.success(self.request, 'Category updated successfully!')
        return super().form_valid(form)

class CategoryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Category
    template_name = 'core/category_confirm_delete.html'
    success_url = reverse_lazy('category_list')

    def test_func(self):
        return self.request.user.is_staff

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Category deleted successfully!')
        return super().delete(request, *args, **kwargs)
