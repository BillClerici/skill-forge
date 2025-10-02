// SkillForge RPG - Initial Neo4j Graph Schema
// Phase 1: Foundation - Graph Relationships with UUID nodes
// Database: Neo4j 5.13

// ============================================
// CREATE CONSTRAINTS (Unique IDs)
// ============================================

// Account nodes
CREATE CONSTRAINT account_id_unique IF NOT EXISTS
FOR (a:Account) REQUIRE a.account_id IS UNIQUE;

// Member nodes
CREATE CONSTRAINT member_id_unique IF NOT EXISTS
FOR (m:Member) REQUIRE m.member_id IS UNIQUE;

// PlayerProfile nodes
CREATE CONSTRAINT profile_id_unique IF NOT EXISTS
FOR (p:PlayerProfile) REQUIRE p.profile_id IS UNIQUE;

// Universe nodes
CREATE CONSTRAINT universe_id_unique IF NOT EXISTS
FOR (u:Universe) REQUIRE u.universe_id IS UNIQUE;

// World nodes
CREATE CONSTRAINT world_id_unique IF NOT EXISTS
FOR (w:World) REQUIRE w.world_id IS UNIQUE;

// Campaign nodes
CREATE CONSTRAINT campaign_id_unique IF NOT EXISTS
FOR (c:Campaign) REQUIRE c.campaign_id IS UNIQUE;

// NPC nodes
CREATE CONSTRAINT npc_id_unique IF NOT EXISTS
FOR (n:NPC) REQUIRE n.npc_id IS UNIQUE;

// ============================================
// CREATE INDEXES FOR PERFORMANCE
// ============================================

// Member role index
CREATE INDEX member_role_idx IF NOT EXISTS
FOR (m:Member) ON (m.role);

// PlayerProfile universe/world index
CREATE INDEX profile_universe_idx IF NOT EXISTS
FOR (p:PlayerProfile) ON (p.universe_id);

CREATE INDEX profile_world_idx IF NOT EXISTS
FOR (p:PlayerProfile) ON (p.world_id);

// World genre index
CREATE INDEX world_genre_idx IF NOT EXISTS
FOR (w:World) ON (w.genre);

// ============================================
// EXAMPLE RELATIONSHIP PATTERNS
// (These will be created by the application)
// ============================================

// Account-Member Relationships:
// CREATE (a:Account {account_id: $account_id})-[:HAS_MEMBER]->(m:Member {member_id: $member_id, role: 'owner'})

// Family Relationships:
// CREATE (parent:Member {member_id: $parent_id})-[:PARENT_OF]->(child:Member {member_id: $child_id})
// CREATE (parent)-[:MANAGES]->(child)

// Member-PlayerProfile Ownership:
// CREATE (m:Member {member_id: $member_id})-[:OWNS]->(p:PlayerProfile {profile_id: $profile_id})

// Universe-World Relationships:
// CREATE (u:Universe {universe_id: $universe_id})-[:CONTAINS {adaptation_level: 'moderate'}]->(w:World {world_id: $world_id})

// Character-World Relationships:
// CREATE (p:PlayerProfile)-[:PLAYS_IN]->(w:World)

// Character-NPC Relationships:
// CREATE (p:PlayerProfile)-[:TRUSTS {level: 8}]->(n:NPC)
// CREATE (p)-[:ALLIED_WITH]->(n)
// CREATE (p)-[:ENEMY_OF {hostility: 10}]->(n)

// Campaign Participation:
// CREATE (p:PlayerProfile)-[:PARTICIPATES_IN {role: 'party_leader', sessions: 5}]->(c:Campaign)

// Skill Dependencies:
// CREATE (skill1:Skill {name: 'Empathy', level: 5})-[:REQUIRES {min_level: 4}]->(skill2:Skill {name: 'Negotiation'})

// Quest Dependencies:
// CREATE (q2:Quest {quest_id: $quest_id2})-[:REQUIRES_COMPLETION]->(q1:Quest {quest_id: $quest_id1})

// ============================================
// SAMPLE QUERIES (For reference)
// ============================================

// Find all family members for an account:
// MATCH (a:Account {account_id: $account_id})-[:HAS_MEMBER]->(m:Member)
// RETURN m

// Find all children of a parent:
// MATCH (parent:Member {member_id: $parent_id})-[:PARENT_OF]->(child:Member)
// RETURN child

// Find all characters for a member:
// MATCH (m:Member {member_id: $member_id})-[:OWNS]->(p:PlayerProfile)
// RETURN p

// Find all worlds in a universe:
// MATCH (u:Universe {universe_id: $universe_id})-[:CONTAINS]->(w:World)
// RETURN w

// Find all campaign participants:
// MATCH (p:PlayerProfile)-[r:PARTICIPATES_IN]->(c:Campaign {campaign_id: $campaign_id})
// RETURN p, r.role, r.sessions

// Find character's NPC relationships:
// MATCH (p:PlayerProfile {profile_id: $profile_id})-[r]->(n:NPC)
// RETURN n, type(r), r

// Find skill dependencies:
// MATCH (s1:Skill)-[r:REQUIRES]->(s2:Skill)
// WHERE s1.name = $skill_name
// RETURN s2, r.min_level

// End of Neo4j initialization script
