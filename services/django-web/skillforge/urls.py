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
from accounts.views import (
    AccountListView, AccountDetailView, AccountCreateView, AccountUpdateView, AccountDeleteView,
    PlayerCreateView as AccountPlayerCreateView, PlayerUpdateView as AccountPlayerUpdateView,
    PlayerDeleteView as AccountPlayerDeleteView
)
from members.views import PlayerListView, PlayerDetailView
from members.views_profile import PlayerProfileConfigView
from worlds.views import (
    UniverseListView, UniverseCreateView, UniverseDetailView,
    UniverseUpdateView, UniverseDeleteView,
    WorldListView, WorldCreateView, WorldDetailView,
    WorldUpdateView, WorldDeleteView,
    WorldGenerateBackstoryView, WorldSaveBackstoryView, WorldGenerateRegionsView,
    WorldGenerateImageView, WorldDeleteImageView, WorldSetPrimaryImageView, WorldTextToSpeechView,
    WorldGenerateMapView, WorldDeleteMapView, WorldSaveMapCoordinatesView,
    RegionListView, RegionCreateView, RegionDetailView,
    RegionUpdateView, RegionDeleteView,
    RegionGenerateBackstoryView, RegionSaveBackstoryView, RegionGenerateLocationsView,
    RegionGenerateImageView, RegionDeleteImageView, RegionSetPrimaryImageView, RegionTextToSpeechView,
    RegionGenerateMapView, RegionDeleteMapView, RegionSaveMapCoordinatesView, RegionUpdateLocationCoordinatesView,
    LocationListView, LocationCreateView, LocationDetailView,
    LocationUpdateView, LocationDeleteView,
    LocationGenerateBackstoryView, LocationSaveBackstoryView,
    LocationGenerateImageView, LocationDeleteImageView, LocationSetPrimaryImageView, LocationTextToSpeechView,
    LocationGenerateMapView, LocationDeleteMapView
)
from worlds.views_species import (
    SpeciesCreateView, SpeciesDetailView, SpeciesEditView, SpeciesDeleteView,
    SpeciesGenerateAIView, SpeciesGenerateImageView,
    SpeciesDeleteImageView, SpeciesSetPrimaryImageView
)
from worlds.views_world_factory import (
    WorldFactoryInitiateView, WorldFactoryStatusView, WorldFactoryResultView,
    WorldFactoryCancelView, WorldFactoryAuditTrailView, WorldFactoryListWorkflowsView
)
from campaigns.views import (
    CampaignListView, CampaignCreateView, CampaignDetailView, CampaignStartView,
    CampaignUpdateView, CampaignDeleteView, CampaignDesignerWizardView,
    CampaignGenerateImageView, QuestGenerateImageView, PlaceGenerateImageView, SceneGenerateImageView,
    CampaignSetPrimaryImageView, QuestSetPrimaryImageView, PlaceSetPrimaryImageView, SceneSetPrimaryImageView,
    CampaignDeletionProgressView, CampaignDeletionStatusAPI,
    CampaignReorderQuestsView, QuestReorderPlacesView, PlaceReorderScenesView,
    SessionObjectivesAPIView
)
from campaigns.views_gameplay import (
    GameLobbyView, StartGameSessionView, GameSessionView,
    PartyLobbyView, JoinSessionView, SessionControlView, CampaignImagesAPIView,
    DeleteSessionView
)
from campaigns import crud_views
from campaigns import npc_image_views
# V1 wizard views removed - using V2 only
from campaigns import wizard_views_v2
from characters.views import (
    CharacterCreateView, CharacterDetailView, CharacterSheetView, CharacterEditView, CharacterDeleteView,
    CharacterGenerateBackstoryView, CharacterSaveBackstoryView,
    CharacterGenerateImageView, CharacterDeleteImageView, CharacterSetPrimaryImageView,
    CharacterTextToSpeechView
)

