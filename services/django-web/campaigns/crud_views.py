"""
CRUD API Views for Campaign Entities
Handles Create, Read, Update, Delete operations for:
- Quests, Objectives, Storyline, Places, Scenes, NPCs
- Discoveries, Events, Challenges, Items
"""
import uuid
import json
import logging
from django.views import View
from django.http import JsonResponse
from pymongo import MongoClient
from neo4j import GraphDatabase
import os

logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Neo4j connection
NEO4J_URL = os.getenv('NEO4J_URL', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))


class EntityCRUDAPIView(View):
    """Base class for entity CRUD operations"""

    def update_neo4j_node(self, entity_type, entity_id, data):
        """Update Neo4j node properties"""
        try:
            # Map entity types to Neo4j node labels
            node_labels = {
                'quest': 'Quest',
                'quests': 'Quest',
                'place': 'Place',
                'places': 'Place',
                'scene': 'Scene',
                'scenes': 'Scene',
                'npc': 'NPC',
                'npcs': 'NPC',
                'discovery': 'Discovery',
                'discoveries': 'Discovery',
                'event': 'Event',
                'events': 'Event',
                'challenge': 'Challenge',
                'challenges': 'Challenge',
                'item': 'Item',
                'items': 'Item'
            }

            label = node_labels.get(entity_type)
            if not label:
                return  # Skip Neo4j update for unsupported types

            with neo4j_driver.session() as session:
                # Build SET clause for all provided fields
                set_clauses = []
                params = {'entity_id': entity_id}

                for key, value in data.items():
                    if key not in ['_id', 'id']:  # Skip ID fields
                        param_key = f"prop_{key}"
                        set_clauses.append(f"n.{key} = ${param_key}")
                        params[param_key] = value

                if set_clauses:
                    query = f"""
                    MATCH (n:{label} {{id: $entity_id}})
                    SET {', '.join(set_clauses)}
                    RETURN n
                    """
                    session.run(query, params)
                    logger.info(f"Updated Neo4j {label} node: {entity_id}")

        except Exception as e:
            logger.error(f"Error updating Neo4j node: {e}", exc_info=True)
            # Don't fail the request if Neo4j update fails

    def delete_neo4j_node(self, entity_type, entity_id):
        """Delete Neo4j node and its relationships"""
        try:
            node_labels = {
                'quest': 'Quest',
                'quests': 'Quest',
                'place': 'Place',
                'places': 'Place',
                'scene': 'Scene',
                'scenes': 'Scene',
                'npc': 'NPC',
                'npcs': 'NPC',
                'discovery': 'Discovery',
                'discoveries': 'Discovery',
                'event': 'Event',
                'events': 'Event',
                'challenge': 'Challenge',
                'challenges': 'Challenge',
                'item': 'Item',
                'items': 'Item'
            }

            label = node_labels.get(entity_type)
            if not label:
                return

            with neo4j_driver.session() as session:
                query = f"""
                MATCH (n:{label} {{id: $entity_id}})
                DETACH DELETE n
                """
                session.run(query, {'entity_id': entity_id})
                logger.info(f"Deleted Neo4j {label} node: {entity_id}")

        except Exception as e:
            logger.error(f"Error deleting Neo4j node: {e}", exc_info=True)

    def get_entity_collection(self, entity_type):
        """Get MongoDB collection for entity type"""
        collections = {
            'quest': db.quests,
            'quests': db.quests,  # Support plural form
            'objective': None,  # Stored in campaign document
            'objectives': None,  # Stored in campaign document
            'storyline': None,  # Stored in campaign document
            'place': db.places,
            'places': db.places,  # Support plural form
            'scene': db.scenes,
            'scenes': db.scenes,  # Support plural form
            'npc': db.npcs,
            'npcs': db.npcs,  # Support plural form
            'discovery': db.discoveries,
            'discoveries': db.discoveries,  # Support plural form
            'event': db.events,
            'events': db.events,  # Support plural form
            'challenge': db.challenges,
            'challenges': db.challenges,  # Support plural form
            'item': db.items,
            'items': db.items  # Support plural form
        }
        return collections.get(entity_type)


