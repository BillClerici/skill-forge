"""
URL Configuration for Games app
"""
from django.urls import path
from . import views

app_name = 'games'

urlpatterns = [
    # Lobby
    path('', views.GamesLobbyView.as_view(), name='lobby'),

    # Game Play
    path('<uuid:game_id>/', views.GamePlayView.as_view(), name='play'),

    # Create Game
    path('create/', views.CreateGameView.as_view(), name='create'),

    # API
    path('api/sessions/', views.GameSessionsAPIView.as_view(), name='sessions_api'),
]
