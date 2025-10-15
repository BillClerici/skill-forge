#!/usr/bin/env python3
"""Check Species and NPC data in MongoDB"""
from pymongo import MongoClient
import os

mongo_client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'))
db = mongo_client['skill_forge']

# Get all species
species = list(db.species.find({}, {'_id': 1, 'name': 1, 'world_id': 1}))
print('All Species in database:')
for s in species:
    print(f"  {s.get('name')} - ID: {s.get('_id')} - World: {s.get('world_id')}")

print()
print('Looking for Elf or species_elf_default:')
elf_species = list(db.species.find({'$or': [{'_id': 'species_elf_default'}, {'name': 'Elf'}]}))
if elf_species:
    for s in elf_species:
        print(f"  Found: {s}")
else:
    print('  NOT FOUND')

print()
print('Sample NPC species references:')
npcs = list(db.npcs.find({}, {'_id': 1, 'name': 1, 'species_id': 1, 'species_name': 1}).limit(5))
for npc in npcs:
    print(f"  {npc.get('name')} - species_id: {npc.get('species_id')} - species_name: {npc.get('species_name')}")

print()
print('Count of NPCs with species_elf_default:')
count = db.npcs.count_documents({'species_id': 'species_elf_default'})
print(f"  {count} NPCs")
