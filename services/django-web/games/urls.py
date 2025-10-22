"""
URL Configuration for Games app
"""
from django.urls import path
from . import views

app_name = 'games'

urlpatterns = [
    # Lobby
    path('', views.GamesLobbyView.as_view(), name='lobby'),

    # Create Game (must come before play pattern to avoid being caught by <str:game_id>)
    path('create/', views.CreateGameView.as_view(), name='create'),

    # API
    path('api/sessions/', views.GameSessionsAPIView.as_view(), name='sessions_api'),

    # Game Play (accepts full session ID format: session_<timestamp>_<uuid>)
    # This must be last since it matches any string
    path('<str:game_id>/', views.GamePlayView.as_view(), name='play'),
]
