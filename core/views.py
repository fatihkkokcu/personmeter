from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import Http404
from django.utils import timezone

from .abuse import consume_rate_limit, is_flooding
from .models import (
    Category,
    Collection,
    CollectionItem,
    Comment,
    Favorite,
    ModerationLog,
    Person,
    Rating,
    Report,
    UserProfile,
)
from django.contrib.auth import login, logout
from .forms import UserRegistrationForm, AdvancedSearchForm, CollectionForm, CollectionItemForm, PersonForm, ReportForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView, UpdateView, ListView, CreateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse


RATING_RATE_LIMIT = (25, 300)
COMMENT_RATE_LIMIT = (10, 300)
REPORT_RATE_LIMIT = (10, 3600)
COMMENT_FLOOD_SECONDS = 30
RATING_DUPLICATE_FLOOD_SECONDS = 10
PERSON_AUTO_HIDE_THRESHOLD = 5
COMMENT_AUTO_HIDE_THRESHOLD = 3
MUTE_DURATION = timedelta(hours=24)
SUSPEND_DURATION = timedelta(days=7)


def _is_staff_user(request):
    return request.user.is_authenticated and request.user.is_staff


def _visible_persons_queryset(request):
    queryset = Person.objects
    if not _is_staff_user(request):
        queryset = queryset.filter(is_hidden=False)
    return queryset


def _visible_comments_queryset(request, person):
    queryset = person.comments
    if not _is_staff_user(request):
        queryset = queryset.filter(is_hidden=False)
    return queryset


def _get_person_by_slug_or_404(slug):
    return get_object_or_404(
        Person.objects.select_related("category", "created_by"),
        slug=slug,
    )


def person_detail_legacy_redirect(request, pk):
    person = get_object_or_404(Person, pk=pk)
    return redirect(person, permanent=True)


def _person_base_queryset(request):
    return _visible_persons_queryset(request).select_related("category", "created_by")


def _get_user_collections(request):
    if not request.user.is_authenticated:
        return []

    cached_collections = getattr(request, "_personmeter_user_collections", None)
    if cached_collections is None:
        cached_collections = list(
            request.user.collections.only("id", "title").order_by("title")
        )
        request._personmeter_user_collections = cached_collections
    return cached_collections


def _attach_person_rating_aliases(persons):
    persons = list(persons)
    for person in persons:
        person.avg_rating = person.ratings_average_cached
        person.rating_count = person.ratings_count_cached
        person.detail_url = person.get_absolute_url()
    return persons


def _decorate_person_cards(request, persons):
    persons = _attach_person_rating_aliases(persons)
    if not persons:
        return persons

    person_ids = [person.pk for person in persons]
    favorite_counts = {}
    favorited_ids = set()

    if request.user.is_authenticated:
        favorite_counts = {
            row["person_id"]: row["total"]
            for row in Favorite.objects.filter(person_id__in=person_ids)
            .values("person_id")
            .annotate(total=Count("id"))
        }
        favorited_ids = set(
            Favorite.objects.filter(
                user_profile=request.user.profile,
                person_id__in=person_ids,
            ).values_list("person_id", flat=True)
        )

    for person in persons:
        person.favorite_count = favorite_counts.get(person.pk, 0)
        person.is_favorited_by_user = person.pk in favorited_ids
        person.image_url = person.get_image_url()
        person.favorite_url = reverse("toggle_favorite", kwargs={"slug": person.slug})

    return persons


def _create_moderation_log(
    action,
    actor=None,
    report=None,
    person=None,
    comment=None,
    target_user=None,
    details="",
):
    ModerationLog.objects.create(
        action=action,
        actor=actor,
        report=report,
        person=person,
        comment=comment,
        target_user=target_user,
        details=details,
    )


def _get_report_target(report):
    if report.person_id:
        return report.person, "person"
    return report.comment, "comment"


def _get_target_owner(report):
    if report.comment_id:
        return report.comment.user
    if report.person_id:
        return report.person.created_by
    return None


