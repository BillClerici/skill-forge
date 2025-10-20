"""
Neo4j Scene-Objective Assignment Persistence
Stores scene-to-objective relationships and knowledge/item provisions in Neo4j graph database
"""
import logging
from typing import Dict, Any, List
from neo4j import Driver

logger = logging.getLogger(__name__)


async def persist_scene_assignments_to_neo4j(state: Dict[str, Any], driver: Driver) -> None:
    """
    Create scene-objective relationships in Neo4j.

    Creates:
    - Scene -[:ADVANCES]-> QuestObjective relationships
    - Scene -[:ADVANCES]-> CampaignObjective relationships
    - Scene -[:PROVIDES]-> Knowledge relationships
    - Scene -[:PROVIDES]-> Item relationships
    - Sets is_required property on scenes
    - Tracks acquisition methods

    Args:
        state: Campaign workflow state with scene_objective_assignments
        driver: Neo4j driver instance
    """
    try:
        logger.info("Persisting scene-objective assignments to Neo4j...")

        campaign_id = state.get("final_campaign_id")
        if not campaign_id:
            logger.warning("No campaign_id found - skipping scene assignment persistence")
            return

        scene_assignments = state.get("scene_objective_assignments", [])
        if not scene_assignments:
            logger.warning("No scene assignments found - skipping")
            return

        with driver.session() as session:
            relationships_created = 0

            for assignment in scene_assignments:
                scene_id = assignment.get("scene_id")
                scene_name = assignment.get("scene_name")

                # 1. Update Scene node with assignment metadata
                session.run("""
                    MATCH (s:Scene {id: $scene_id})
                    SET s.is_required = $is_required,
                        s.is_redundant = $is_redundant,
                        s.assignment_updated_at = datetime()
                """, {
                    "scene_id": scene_id,
                    "is_required": assignment.get("is_required", False),
                    "is_redundant": assignment.get("is_redundant", False)
                })

                # 2. Create Scene -[:ADVANCES]-> QuestObjective relationships
                for quest_obj_id in assignment.get("advances_quest_objectives", []):
                    session.run("""
                        MATCH (s:Scene {id: $scene_id})
                        MATCH (qo:QuestObjective {id: $quest_obj_id})
                        MERGE (s)-[:ADVANCES {
                            type: 'quest_objective',
                            created_at: datetime()
                        }]->(qo)
                    """, {
                        "scene_id": scene_id,
                        "quest_obj_id": quest_obj_id
                    })
                    relationships_created += 1

                # 3. Create Scene -[:ADVANCES]-> CampaignObjective relationships
                for campaign_obj_id in assignment.get("advances_campaign_objectives", []):
                    session.run("""
                        MATCH (s:Scene {id: $scene_id})
                        MATCH (co:CampaignObjective {id: $campaign_obj_id})
                        MERGE (s)-[:ADVANCES {
                            type: 'campaign_objective',
                            created_at: datetime()
                        }]->(co)
                    """, {
                        "scene_id": scene_id,
                        "campaign_obj_id": campaign_obj_id
                    })
                    relationships_created += 1

                # 4. Link Scene -[:PROVIDES]-> Knowledge
                for kg_spec in assignment.get("provides_knowledge", []):
                    domain = kg_spec.get("domain", kg_spec.get("knowledge_id", ""))
                    max_level = kg_spec.get("max_level", 3)

                    # Match knowledge by domain/type and create provision relationship
                    session.run("""
                        MATCH (s:Scene {id: $scene_id})
                        MATCH (k:Knowledge)
                        WHERE k.campaign_id = $campaign_id
                          AND (k.knowledge_type CONTAINS $domain
                               OR k.name CONTAINS $domain
                               OR k.primary_dimension CONTAINS $domain)
                        MERGE (s)-[:PROVIDES {
                            resource_type: 'knowledge',
                            domain: $domain,
                            max_level: $max_level,
                            created_at: datetime()
                        }]->(k)
                    """, {
                        "scene_id": scene_id,
                        "campaign_id": campaign_id,
                        "domain": domain.lower(),
                        "max_level": max_level
                    })

                # 5. Link Scene -[:PROVIDES]-> Item
                for item_spec in assignment.get("provides_items", []):
                    category = item_spec.get("category", item_spec.get("item_id", ""))
                    quantity = item_spec.get("quantity", 1)

                    # Match items by category/type and create provision relationship
                    session.run("""
                        MATCH (s:Scene {id: $scene_id})
                        MATCH (i:Item)
                        WHERE i.campaign_id = $campaign_id
                          AND (i.item_type CONTAINS $category
                               OR i.name CONTAINS $category)
                        MERGE (s)-[:PROVIDES {
                            resource_type: 'item',
                            category: $category,
                            quantity: $quantity,
                            created_at: datetime()
                        }]->(i)
                    """, {
                        "scene_id": scene_id,
                        "campaign_id": campaign_id,
                        "category": category.lower(),
                        "quantity": quantity
                    })

                # 6. Store acquisition methods as scene properties
                acquisition_methods = assignment.get("acquisition_methods", [])
                if acquisition_methods:
                    session.run("""
                        MATCH (s:Scene {id: $scene_id})
                        SET s.acquisition_methods = $methods
                    """, {
                        "scene_id": scene_id,
                        "methods": [method.get("method_type", "unknown") for method in acquisition_methods]
                    })

                logger.debug(f"Persisted assignments for scene: {scene_name[:50]}...")

        logger.info(f"✓ Created {relationships_created} scene-objective relationships in Neo4j")

    except Exception as e:
        logger.error(f"Error persisting scene assignments to Neo4j: {str(e)}")
        raise


