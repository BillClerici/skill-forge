-- SkillForge RPG - Initial PostgreSQL Schema
-- Phase 1: Foundation - Core Tables with UUID Primary Keys
-- Database: PostgreSQL 16

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- ACCOUNTS TABLE
-- ============================================
CREATE TABLE accounts (
  account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  account_owner_member_id UUID, -- Will reference members.member_id after members table is created
  account_type VARCHAR(50) NOT NULL CHECK (account_type IN ('individual', 'family', 'educational', 'organizational')),

  -- Subscription
  subscription_tier VARCHAR(50),
  subscription_status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (subscription_status IN ('active', 'past_due', 'cancelled', 'suspended')),
  billing_cycle VARCHAR(20) CHECK (billing_cycle IN ('monthly', 'annual')),
  subscription_start_date DATE,
  next_billing_date DATE,

  -- Limits
  max_members INT DEFAULT 1,
  current_member_count INT DEFAULT 1,

  -- Payment
  stripe_customer_id VARCHAR(100),
  stripe_subscription_id VARCHAR(100),

  -- Timestamps
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_accounts_owner ON accounts(account_owner_member_id);
CREATE INDEX idx_accounts_type ON accounts(account_type);
CREATE INDEX idx_accounts_status ON accounts(subscription_status);

-- ============================================
-- MEMBERS TABLE
-- ============================================
CREATE TABLE members (
  member_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  account_id UUID NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,

  -- Identity
  display_name VARCHAR(100) NOT NULL,
  email VARCHAR(255), -- Optional for children
  date_of_birth DATE NOT NULL,

  -- Role & Permissions
  role VARCHAR(20) NOT NULL CHECK (role IN ('owner', 'parent', 'teen', 'child', 'student', 'employee')),
  can_manage_account BOOLEAN DEFAULT FALSE,
  can_manage_members BOOLEAN DEFAULT FALSE,
  can_view_billing BOOLEAN DEFAULT FALSE,

  -- Content Restrictions
  content_restriction_level VARCHAR(20) DEFAULT 'automatic' CHECK (content_restriction_level IN ('automatic', 'custom')),
  allowed_universes JSONB, -- Array of universe_ids
  blocked_universes JSONB,

  -- Time Limits (for children)
  daily_time_limit_minutes INT,
  weekday_time_limit_minutes INT,
  weekend_time_limit_minutes INT,
  quiet_hours_start TIME,
  quiet_hours_end TIME,

  -- Multiplayer Settings
  can_play_with_family BOOLEAN DEFAULT TRUE,
  can_play_with_friends BOOLEAN DEFAULT FALSE,
  can_play_with_strangers BOOLEAN DEFAULT FALSE,
  friend_requests_require_approval BOOLEAN DEFAULT TRUE,

  -- Communication
  can_chat_in_family_campaigns BOOLEAN DEFAULT TRUE,
  can_chat_with_friends BOOLEAN DEFAULT FALSE,
  can_chat_with_strangers BOOLEAN DEFAULT FALSE,

  -- Monitoring (for children)
  parent_can_view_activity BOOLEAN DEFAULT TRUE,
  send_weekly_report_to_parent BOOLEAN DEFAULT TRUE,
  notify_parent_on_new_campaign BOOLEAN DEFAULT TRUE,
  parent_email_for_notifications VARCHAR(255),

  -- Login
  password_hash VARCHAR(255), -- NULL for children using parent login
  last_login TIMESTAMP,
  login_count INT DEFAULT 0,

  -- Status
  is_active BOOLEAN DEFAULT TRUE,

  -- Timestamps
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_members_account ON members(account_id);
CREATE INDEX idx_members_email ON members(email);
CREATE INDEX idx_members_role ON members(role);

-- ============================================
-- MEMBER COGNITIVE PROGRESS TABLE
-- ============================================
CREATE TABLE member_cognitive_progress (
  member_id UUID PRIMARY KEY REFERENCES members(member_id) ON DELETE CASCADE,

  -- Bloom's Taxonomy Mastery
  remember_mastered BOOLEAN DEFAULT FALSE,
  understand_mastered BOOLEAN DEFAULT FALSE,
  apply_mastered BOOLEAN DEFAULT FALSE,
  analyze_progress DECIMAL(3,2) DEFAULT 0.00 CHECK (analyze_progress >= 0.00 AND analyze_progress <= 1.00),
  evaluate_progress DECIMAL(3,2) DEFAULT 0.00 CHECK (evaluate_progress >= 0.00 AND evaluate_progress <= 1.00),
  create_progress DECIMAL(3,2) DEFAULT 0.00 CHECK (create_progress >= 0.00 AND create_progress <= 1.00),

  -- Core Cognitive Skills (1-10 scale)
  empathy_level INT DEFAULT 1 CHECK (empathy_level >= 1 AND empathy_level <= 10),
  strategy_level INT DEFAULT 1 CHECK (strategy_level >= 1 AND strategy_level <= 10),
  creativity_level INT DEFAULT 1 CHECK (creativity_level >= 1 AND creativity_level <= 10),
  courage_level INT DEFAULT 1 CHECK (courage_level >= 1 AND courage_level <= 10),
  collaboration_level INT DEFAULT 1 CHECK (collaboration_level >= 1 AND collaboration_level <= 10),
  resilience_level INT DEFAULT 1 CHECK (resilience_level >= 1 AND resilience_level <= 10),

  -- Meta-Cognitive Insights (stored as JSON)
  problem_solving_patterns JSONB,
  decision_making_patterns JSONB,
  learning_strategies JSONB,

  -- Aggregate Stats
  total_sessions_across_all_profiles INT DEFAULT 0,
  total_playtime_minutes INT DEFAULT 0,

  -- Timestamps
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- UNIVERSES TABLE
-- ============================================
CREATE TABLE universes (
  universe_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  universe_name VARCHAR(255) NOT NULL,
  universe_type VARCHAR(30) NOT NULL CHECK (universe_type IN ('content_rating', 'age_focused', 'gameplay_style', 'context_based')),
  purpose TEXT,
  description TEXT,

  -- Target Audience
  target_age_min INT,
  target_age_max INT,
  target_users JSONB, -- ["students", "teachers", "families"]

  -- Content Guidelines
  max_content_rating VARCHAR(10), -- G, PG, PG-13, R, M
  violence_level VARCHAR(20),
  language_level VARCHAR(20),
  themes_allowed JSONB,
  themes_prohibited JSONB,

  -- Features
  features JSONB, -- teacher_dashboard, leaderboards, etc.
  modifications JSONB, -- AI behavior, pacing, etc.

  -- Administrative
  creator_type VARCHAR(20) DEFAULT 'official' CHECK (creator_type IN ('official', 'community')),
  requires_certification BOOLEAN DEFAULT FALSE,
  subscription_tier VARCHAR(50),

  -- Timestamps
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_universes_type ON universes(universe_type);
CREATE INDEX idx_universes_rating ON universes(max_content_rating);
CREATE INDEX idx_universes_age ON universes(target_age_min, target_age_max);

-- ============================================
-- WORLDS TABLE
-- ============================================
CREATE TABLE worlds (
  world_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  world_name VARCHAR(255) NOT NULL,

  -- Genre (Now at World level!)
  genre VARCHAR(50) NOT NULL, -- fantasy, scifi, horror, etc.
  subgenre VARCHAR(50),

  -- Setting
  setting_type VARCHAR(50),
  setting_description TEXT,

  -- Content
  base_content_rating VARCHAR(10),
  themes JSONB,
  cognitive_focus JSONB,

  -- Structure
  geographic_type VARCHAR(50),
  size_scale VARCHAR(50),
  population_total BIGINT,

  -- Visual
  visual_style VARCHAR(100),
  art_direction TEXT,
  tone TEXT,

  -- Compatibility
  can_be_adapted_to JSONB, -- ["family_friendly", "educational"]
  available_in_universes JSONB, -- References to universe_ids

  -- Versioning
  is_base_version BOOLEAN DEFAULT TRUE,
  parent_world_id UUID REFERENCES worlds(world_id),

  -- Administrative
  creator_id UUID,
  creator_type VARCHAR(20) DEFAULT 'official' CHECK (creator_type IN ('official', 'community')),
  certification JSONB, -- ["educator_approved", "age_appropriate"]

  -- Stats
  play_count INT DEFAULT 0,
  rating_average DECIMAL(3,2),
  rating_count INT DEFAULT 0,

  -- Timestamps
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_worlds_genre ON worlds(genre);
CREATE INDEX idx_worlds_rating ON worlds(base_content_rating);
CREATE INDEX idx_worlds_creator ON worlds(creator_id);

-- ============================================
-- UNIVERSE-WORLD MAPPINGS TABLE
-- ============================================
CREATE TABLE universe_world_mappings (
  mapping_id BIGSERIAL PRIMARY KEY,
  universe_id UUID NOT NULL REFERENCES universes(universe_id) ON DELETE CASCADE,
  world_id UUID NOT NULL REFERENCES worlds(world_id) ON DELETE CASCADE,

  -- Adaptation Info
  requires_adaptation BOOLEAN DEFAULT FALSE,
  adaptation_level VARCHAR(20) CHECK (adaptation_level IN ('none', 'light', 'moderate', 'heavy')),
  adapted_world_version_id UUID REFERENCES worlds(world_id),

  -- Modifications Applied
  modifications_applied JSONB,

  -- Visibility
  is_featured BOOLEAN DEFAULT FALSE,
  is_recommended BOOLEAN DEFAULT FALSE,
  display_order INT,

  -- Administrative
  approved_by UUID,
  approved_at TIMESTAMP,

  -- Timestamps
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE(universe_id, world_id)
);

CREATE INDEX idx_uwm_universe ON universe_world_mappings(universe_id);
CREATE INDEX idx_uwm_world ON universe_world_mappings(world_id);
CREATE INDEX idx_uwm_featured ON universe_world_mappings(is_featured);

-- ============================================
-- PLAYER PROFILES TABLE
-- ============================================
CREATE TABLE player_profiles (
  profile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  member_id UUID NOT NULL REFERENCES members(member_id) ON DELETE CASCADE,

  -- Character Info
  character_name VARCHAR(100) NOT NULL,
  universe_id UUID NOT NULL REFERENCES universes(universe_id),
  world_id UUID NOT NULL REFERENCES worlds(world_id),
  archetype VARCHAR(100),

  -- Appearance
  appearance_data JSONB, -- Visual customization
  portrait_url VARCHAR(500),

  -- World-Specific Knowledge (Character-specific)
  world_knowledge_level DECIMAL(3,2) DEFAULT 0.00 CHECK (world_knowledge_level >= 0.00 AND world_knowledge_level <= 1.00),
  discovered_locations JSONB,
  known_npcs JSONB,
  completed_quests JSONB,

  -- Character Stats
  total_playtime_minutes INT DEFAULT 0,
  character_level INT DEFAULT 1,
  character_achievements JSONB,

  -- Status
  is_active BOOLEAN DEFAULT TRUE,

  -- Timestamps
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_played_at TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_profiles_member ON player_profiles(member_id);
CREATE INDEX idx_profiles_universe_world ON player_profiles(universe_id, world_id);
CREATE INDEX idx_profiles_active ON player_profiles(is_active);
CREATE INDEX idx_profiles_last_played ON player_profiles(last_played_at);

-- ============================================
-- CAMPAIGNS TABLE
-- ============================================
CREATE TABLE campaigns (
  campaign_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_name VARCHAR(255) NOT NULL,

  -- World Context
  universe_id UUID NOT NULL REFERENCES universes(universe_id),
  world_id UUID NOT NULL REFERENCES worlds(world_id),

  -- Campaign Type
  campaign_type VARCHAR(30) NOT NULL CHECK (campaign_type IN ('solo', 'multiplayer_coop', 'family', 'competitive')),
  max_players INT DEFAULT 1,
  current_player_count INT DEFAULT 0,

  -- State
  state_model VARCHAR(20) DEFAULT 'instanced' CHECK (state_model IN ('shared', 'instanced', 'hybrid')),
  current_chapter INT DEFAULT 1,
  campaign_progress DECIMAL(3,2) DEFAULT 0.00 CHECK (campaign_progress >= 0.00 AND campaign_progress <= 1.00),

  -- Timestamps
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_session_at TIMESTAMP,
  completed_at TIMESTAMP
);

CREATE INDEX idx_campaigns_universe_world ON campaigns(universe_id, world_id);
CREATE INDEX idx_campaigns_type ON campaigns(campaign_type);
CREATE INDEX idx_campaigns_last_session ON campaigns(last_session_at);

-- ============================================
-- CAMPAIGN PARTICIPANTS TABLE
-- ============================================
CREATE TABLE campaign_participants (
  participant_id BIGSERIAL PRIMARY KEY,
  campaign_id UUID NOT NULL REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
  profile_id UUID NOT NULL REFERENCES player_profiles(profile_id) ON DELETE CASCADE,
  member_id UUID NOT NULL REFERENCES members(member_id) ON DELETE CASCADE, -- Denormalized for easy lookups

  -- Participation
  role VARCHAR(50), -- party_leader, member, spectator
  joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_active_at TIMESTAMP,
  is_active BOOLEAN DEFAULT TRUE,

  -- Session Stats
  sessions_participated INT DEFAULT 0,
  total_playtime_minutes INT DEFAULT 0,

  -- Constraint: One profile per member per campaign (prevents multi-boxing)
  UNIQUE(campaign_id, member_id)
);

CREATE INDEX idx_participants_campaign ON campaign_participants(campaign_id);
CREATE INDEX idx_participants_profile ON campaign_participants(profile_id);
CREATE INDEX idx_participants_member ON campaign_participants(member_id);
CREATE INDEX idx_participants_active ON campaign_participants(is_active);

-- ============================================
-- ACTIVITY LOGS TABLE (For Parental Monitoring)
-- ============================================
CREATE TABLE activity_logs (
  log_id BIGSERIAL PRIMARY KEY,
  member_id UUID NOT NULL REFERENCES members(member_id) ON DELETE CASCADE,
  profile_id UUID REFERENCES player_profiles(profile_id) ON DELETE SET NULL,
  campaign_id UUID REFERENCES campaigns(campaign_id) ON DELETE SET NULL,

  -- Activity Details
  activity_type VARCHAR(50) NOT NULL CHECK (activity_type IN (
    'session_start',
    'session_end',
    'character_created',
    'campaign_joined',
    'achievement_earned',
    'content_blocked',
    'time_limit_reached',
    'universe_accessed',
    'multiplayer_interaction'
  )),
  activity_data JSONB,

  -- Duration (for sessions)
  duration_minutes INT,

  -- Content
  universe_id UUID,
  content_rating VARCHAR(10),

  -- Timestamp
  occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_member_date ON activity_logs(member_id, occurred_at);
CREATE INDEX idx_activity_type ON activity_logs(activity_type);
CREATE INDEX idx_activity_occurred ON activity_logs(occurred_at);

-- ============================================
-- ADD FOREIGN KEY CONSTRAINT TO ACCOUNTS
-- (After members table exists)
-- ============================================
ALTER TABLE accounts
  ADD CONSTRAINT fk_accounts_owner
  FOREIGN KEY (account_owner_member_id)
  REFERENCES members(member_id)
  ON DELETE SET NULL;

-- ============================================
-- UPDATE TIMESTAMP TRIGGERS
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON accounts
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_members_updated_at BEFORE UPDATE ON members
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_member_cognitive_progress_updated_at BEFORE UPDATE ON member_cognitive_progress
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_universes_updated_at BEFORE UPDATE ON universes
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_worlds_updated_at BEFORE UPDATE ON worlds
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_player_profiles_updated_at BEFORE UPDATE ON player_profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- INITIAL DATA SEED (Optional - for testing)
-- ============================================
-- Uncomment to add sample data for development

-- INSERT INTO accounts (account_type, subscription_tier, subscription_status, max_members)
-- VALUES ('individual', 'standard', 'active', 1);

-- End of migration
