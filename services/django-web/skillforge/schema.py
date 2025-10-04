"""
Main GraphQL Schema for SkillForge Django
"""
import graphene
from graphene_django import DjangoObjectType
from accounts.models import Account
from members.models import Player
from pymongo import MongoClient
import os


# MongoDB connection for world building entities
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']


# PostgreSQL Object Types
class AccountType(DjangoObjectType):
    class Meta:
        model = Account
        fields = '__all__'


class PlayerType(DjangoObjectType):
    age = graphene.Int()

    class Meta:
        model = Player
        fields = '__all__'

    def resolve_age(self, info):
        return self.age


# MongoDB Object Types for World Building
class UniverseType(graphene.ObjectType):
    universe_id = graphene.String()
    universe_name = graphene.String()
    max_content_rating = graphene.String()
    description = graphene.String()


class WorldType(graphene.ObjectType):
    world_id = graphene.String()
    world_name = graphene.String()
    description = graphene.String()
    genre = graphene.String()
    themes = graphene.List(graphene.String)
    visual_style = graphene.List(graphene.String)


class RegionType(graphene.ObjectType):
    region_id = graphene.String()
    region_name = graphene.String()
    region_type = graphene.String()
    climate = graphene.String()
    description = graphene.String()
    world_id = graphene.String()


class LocationType(graphene.ObjectType):
    location_id = graphene.String()
    location_name = graphene.String()
    location_type = graphene.String()
    description = graphene.String()
    region_id = graphene.String()
    world_id = graphene.String()


class SpeciesType(graphene.ObjectType):
    species_id = graphene.String()
    species_name = graphene.String()
    species_type = graphene.String()
    category = graphene.String()
    description = graphene.String()
    backstory = graphene.String()
    character_traits = graphene.List(graphene.String)
    world_id = graphene.String()


