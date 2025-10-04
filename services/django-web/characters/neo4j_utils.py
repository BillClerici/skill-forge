"""
Neo4j utilities for Character relationships
"""
import os
from neo4j import GraphDatabase


def get_neo4j_driver():
    """Get Neo4j driver instance"""
    neo4j_uri = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
    return GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))


def create_character_node(character_id, name, player_id):
    """Create a Character node in Neo4j"""
    driver = get_neo4j_driver()
    with driver.session() as session:
        query = """
        MERGE (c:Character {character_id: $character_id})
        SET c.name = $name,
            c.player_id = $player_id,
            c.created_at = datetime()
        RETURN c
        """
        session.run(query,
                   character_id=str(character_id),
                   name=name,
                   player_id=str(player_id))
    driver.close()


def create_character_player_relationship(character_id, player_id):
    """Link Character to their Player (CREATED_BY)"""
    driver = get_neo4j_driver()
    with driver.session() as session:
        query = """
        MATCH (c:Character {character_id: $character_id})
        MATCH (p:Player {player_id: $player_id})
        MERGE (p)-[r:CREATED]->(c)
        SET r.created_at = datetime()
        RETURN r
        """
        session.run(query,
                   character_id=str(character_id),
                   player_id=str(player_id))
    driver.close()


def create_character_world_relationship(character_id, world_id):
    """Link Character to their World (LIVES_IN)"""
    driver = get_neo4j_driver()
    with driver.session() as session:
        query = """
        MATCH (c:Character {character_id: $character_id})
        MATCH (w:World {world_id: $world_id})
        MERGE (c)-[r:LIVES_IN]->(w)
        SET r.created_at = datetime()
        RETURN r
        """
        session.run(query,
                   character_id=str(character_id),
                   world_id=world_id)
    driver.close()


def create_character_species_relationship(character_id, species_id):
    """Link Character to their Species (IS_A)"""
    driver = get_neo4j_driver()
    with driver.session() as session:
        query = """
        MATCH (c:Character {character_id: $character_id})
        MATCH (s:Species {species_id: $species_id})
        MERGE (c)-[r:IS_A]->(s)
        SET r.created_at = datetime()
        RETURN r
        """
        session.run(query,
                   character_id=str(character_id),
                   species_id=species_id)
    driver.close()


def create_character_location_relationship(character_id, location_id, relationship_type='CURRENTLY_AT'):
    """Link Character to a Location"""
    driver = get_neo4j_driver()
    with driver.session() as session:
        query = f"""
        MATCH (c:Character {{character_id: $character_id}})
        MATCH (l:Location {{location_id: $location_id}})
        MERGE (c)-[r:{relationship_type}]->(l)
        SET r.updated_at = datetime()
        RETURN r
        """
        session.run(query,
                   character_id=str(character_id),
                   location_id=location_id)
    driver.close()


def delete_character_node(character_id):
    """Delete Character node and all relationships"""
    driver = get_neo4j_driver()
    with driver.session() as session:
        query = """
        MATCH (c:Character {character_id: $character_id})
        DETACH DELETE c
        """
        session.run(query, character_id=str(character_id))
    driver.close()


def get_character_relationships(character_id):
    """Get all relationships for a character"""
    driver = get_neo4j_driver()
    with driver.session() as session:
        query = """
        MATCH (c:Character {character_id: $character_id})-[r]->(n)
        RETURN type(r) as relationship_type, labels(n) as node_labels, n
        """
        result = session.run(query, character_id=str(character_id))
        relationships = []
        for record in result:
            relationships.append({
                'type': record['relationship_type'],
                'labels': record['node_labels'],
                'node': dict(record['n'])
            })
        driver.close()
        return relationships