class GetEntityAPIView(EntityCRUDAPIView):
    """Get a single entity by ID"""

    def get(self, request, campaign_id, entity_type, entity_id):
        try:
            collection = self.get_entity_collection(entity_type)

            if collection is None:
                # Handle special cases (objectives, storyline)
                campaign = db.campaigns.find_one({'_id': campaign_id})
                if not campaign:
                    return JsonResponse({'error': 'Campaign not found'}, status=404)

                if entity_type in ['objective', 'objectives']:
                    objectives = campaign.get('primary_objectives', [])
                    # Find objective by index (entity_id format: "obj_0", "obj_1", etc.)
                    try:
                        idx = int(entity_id.split('_')[1])
                        if 0 <= idx < len(objectives):
                            # Handle both string and dict objectives
                            obj = objectives[idx]
                            if isinstance(obj, str):
                                return JsonResponse({
                                    'id': entity_id,
                                    'name': obj,
                                    'description': obj,
                                    'type': 'objective'
                                })
                            else:
                                return JsonResponse({
                                    'id': entity_id,
                                    'name': obj.get('objective', obj.get('description', 'Objective')),
                                    'description': obj.get('objective', obj.get('description', '')),
                                    'type': 'objective'
                                })
                    except Exception as ex:
                        logger.error(f"Error parsing objective index: {ex}")
                        pass
                    return JsonResponse({'error': 'Objective not found'}, status=404)

                elif entity_type == 'storyline':
                    return JsonResponse({
                        'id': 'storyline_1',
                        'name': 'Campaign Storyline',
                        'content': campaign.get('storyline', ''),
                        'description': campaign.get('storyline', ''),
                        'type': 'storyline'
                    })

                return JsonResponse({'error': 'Entity type not supported'}, status=400)

            # Query normal collection
            entity = collection.find_one({'_id': entity_id})
            if not entity:
                return JsonResponse({'error': f'{entity_type.capitalize()} not found'}, status=404)

            # Convert ObjectId to string
            entity['id'] = str(entity['_id'])
            return JsonResponse(entity)

        except Exception as e:
            logger.error(f"Error getting {entity_type}: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)


class UpdateEntityAPIView(EntityCRUDAPIView):
    """Update an entity"""

    def post(self, request, campaign_id, entity_type, entity_id):
        try:
            data = json.loads(request.body)
            collection = self.get_entity_collection(entity_type)

            if collection is None:
                # Handle special cases
                campaign = db.campaigns.find_one({'_id': campaign_id})
                if not campaign:
                    return JsonResponse({'error': 'Campaign not found'}, status=404)

                if entity_type in ['objective', 'objectives']:
                    objectives = campaign.get('primary_objectives', [])
                    try:
                        idx = int(entity_id.split('_')[1])
                        if 0 <= idx < len(objectives):
                            # Handle both old string format and new object format
                            if 'blooms_level' in data or 'contribution' in data:
                                # New format: save as object with all fields
                                new_value = {
                                    'description': data.get('description', ''),
                                    'blooms_level': data.get('blooms_level'),
                                    'contribution': data.get('contribution', '')
                                }
                            else:
                                # Old format: just description as string
                                new_value = data.get('name', data.get('description', objectives[idx]))

                            objectives[idx] = new_value
                            db.campaigns.update_one(
                                {'_id': campaign_id},
                                {'$set': {'primary_objectives': objectives}}
                            )
                            return JsonResponse({'success': True, 'message': 'Objective updated'})
                    except Exception as ex:
                        logger.error(f"Error updating objective: {ex}")
                        pass
                    return JsonResponse({'error': 'Objective not found'}, status=404)

                elif entity_type == 'storyline':
                    # Update with description or content field
                    new_storyline = data.get('description', data.get('content', ''))
                    db.campaigns.update_one(
                        {'_id': campaign_id},
                        {'$set': {'storyline': new_storyline}}
                    )
                    return JsonResponse({'success': True, 'message': 'Storyline updated'})

                return JsonResponse({'error': 'Entity type not supported'}, status=400)

            # Update normal collection
            result = collection.update_one(
                {'_id': entity_id},
                {'$set': data}
            )

            if result.matched_count == 0:
                return JsonResponse({'error': f'{entity_type.capitalize()} not found'}, status=404)

            # Update Neo4j as well
            self.update_neo4j_node(entity_type, entity_id, data)

            return JsonResponse({'success': True, 'message': f'{entity_type.capitalize()} updated successfully'})

        except Exception as e:
            logger.error(f"Error updating {entity_type}: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)


class DeleteEntityAPIView(EntityCRUDAPIView):
    """Delete an entity"""

    def post(self, request, campaign_id, entity_type, entity_id):
        try:
            collection = self.get_entity_collection(entity_type)

            if collection is None:
                # Handle special cases
                if entity_type in ['objective', 'objectives']:
                    campaign = db.campaigns.find_one({'_id': campaign_id})
                    if not campaign:
                        return JsonResponse({'error': 'Campaign not found'}, status=404)

                    objectives = campaign.get('primary_objectives', [])
                    try:
                        idx = int(entity_id.split('_')[1])
                        if 0 <= idx < len(objectives):
                            objectives.pop(idx)
                            db.campaigns.update_one(
                                {'_id': campaign_id},
                                {'$set': {'primary_objectives': objectives}}
                            )
                            return JsonResponse({'success': True, 'message': 'Objective deleted'})
                    except Exception as ex:
                        logger.error(f"Error deleting objective: {ex}")
                        pass
                    return JsonResponse({'error': 'Objective not found'}, status=404)

                return JsonResponse({'error': 'Cannot delete this entity type'}, status=400)

            # Delete from collection
            result = collection.delete_one({'_id': entity_id})

            if result.deleted_count == 0:
                return JsonResponse({'error': f'{entity_type.capitalize()} not found'}, status=404)

            # Delete from Neo4j
            self.delete_neo4j_node(entity_type, entity_id)

            # Clean up references in MongoDB
            if entity_type in ['quest', 'quests']:
                # Remove from campaign's quest_ids
                db.campaigns.update_one(
                    {'_id': campaign_id},
                    {'$pull': {'quest_ids': entity_id}}
                )
            elif entity_type in ['place', 'places']:
                # Remove from quest's place_ids
                db.quests.update_many(
                    {},
                    {'$pull': {'place_ids': entity_id}}
                )
            elif entity_type in ['scene', 'scenes']:
                # Remove from place's scene_ids
                db.places.update_many(
                    {},
                    {'$pull': {'scene_ids': entity_id}}
                )

            return JsonResponse({'success': True, 'message': f'{entity_type.capitalize()} deleted successfully'})

        except Exception as e:
            logger.error(f"Error deleting {entity_type}: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)


class CreateEntityAPIView(EntityCRUDAPIView):
    """Create a new entity"""

    def post(self, request, campaign_id, entity_type):
        try:
            data = json.loads(request.body)
            collection = self.get_entity_collection(entity_type)

            # Generate new ID
            entity_id = f"{entity_type}_{uuid.uuid4().hex[:16]}"
            data['_id'] = entity_id

            if collection is None:
                # Handle special cases
                if entity_type == 'objective':
                    campaign = db.campaigns.find_one({'_id': campaign_id})
                    if not campaign:
                        return JsonResponse({'error': 'Campaign not found'}, status=404)

                    objectives = campaign.get('primary_objectives', [])
                    objectives.append(data.get('description', 'New Objective'))
                    db.campaigns.update_one(
                        {'_id': campaign_id},
                        {'$set': {'primary_objectives': objectives}}
                    )
                    return JsonResponse({
                        'success': True,
                        'id': f"obj_{len(objectives) - 1}",
                        'message': 'Objective created'
                    })

                return JsonResponse({'error': 'Cannot create this entity type'}, status=400)

            # Insert into collection
            collection.insert_one(data)

            # Add reference to parent
            if entity_type == 'quest':
                db.campaigns.update_one(
                    {'_id': campaign_id},
                    {'$push': {'quest_ids': entity_id}}
                )
            elif entity_type == 'place':
                quest_id = data.get('parent_quest_id')
                if quest_id:
                    db.quests.update_one(
                        {'_id': quest_id},
                        {'$push': {'place_ids': entity_id}}
                    )
            elif entity_type == 'scene':
                place_id = data.get('parent_place_id')
                if place_id:
                    db.places.update_one(
                        {'_id': place_id},
                        {'$push': {'scene_ids': entity_id}}
                    )

            return JsonResponse({
                'success': True,
                'id': entity_id,
                'message': f'{entity_type.capitalize()} created successfully'
            })

        except Exception as e:
            logger.error(f"Error creating {entity_type}: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)


class WorldSpeciesListView(View):
    """API endpoint to get species for a world"""

    def get(self, request, world_id):
        try:
            # Get species IDs from world
            world = db.world_definitions.find_one({'_id': world_id})
            if not world:
                return JsonResponse({'error': 'World not found'}, status=404)

            species_ids = world.get('species', [])
            if not species_ids:
                return JsonResponse({'species': []})

            # Fetch species details
            species_list = list(db.species_definitions.find(
                {'_id': {'$in': species_ids}},
                {'_id': 1, 'species_name': 1}
            ))

            # Format for JSON response
            species_data = [
                {
                    'id': s['_id'],
                    'name': s.get('species_name', 'Unknown')
                }
                for s in species_list
            ]

            # Sort alphabetically by name
            species_data.sort(key=lambda x: x['name'].lower())

            return JsonResponse({'species': species_data})

        except Exception as e:
            logger.error(f"Error fetching species for world {world_id}: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)


class ListScenesAPIView(View):
    """API to list all scenes for a campaign"""

    def get(self, request, campaign_id):
        try:
            # Get campaign
            campaign = db.campaigns.find_one({'_id': campaign_id})
            if not campaign:
                campaign = db.campaign_state.find_one({'_id': campaign_id})
                if not campaign:
                    return JsonResponse({'error': 'Campaign not found'}, status=404)

            # Get all quests and their places
            quest_ids = campaign.get('quest_ids', [])
            quests = list(db.quests.find({'_id': {'$in': quest_ids}})) if quest_ids else []

            place_ids = []
            for quest in quests:
                place_ids.extend(quest.get('place_ids', []))

            places = list(db.places.find({'_id': {'$in': place_ids}})) if place_ids else []

            # Gather all scene IDs from places
            scene_ids = []
            for place in places:
                scene_ids.extend(place.get('scene_ids', []))

            # Get scene documents
            scenes = list(db.scenes.find({'_id': {'$in': scene_ids}})) if scene_ids else []

            # Format scenes for response - sort by order_sequence
            scenes_data = [
                {
                    '_id': scene['_id'],
                    'level_3_location_id': scene.get('level_3_location_id'),
                    'name': scene.get('name', 'Unnamed Scene'),
                    'description': scene.get('description', ''),
                    'order_sequence': scene.get('order_sequence', 0)
                }
                for scene in scenes
            ]

            # Sort by order_sequence
            scenes_data.sort(key=lambda s: s.get('order_sequence', 0))

            return JsonResponse({'scenes': scenes_data})

        except Exception as e:
            logger.error(f"Error fetching scenes for campaign {campaign_id}: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)