def _pending_reports_count(report):
    if report.person_id:
        return Report.objects.filter(
            person=report.person,
            status=Report.STATUS_PENDING,
        ).count()
    return Report.objects.filter(
        comment=report.comment,
        status=Report.STATUS_PENDING,
    ).count()


def _has_actioned_report(report):
    if report.person_id:
        return Report.objects.filter(
            person=report.person,
            status=Report.STATUS_ACTIONED,
        ).exists()
    return Report.objects.filter(
        comment=report.comment,
        status=Report.STATUS_ACTIONED,
    ).exists()


def _auto_hide_threshold(report):
    return PERSON_AUTO_HIDE_THRESHOLD if report.person_id else COMMENT_AUTO_HIDE_THRESHOLD


def _reconcile_target_visibility(report, actor=None):
    target, target_type = _get_report_target(report)
    if target is None:
        return

    pending_count = _pending_reports_count(report)
    actioned_exists = _has_actioned_report(report)
    threshold = _auto_hide_threshold(report)

    if actioned_exists:
        if not target.is_hidden or target.hidden_reason != "Hidden by moderation action":
            target.hide("Hidden by moderation action")
            _create_moderation_log(
                action=ModerationLog.ACTION_TARGET_HIDDEN_ACTIONED,
                actor=actor,
                report=report,
                person=target if target_type == "person" else None,
                comment=target if target_type == "comment" else None,
                target_user=_get_target_owner(report),
                details="Target hidden due to an actioned report.",
            )
        return

    if pending_count >= threshold:
        if not target.is_hidden:
            reason = f"Auto-hidden after {pending_count} pending reports"
            target.hide(reason)
            _create_moderation_log(
                action=ModerationLog.ACTION_TARGET_AUTO_HIDDEN,
                actor=actor,
                report=report,
                person=target if target_type == "person" else None,
                comment=target if target_type == "comment" else None,
                target_user=_get_target_owner(report),
                details=reason,
            )
        return

    if target.is_hidden and target.hidden_reason.startswith("Auto-hidden"):
        target.unhide()
        _create_moderation_log(
            action=ModerationLog.ACTION_TARGET_UNHIDDEN,
            actor=actor,
            report=report,
            person=target if target_type == "person" else None,
            comment=target if target_type == "comment" else None,
            target_user=_get_target_owner(report),
            details="Target unhidden after pending reports dropped below threshold.",
        )


def _apply_escalating_sanction(report, actor):
    target_user = _get_target_owner(report)
    if not target_user:
        return

    profile = target_user.profile
    profile.normalize_moderation_state()

    if profile.moderation_status == UserProfile.STATUS_BANNED:
        return

    profile.strike_count += 1
    now = timezone.now()
    log_action = None
    detail = ""

    if profile.strike_count == 1:
        profile.warning_count += 1
        profile.moderation_status = UserProfile.STATUS_WARNED
        detail = "Automatic warning after first actioned report."
        log_action = ModerationLog.ACTION_SANCTION_WARN
    elif profile.strike_count == 2:
        profile.moderation_status = UserProfile.STATUS_MUTED
        profile.muted_until = now + MUTE_DURATION
        detail = "Automatic mute after repeated violations."
        log_action = ModerationLog.ACTION_SANCTION_MUTE
    elif profile.strike_count == 3:
        profile.moderation_status = UserProfile.STATUS_SUSPENDED
        profile.suspended_until = now + SUSPEND_DURATION
        detail = "Automatic suspension after repeated violations."
        log_action = ModerationLog.ACTION_SANCTION_SUSPEND
    else:
        profile.moderation_status = UserProfile.STATUS_BANNED
        profile.banned_at = now
        profile.muted_until = None
        profile.suspended_until = None
        detail = "Automatic permanent ban after repeated violations."
        log_action = ModerationLog.ACTION_SANCTION_BAN

    profile.moderation_note = detail
    profile.save()

    _create_moderation_log(
        action=log_action,
        actor=actor,
        report=report,
        person=report.person if report.person_id else None,
        comment=report.comment if report.comment_id else None,
        target_user=target_user,
        details=detail,
    )


