"""
Neo4j Objective Hierarchy Persistence
Stores objective nodes and relationships in Neo4j graph database
"""
import logging
from typing import Dict, Any, List
from neo4j import Driver

logger = logging.getLogger(__name__)


async def persist_objective_hierarchy_to_neo4j(state: Dict[str, Any], driver: Driver) -> None:
    """
    Create objective nodes and relationships in Neo4j.

    Creates:
    - CampaignObjective nodes
    - QuestObjective nodes
    - Relationships: HAS_OBJECTIVE, DECOMPOSES_TO, SUPPORTS, ACHIEVES
    - Knowledge and Item requirement links

    Args:
        state: Campaign workflow state with objective_decompositions
        driver: Neo4j driver instance
    """
    try:
        logger.info("Persisting objective hierarchy to Neo4j...")

        campaign_id = state.get("final_campaign_id")
        if not campaign_id:
            logger.warning("No campaign_id found - skipping objective persistence")
            return

        decompositions = state.get("objective_decompositions", [])
        if not decompositions:
            logger.warning("No objective decompositions found - skipping")
            return

        with driver.session() as session:
            objectives_created = 0

            # Create Campaign Objectives and Quest Objectives
            for decomp in decompositions:
                campaign_obj_id = decomp.get("campaign_objective_id")
                campaign_obj_desc = decomp.get("campaign_objective_description")

                # 1. Create Campaign Objective node
                session.run("""
                    MERGE (co:CampaignObjective {id: $obj_id})
                    SET co.description = $description,
                        co.status = 'not_started',
                        co.completion_criteria = $criteria,
                        co.minimum_quests_required = $min_quests,
                        co.campaign_id = $campaign_id

                    WITH co
                    MATCH (camp:Campaign {id: $campaign_id})
                    MERGE (camp)-[:HAS_OBJECTIVE]->(co)
                """, {
                    "obj_id": campaign_obj_id,
                    "description": campaign_obj_desc,
                    "criteria": decomp.get("completion_criteria", []),
                    "min_quests": decomp.get("minimum_quests_required", 1),
                    "campaign_id": campaign_id
                })

                objectives_created += 1
                logger.debug(f"Created campaign objective: {campaign_obj_desc[:50]}...")

                # 2. Create Quest Objectives
                for qobj in decomp.get("quest_objectives", []):
                    qobj_id = qobj.get("objective_id")
                    qobj_desc = qobj.get("description")
                    quest_num = qobj.get("quest_number", 1)

                    # Create Quest Objective node
                    session.run("""
                        MERGE (qo:QuestObjective {id: $obj_id})
                        SET qo.description = $description,
                            qo.blooms_level = $blooms_level,
                            qo.quest_number = $quest_num,
                            qo.success_criteria = $criteria,
                            qo.status = 'not_started',
                            qo.campaign_id = $campaign_id,
                            qo.is_required = $is_required

                        WITH qo
                        MATCH (co:CampaignObjective {id: $campaign_obj_id})
                        MERGE (qo)-[:SUPPORTS]->(co)
                        MERGE (co)-[:DECOMPOSES_TO]->(qo)
                    """, {
                        "obj_id": qobj_id,
                        "description": qobj_desc,
                        "blooms_level": qobj.get("blooms_level", 3),
                        "quest_num": quest_num,
                        "criteria": qobj.get("success_criteria", []),
                        "campaign_id": campaign_id,
                        "is_required": qobj.get("is_required", True),
                        "campaign_obj_id": campaign_obj_id
                    })

                    objectives_created += 1
                    logger.debug(f"Created quest objective: {qobj_desc[:50]}...")

                    # 3. Link Quest Objective to Quest node
                    # Match quest by order_sequence and campaign_id
                    session.run("""
                        MATCH (qo:QuestObjective {id: $obj_id})
                        MATCH (q:Quest)
                        WHERE q.campaign_id = $campaign_id
                          AND q.order_sequence = $quest_num
                        MERGE (q)-[:ACHIEVES]->(qo)
                    """, {
                        "obj_id": qobj_id,
                        "campaign_id": campaign_id,
                        "quest_num": quest_num
                    })

                    # 4. Link knowledge domain requirements
                    for kg_domain in qobj.get("required_knowledge_domains", []):
                        session.run("""
                            MATCH (qo:QuestObjective {id: $obj_id})
                            MATCH (k:Knowledge)
                            WHERE k.campaign_id = $campaign_id
                              AND (k.knowledge_type CONTAINS $domain
                                   OR k.name CONTAINS $domain
                                   OR k.primary_dimension CONTAINS $domain)
                            MERGE (qo)-[:REQUIRES_KNOWLEDGE {domain: $domain}]->(k)
                        """, {
                            "obj_id": qobj_id,
                            "campaign_id": campaign_id,
                            "domain": kg_domain.lower()
                        })

                    # 5. Link item category requirements
                    for item_category in qobj.get("required_item_categories", []):
                        session.run("""
                            MATCH (qo:QuestObjective {id: $obj_id})
                            MATCH (i:Item)
                            WHERE i.campaign_id = $campaign_id
                              AND (i.item_type CONTAINS $category
                                   OR i.name CONTAINS $category)
                            MERGE (qo)-[:REQUIRES_ITEM {category: $category}]->(i)
                        """, {
                            "obj_id": qobj_id,
                            "campaign_id": campaign_id,
                            "category": item_category.lower()
                        })

        logger.info(f"✓ Created {objectives_created} objective nodes in Neo4j")

    except Exception as e:
        logger.error(f"Error persisting objective hierarchy to Neo4j: {str(e)}")
        raise