async def persist_acquisition_paths_to_neo4j(state: Dict[str, Any], driver: Driver) -> None:
    """
    Create detailed acquisition path relationships linking encounters to resources.

    Creates:
    - NPC -[:TEACHES]-> Knowledge (already exists, enhance with scene context)
    - NPC -[:GIVES]-> Item (already exists, enhance with scene context)
    - Discovery -[:REVEALS]-> Knowledge
    - Discovery -[:CONTAINS]-> Item
    - Challenge -[:REWARDS {on_success}]-> Knowledge
    - Challenge -[:REWARDS {on_success}]-> Item
    - Event -[:GRANTS]-> Knowledge/Item

    Args:
        state: Campaign workflow state with scene_objective_assignments and elements
        driver: Neo4j driver instance
    """
    try:
        logger.info("Persisting detailed acquisition paths to Neo4j...")

        campaign_id = state.get("final_campaign_id")
        if not campaign_id:
            return

        scene_assignments = state.get("scene_objective_assignments", [])

        with driver.session() as session:
            for assignment in scene_assignments:
                scene_id = assignment.get("scene_id")

                # Process acquisition methods
                for method in assignment.get("acquisition_methods", []):
                    method_type = method.get("method_type")  # npc, discovery, challenge, event
                    encounter_id = method.get("encounter_id")
                    resource_type = method.get("resource_type")  # knowledge or item
                    resource_id = method.get("resource_id")

                    if not all([method_type, encounter_id, resource_type, resource_id]):
                        continue

                    # Map method type to relationship type
                    rel_type_map = {
                        ("npc", "knowledge"): "TEACHES",
                        ("npc", "item"): "GIVES",
                        ("discovery", "knowledge"): "REVEALS",
                        ("discovery", "item"): "CONTAINS",
                        ("challenge", "knowledge"): "REWARDS",
                        ("challenge", "item"): "REWARDS",
                        ("event", "knowledge"): "GRANTS",
                        ("event", "item"): "GRANTS"
                    }

                    rel_type = rel_type_map.get((method_type, resource_type))
                    if not rel_type:
                        continue

                    # Determine encounter node label
                    label_map = {
                        "npc": "NPC",
                        "discovery": "Discovery",
                        "challenge": "Challenge",
                        "event": "Event"
                    }
                    encounter_label = label_map.get(method_type, "Encounter")

                    # Determine resource node label
                    resource_label = "Knowledge" if resource_type == "knowledge" else "Item"

                    # Create the acquisition relationship
                    session.run(f"""
                        MATCH (e:{encounter_label} {{id: $encounter_id}})
                        MATCH (r:{resource_label} {{id: $resource_id}})
                        MATCH (s:Scene {{id: $scene_id}})
                        MERGE (e)-[rel:{rel_type}]->(r)
                        SET rel.scene_id = $scene_id,
                            rel.method = $method_type,
                            rel.created_at = datetime()
                    """, {
                        "encounter_id": encounter_id,
                        "resource_id": resource_id,
                        "scene_id": scene_id,
                        "method_type": method_type
                    })

        logger.info("✓ Detailed acquisition paths persisted to Neo4j")

    except Exception as e:
        logger.error(f"Error persisting acquisition paths: {str(e)}")
        # Non-critical, don't raise


async def persist_redundancy_analysis_to_neo4j(state: Dict[str, Any], driver: Driver) -> None:
    """
    Analyze and store redundancy information for critical resources.

    For each Knowledge/Item:
    - Count number of acquisition paths
    - Mark as single_path_only (warning) or has_redundancy
    - Store redundancy_score

    Args:
        state: Campaign workflow state
        driver: Neo4j driver instance
    """
    try:
        logger.info("Analyzing and persisting redundancy information...")

        campaign_id = state.get("final_campaign_id")
        if not campaign_id:
            return

        with driver.session() as session:
            # Analyze Knowledge redundancy
            session.run("""
                MATCH (k:Knowledge {campaign_id: $campaign_id})
                OPTIONAL MATCH (e)-[rel]->(k)
                WHERE type(rel) IN ['TEACHES', 'REVEALS', 'REWARDS', 'GRANTS']
                WITH k, count(DISTINCT e) as path_count
                SET k.redundancy_paths = path_count,
                    k.has_redundancy = CASE WHEN path_count >= 2 THEN true ELSE false END,
                    k.single_path_warning = CASE WHEN path_count = 1 THEN true ELSE false END,
                    k.redundancy_updated_at = datetime()
            """, {"campaign_id": campaign_id})

            # Analyze Item redundancy
            session.run("""
                MATCH (i:Item {campaign_id: $campaign_id})
                OPTIONAL MATCH (e)-[rel]->(i)
                WHERE type(rel) IN ['GIVES', 'CONTAINS', 'REWARDS', 'GRANTS']
                WITH i, count(DISTINCT e) as path_count
                SET i.redundancy_paths = path_count,
                    i.has_redundancy = CASE WHEN path_count >= 2 THEN true ELSE false END,
                    i.single_path_warning = CASE WHEN path_count = 1 THEN true ELSE false END,
                    i.redundancy_updated_at = datetime()
            """, {"campaign_id": campaign_id})

            # Get counts for logging
            result = session.run("""
                MATCH (r)
                WHERE r.campaign_id = $campaign_id
                  AND (r:Knowledge OR r:Item)
                  AND r.single_path_warning = true
                RETURN count(r) as single_path_count
            """, {"campaign_id": campaign_id})

            single_path_count = result.single()["single_path_count"] if result.peek() else 0

        logger.info(f"✓ Redundancy analysis complete. {single_path_count} resources with single path.")

    except Exception as e:
        logger.error(f"Error analyzing redundancy: {str(e)}")
        # Non-critical, don't raise