def _reject_sanctioned_action(request, action_name):
    profile = request.user.profile
    profile.normalize_moderation_state()

    if profile.moderation_status == UserProfile.STATUS_BANNED:
        messages.error(request, "Your account is banned and cannot perform this action.")
        return True

    if profile.moderation_status == UserProfile.STATUS_SUSPENDED and profile.suspended_until:
        until = profile.suspended_until.strftime("%Y-%m-%d %H:%M UTC")
        messages.error(request, f"Your account is suspended until {until}.")
        return True

    if action_name == "comment" and profile.moderation_status == UserProfile.STATUS_MUTED and profile.muted_until:
        until = profile.muted_until.strftime("%Y-%m-%d %H:%M UTC")
        messages.error(request, f"You are muted from commenting until {until}.")
        return True

    return False


def _is_honeypot_triggered(request):
    return bool(request.POST.get("website", "").strip())


def _reject_rate_limit(request, scope, limit_config, message_prefix):
    limit, window_seconds = limit_config
    allowed, retry_after = consume_rate_limit(scope, request.user.id, limit, window_seconds)
    if allowed:
        return False

    messages.error(
        request,
        f"{message_prefix} Please try again in about {retry_after} seconds.",
    )
    return True


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('home')

def home(request):
    # Get selected category
    category_id = request.GET.get('category')
    selected_category = None
    
    # Base querysets
    persons_query = _person_base_queryset(request)
    if category_id:
        try:
            selected_category = int(category_id)
            persons_query = persons_query.filter(category_id=selected_category)
        except (ValueError, TypeError):
            pass
    
    # Get trending persons
    trending_persons = _decorate_person_cards(
        request,
        persons_query.filter(ratings_count_cached__gt=0).order_by(
            '-ratings_count_cached',
            '-ratings_average_cached',
            'name',
        )[:6],
    )
    
    # Get recent persons
    recent_persons = _decorate_person_cards(
        request,
        persons_query.order_by('-created_at', '-pk')[:6],
    )
    
    # Get top rated persons
    top_rated = _decorate_person_cards(
        request,
        persons_query.filter(ratings_count_cached__gt=10).order_by(
            '-ratings_average_cached',
            '-ratings_count_cached',
            'name',
        )[:6],
    )
    
    # Get all categories
    categories = Category.objects.annotate(
        person_count=Count('persons')
    ).filter(person_count__gt=0).order_by('name')
    
    context = {
        'trending_persons': trending_persons,
        'recent_persons': recent_persons,
        'top_rated': top_rated,
        'categories': categories,
        'selected_category': selected_category,
        'user_collections': _get_user_collections(request),
    }
    return render(request, 'core/home.html', context)

def person_list(request):
    persons = _person_base_queryset(request).order_by('-created_at', '-pk')
    
    paginator = Paginator(persons, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_obj.object_list = _decorate_person_cards(request, page_obj.object_list)
    
    return render(
        request,
        'core/person_list.html',
        {
            'page_obj': page_obj,
            'user_collections': _get_user_collections(request),
        },
    )

def person_detail(request, slug):
    person = _get_person_by_slug_or_404(slug)
    if person.is_hidden and not _is_staff_user(request):
        raise Http404("Person not found.")

    person.image_url = person.get_image_url()

    user_rating = None
    if request.user.is_authenticated:
        user_rating = Rating.objects.filter(person=person, user=request.user).first()
    
    comments = _visible_comments_queryset(request, person).select_related('user').order_by('-created_at')
    paginator = Paginator(comments, 10)
    page_number = request.GET.get('page')
    comments_page = paginator.get_page(page_number)
    
    # Get statistics
    stats = person.get_stats_summary()
    stats['total_comments'] = comments.count()
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
        'report_form': ReportForm(),
    }
    return render(request, 'core/person_detail.html', context)

