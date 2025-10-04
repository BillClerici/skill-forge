"""
SkillForge URL Configuration
"""
from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView
from django.conf import settings
from django.conf.urls.static import static

from .views import dashboard
from accounts.views import AccountListView, AccountDetailView
from members.views import PlayerListView, PlayerDetailView
from worlds.views import (
    UniverseListView, UniverseCreateView, UniverseDetailView,
    UniverseUpdateView, UniverseDeleteView,
    WorldListView, WorldCreateView, WorldDetailView,
    WorldUpdateView, WorldDeleteView,
    WorldGenerateBackstoryView, WorldSaveBackstoryView, WorldGenerateRegionsView,
    WorldGenerateImageView, WorldDeleteImageView, WorldSetPrimaryImageView,
    RegionListView, RegionCreateView, RegionDetailView,
    RegionUpdateView, RegionDeleteView,
    RegionGenerateBackstoryView, RegionSaveBackstoryView, RegionGenerateLocationsView,
    RegionGenerateImageView, RegionDeleteImageView, RegionSetPrimaryImageView,
    LocationListView, LocationCreateView, LocationDetailView,
    LocationUpdateView, LocationDeleteView,
    LocationGenerateBackstoryView, LocationSaveBackstoryView,
    LocationGenerateImageView, LocationDeleteImageView, LocationSetPrimaryImageView
)
from worlds.views_species import (
    SpeciesCreateView, SpeciesDetailView, SpeciesEditView, SpeciesDeleteView,
    SpeciesGenerateAIView, SpeciesGenerateImageView,
    SpeciesDeleteImageView, SpeciesSetPrimaryImageView
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

    # Players
    path('players/', PlayerListView.as_view(), name='player_list'),
    path('players/<uuid:player_id>/', PlayerDetailView.as_view(), name='player_detail'),

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
    path('worlds/<str:world_id>/generate-image/', WorldGenerateImageView.as_view(), name='world_generate_image'),
    path('worlds/<str:world_id>/delete-image/', WorldDeleteImageView.as_view(), name='world_delete_image'),
    path('worlds/<str:world_id>/set-primary-image/', WorldSetPrimaryImageView.as_view(), name='world_set_primary_image'),

    # Species
    path('worlds/<str:world_id>/species/create/', SpeciesCreateView.as_view(), name='species_create'),
    path('worlds/<str:world_id>/species/<str:species_id>/', SpeciesDetailView.as_view(), name='species_detail'),
    path('worlds/<str:world_id>/species/<str:species_id>/edit/', SpeciesEditView.as_view(), name='species_edit'),
    path('worlds/<str:world_id>/species/<str:species_id>/delete/', SpeciesDeleteView.as_view(), name='species_delete'),
    path('worlds/<str:world_id>/species/generate-ai/', SpeciesGenerateAIView.as_view(), name='species_generate_ai'),
    path('worlds/<str:world_id>/species/<str:species_id>/generate-image/', SpeciesGenerateImageView.as_view(), name='species_generate_image'),
    path('worlds/<str:world_id>/species/<str:species_id>/delete-image/', SpeciesDeleteImageView.as_view(), name='species_delete_image'),
    path('worlds/<str:world_id>/species/<str:species_id>/set-primary-image/', SpeciesSetPrimaryImageView.as_view(), name='species_set_primary_image'),

    # Regions
    path('worlds/<str:world_id>/regions/', RegionListView.as_view(), name='region_list'),
    path('worlds/<str:world_id>/regions/create/', RegionCreateView.as_view(), name='region_create'),
    path('worlds/<str:world_id>/regions/<str:region_id>/', RegionDetailView.as_view(), name='region_detail'),
    path('worlds/<str:world_id>/regions/<str:region_id>/edit/', RegionUpdateView.as_view(), name='region_update'),
    path('worlds/<str:world_id>/regions/<str:region_id>/delete/', RegionDeleteView.as_view(), name='region_delete'),
    path('worlds/<str:world_id>/regions/<str:region_id>/generate-backstory/', RegionGenerateBackstoryView.as_view(), name='region_generate_backstory'),
    path('worlds/<str:world_id>/regions/<str:region_id>/save-backstory/', RegionSaveBackstoryView.as_view(), name='region_save_backstory'),
    path('worlds/<str:world_id>/regions/<str:region_id>/generate-locations/', RegionGenerateLocationsView.as_view(), name='region_generate_locations'),
    path('worlds/<str:world_id>/regions/<str:region_id>/generate-image/', RegionGenerateImageView.as_view(), name='region_generate_image'),
    path('worlds/<str:world_id>/regions/<str:region_id>/delete-image/', RegionDeleteImageView.as_view(), name='region_delete_image'),
    path('worlds/<str:world_id>/regions/<str:region_id>/set-primary-image/', RegionSetPrimaryImageView.as_view(), name='region_set_primary_image'),

    # Locations
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/', LocationListView.as_view(), name='location_list'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/create/', LocationCreateView.as_view(), name='location_create'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/', LocationDetailView.as_view(), name='location_detail'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/edit/', LocationUpdateView.as_view(), name='location_update'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/delete/', LocationDeleteView.as_view(), name='location_delete'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/generate-backstory/', LocationGenerateBackstoryView.as_view(), name='location_generate_backstory'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/save-backstory/', LocationSaveBackstoryView.as_view(), name='location_save_backstory'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/generate-image/', LocationGenerateImageView.as_view(), name='location_generate_image'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/delete-image/', LocationDeleteImageView.as_view(), name='location_delete_image'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/set-primary-image/', LocationSetPrimaryImageView.as_view(), name='location_set_primary_image'),

    # Campaigns
    path('campaigns/', CampaignListView.as_view(), name='campaign_list'),
    path('campaigns/create/', CampaignCreateView.as_view(), name='campaign_create'),
    path('campaigns/<str:campaign_id>/', CampaignDetailView.as_view(), name='campaign_detail'),
    path('campaigns/<str:campaign_id>/edit/', CampaignUpdateView.as_view(), name='campaign_update'),
    path('campaigns/<str:campaign_id>/delete/', CampaignDeleteView.as_view(), name='campaign_delete'),
    path('campaigns/<str:campaign_id>/start/', CampaignStartView.as_view(), name='campaign_start'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