async def persist_dimensional_objectives_to_neo4j(state: Dict[str, Any], driver: Driver) -> None:
    """
    Create Dimension nodes and link objectives to dimensions they develop.

    Creates:
    - 7 Dimension nodes (Physical, Emotional, Intellectual, Social, Spiritual, Vocational, Environmental)
    - DEVELOPS relationships from objectives/challenges to dimensions

    Args:
        state: Campaign workflow state
        driver: Neo4j driver instance
    """
    try:
        logger.info("Persisting dimensional development to Neo4j...")

        campaign_id = state.get("final_campaign_id")
        if not campaign_id:
            return

        # Define the 7 dimensions
        dimensions = [
            {"name": "Physical", "description": "Combat, endurance, precision, strength, reflexes"},
            {"name": "Emotional", "description": "Empathy, stress management, self-awareness, emotional regulation"},
            {"name": "Intellectual", "description": "Problem-solving, analysis, memory, logic, creativity"},
            {"name": "Social", "description": "Communication, negotiation, leadership, teamwork, cultural awareness"},
            {"name": "Spiritual", "description": "Ethics, values, purpose, meaning, faith, forgiveness"},
            {"name": "Vocational", "description": "Craftsmanship, skill mastery, innovation, professional development"},
            {"name": "Environmental", "description": "Ecology, resource management, sustainability, conservation"}
        ]

        with driver.session() as session:
            # 1. Create Dimension nodes
            for dim in dimensions:
                session.run("""
                    MERGE (d:Dimension {name: $name})
                    SET d.description = $description
                """, {
                    "name": dim["name"],
                    "description": dim["description"]
                })

            logger.info(f"✓ Created {len(dimensions)} dimension nodes")

            # 2. Link Knowledge entities to dimensions
            for knowledge in state.get("knowledge_entities", []):
                kg_id = knowledge.get("knowledge_id")
                primary_dim = knowledge.get("primary_dimension", "Intellectual")

                if kg_id and primary_dim:
                    session.run("""
                        MATCH (k:Knowledge {id: $kg_id})
                        MATCH (d:Dimension {name: $dim_name})
                        MERGE (k)-[:DEVELOPS {primary: true, bloom_target: $bloom_target}]->(d)
                    """, {
                        "kg_id": kg_id,
                        "dim_name": primary_dim.capitalize(),
                        "bloom_target": knowledge.get("bloom_level_target", 3)
                    })

            # 3. Link Challenges to dimensions
            for challenge in state.get("challenges", []):
                challenge_id = challenge.get("challenge_id")
                primary_dim = challenge.get("primary_dimension", "Physical")
                secondary_dims = challenge.get("secondary_dimensions", [])

                if challenge_id and primary_dim:
                    # Primary dimension
                    session.run("""
                        MATCH (c:Challenge {id: $challenge_id})
                        MATCH (d:Dimension {name: $dim_name})
                        MERGE (c)-[:DEVELOPS {primary: true}]->(d)
                    """, {
                        "challenge_id": challenge_id,
                        "dim_name": primary_dim.capitalize()
                    })

                    # Secondary dimensions
                    for sec_dim in secondary_dims:
                        session.run("""
                            MATCH (c:Challenge {id: $challenge_id})
                            MATCH (d:Dimension {name: $dim_name})
                            MERGE (c)-[:DEVELOPS {secondary: true}]->(d)
                        """, {
                            "challenge_id": challenge_id,
                            "dim_name": sec_dim.capitalize()
                        })

        logger.info("✓ Dimensional development links created")

    except Exception as e:
        logger.error(f"Error persisting dimensional objectives: {str(e)}")
        # Non-critical, don't raise