@login_required
def rate_person(request, slug):
    if request.method == 'POST':
        if _reject_sanctioned_action(request, "rate"):
            return redirect('person_detail', slug=slug)

        if _is_honeypot_triggered(request):
            messages.error(request, 'Suspicious submission blocked.')
            return redirect('person_detail', slug=slug)

        if _reject_rate_limit(
            request,
            scope='rate',
            limit_config=RATING_RATE_LIMIT,
            message_prefix='Too many rating attempts.',
        ):
            return redirect('person_detail', slug=slug)

        score = request.POST.get('score')
        person = _get_person_by_slug_or_404(slug)
        if person.is_hidden and not _is_staff_user(request):
            messages.error(request, 'This profile is under moderation review.')
            return redirect('home')
        existing_rating = Rating.objects.filter(person=person, user=request.user).first()

        if score and score.isdigit() and 1 <= int(score) <= 10:
            score_value = int(score)

            if (
                existing_rating
                and existing_rating.score == score_value
                and is_flooding(existing_rating.updated_at, RATING_DUPLICATE_FLOOD_SECONDS)
            ):
                messages.warning(request, 'You already submitted this score recently.')
                return redirect('person_detail', slug=slug)

            Rating.objects.update_or_create(
                person=person,
                user=request.user,
                defaults={'score': score_value}
            )
            messages.success(request, 'Rating submitted successfully!')
        else:
            messages.error(request, 'Invalid rating value!')
    return redirect('person_detail', slug=slug)

@login_required
def add_comment(request, slug):
    if request.method == 'POST':
        if _reject_sanctioned_action(request, "comment"):
            return redirect('person_detail', slug=slug)

        if _is_honeypot_triggered(request):
            messages.error(request, 'Suspicious submission blocked.')
            return redirect('person_detail', slug=slug)

        if _reject_rate_limit(
            request,
            scope='comment',
            limit_config=COMMENT_RATE_LIMIT,
            message_prefix='Comment limit reached.',
        ):
            return redirect('person_detail', slug=slug)

        content = (request.POST.get('content') or '').strip()
        if not content:
            messages.error(request, 'Comment cannot be empty!')
            return redirect('person_detail', slug=slug)

        person = _get_person_by_slug_or_404(slug)
        if person.is_hidden and not _is_staff_user(request):
            messages.error(request, 'This profile is under moderation review.')
            return redirect('home')
        latest_comment = Comment.objects.filter(person=person, user=request.user).order_by('-created_at').first()

        if latest_comment and is_flooding(latest_comment.created_at, COMMENT_FLOOD_SECONDS):
            messages.error(request, 'Please wait a bit before posting another comment.')
            return redirect('person_detail', slug=slug)

        duplicate_window_start = timezone.now() - timedelta(minutes=15)
        duplicate_comment_exists = Comment.objects.filter(
            person=person,
            user=request.user,
            content__iexact=content,
            created_at__gte=duplicate_window_start,
        ).exists()
        if duplicate_comment_exists:
            messages.error(request, 'Duplicate comment detected. Please post something new.')
            return redirect('person_detail', slug=slug)

        Comment.objects.create(
            person=person,
            user=request.user,
            content=content
        )
        messages.success(request, 'Comment added successfully!')
    return redirect('person_detail', slug=slug)


