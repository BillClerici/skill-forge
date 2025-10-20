"""
Neo4j Graph Database Service
Tracks relationships, knowledge, and player progression in graph structure
"""
from typing import Dict, Any, List, Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from datetime import datetime

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class Neo4jGraphService:
    """
    Neo4j service for managing game world relationships and knowledge graphs
    """

    def __init__(self):
        self.driver: Optional[AsyncDriver] = None

    async def connect(self):
        """Connect to Neo4j"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )

            # Verify connection
            await self.driver.verify_connectivity()

            logger.info("neo4j_connected", uri=settings.NEO4J_URI)

            # Create indexes and constraints
            await self._create_schema()

        except Exception as e:
            logger.error("neo4j_connection_failed", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from Neo4j"""
        if self.driver:
            await self.driver.close()
            logger.info("neo4j_disconnected")

    async def _create_schema(self):
        """Create Neo4j schema (constraints and indexes)"""
        try:
            async with self.driver.session() as session:
                # Constraints
                constraints = [
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Player) REQUIRE p.player_id IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:NPC) REQUIRE n.npc_id IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (k:Knowledge) REQUIRE k.knowledge_id IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.location_id IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (q:Quest) REQUIRE q.quest_id IS UNIQUE"
                ]

                for constraint in constraints:
                    await session.run(constraint)

                # Indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS FOR (p:Player) ON (p.session_id)",
                    "CREATE INDEX IF NOT EXISTS FOR ()-[r:KNOWS]-() ON (r.timestamp)",
                    "CREATE INDEX IF NOT EXISTS FOR ()-[r:INTERACTED_WITH]-() ON (r.timestamp)"
                ]

                for index in indexes:
                    await session.run(index)

                logger.info("neo4j_schema_created")

        except Exception as e:
            logger.error("schema_creation_failed", error=str(e))

    # ============================================
    # Player Relationships
    # ============================================

    async def create_or_update_player_node(
        self,
        player_id: str,
        session_id: str,
        character_name: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create or update player node in graph

        Args:
            player_id: Player ID
            session_id: Current session ID
            character_name: Character name
            properties: Additional properties

        Returns:
            Success status
        """
        try:
            async with self.driver.session() as session:
                query = """
                MERGE (p:Player {player_id: $player_id})
                SET p.character_name = $character_name,
                    p.current_session_id = $session_id,
                    p.last_active = $timestamp,
                    p += $properties
                RETURN p
                """

                await session.run(
                    query,
                    player_id=player_id,
                    character_name=character_name,
                    session_id=session_id,
                    timestamp=datetime.utcnow().isoformat(),
                    properties=properties or {}
                )

                logger.info("player_node_updated", player_id=player_id)
                return True

        except Exception as e:
            logger.error("player_node_update_failed", error=str(e))
            return False

    async def record_npc_interaction(
        self,
        player_id: str,
        npc_id: str,
        interaction_type: str,
        affinity_change: int,
        session_id: str
    ) -> bool:
        """
        Record player-NPC interaction in graph

        Args:
            player_id: Player ID
            npc_id: NPC ID
            interaction_type: Type of interaction
            affinity_change: Change in affinity
            session_id: Session ID

        Returns:
            Success status
        """
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:Player {player_id: $player_id})
                MERGE (n:NPC {npc_id: $npc_id})
                MERGE (p)-[r:INTERACTED_WITH]->(n)
                ON CREATE SET r.first_interaction = $timestamp,
                              r.interaction_count = 1,
                              r.total_affinity_change = $affinity_change,
                              r.session_id = $session_id
                ON MATCH SET r.last_interaction = $timestamp,
                             r.interaction_count = r.interaction_count + 1,
                             r.total_affinity_change = r.total_affinity_change + $affinity_change
                WITH p, n, r
                CREATE (i:Interaction {
                    interaction_id: $interaction_id,
                    type: $interaction_type,
                    affinity_change: $affinity_change,
                    timestamp: $timestamp,
                    session_id: $session_id
                })
                CREATE (p)-[:HAD_INTERACTION]->(i)-[:WITH_NPC]->(n)
                RETURN r
                """

                await session.run(
                    query,
                    player_id=player_id,
                    npc_id=npc_id,
                    interaction_id=f"interaction_{datetime.utcnow().timestamp()}",
                    interaction_type=interaction_type,
                    affinity_change=affinity_change,
                    timestamp=datetime.utcnow().isoformat(),
                    session_id=session_id
                )

                logger.info(
                    "npc_interaction_recorded",
                    player_id=player_id,
                    npc_id=npc_id,
                    affinity_change=affinity_change
                )
                return True

        except Exception as e:
            logger.error("interaction_recording_failed", error=str(e))
            return False

    # ============================================
    # Knowledge Graph
    # ============================================

    async def record_knowledge_acquired(
        self,
        player_id: str,
        knowledge_id: str,
        knowledge_title: str,
        bloom_level: str,
        source_npc: Optional[str] = None
    ) -> bool:
        """
        Record player acquiring knowledge

        Args:
            player_id: Player ID
            knowledge_id: Knowledge ID
            knowledge_title: Knowledge title
            bloom_level: Bloom's level demonstrated
            source_npc: NPC who revealed knowledge (optional)

        Returns:
            Success status
        """
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:Player {player_id: $player_id})
                MERGE (k:Knowledge {knowledge_id: $knowledge_id})
                ON CREATE SET k.title = $knowledge_title
                MERGE (p)-[r:KNOWS]->(k)
                ON CREATE SET r.acquired_at = $timestamp,
                              r.bloom_level = $bloom_level,
                              r.confidence = 0.5
                ON MATCH SET r.reinforced_at = $timestamp,
                             r.confidence = CASE
                                WHEN r.confidence < 1.0
                                THEN r.confidence + 0.1
                                ELSE 1.0
                             END
                """

                params = {
                    "player_id": player_id,
                    "knowledge_id": knowledge_id,
                    "knowledge_title": knowledge_title,
                    "bloom_level": bloom_level,
                    "timestamp": datetime.utcnow().isoformat()
                }

                if source_npc:
                    query += """
                    WITH p, k, r
                    MATCH (n:NPC {npc_id: $source_npc})
                    MERGE (k)-[:REVEALED_BY]->(n)
                    """
                    params["source_npc"] = source_npc

                await session.run(query, **params)

                logger.info(
                    "knowledge_recorded",
                    player_id=player_id,
                    knowledge_id=knowledge_id
                )
                return True

        except Exception as e:
            logger.error("knowledge_recording_failed", error=str(e))
            return False

    async def get_player_knowledge_graph(self, player_id: str) -> List[Dict[str, Any]]:
        """Get player's knowledge graph"""
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:Player {player_id: $player_id})-[r:KNOWS]->(k:Knowledge)
                OPTIONAL MATCH (k)-[:REVEALED_BY]->(n:NPC)
                OPTIONAL MATCH (k)-[:PREREQUISITE_FOR]->(k2:Knowledge)
                RETURN k.knowledge_id as knowledge_id,
                       k.title as title,
                       r.bloom_level as bloom_level,
                       r.confidence as confidence,
                       r.acquired_at as acquired_at,
                       n.npc_id as source_npc,
                       collect(k2.knowledge_id) as unlocks
                ORDER BY r.acquired_at DESC
                """

                result = await session.run(query, player_id=player_id)

                knowledge_items = []
                async for record in result:
                    knowledge_items.append({
                        "knowledge_id": record["knowledge_id"],
                        "title": record["title"],
                        "bloom_level": record["bloom_level"],
                        "confidence": record["confidence"],
                        "acquired_at": record["acquired_at"],
                        "source_npc": record["source_npc"],
                        "unlocks": record["unlocks"]
                    })

                logger.info(
                    "knowledge_graph_retrieved",
                    player_id=player_id,
                    knowledge_count=len(knowledge_items)
                )

                return knowledge_items

        except Exception as e:
            logger.error("knowledge_graph_retrieval_failed", error=str(e))
            return []

    # ============================================
    # Quest & Location Tracking
    # ============================================

    async def record_location_visit(
        self,
        player_id: str,
        location_id: str,
        location_name: str,
        session_id: str
    ) -> bool:
        """Record player visiting a location"""
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:Player {player_id: $player_id})
                MERGE (l:Location {location_id: $location_id})
                ON CREATE SET l.name = $location_name
                MERGE (p)-[r:VISITED]->(l)
                ON CREATE SET r.first_visit = $timestamp,
                              r.visit_count = 1,
                              r.session_id = $session_id
                ON MATCH SET r.last_visit = $timestamp,
                             r.visit_count = r.visit_count + 1
                RETURN r
                """

                await session.run(
                    query,
                    player_id=player_id,
                    location_id=location_id,
                    location_name=location_name,
                    timestamp=datetime.utcnow().isoformat(),
                    session_id=session_id
                )

                logger.info(
                    "location_visit_recorded",
                    player_id=player_id,
                    location_id=location_id
                )
                return True

        except Exception as e:
            logger.error("location_visit_recording_failed", error=str(e))
            return False

    async def record_quest_progress(
        self,
        player_id: str,
        quest_id: str,
        quest_title: str,
        status: str,
        completion_percentage: int
    ) -> bool:
        """Record player's quest progress"""
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:Player {player_id: $player_id})
                MERGE (q:Quest {quest_id: $quest_id})
                ON CREATE SET q.title = $quest_title
                MERGE (p)-[r:PURSUING]->(q)
                SET r.status = $status,
                    r.completion_percentage = $completion_percentage,
                    r.last_updated = $timestamp
                """

                if status == "completed":
                    query += """
                    SET r.completed_at = $timestamp
                    """

                await session.run(
                    query,
                    player_id=player_id,
                    quest_id=quest_id,
                    quest_title=quest_title,
                    status=status,
                    completion_percentage=completion_percentage,
                    timestamp=datetime.utcnow().isoformat()
                )

                logger.info(
                    "quest_progress_recorded",
                    player_id=player_id,
                    quest_id=quest_id,
                    completion=completion_percentage
                )
                return True

        except Exception as e:
            logger.error("quest_progress_recording_failed", error=str(e))
            return False

    # ============================================
    # Encounter Tracking
    # ============================================

    async def record_encounter(
        self,
        player_id: str,
        encounter_type: str,
        encounter_id: str,
        encounter_name: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Record player encounter with NPC, Event, Discovery, or Challenge

        Args:
            player_id: Player ID
            encounter_type: Type (npc, event, discovery, challenge)
            encounter_id: Encounter ID
            encounter_name: Encounter name
            metadata: Metadata (quest, place, scene, timestamp)

        Returns:
            Success status
        """
        try:
            async with self.driver.session() as session:
                # Map encounter type to node label
                node_label = {
                    "npc": "NPC",
                    "event": "Event",
                    "discovery": "Discovery",
                    "challenge": "Challenge"
                }.get(encounter_type, "Encounter")

                query = f"""
                MATCH (p:Player {{player_id: $player_id}})
                MERGE (e:{node_label} {{encounter_id: $encounter_id}})
                ON CREATE SET e.name = $encounter_name
                MERGE (p)-[r:ENCOUNTERED]->(e)
                ON CREATE SET r.first_encounter = $timestamp,
                              r.encounter_count = 1,
                              r.session_id = $session_id,
                              r.quest_id = $quest_id,
                              r.scene_id = $scene_id
                ON MATCH SET r.last_encounter = $timestamp,
                             r.encounter_count = r.encounter_count + 1
                RETURN r
                """

                await session.run(
                    query,
                    player_id=player_id,
                    encounter_id=encounter_id,
                    encounter_name=encounter_name,
                    timestamp=metadata.get("timestamp", datetime.utcnow().isoformat()),
                    session_id=metadata.get("session_id"),
                    quest_id=metadata.get("quest_id"),
                    scene_id=metadata.get("scene_id")
                )

                logger.info(
                    "encounter_recorded_neo4j",
                    player_id=player_id,
                    encounter_type=encounter_type,
                    encounter_name=encounter_name
                )
                return True

        except Exception as e:
            logger.error("encounter_recording_failed", error=str(e))
            return False

    async def record_knowledge_acquisition_with_source(
        self,
        player_id: str,
        knowledge_id: str,
        knowledge_name: str,
        source_type: str,
        source_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Record knowledge acquisition with source tracking

        Args:
            player_id: Player ID
            knowledge_id: Knowledge ID
            knowledge_name: Knowledge name
            source_type: Source type (npc, discovery, challenge, event)
            source_id: Source entity ID
            metadata: Context metadata

        Returns:
            Success status
        """
        try:
            async with self.driver.session() as session:
                # Map source type to node label
                source_label = {
                    "npc": "NPC",
                    "discovery": "Discovery",
                    "challenge": "Challenge",
                    "event": "Event"
                }.get(source_type, "Source")

                query = f"""
                MATCH (p:Player {{player_id: $player_id}})
                MERGE (k:Knowledge {{knowledge_id: $knowledge_id}})
                ON CREATE SET k.name = $knowledge_name
                MERGE (s:{source_label} {{encounter_id: $source_id}})
                MERGE (p)-[r:ACQUIRED_KNOWLEDGE]->(k)
                ON CREATE SET r.acquired_at = $timestamp,
                              r.session_id = $session_id,
                              r.quest_id = $quest_id,
                              r.scene_id = $scene_id
                MERGE (k)-[:REVEALED_BY]->(s)
                RETURN r
                """

                await session.run(
                    query,
                    player_id=player_id,
                    knowledge_id=knowledge_id,
                    knowledge_name=knowledge_name,
                    source_id=source_id,
                    timestamp=metadata.get("timestamp", datetime.utcnow().isoformat()),
                    session_id=metadata.get("session_id"),
                    quest_id=metadata.get("quest_id"),
                    scene_id=metadata.get("scene_id")
                )

                logger.info(
                    "knowledge_acquisition_recorded_neo4j",
                    player_id=player_id,
                    knowledge_id=knowledge_id,
                    source_type=source_type
                )
                return True

        except Exception as e:
            logger.error("knowledge_acquisition_recording_failed", error=str(e))
            return False

    async def record_item_acquisition_with_source(
        self,
        player_id: str,
        item_id: str,
        item_name: str,
        source_type: str,
        source_id: Optional[str],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Record item acquisition with source tracking

        Args:
            player_id: Player ID
            item_id: Item ID
            item_name: Item name
            source_type: Source type (npc, discovery, challenge, scene)
            source_id: Source entity ID (optional for scene)
            metadata: Context metadata

        Returns:
            Success status
        """
        try:
            async with self.driver.session() as session:
                if source_id:
                    # Map source type to node label
                    source_label = {
                        "npc": "NPC",
                        "discovery": "Discovery",
                        "challenge": "Challenge",
                        "scene": "Location"
                    }.get(source_type, "Source")

                    query = f"""
                    MATCH (p:Player {{player_id: $player_id}})
                    MERGE (i:Item {{item_id: $item_id}})
                    ON CREATE SET i.name = $item_name
                    MERGE (s:{source_label} {{encounter_id: $source_id}})
                    MERGE (p)-[r:ACQUIRED_ITEM]->(i)
                    ON CREATE SET r.acquired_at = $timestamp,
                                  r.session_id = $session_id,
                                  r.quest_id = $quest_id,
                                  r.scene_id = $scene_id
                    MERGE (i)-[:FOUND_AT]->(s)
                    RETURN r
                    """
                else:
                    # No specific source (picked up from scene)
                    query = """
                    MATCH (p:Player {player_id: $player_id})
                    MERGE (i:Item {item_id: $item_id})
                    ON CREATE SET i.name = $item_name
                    MERGE (p)-[r:ACQUIRED_ITEM]->(i)
                    ON CREATE SET r.acquired_at = $timestamp,
                                  r.session_id = $session_id,
                                  r.quest_id = $quest_id,
                                  r.scene_id = $scene_id
                    RETURN r
                    """

                await session.run(
                    query,
                    player_id=player_id,
                    item_id=item_id,
                    item_name=item_name,
                    source_id=source_id,
                    timestamp=metadata.get("timestamp", datetime.utcnow().isoformat()),
                    session_id=metadata.get("session_id"),
                    quest_id=metadata.get("quest_id"),
                    scene_id=metadata.get("scene_id")
                )

                logger.info(
                    "item_acquisition_recorded_neo4j",
                    player_id=player_id,
                    item_id=item_id,
                    source_type=source_type
                )
                return True

        except Exception as e:
            logger.error("item_acquisition_recording_failed", error=str(e))
            return False

    async def get_player_encounter_history(
        self,
        player_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get player's encounter history from graph"""
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:Player {player_id: $player_id})-[r:ENCOUNTERED]->(e)
                RETURN labels(e)[0] as encounter_type,
                       e.encounter_id as encounter_id,
                       e.name as encounter_name,
                       r.encounter_count as count,
                       r.first_encounter as first_encounter,
                       r.last_encounter as last_encounter,
                       r.quest_id as quest_id,
                       r.scene_id as scene_id
                ORDER BY r.last_encounter DESC
                LIMIT $limit
                """

                result = await session.run(query, player_id=player_id, limit=limit)

                encounters = []
                async for record in result:
                    encounters.append({
                        "encounter_type": record["encounter_type"],
                        "encounter_id": record["encounter_id"],
                        "encounter_name": record["encounter_name"],
                        "encounter_count": record["count"],
                        "first_encounter": record["first_encounter"],
                        "last_encounter": record["last_encounter"],
                        "quest_id": record["quest_id"],
                        "scene_id": record["scene_id"]
                    })

                logger.info(
                    "encounter_history_retrieved",
                    player_id=player_id,
                    count=len(encounters)
                )

                return encounters

        except Exception as e:
            logger.error("encounter_history_retrieval_failed", error=str(e))
            return []

    # ============================================
    # Analytics & Insights
    # ============================================

    async def get_player_relationship_network(
        self,
        player_id: str
    ) -> Dict[str, Any]:
        """Get player's complete relationship network"""
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:Player {player_id: $player_id})-[r:INTERACTED_WITH]->(n:NPC)
                OPTIONAL MATCH (p)-[:KNOWS]->(k:Knowledge)-[:REVEALED_BY]->(n)
                RETURN n.npc_id as npc_id,
                       n.name as npc_name,
                       r.interaction_count as interactions,
                       r.total_affinity_change as affinity,
                       r.last_interaction as last_interaction,
                       count(k) as knowledge_shared
                ORDER BY r.total_affinity_change DESC
                """

                result = await session.run(query, player_id=player_id)

                relationships = []
                async for record in result:
                    relationships.append({
                        "npc_id": record["npc_id"],
                        "npc_name": record["npc_name"],
                        "interactions": record["interactions"],
                        "affinity": record["affinity"],
                        "last_interaction": record["last_interaction"],
                        "knowledge_shared": record["knowledge_shared"]
                    })

                return {
                    "player_id": player_id,
                    "relationships": relationships,
                    "total_npcs_met": len(relationships)
                }

        except Exception as e:
            logger.error("relationship_network_retrieval_failed", error=str(e))
            return {"player_id": player_id, "relationships": [], "total_npcs_met": 0}

    async def get_recommended_npcs(
        self,
        player_id: str,
        current_location_id: str
    ) -> List[Dict[str, Any]]:
        """Get recommended NPCs to talk to based on player's knowledge gaps"""
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:Player {player_id: $player_id})
                MATCH (n:NPC)-[:LOCATED_AT]->(:Location {location_id: $location_id})
                OPTIONAL MATCH (p)-[r:INTERACTED_WITH]->(n)
                OPTIONAL MATCH (k:Knowledge)-[:REVEALED_BY]->(n)
                WHERE NOT (p)-[:KNOWS]->(k)
                WITH n, r, count(k) as potential_knowledge
                WHERE r IS NULL OR r.interaction_count < 3
                RETURN n.npc_id as npc_id,
                       n.name as name,
                       potential_knowledge,
                       COALESCE(r.total_affinity_change, 0) as current_affinity
                ORDER BY potential_knowledge DESC, current_affinity ASC
                LIMIT 5
                """

                result = await session.run(
                    query,
                    player_id=player_id,
                    location_id=current_location_id
                )

                recommendations = []
                async for record in result:
                    recommendations.append({
                        "npc_id": record["npc_id"],
                        "name": record["name"],
                        "potential_knowledge": record["potential_knowledge"],
                        "current_affinity": record["current_affinity"],
                        "reason": "Has knowledge you haven't learned yet" if record["potential_knowledge"] > 0 else "You haven't talked much yet"
                    })

                return recommendations

        except Exception as e:
            logger.error("npc_recommendation_failed", error=str(e))
            return []

    # ============================================
    # Objective Cascade System (Campaign Design Integration)
    # ============================================

    async def get_player_objective_progress(
        self,
        player_id: str,
        campaign_id: str
    ) -> Dict[str, Any]:
        """
        Get player's progress on campaign and quest objectives.

        Returns campaign objectives with nested quest objectives,
        showing completion percentage and status for each level.

        Args:
            player_id: Player ID
            campaign_id: Campaign ID

        Returns:
            Dict containing:
            - campaign_objectives: List of campaign objectives with nested quest objectives
            - overall_progress: Overall campaign completion percentage
        """
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (camp:Campaign {id: $campaign_id})-[:HAS_OBJECTIVE]->(co:CampaignObjective)
                OPTIONAL MATCH (co)-[:DECOMPOSES_TO]->(qo:QuestObjective)
                OPTIONAL MATCH (p:Player {player_id: $player_id})-[prog:PROGRESS]->(qo)
                OPTIONAL MATCH (q:Quest)-[:ACHIEVES]->(qo)
                WITH co,
                     collect(DISTINCT {
                         id: qo.id,
                         description: qo.description,
                         status: COALESCE(qo.status, 'not_started'),
                         quest_name: q.name,
                         quest_number: qo.quest_number,
                         blooms_level: qo.blooms_level,
                         progress: COALESCE(prog.percentage, 0),
                         completed_at: prog.completed_at
                     }) as quest_objectives
                OPTIONAL MATCH (p2:Player {player_id: $player_id})-[cprog:PROGRESS]->(co)
                RETURN co.id as id,
                       co.description as description,
                       COALESCE(co.status, 'not_started') as status,
                       COALESCE(cprog.percentage, 0) as completion_percentage,
                       co.completion_criteria as completion_criteria,
                       co.minimum_quests_required as minimum_quests_required,
                       quest_objectives
                ORDER BY co.description
                """

                result = await session.run(
                    query,
                    campaign_id=campaign_id,
                    player_id=player_id
                )

                campaign_objectives = []
                total_progress = 0
                async for record in result:
                    # Filter out empty quest objectives
                    quest_objs = [
                        qo for qo in record["quest_objectives"]
                        if qo.get("id") is not None
                    ]

                    campaign_objectives.append({
                        "id": record["id"],
                        "description": record["description"],
                        "status": record["status"],
                        "completion_percentage": record["completion_percentage"],
                        "completion_criteria": record["completion_criteria"],
                        "minimum_quests_required": record["minimum_quests_required"],
                        "quest_objectives": quest_objs
                    })

                    total_progress += record["completion_percentage"]

                overall_progress = (
                    total_progress / len(campaign_objectives)
                    if campaign_objectives else 0
                )

                logger.info(
                    "objective_progress_retrieved",
                    player_id=player_id,
                    campaign_id=campaign_id,
                    overall_progress=overall_progress
                )

                return {
                    "campaign_objectives": campaign_objectives,
                    "overall_progress": int(overall_progress)
                }

        except Exception as e:
            logger.error("objective_progress_retrieval_failed", error=str(e))
            return {"campaign_objectives": [], "overall_progress": 0}

    async def get_available_acquisition_paths(
        self,
        player_id: str,
        resource_id: str,
        resource_type: str
    ) -> List[Dict[str, Any]]:
        """
        Find all ways to acquire a knowledge/item, showing which paths
        are still available based on player's acquisition status.

        Args:
            player_id: Player ID
            resource_id: Knowledge or Item ID
            resource_type: "knowledge" or "item"

        Returns:
            List of acquisition paths with availability and redundancy info
        """
        try:
            label = "Knowledge" if resource_type == "knowledge" else "Item"

            async with self.driver.session() as session:
                query = f"""
                MATCH (r:{label} {{id: $resource_id}})
                MATCH (e)-[rel]->(r)
                WHERE type(rel) IN ['TEACHES', 'GIVES', 'REVEALS', 'CONTAINS', 'REWARDS', 'GRANTS']
                MATCH (s:Scene)-[:CONTAINS]->(e)

                // Check if player has already acquired this resource
                OPTIONAL MATCH (p:Player {{player_id: $player_id}})-[acq:ACQUIRED]->(r)

                // Get redundancy info
                WITH s, e, type(rel) as rel_type, acq, r.redundancy_paths as total_paths

                RETURN s.id as scene_id,
                       s.name as scene_name,
                       e.id as encounter_id,
                       e.name as encounter_name,
                       labels(e)[0] as encounter_type,
                       rel_type as relationship_type,
                       acq IS NULL as available,
                       CASE
                           WHEN total_paths >= 3 THEN 'high'
                           WHEN total_paths = 2 THEN 'medium'
                           ELSE 'low'
                       END as redundancy_level,
                       COALESCE(s.order_sequence, 0) as scene_order
                ORDER BY scene_order
                """

                result = await session.run(
                    query,
                    resource_id=resource_id,
                    player_id=player_id
                )

                paths = []
                async for record in result:
                    # Map encounter type to method
                    encounter_type = record["encounter_type"].lower()
                    method = {
                        "npc": "npc",
                        "discovery": "discovery",
                        "challenge": "challenge",
                        "event": "event"
                    }.get(encounter_type, encounter_type)

                    paths.append({
                        "method": method,
                        "encounter_id": record["encounter_id"],
                        "encounter_name": record["encounter_name"],
                        "encounter_type": record["encounter_type"],
                        "scene_id": record["scene_id"],
                        "scene_name": record["scene_name"],
                        "available": record["available"],
                        "redundancy_level": record["redundancy_level"]
                    })

                logger.info(
                    "acquisition_paths_retrieved",
                    resource_id=resource_id,
                    resource_type=resource_type,
                    total_paths=len(paths)
                )

                return paths

        except Exception as e:
            logger.error("acquisition_paths_retrieval_failed", error=str(e))
            return []

    async def get_scene_objectives(
        self,
        scene_id: str
    ) -> Dict[str, Any]:
        """
        Get all objectives that can be advanced in this scene,
        plus knowledge and items that can be acquired.

        Args:
            scene_id: Scene ID

        Returns:
            Dict containing objectives, knowledge, and items available in scene
        """
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (s:Scene {id: $scene_id})

                // Quest objectives
                OPTIONAL MATCH (s)-[:ADVANCES]->(qo:QuestObjective)

                // Campaign objectives
                OPTIONAL MATCH (s)-[:ADVANCES]->(co:CampaignObjective)

                // Knowledge provisions - get encounter methods
                OPTIONAL MATCH (s)-[:CONTAINS]->(ek)
                OPTIONAL MATCH (ek)-[rk]->(k:Knowledge)
                WHERE type(rk) IN ['TEACHES', 'REVEALS', 'REWARDS', 'GRANTS']

                // Item provisions - get encounter methods
                OPTIONAL MATCH (s)-[:CONTAINS]->(ei)
                OPTIONAL MATCH (ei)-[ri]->(i:Item)
                WHERE type(ri) IN ['GIVES', 'CONTAINS', 'REWARDS', 'GRANTS']

                RETURN s.id as scene_id,
                       s.name as scene_name,
                       collect(DISTINCT {
                           id: qo.id,
                           description: qo.description,
                           success_criteria: qo.success_criteria
                       }) as quest_objectives,
                       collect(DISTINCT {
                           id: co.id,
                           description: co.description
                       }) as campaign_objectives,
                       collect(DISTINCT {
                           id: k.id,
                           name: k.name,
                           max_level: k.max_level,
                           description: k.description,
                           method: type(rk)
                       }) as knowledge_items,
                       collect(DISTINCT {
                           id: i.id,
                           name: i.name,
                           category: i.category,
                           description: i.description,
                           method: type(ri)
                       }) as item_items
                """

                result = await session.run(query, scene_id=scene_id)
                record = await result.single()

                if not record:
                    return {
                        "scene_id": scene_id,
                        "scene_name": None,
                        "advances_quest_objectives": [],
                        "advances_campaign_objectives": [],
                        "provides_knowledge": [],
                        "provides_items": []
                    }

                # Process knowledge items - group by knowledge ID and collect methods
                knowledge_map = {}
                for k in record["knowledge_items"]:
                    if k.get("id"):
                        kid = k["id"]
                        if kid not in knowledge_map:
                            knowledge_map[kid] = {
                                "id": kid,
                                "name": k.get("name"),
                                "max_level": k.get("max_level"),
                                "description": k.get("description"),
                                "acquisition_methods": []
                            }
                        if k.get("method"):
                            method = k["method"].lower().replace("_", " ")
                            if method not in knowledge_map[kid]["acquisition_methods"]:
                                knowledge_map[kid]["acquisition_methods"].append(method)

                # Process item items - group by item ID and collect methods
                item_map = {}
                for i in record["item_items"]:
                    if i.get("id"):
                        iid = i["id"]
                        if iid not in item_map:
                            item_map[iid] = {
                                "id": iid,
                                "name": i.get("name"),
                                "category": i.get("category"),
                                "description": i.get("description"),
                                "acquisition_methods": []
                            }
                        if i.get("method"):
                            method = i["method"].lower().replace("_", " ")
                            if method not in item_map[iid]["acquisition_methods"]:
                                item_map[iid]["acquisition_methods"].append(method)

                # Filter out empty objectives
                quest_objectives = [
                    qo for qo in record["quest_objectives"]
                    if qo.get("id") is not None
                ]
                campaign_objectives = [
                    co for co in record["campaign_objectives"]
                    if co.get("id") is not None
                ]

                result_data = {
                    "scene_id": record["scene_id"],
                    "scene_name": record["scene_name"],
                    "advances_quest_objectives": quest_objectives,
                    "advances_campaign_objectives": campaign_objectives,
                    "provides_knowledge": list(knowledge_map.values()),
                    "provides_items": list(item_map.values())
                }

                logger.info(
                    "scene_objectives_retrieved",
                    scene_id=scene_id,
                    quest_objectives=len(quest_objectives),
                    knowledge_items=len(knowledge_map),
                    items=len(item_map)
                )

                return result_data

        except Exception as e:
            logger.error("scene_objectives_retrieval_failed", error=str(e))
            return {
                "scene_id": scene_id,
                "scene_name": None,
                "advances_quest_objectives": [],
                "advances_campaign_objectives": [],
                "provides_knowledge": [],
                "provides_items": []
            }

    async def get_dimensional_progress(
        self,
        player_id: str,
        campaign_id: str
    ) -> Dict[str, Any]:
        """
        Get player's dimensional development progress across
        7 dimensions (Physical, Emotional, Intellectual, Social,
        Spiritual, Vocational, Environmental).

        Args:
            player_id: Player ID
            campaign_id: Campaign ID

        Returns:
            Dict with dimensional progress information
        """
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (d:Dimension)

                // Knowledge for this dimension in campaign
                OPTIONAL MATCH (k:Knowledge {campaign_id: $campaign_id})-[:DEVELOPS]->(d)

                // Player's acquired knowledge
                OPTIONAL MATCH (p:Player {player_id: $player_id})-[acq:ACQUIRED]->(k)

                // Challenges for this dimension
                OPTIONAL MATCH (ch:Challenge {campaign_id: $campaign_id})-[:DEVELOPS]->(d)
                OPTIONAL MATCH (p)-[comp:COMPLETED]->(ch)

                WITH d,
                     count(DISTINCT k) as total_knowledge,
                     count(DISTINCT acq) as acquired_knowledge,
                     count(DISTINCT ch) as total_challenges,
                     count(DISTINCT comp) as completed_challenges

                RETURN d.name as dimension_name,
                       total_knowledge,
                       acquired_knowledge,
                       total_challenges,
                       completed_challenges
                ORDER BY d.name
                """

                result = await session.run(
                    query,
                    player_id=player_id,
                    campaign_id=campaign_id
                )

                dimensions = []
                async for record in result:
                    total_knowledge = record["total_knowledge"]
                    acquired_knowledge = record["acquired_knowledge"]
                    total_challenges = record["total_challenges"]
                    completed_challenges = record["completed_challenges"]

                    # Calculate overall progress for this dimension
                    # Weight: 60% knowledge, 40% challenges
                    knowledge_pct = (
                        (acquired_knowledge / total_knowledge * 100)
                        if total_knowledge > 0 else 0
                    )
                    challenges_pct = (
                        (completed_challenges / total_challenges * 100)
                        if total_challenges > 0 else 0
                    )
                    overall_pct = (knowledge_pct * 0.6) + (challenges_pct * 0.4)

                    # Map percentage to level (1-6 based on Bloom's taxonomy)
                    current_level = min(int(overall_pct / 16.67) + 1, 6)
                    target_level = min(current_level + 1, 6)

                    dimensions.append({
                        "name": record["dimension_name"],
                        "current_level": current_level,
                        "target_level": target_level,
                        "percentage": int(overall_pct),
                        "knowledge_acquired": acquired_knowledge,
                        "knowledge_total": total_knowledge,
                        "challenges_completed": completed_challenges,
                        "challenges_total": total_challenges
                    })

                logger.info(
                    "dimensional_progress_retrieved",
                    player_id=player_id,
                    campaign_id=campaign_id,
                    dimensions_tracked=len(dimensions)
                )

                return {"dimensions": dimensions}

        except Exception as e:
            logger.error("dimensional_progress_retrieval_failed", error=str(e))
            return {"dimensions": []}

    async def record_objective_progress(
        self,
        player_id: str,
        objective_id: str,
        objective_type: str,
        completion_percentage: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record player's progress on a specific objective
        (either campaign or quest level).

        Args:
            player_id: Player ID
            objective_id: Objective ID
            objective_type: "campaign" or "quest"
            completion_percentage: 0-100
            metadata: Optional metadata about the progress

        Returns:
            Success status
        """
        try:
            label = "CampaignObjective" if objective_type == "campaign" else "QuestObjective"

            async with self.driver.session() as session:
                query = f"""
                MATCH (p:Player {{player_id: $player_id}})
                MATCH (obj:{label} {{id: $objective_id}})
                MERGE (p)-[prog:PROGRESS]->(obj)
                SET prog.percentage = $percentage,
                    prog.updated_at = $timestamp,
                    prog.metadata = $metadata,
                    prog.status = CASE
                        WHEN $percentage >= 100 THEN 'completed'
                        WHEN $percentage > 0 THEN 'in_progress'
                        ELSE 'not_started'
                    END
                SET obj.status = prog.status

                // If completed, set completion timestamp
                FOREACH (_ IN CASE WHEN $percentage >= 100 THEN [1] ELSE [] END |
                    SET prog.completed_at = $timestamp
                )

                RETURN prog
                """

                await session.run(
                    query,
                    player_id=player_id,
                    objective_id=objective_id,
                    percentage=completion_percentage,
                    timestamp=datetime.utcnow().isoformat(),
                    metadata=metadata or {}
                )

                logger.info(
                    "objective_progress_recorded",
                    player_id=player_id,
                    objective_id=objective_id,
                    objective_type=objective_type,
                    percentage=completion_percentage
                )

                return True

        except Exception as e:
            logger.error("objective_progress_recording_failed", error=str(e))
            return False


# Global instance
neo4j_graph = Neo4jGraphService()
