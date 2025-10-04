"""
URL configuration for characters app
"""
from django.urls import path
from . import views

urlpatterns = [
    path('player/<uuid:player_id>/create/', views.CharacterCreateView.as_view(), name='character_create'),
    path('<uuid:character_id>/', views.CharacterDetailView.as_view(), name='character_detail'),
    path('<uuid:character_id>/edit/', views.CharacterEditView.as_view(), name='character_edit'),
    path('<uuid:character_id>/delete/', views.CharacterDeleteView.as_view(), name='character_delete'),
]