@login_required
def report_person(request, slug):
    person = _get_person_by_slug_or_404(slug)
    if person.is_hidden and not _is_staff_user(request):
        messages.error(request, 'This profile is currently unavailable.')
        return redirect('home')

    if request.method != 'POST':
        return redirect('person_detail', slug=slug)

    if _reject_sanctioned_action(request, "report"):
        return redirect('person_detail', slug=slug)

    if _is_honeypot_triggered(request):
        messages.error(request, 'Suspicious submission blocked.')
        return redirect('person_detail', slug=slug)

    if _reject_rate_limit(
        request,
        scope='report',
        limit_config=REPORT_RATE_LIMIT,
        message_prefix='Report limit reached.',
    ):
        return redirect('person_detail', slug=slug)

    form = ReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Invalid report form.')
        return redirect('person_detail', slug=slug)

    reason = form.cleaned_data['reason']
    details = form.cleaned_data['details']

    report, created = Report.objects.get_or_create(
        reporter=request.user,
        person=person,
        defaults={
            'reason': reason,
            'details': details,
        },
    )

    if created:
        _reconcile_target_visibility(report)
        messages.success(request, 'Report submitted. Thank you for helping moderate the platform.')
        return redirect('person_detail', slug=slug)

    report.reason = reason
    report.details = details
    report.status = Report.STATUS_PENDING
    report.reviewed_at = None
    report.reviewed_by = None
    report.resolution_notes = ''
    report.save(
        update_fields=[
            'reason',
            'details',
            'status',
            'reviewed_at',
            'reviewed_by',
            'resolution_notes',
        ]
    )
    _reconcile_target_visibility(report)
    messages.info(request, 'Your existing report has been updated and re-opened.')
    return redirect('person_detail', slug=slug)


@login_required
def report_comment(request, pk):
    comment = get_object_or_404(Comment.objects.select_related('person'), pk=pk)
    if comment.person.is_hidden and not _is_staff_user(request):
        messages.error(request, 'This profile is currently unavailable.')
        return redirect('home')

    if request.method != 'POST':
        return redirect(comment.person)

    if _reject_sanctioned_action(request, "report"):
        return redirect(comment.person)

    if _is_honeypot_triggered(request):
        messages.error(request, 'Suspicious submission blocked.')
        return redirect(comment.person)

    if _reject_rate_limit(
        request,
        scope='report',
        limit_config=REPORT_RATE_LIMIT,
        message_prefix='Report limit reached.',
    ):
        return redirect(comment.person)

    form = ReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Invalid report form.')
        return redirect(comment.person)

    reason = form.cleaned_data['reason']
    details = form.cleaned_data['details']

    report, created = Report.objects.get_or_create(
        reporter=request.user,
        comment=comment,
        defaults={
            'reason': reason,
            'details': details,
        },
    )

    if created:
        _reconcile_target_visibility(report)
        messages.success(request, 'Comment reported successfully.')
        return redirect(comment.person)

    report.reason = reason
    report.details = details
    report.status = Report.STATUS_PENDING
    report.reviewed_at = None
    report.reviewed_by = None
    report.resolution_notes = ''
    report.save(
        update_fields=[
            'reason',
            'details',
            'status',
            'reviewed_at',
            'reviewed_by',
            'resolution_notes',
        ]
    )
    _reconcile_target_visibility(report)
    messages.info(request, 'Your existing comment report has been updated and re-opened.')
    return redirect(comment.person)

def top_rated(request):
    persons = _attach_person_rating_aliases(
        _person_base_queryset(request)
        .filter(ratings_count_cached__gt=100)
        .order_by('-ratings_average_cached', '-ratings_count_cached', 'name')[:250]
    )
    
    return render(request, 'core/top_rated.html', {'persons': persons})

