from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('people/', views.person_list, name='person_list'),
    path('person/new/', views.PersonCreateView.as_view(), name='person_create'),
    path('person/<int:pk>/', views.person_detail_legacy_redirect, name='person_detail_legacy'),
    path('person/<slug:slug>/', views.person_detail, name='person_detail'),
    path('person/<slug:slug>/edit/', views.PersonUpdateView.as_view(), name='person_edit'),
    path('person/<slug:slug>/rate/', views.rate_person, name='rate_person'),
    path('person/<slug:slug>/comment/', views.add_comment, name='add_comment'),
    path('person/<slug:slug>/report/', views.report_person, name='report_person'),
    path('comment/<int:pk>/report/', views.report_comment, name='report_comment'),
    path('person/<slug:slug>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('top-rated/', views.top_rated, name='top_rated'),
    path('search/', views.search, name='search'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('profile/<int:pk>/', views.UserProfileView.as_view(), name='user_profile'),
    path('logout/', views.logout_view, name='logout'),
    
    # Collection URLs
    path('collections/', views.CollectionListView.as_view(), name='collection_list'),
    path('collections/my/', views.UserCollectionListView.as_view(), name='user_collections'),
    path('collections/new/', views.CollectionCreateView.as_view(), name='collection_create'),
    path('collections/<int:pk>/', views.CollectionDetailView.as_view(), name='collection_detail'),
    path('collections/<int:pk>/edit/', views.CollectionUpdateView.as_view(), name='collection_edit'),
    path('collections/<int:pk>/delete/', views.CollectionDeleteView.as_view(), name='collection_delete'),
    path('collections/add/<slug:slug>/', views.add_to_collection, name='add_to_collection'),
    path('collections/<int:collection_pk>/remove/<int:person_pk>/', views.remove_from_collection, name='remove_from_collection'),
    
    # Category management URLs
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/new/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    path('moderation/reports/', views.ReportListView.as_view(), name='report_list'),
    path('moderation/logs/', views.ModerationLogListView.as_view(), name='moderation_log_list'),
    path('moderation/reports/<int:pk>/status/', views.update_report_status, name='report_status_update'),
] 