from django.urls import include

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('admin/', admin.site.urls),
    path('graphql/', csrf_exempt(GraphQLView.as_view(graphiql=True))),

    # Accounts
    path('accounts/', AccountListView.as_view(), name='account_list'),
    path('accounts/create/', AccountCreateView.as_view(), name='account_create'),
    path('accounts/<uuid:account_id>/', AccountDetailView.as_view(), name='account_detail'),
    path('accounts/<uuid:account_id>/edit/', AccountUpdateView.as_view(), name='account_edit'),
    path('accounts/<uuid:account_id>/delete/', AccountDeleteView.as_view(), name='account_delete'),

    # Account Players
    path('accounts/<uuid:account_id>/players/add/', AccountPlayerCreateView.as_view(), name='account_player_add'),
    path('accounts/<uuid:account_id>/players/<uuid:player_id>/edit/', AccountPlayerUpdateView.as_view(), name='account_player_edit'),
    path('accounts/<uuid:account_id>/players/<uuid:player_id>/delete/', AccountPlayerDeleteView.as_view(), name='account_player_delete'),

    # Players
    path('players/', PlayerListView.as_view(), name='player_list'),
    path('players/<uuid:player_id>/', PlayerDetailView.as_view(), name='player_detail'),
    path('players/<uuid:player_id>/profile/config/', PlayerProfileConfigView.as_view(), name='player_profile_config'),

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
    path('worlds/<str:world_id>/tts-backstory/', WorldTextToSpeechView.as_view(), name='world_tts_backstory'),
    path('worlds/<str:world_id>/generate-map/', WorldGenerateMapView.as_view(), name='world_generate_map'),
    path('worlds/<str:world_id>/delete-map/', WorldDeleteMapView.as_view(), name='world_delete_map'),
    path('worlds/<str:world_id>/save-map-coordinates/', WorldSaveMapCoordinatesView.as_view(), name='world_save_map_coordinates'),

    # World Factory API
    path('api/world-factory/initiate/', WorldFactoryInitiateView.as_view(), name='world_factory_initiate'),
    path('api/world-factory/<str:workflow_id>/status/', WorldFactoryStatusView.as_view(), name='world_factory_status'),
    path('api/world-factory/<str:workflow_id>/result/', WorldFactoryResultView.as_view(), name='world_factory_result'),
    path('api/world-factory/<str:workflow_id>/cancel/', WorldFactoryCancelView.as_view(), name='world_factory_cancel'),
    path('api/world-factory/<str:workflow_id>/audit/', WorldFactoryAuditTrailView.as_view(), name='world_factory_audit'),
    path('api/world-factory/workflows/', WorldFactoryListWorkflowsView.as_view(), name='world_factory_list'),

    # Species
    path('worlds/<str:world_id>/species/create/', SpeciesCreateView.as_view(), name='species_create'),
    path('worlds/<str:world_id>/species/generate-ai/', SpeciesGenerateAIView.as_view(), name='species_generate_ai'),
    path('worlds/<str:world_id>/species/<str:species_id>/', SpeciesDetailView.as_view(), name='species_detail'),
    path('worlds/<str:world_id>/species/<str:species_id>/edit/', SpeciesEditView.as_view(), name='species_edit'),
    path('worlds/<str:world_id>/species/<str:species_id>/delete/', SpeciesDeleteView.as_view(), name='species_delete'),
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
    path('worlds/<str:world_id>/regions/<str:region_id>/tts-backstory/', RegionTextToSpeechView.as_view(), name='region_tts_backstory'),
    path('worlds/<str:world_id>/regions/<str:region_id>/generate-map/', RegionGenerateMapView.as_view(), name='region_generate_map'),
    path('worlds/<str:world_id>/regions/<str:region_id>/delete-map/', RegionDeleteMapView.as_view(), name='region_delete_map'),
    path('worlds/<str:world_id>/regions/<str:region_id>/save-map-coordinates/', RegionSaveMapCoordinatesView.as_view(), name='region_save_map_coordinates'),
    path('worlds/<str:world_id>/regions/<str:region_id>/update-location-coordinates/', RegionUpdateLocationCoordinatesView.as_view(), name='region_update_location_coordinates'),

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
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/tts-backstory/', LocationTextToSpeechView.as_view(), name='location_tts_backstory'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/generate-map/', LocationGenerateMapView.as_view(), name='location_generate_map'),
    path('worlds/<str:world_id>/regions/<str:region_id>/locations/<str:location_id>/delete-map/', LocationDeleteMapView.as_view(), name='location_delete_map'),

    # Campaigns
    path('campaigns/', CampaignListView.as_view(), name='campaign_list'),
    path('campaigns/create/', CampaignCreateView.as_view(), name='campaign_create'),
    path('campaigns/designer/', CampaignDesignerWizardView.as_view(), name='campaign_designer_wizard'),
    path('campaigns/<str:campaign_id>/', CampaignDetailView.as_view(), name='campaign_detail'),
    path('campaigns/<str:campaign_id>/edit/', CampaignUpdateView.as_view(), name='campaign_update'),
    path('campaigns/<str:campaign_id>/delete/', CampaignDeleteView.as_view(), name='campaign_delete'),
    path('campaigns/<str:campaign_id>/start/', StartGameSessionView.as_view(), name='campaign_start'),

    # Game Lobby & Sessions
    path('game/lobby/', GameLobbyView.as_view(), name='game_lobby'),
    path('game/session/<str:session_id>/', GameSessionView.as_view(), name='game_session'),
    path('api/session/<str:session_id>/objectives/', SessionObjectivesAPIView.as_view(), name='session_objectives'),
    path('game/party/<str:session_id>/', PartyLobbyView.as_view(), name='party_lobby'),
    path('game/join/', JoinSessionView.as_view(), name='join_session'),
    path('game/session/<str:session_id>/control/', SessionControlView.as_view(), name='session_control'),
    path('api/campaigns/<str:campaign_id>/images/', CampaignImagesAPIView.as_view(), name='campaign_images_api'),
    path('api/session/delete/', DeleteSessionView.as_view(), name='delete_session'),

    # Campaign Deletion
    path('campaigns/deletion/progress/<str:request_id>/', CampaignDeletionProgressView.as_view(), name='campaign_deletion_progress'),
    path('api/campaigns/deletion/status/<str:request_id>/', CampaignDeletionStatusAPI.as_view(), name='campaign_deletion_status'),
    path('campaigns/<str:campaign_id>/generate-image/', CampaignGenerateImageView.as_view(), name='campaign_generate_image'),
    path('campaigns/<str:campaign_id>/quests/<str:quest_id>/generate-image/', QuestGenerateImageView.as_view(), name='quest_generate_image'),
    path('campaigns/<str:campaign_id>/quests/<str:quest_id>/places/<str:place_id>/generate-image/', PlaceGenerateImageView.as_view(), name='place_generate_image'),
    path('campaigns/<str:campaign_id>/quests/<str:quest_id>/places/<str:place_id>/scenes/<str:scene_id>/generate-image/', SceneGenerateImageView.as_view(), name='scene_generate_image'),
    path('campaigns/<str:campaign_id>/set-primary-image/', CampaignSetPrimaryImageView.as_view(), name='campaign_set_primary_image'),
    path('campaigns/<str:campaign_id>/quests/<str:quest_id>/set-primary-image/', QuestSetPrimaryImageView.as_view(), name='quest_set_primary_image'),
    path('campaigns/<str:campaign_id>/quests/<str:quest_id>/places/<str:place_id>/set-primary-image/', PlaceSetPrimaryImageView.as_view(), name='place_set_primary_image'),
    path('campaigns/<str:campaign_id>/quests/<str:quest_id>/places/<str:place_id>/scenes/<str:scene_id>/set-primary-image/', SceneSetPrimaryImageView.as_view(), name='scene_set_primary_image'),

    # Campaign Reordering
    path('campaigns/<str:campaign_id>/reorder-quests/', CampaignReorderQuestsView.as_view(), name='campaign_reorder_quests'),
    path('campaigns/<str:campaign_id>/quests/<str:quest_id>/reorder-places/', QuestReorderPlacesView.as_view(), name='quest_reorder_places'),
    path('campaigns/<str:campaign_id>/places/<str:place_id>/reorder-scenes/', PlaceReorderScenesView.as_view(), name='place_reorder_scenes'),

    # Entity CRUD API
    path('api/campaigns/<str:campaign_id>/<str:entity_type>/create/', crud_views.CreateEntityAPIView.as_view(), name='entity_create'),
    path('api/campaigns/<str:campaign_id>/<str:entity_type>/<str:entity_id>/', crud_views.GetEntityAPIView.as_view(), name='entity_get'),
    path('api/campaigns/<str:campaign_id>/<str:entity_type>/<str:entity_id>/update/', crud_views.UpdateEntityAPIView.as_view(), name='entity_update'),
    path('api/campaigns/<str:campaign_id>/<str:entity_type>/<str:entity_id>/delete/', crud_views.DeleteEntityAPIView.as_view(), name='entity_delete'),

    # NPC Image Generation and AI Regeneration API
    path('api/campaigns/<str:campaign_id>/npcs/<str:npc_id>/generate-image/', npc_image_views.NPCGenerateImageView.as_view(), name='npc_generate_image'),
    path('api/campaigns/<str:campaign_id>/npcs/<str:npc_id>/save-image/', npc_image_views.NPCSaveImageView.as_view(), name='npc_save_image'),
    path('api/campaigns/<str:campaign_id>/npcs/<str:npc_id>/delete-image/', npc_image_views.NPCDeleteImageView.as_view(), name='npc_delete_image'),
    path('api/campaigns/<str:campaign_id>/npcs/<str:npc_id>/regenerate-fields/', npc_image_views.NPCRegenerateFieldsView.as_view(), name='npc_regenerate_fields'),

    # World Species API
    path('api/worlds/<str:world_id>/species/', crud_views.WorldSpeciesListView.as_view(), name='world_species_list'),

    # Campaign Wizard V2 - Main Entry Point
    path('campaigns/wizard/', wizard_views_v2.campaign_wizard_v2, name='campaign_wizard_v2'),

    # Campaign Wizard V2 API Endpoints
    path('campaigns/wizard/api/worlds/<str:universe_id>', wizard_views_v2.get_worlds_for_universe_api, name='get_worlds_for_universe_api'),
    path('campaigns/wizard/api/regions/<str:world_id>', wizard_views_v2.get_regions_for_world_api, name='get_regions_for_world_api'),
    path('campaigns/wizard/api/generate-stories', wizard_views_v2.generate_stories_api, name='generate_stories_api'),
    path('campaigns/wizard/api/regenerate-stories', wizard_views_v2.regenerate_stories_api, name='regenerate_stories_api'),
    path('campaigns/wizard/api/generate-core', wizard_views_v2.generate_core_api, name='generate_core_api'),
    path('campaigns/wizard/api/approve-core', wizard_views_v2.approve_core_api, name='approve_core_api'),
    path('campaigns/wizard/api/approve-quests', wizard_views_v2.approve_quests_api, name='approve_quests_api'),
    path('campaigns/wizard/api/approve-places', wizard_views_v2.approve_places_api, name='approve_places_api'),
    path('campaigns/wizard/api/status/<str:request_id>', wizard_views_v2.get_workflow_status_api, name='get_workflow_status_api'),
    path('campaigns/wizard/api/finalize', wizard_views_v2.finalize_campaign_api, name='finalize_campaign_api'),
    path('campaigns/wizard/api/in-progress', wizard_views_v2.list_in_progress_campaigns_api, name='list_in_progress_campaigns_api'),
    # NEW: Objective cascade endpoints
    path('campaigns/wizard/api/objective-decomposition/<str:request_id>', wizard_views_v2.get_objective_decomposition_api, name='get_objective_decomposition_api'),
    path('campaigns/wizard/api/scene-assignments/<str:request_id>', wizard_views_v2.get_scene_assignments_api, name='get_scene_assignments_api'),
    path('campaigns/wizard/api/validation-report/<str:request_id>', wizard_views_v2.get_validation_report_api, name='get_validation_report_api'),
    path('campaigns/wizard/api/retry-validation/<str:request_id>', wizard_views_v2.retry_validation_api, name='retry_validation_api'),

    # Characters
    path('players/<uuid:player_id>/characters/create/', CharacterCreateView.as_view(), name='character_create'),
    path('characters/<uuid:character_id>/', CharacterDetailView.as_view(), name='character_detail'),
    path('characters/<uuid:character_id>/sheet/', CharacterSheetView.as_view(), name='character_sheet'),
    path('characters/<uuid:character_id>/edit/', CharacterEditView.as_view(), name='character_edit'),
    path('characters/<uuid:character_id>/delete/', CharacterDeleteView.as_view(), name='character_delete'),
    path('characters/<uuid:character_id>/generate-backstory/', CharacterGenerateBackstoryView.as_view(), name='character_generate_backstory'),
    path('characters/<uuid:character_id>/save-backstory/', CharacterSaveBackstoryView.as_view(), name='character_save_backstory'),
    path('characters/<uuid:character_id>/generate-image/', CharacterGenerateImageView.as_view(), name='character_generate_image'),
    path('characters/<uuid:character_id>/delete-image/', CharacterDeleteImageView.as_view(), name='character_delete_image'),
    path('characters/<uuid:character_id>/set-primary-image/', CharacterSetPrimaryImageView.as_view(), name='character_set_primary_image'),
    path('characters/<uuid:character_id>/tts-backstory/', CharacterTextToSpeechView.as_view(), name='character_tts_backstory'),

    # Games (New Event-Driven UI)
    path('games/', include('games.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