def search(request):
    query = request.GET.get('q', '')
    form = AdvancedSearchForm(request.GET)
    persons = _person_base_queryset(request)
    
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
        
        if min_rating is not None:
            persons = persons.filter(ratings_average_cached__gte=min_rating)
        if max_rating is not None:
            persons = persons.filter(ratings_average_cached__lte=max_rating)
        # Handle minimum ratings count
        min_ratings_count = form.cleaned_data.get('min_ratings_count')
        if min_ratings_count is not None:
            persons = persons.filter(ratings_count_cached__gte=min_ratings_count)
    # Order results
    sort_by = request.GET.get('sort', '-created_at')
    sort_map = {
        '-created_at': ('-created_at', '-pk'),
        'created_at': ('created_at', 'pk'),
        'name': ('name', 'pk'),
        '-name': ('-name', 'pk'),
        '-avg_rating': ('-ratings_average_cached', '-ratings_count_cached', 'name'),
        'avg_rating': ('ratings_average_cached', '-ratings_count_cached', 'name'),
        '-rating_count': ('-ratings_count_cached', '-ratings_average_cached', 'name'),
    }
    persons = persons.order_by(*sort_map.get(sort_by, sort_map['-created_at']))
    
    # Add pagination
    paginator = Paginator(persons, 12)  # Show 12 persons per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_obj.object_list = _decorate_person_cards(request, page_obj.object_list)
    
    context = {
        'query': query,
        'form': form,
        'page_obj': page_obj,
        'sort_by': sort_by if sort_by in sort_map else '-created_at',
        'user_collections': _get_user_collections(request),
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


class ReportListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Report
    template_name = 'core/report_list.html'
    context_object_name = 'reports'
    paginate_by = 25

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = Report.objects.select_related(
            'reporter',
            'person',
            'comment__person',
            'reviewed_by',
        )
        status = self.request.GET.get('status')
        valid_statuses = {choice[0] for choice in Report.STATUS_CHOICES}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Report.STATUS_CHOICES
        context['selected_status'] = self.request.GET.get('status', '')
        return context


class ModerationLogListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ModerationLog
    template_name = 'core/moderation_log_list.html'
    context_object_name = 'logs'
    paginate_by = 50

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = ModerationLog.objects.select_related(
            'actor',
            'target_user',
            'report',
            'person',
            'comment',
        )
        action = self.request.GET.get('action')
        valid_actions = {choice[0] for choice in ModerationLog.ACTION_CHOICES}
        if action in valid_actions:
            queryset = queryset.filter(action=action)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_choices'] = ModerationLog.ACTION_CHOICES
        context['selected_action'] = self.request.GET.get('action', '')
        return context


@login_required
@user_passes_test(lambda u: u.is_staff)
def update_report_status(request, pk):
    if request.method != 'POST':
        return redirect('report_list')

    report = get_object_or_404(Report, pk=pk)
    previous_status = report.status
    status = request.POST.get('status')
    resolution_notes = (request.POST.get('resolution_notes') or '').strip()
    valid_statuses = {choice[0] for choice in Report.STATUS_CHOICES}

    if status not in valid_statuses:
        messages.error(request, 'Invalid report status.')
        return redirect('report_list')

    report.status = status
    report.resolution_notes = resolution_notes
    if status == Report.STATUS_PENDING:
        report.reviewed_by = None
        report.reviewed_at = None
    else:
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
    report.save(update_fields=['status', 'resolution_notes', 'reviewed_by', 'reviewed_at'])

    _create_moderation_log(
        action=ModerationLog.ACTION_REPORT_STATUS_CHANGED,
        actor=request.user,
        report=report,
        person=report.person if report.person_id else None,
        comment=report.comment if report.comment_id else None,
        target_user=_get_target_owner(report),
        details=f"Status changed from {previous_status} to {status}. {resolution_notes}",
    )

    if status == Report.STATUS_ACTIONED:
        _reconcile_target_visibility(report, actor=request.user)
        _apply_escalating_sanction(report, actor=request.user)
    else:
        _reconcile_target_visibility(report, actor=request.user)

    messages.success(request, f'Report #{report.pk} updated.')

    selected_status = request.GET.get('status')
    if selected_status:
        return redirect(f"{reverse_lazy('report_list')}?status={selected_status}")
    return redirect('report_list')


@login_required
def toggle_favorite(request, slug):
    if request.method == 'POST':
        person = _get_person_by_slug_or_404(slug)
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
def add_to_collection(request, slug):
    person = _get_person_by_slug_or_404(slug)
    
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
    
    return redirect(person)

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
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def test_func(self):
        person = self.get_object()
        return self.request.user.is_superuser or person.created_by == self.request.user

    def get_success_url(self):
        return self.object.get_absolute_url()

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
