"""
SkillForge URL Configuration
"""
from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView

from .views import dashboard
from accounts.views import AccountListView, AccountDetailView
from members.views import MemberListView, MemberDetailView
from worlds.views import (
    UniverseListView, UniverseCreateView, UniverseDetailView,
    UniverseUpdateView, UniverseDeleteView,
    WorldListView, WorldCreateView, WorldDetailView,
    WorldUpdateView, WorldDeleteView,
    WorldGenerateBackstoryView, WorldSaveBackstoryView, WorldGenerateRegionsView,
    RegionListView, RegionCreateView, RegionDetailView,
    RegionUpdateView, RegionDeleteView,
    RegionGenerateBackstoryView, RegionSaveBackstoryView, RegionGenerateLocationsView,
    LocationListView, LocationCreateView, LocationDetailView,
    LocationUpdateView, LocationDeleteView,
    LocationGenerateBackstoryView, LocationSaveBackstoryView
)
from campaigns.views import (
    CampaignListView, CampaignCreateView, CampaignDetailView, CampaignStartView,
    CampaignUpdateView, CampaignDeleteView
)

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('admin/', admin.site.urls),
    path('graphql/', csrf_exempt(GraphQLView.as_view(graphiql=True))),

    # Accounts
    path('accounts/', AccountListView.as_view(), name='account_list'),
    path('accounts/<uuid:account_id>/', AccountDetailView.as_view(), name='account_detail'),

    # Members
    path('members/', MemberListView.as_view(), name='member_list'),
    path('members/<uuid:member_id>/', MemberDetailView.as_view(), name='member_detail'),

    # Universes
    path('universes/', UniverseListView.as_view(), name='universe_list'),
    path('universes/create/', UniverseCreateView.as_view(), name='universe_create'),
    path('universes/<str:universe_id>/', UniverseDetailView.as_view(), name='universe_detail'),
    path('universes/<str:universe_id>/edit/', UniverseUpdateView.as_view(), name='universe_update'),
    path('universes/<str:universe_id>/delete/', UniverseDeleteView.as_view(), name='universe_delete'),

    # Worlds
    path('worlds/', WorldListView.as_view(), name='world_list'),
    path('worlds/create/', WorldCreateView.as_view(), name='world_create'),
    path('worlds/<str:world_id>/', WorldDetailView.as_view(), name='world_detail'),
    path('worlds/<str:world_id>/edit/', WorldUpdateView.as_view(), name='world_update'),
    path('worlds/<str:world_id>/delete/', WorldDeleteView.as_view(), name='world_delete'),
    path('worlds/<str:world_id>/generate-backstory/', WorldGenerateBackstoryView.as_view(), name='world_generate_backstory'),
    path('worlds/<str:world_id>/save-backstory/', WorldSaveBackstoryView.as_view(), name='world_save_backstory'),
    path('worlds/<str:world_id>/generate-regions/', WorldGenerateRegionsView.as_view(), name='world_generate_regions'),

    # Regions
    path('worlds/<str:world_id>/regions/', RegionListView.as_view(), name='region_list'),
    path('worlds/<str:world_id>/regions/create/', RegionCreateView.as_view(), name='region_create'),
    path('worlds/<str:world_id>/regions/<str:region_id>/', RegionDetailView.as_view(), name='region_detail'),
    path('worlds/<str:world_id>/regions/<str:region_id>/edit/', RegionUpdateView.as_view(), name='region_update'),
    path('worlds/<str:world_id>/regions/<str:region_id>/delete/', RegionDeleteView.as_view(), name='region_delete'),
    path('worlds/<str:world_id>/regions/<str:region_id>/generate-backstory/', RegionGenerateBackstoryView.as_view(), name='region_generate_backstory'),
    path('worlds/<str:world_id>/regions/<str:region_id>/save-backstory/', RegionSaveBackstoryView.as_view(), name='region_save_backstory'),
    path('worlds/<str:world_id>/regions/<str:region_id>/generate-locations/', RegionGenerateLocationsView.as_view(), name='region_generate_locations'),

    # Locations
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/', LocationListView.as_view(), name='location_list'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/create/', LocationCreateView.as_view(), name='location_create'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/', LocationDetailView.as_view(), name='location_detail'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/edit/', LocationUpdateView.as_view(), name='location_update'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/delete/', LocationDeleteView.as_view(), name='location_delete'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/generate-backstory/', LocationGenerateBackstoryView.as_view(), name='location_generate_backstory'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/save-backstory/', LocationSaveBackstoryView.as_view(), name='location_save_backstory'),

    # Campaigns
    path('campaigns/', CampaignListView.as_view(), name='campaign_list'),
    path('campaigns/create/', CampaignCreateView.as_view(), name='campaign_create'),
    path('campaigns/<str:campaign_id>/', CampaignDetailView.as_view(), name='campaign_detail'),
    path('campaigns/<str:campaign_id>/edit/', CampaignUpdateView.as_view(), name='campaign_update'),
    path('campaigns/<str:campaign_id>/delete/', CampaignDeleteView.as_view(), name='campaign_delete'),
    path('campaigns/<str:campaign_id>/start/', CampaignStartView.as_view(), name='campaign_start'),
]