# Queries
class Query(graphene.ObjectType):
    # Account queries
    all_accounts = graphene.List(AccountType)
    account = graphene.Field(AccountType, account_id=graphene.UUID(required=True))

    # Player queries
    all_players = graphene.List(PlayerType)
    player = graphene.Field(PlayerType, player_id=graphene.UUID(required=True))
    players_by_account = graphene.List(PlayerType, account_id=graphene.UUID(required=True))

    # Universe queries
    all_universes = graphene.List(UniverseType)
    universe = graphene.Field(UniverseType, universe_id=graphene.String(required=True))

    # World queries
    all_worlds = graphene.List(WorldType)
    world = graphene.Field(WorldType, world_id=graphene.String(required=True))
    worlds_by_universe = graphene.List(WorldType, universe_id=graphene.String(required=True))

    # Region queries
    all_regions = graphene.List(RegionType)
    region = graphene.Field(RegionType, region_id=graphene.String(required=True))
    regions_by_world = graphene.List(RegionType, world_id=graphene.String(required=True))

    # Location queries
    all_locations = graphene.List(LocationType)
    location = graphene.Field(LocationType, location_id=graphene.String(required=True))
    locations_by_region = graphene.List(LocationType, region_id=graphene.String(required=True))
    locations_by_world = graphene.List(LocationType, world_id=graphene.String(required=True))

    # Species queries
    all_species = graphene.List(SpeciesType)
    species = graphene.Field(SpeciesType, species_id=graphene.String(required=True))
    species_by_world = graphene.List(SpeciesType, world_id=graphene.String(required=True))

    def resolve_all_accounts(root, info):
        return Account.objects.all()

    def resolve_account(root, info, account_id):
        try:
            return Account.objects.get(account_id=account_id)
        except Account.DoesNotExist:
            return None

    def resolve_all_players(root, info):
        return Player.objects.all()

    def resolve_player(root, info, player_id):
        try:
            return Player.objects.get(player_id=player_id)
        except Player.DoesNotExist:
            return None

    def resolve_players_by_account(root, info, account_id):
        return Player.objects.filter(account_id=account_id)

    # Universe resolvers
    def resolve_all_universes(root, info):
        universes = list(db.universe_definitions.find())
        for u in universes:
            u['universe_id'] = u['_id']
        return universes

    def resolve_universe(root, info, universe_id):
        universe = db.universe_definitions.find_one({'_id': universe_id})
        if universe:
            universe['universe_id'] = universe['_id']
        return universe

    # World resolvers
    def resolve_all_worlds(root, info):
        worlds = list(db.world_definitions.find())
        for w in worlds:
            w['world_id'] = w['_id']
        return worlds

    def resolve_world(root, info, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if world:
            world['world_id'] = world['_id']
        return world

    def resolve_worlds_by_universe(root, info, universe_id):
        worlds = list(db.world_definitions.find({'universe_ids': universe_id}))
        for w in worlds:
            w['world_id'] = w['_id']
        return worlds

    # Region resolvers
    def resolve_all_regions(root, info):
        regions = list(db.region_definitions.find())
        for r in regions:
            r['region_id'] = r['_id']
        return regions

    def resolve_region(root, info, region_id):
        region = db.region_definitions.find_one({'_id': region_id})
        if region:
            region['region_id'] = region['_id']
        return region

    def resolve_regions_by_world(root, info, world_id):
        regions = list(db.region_definitions.find({'world_id': world_id}))
        for r in regions:
            r['region_id'] = r['_id']
        return regions

    # Location resolvers
    def resolve_all_locations(root, info):
        locations = list(db.location_definitions.find())
        for l in locations:
            l['location_id'] = l['_id']
        return locations

    def resolve_location(root, info, location_id):
        location = db.location_definitions.find_one({'_id': location_id})
        if location:
            location['location_id'] = location['_id']
        return location

    def resolve_locations_by_region(root, info, region_id):
        locations = list(db.location_definitions.find({'region_id': region_id}))
        for l in locations:
            l['location_id'] = l['_id']
        return locations

    def resolve_locations_by_world(root, info, world_id):
        locations = list(db.location_definitions.find({'world_id': world_id}))
        for l in locations:
            l['location_id'] = l['_id']
        return locations

    # Species resolvers
    def resolve_all_species(root, info):
        species_list = list(db.species_definitions.find())
        for s in species_list:
            s['species_id'] = s['_id']
        return species_list

    def resolve_species(root, info, species_id):
        species = db.species_definitions.find_one({'_id': species_id})
        if species:
            species['species_id'] = species['_id']
        return species

    def resolve_species_by_world(root, info, world_id):
        species_list = list(db.species_definitions.find({'world_id': world_id}))
        for s in species_list:
            s['species_id'] = s['_id']
        return species_list


# Mutations
class CreateAccount(graphene.Mutation):
    class Arguments:
        account_type = graphene.String(required=True)
        subscription_tier = graphene.String()
        max_members = graphene.Int()

    account = graphene.Field(AccountType)

    @staticmethod
    def mutate(root, info, account_type, subscription_tier=None, max_members=1):
        account = Account(
            account_type=account_type,
            subscription_tier=subscription_tier,
            max_members=max_members
        )
        account.save()
        return CreateAccount(account=account)


class CreatePlayer(graphene.Mutation):
    class Arguments:
        account_id = graphene.UUID(required=True)
        display_name = graphene.String(required=True)
        email = graphene.String()
        date_of_birth = graphene.Date(required=True)
        role = graphene.String(required=True)

    player = graphene.Field(PlayerType)

    @staticmethod
    def mutate(root, info, account_id, display_name, date_of_birth, role, email=None):
        player = Player(
            account_id=account_id,
            display_name=display_name,
            email=email,
            date_of_birth=date_of_birth,
            role=role
        )
        player.save()
        return CreatePlayer(player=player)


class Mutation(graphene.ObjectType):
    create_account = CreateAccount.Field()
    create_player = CreatePlayer.Field()


# Schema
schema = graphene.Schema(query=Query, mutation=Mutation)
