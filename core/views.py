from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.core.paginator import Paginator
from .models import Person, Rating, Comment, UserProfile, Favorite, Collection, CollectionItem, Category
from django.contrib.auth import login, logout
from .forms import UserRegistrationForm, AdvancedSearchForm, CollectionForm, CollectionItemForm, PersonForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView, UpdateView, ListView, CreateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('home')

def home(request):
    # Get selected category
    category_id = request.GET.get('category')
    selected_category = None
    
    # Base querysets
    persons_query = Person.objects
    if category_id:
        try:
            selected_category = int(category_id)
            persons_query = persons_query.filter(category_id=selected_category)
        except (ValueError, TypeError):
            pass
    
    # Get trending persons
    trending_persons = persons_query.annotate(
        rating_count=Count('ratings'),
        avg_rating=Avg('ratings__score')
    ).filter(rating_count__gt=0).order_by('-rating_count')[:6]
    
    # Get recent persons
    recent_persons = persons_query.annotate(
        rating_count=Count('ratings'),
        avg_rating=Avg('ratings__score')
    ).order_by('-created_at')[:6]
    
    # Get top rated persons
    top_rated = persons_query.annotate(
        rating_count=Count('ratings'),
        avg_rating=Avg('ratings__score')
    ).filter(rating_count__gt=10).order_by('-avg_rating')[:6]
    
    # Get all categories
    categories = Category.objects.annotate(
        person_count=Count('persons')
    ).filter(person_count__gt=0).order_by('name')
    
    # Add favorite information for authenticated users
    if request.user.is_authenticated:
        user_favorites = set(request.user.profile.favorite_set.values_list('person_id', flat=True))
        for persons in [trending_persons, recent_persons, top_rated]:
            for person in persons:
                person.is_favorited_by_user = person.id in user_favorites
    
    context = {
        'trending_persons': trending_persons,
        'recent_persons': recent_persons,
        'top_rated': top_rated,
        'categories': categories,
        'selected_category': selected_category,
    }
    return render(request, 'core/home.html', context)

def person_list(request):
    persons = Person.objects.annotate(
        rating_count=Count('ratings'),
        avg_rating=Avg('ratings__score')
    ).order_by('-created_at')
    
    # Add favorite information for authenticated users
    if request.user.is_authenticated:
        user_favorites = set(request.user.profile.favorite_set.values_list('person_id', flat=True))
        for person in persons:
            person.is_favorited_by_user = person.id in user_favorites
    
    paginator = Paginator(persons, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'core/person_list.html', {'page_obj': page_obj})

def person_detail(request, pk):
    person = get_object_or_404(Person, pk=pk)
    user_rating = None
    if request.user.is_authenticated:
        user_rating = Rating.objects.filter(person=person, user=request.user).first()
    
    comments = person.comments.order_by('-created_at')
    paginator = Paginator(comments, 10)
    page_number = request.GET.get('page')
    comments_page = paginator.get_page(page_number)
    
    # Get statistics
    stats = person.get_stats_summary()
    rating_distribution = person.get_rating_distribution()
    rating_trend = person.get_rating_trend(days=30)
    demographics = person.get_demographics()
    similar_persons = person.get_similar_persons(limit=6)
    
    context = {
        'person': person,
        'user_rating': user_rating,
        'comments_page': comments_page,
        'stats': stats,
        'rating_distribution': rating_distribution,
        'rating_trend': rating_trend,
        'demographics': demographics,
        'similar_persons': similar_persons,
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
    persons = Person.objects.annotate(
        rating_count=Count('ratings'),
        avg_rating=Avg('ratings__score')
    ).filter(rating_count__gt=100).order_by('-avg_rating')[:250]
    
    return render(request, 'core/top_rated.html', {'persons': persons})

def search(request):
    query = request.GET.get('q', '')
    form = AdvancedSearchForm(request.GET)
    persons = Person.objects.annotate(
        rating_count=Count('ratings'),
        avg_rating=Avg('ratings__score')
    )
    
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
    
    # Add favorite information for authenticated users
    if request.user.is_authenticated:
        user_favorites = set(request.user.profile.favorite_set.values_list('person_id', flat=True))
        for person in persons:
            person.is_favorited_by_user = person.id in user_favorites
    
    # Add pagination
    paginator = Paginator(persons, 12)  # Show 12 persons per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'query': query,
        'form': form,
        'page_obj': page_obj,
        'sort_by': sort_by
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
