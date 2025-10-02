#!/bin/bash
# Start SkillForge databases

echo "🚀 Starting SkillForge databases..."

# Start database containers
docker-compose up -d postgres neo4j mongodb redis rabbitmq

echo "⏳ Waiting for databases to be ready..."
sleep 10

# Check PostgreSQL health
echo "Checking PostgreSQL..."
docker-compose exec -T postgres pg_isready -U skillforge_user

# Check if databases are up
docker-compose ps

echo "✅ Databases started! Check status above."
echo ""
echo "Access points:"
echo "  - PostgreSQL: localhost:5432"
echo "  - Neo4j Browser: http://localhost:7474"
echo "  - RabbitMQ Management: http://localhost:15672"
echo "  - MongoDB: localhost:27017"
echo "  - Redis: localhost:6379"
