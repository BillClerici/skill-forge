"""
Migration script to sync existing Species from MongoDB to Neo4j
"""
import os
from pymongo import MongoClient
from neo4j import GraphDatabase

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:zpt9J5fCVti_bqp_P67vzNQqnVUeVixBkyXyR4Pr-3c@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Neo4j connection
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def migrate_species():
    """Migrate all species from MongoDB to Neo4j"""
    species_list = list(db.species_definitions.find())
    print(f"Found {len(species_list)} species in MongoDB")
    
    migrated = 0
    with neo4j_driver.session() as session:
        for species in species_list:
            species_id = species['_id']
            world_id = species.get('world_id')
            region_ids = species.get('regions', [])
            
            # Create Species node and link to World
            session.run("""
                MATCH (w:World {id: $world_id})
                MERGE (s:Species {id: $species_id})
                ON CREATE SET s.name = $species_name,
                             s.type = $species_type,
                             s.category = $category
                MERGE (s)-[:IN_WORLD]->(w)
            """, world_id=world_id,
               species_id=species_id,
               species_name=species.get('species_name', ''),
               species_type=species.get('species_type', ''),
               category=species.get('category', ''))
            
            # Link to regions
            for region_id in region_ids:
                session.run("""
                    MATCH (s:Species {id: $species_id})
                    MATCH (r:Region {id: $region_id})
                    MERGE (s)-[:INHABITS]->(r)
                """, species_id=species_id, region_id=region_id)
            
            migrated += 1
            print(f"Migrated: {species.get('species_name')} ({species_id})")
    
    print(f"\nMigration complete! Migrated {migrated} species to Neo4j")

if __name__ == '__main__':
    migrate_species()
    neo4j_driver.close()
