# SkillForge: Complete Account & Character System

**Comprehensive User Account, Family Management & Multi-Character Architecture**  
*Individual, Family, Educational, and Organizational Account Types*

*Version 4.1 - Account & Character System Edition*  
*October 1, 2025*

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Account Hierarchy](#account-hierarchy)
3. [Account Types](#account-types)
4. [Family Account System](#family-account-system)
5. [Multi-Character System](#multi-character-system)
6. [Parental Controls](#parental-controls)
7. [Educational Accounts](#educational-accounts)
8. [Subscription Models](#subscription-models)
9. [Technical Implementation](#technical-implementation)
10. [User Flows](#user-flows)
11. [Privacy & Safety](#privacy-safety)

---

# Executive Summary

## The Complete Hierarchy

```
ACCOUNT OWNER (Primary Account Holder)
  ├─ Subscription (Billing & Features)
  ├─ Account Type (Individual, Family, Educational, Organizational)
  │
  └─ ACCOUNT MEMBERS (People who can play)
      ├─ Member 1 (Parent/Owner)
      │   ├─ Player Profile 1 (Seraphina - Fantasy Diplomat)
      │   │   ├─ Campaign A: "The Queen's Quest"
      │   │   ├─ Campaign B: "Northern Alliance" (Multiplayer)
      │   │   └─ Cognitive Progress (Shared across all profiles)
      │   │
      │   ├─ Player Profile 2 (Dr. Chen - Sci-Fi Scientist)
      │   │   ├─ Campaign C: "First Contact"
      │   │   └─ Campaign D: "Colony Crisis"
      │   │
      │   └─ Player Profile 3 (Detective Mercer - Horror)
      │       └─ Campaign E: "The Hospital Mystery"
      │
      ├─ Member 2 (Child, age 10)
      │   ├─ Player Profile 1 (Young Knight - Family Fantasy)
      │   │   └─ Campaign F: "Dragon Friends" (Family Co-Play)
      │   │
      │   └─ Player Profile 2 (Space Cadet - Sci-Fi)
      │       └─ Campaign G: "Junior Explorers"
      │
      └─ Member 3 (Teenager, age 15)
          ├─ Player Profile 1 (Rogue - Fantasy)
          │   ├─ Campaign B: "Northern Alliance" (Same multiplayer as Parent)
          │   └─ Campaign H: "Shadow Guild"
          │
          └─ Player Profile 2 (Hacker - Cyberpunk)
              └─ Campaign I: "Digital Revolution"
```

## Key Features

### Account Level
- **One subscription** covers all family members
- **Account owner** manages billing and permissions
- **Multiple account types** (Individual, Family, Educational, Organizational)

### Member Level
- **Multiple people** can be on one account (family, students, team)
- **Each member** has their own login and privacy
- **Age-based restrictions** automatically applied

### Player Profile Level
- **Multiple characters** per member (play different genres simultaneously)
- **Each character** has unique progression and story
- **Cognitive skills** shared across all characters (transfer learning)

### Campaign Level
- **Multiple active campaigns** per character
- **Characters from same member** cannot be in same campaign (no multi-boxing)
- **Cross-member multiplayer** allowed (family plays together)

---

# Account Hierarchy

## Level 1: Account (Billing Entity)

**Definition:** The top-level entity that owns the subscription and manages billing

**Attributes:**
- Account ID
- Account Owner (primary contact, billing)
- Account Type (Individual, Family, Educational, Organizational)
- Subscription Tier
- Payment Method
- Account Status (Active, Suspended, Cancelled)

**Ownership:**
- One person/organization owns the account
- Owner has full control over account
- Owner manages all members and permissions

---

## Level 2: Account Members (Users/Players)

**Definition:** Individual people who can access the platform under this account

**Attributes:**
- Member ID
- Name
- Email (optional for children)
- Date of Birth
- Age (calculated, affects content access)
- Role (Owner, Parent, Child, Student, Employee)
- Permissions (what they can do)
- Content Restrictions (based on age/parental settings)

**Key Rules:**
- **Individual Account:** 1 member (the owner)
- **Family Account:** Up to 6 members
- **Educational Account:** Up to 30 members (one classroom)
- **Organizational Account:** Unlimited members

---

## Level 3: Player Profiles (Characters)

**Definition:** Individual game characters created by a member

**Attributes:**
- Player Profile ID
- Character Name
- Universe (which universe they play in)
- World (which world they inhabit)
- Archetype (Diplomat, Knight, Scientist, etc.)
- Appearance (visual customization)
- Creation Date
- Last Played

**Key Rules:**
- **Each member can create multiple player profiles** (up to 10)
- **Each profile is independent** with its own story progression
- **Cognitive skills transfer** across all profiles (shared learning)
- **Universe knowledge is profile-specific** (fantasy lore vs. sci-fi lore)

**Why Multiple Profiles?**
- Play different genres simultaneously (fantasy AND sci-fi)
- Try different character types
- Participate in multiple campaigns
- Keep stories separate

---

## Level 4: Campaigns (Game Sessions)

**Definition:** Individual storylines/adventures that a character participates in

**Attributes:**
- Campaign ID
- Name
- Universe & World
- Campaign Type (Solo, Multiplayer)
- Player Profiles in Campaign (list)
- Current Progress
- State Model (Shared, Instanced, Hybrid)
- Last Session Date

**Key Rules:**
- **Each player profile can be in multiple campaigns** (up to 5 active)
- **Characters from same member cannot be in same campaign** (prevents multi-boxing)
- **Characters from different members CAN be in same campaign** (family co-op)
- **Each campaign has independent story progress**

---

# Account Types

## 1. Individual Account 👤

**Definition:** Single user account for one person

**Members:** 1 (the account owner only)

**Use Cases:**
- Adult playing solo
- Teenager with their own account
- Professional using for training
- Individual gamer

**Features:**
- Full access to all content (age-appropriate)
- Create multiple player profiles
- Join multiplayer campaigns with others
- Personal progression tracking

**Subscription Options:**
- Free Tier (limited)
- Standard Tier ($10/month)
- Premium Tier ($20/month)

**Example Structure:**
```
Account: john.smith@email.com
  └─ Member: John Smith (Owner, Age 32)
      ├─ Profile 1: "Gareth" (Fantasy Knight)
      │   ├─ Campaign: "The Shattered Kingdoms"
      │   └─ Campaign: "Northern Alliance" (Multiplayer)
      ├─ Profile 2: "Captain Stone" (Sci-Fi Commander)
      │   └─ Campaign: "Frontier Beyond"
      └─ Profile 3: "Detective Vale" (Horror Investigator)
          └─ Campaign: "Whispers in the Veil"
```

---

## 2. Family Account 👨‍👩‍👧‍👦

**Definition:** Shared account for household family members

**Members:** 2-6 family members

**Use Cases:**
- Parents playing with children
- Siblings sharing account
- Multigenerational household
- Family game nights

**Features:**
- One subscription covers entire family
- Each member has own login
- Parents control children's access
- Age-appropriate content per member
- Family co-play campaigns
- Shared family achievements

**Subscription:**
- Family Tier ($25/month) - Up to 6 members

**Key Benefits:**
- **Cost-effective:** $25/month vs. $10/member = $60 saved
- **Unified management:** Parents control everything
- **Safe for kids:** Age-based restrictions automatic
- **Play together:** Family co-op campaigns

**Example Structure:**
```
Account: smith.family@email.com
  ├─ Member 1: Sarah Smith (Owner/Parent, Age 38)
  │   ├─ Profile 1: "Lady Seraphina" (Fantasy Diplomat)
  │   │   ├─ Campaign: "The Queen's Quest" (Solo)
  │   │   └─ Campaign: "Family Adventure" (Family Co-Play)
  │   └─ Profile 2: "Dr. Sarah Chen" (Sci-Fi Scientist)
  │       └─ Campaign: "First Contact"
  │
  ├─ Member 2: Michael Smith (Parent, Age 40)
  │   ├─ Profile 1: "Sir Michael" (Fantasy Knight)
  │   │   └─ Campaign: "Family Adventure" (Family Co-Play)
  │   └─ Profile 2: "Captain Mike" (Sci-Fi Captain)
  │       └─ Campaign: "Deep Space Patrol"
  │
  ├─ Member 3: Emma Smith (Child, Age 10)
  │   ├─ Profile 1: "Princess Emma" (Family Fantasy)
  │   │   └─ Campaign: "Family Adventure" (Family Co-Play)
  │   └─ Profile 2: "Space Scout Emma" (Kids Sci-Fi)
  │       └─ Campaign: "Junior Explorers"
  │
  ├─ Member 4: Jake Smith (Child, Age 8)
  │   └─ Profile 1: "Jake the Brave" (Family Fantasy)
  │       └─ Campaign: "Family Adventure" (Family Co-Play)
  │
  └─ Member 5: Olivia Smith (Teenager, Age 15)
      ├─ Profile 1: "Shadow" (Fantasy Rogue)
      │   └─ Campaign: "Teen Adventures"
      └─ Profile 2: "Ghost" (Cyberpunk Hacker)
          └─ Campaign: "Neon Rebellion"
```

**Content Access by Member:**
- Sarah & Michael: Adult universes (all content)
- Emma (10): Family-Friendly, Middle Grade universes only
- Jake (8): Family-Friendly, Early Learners universes only
- Olivia (15): Teen Adventures, Young Adult universes

---

## 3. Educational Account 🎓

**Definition:** Account for teachers and classrooms

**Members:** 1 teacher + up to 30 students

**Use Cases:**
- K-12 classroom
- Homeschool co-op
- After-school program
- University course

**Features:**
- Teacher dashboard
- Student progress tracking
- Class management tools
- Curriculum alignment
- Assessment integration
- Discussion prompts
- Session control (pause/resume all)

**Subscription:**
- Education Tier ($50/month per classroom)
- School/District licensing available

**Example Structure:**
```
Account: mrs.johnson.class@school.edu
  ├─ Member 1: Mrs. Johnson (Teacher/Owner, Age 42)
  │   └─ Teacher Dashboard Access (no play profile)
  │
  ├─ Member 2: Student - Alex Martinez (Age 14)
  │   └─ Profile: "Alex the Apprentice" (Educational Fantasy)
  │       └─ Campaign: "Civics Quest" (Class Group A)
  │
  ├─ Member 3: Student - Sam Chen (Age 14)
  │   └─ Profile: "Sam the Scholar" (Educational Fantasy)
  │       └─ Campaign: "Civics Quest" (Class Group A)
  │
  └─ [28 more students...]
```

**Teacher Capabilities:**
- View all student progress
- Create/assign campaigns
- Pause game for whole class
- Export progress reports
- Moderate interactions
- Set session time limits

---

## 4. Organizational Account 🏢

**Definition:** Account for businesses, training programs, therapy practices

**Members:** Unlimited (based on license)

**Use Cases:**
- Corporate training department
- Therapy practice (multiple therapists)
- Professional development
- Research studies

**Features:**
- Organizational dashboard
- Employee/client management
- Performance analytics
- Custom content creation
- API access
- White-label options

**Subscription:**
- Custom enterprise pricing
- Based on member count and features

**Example Structure:**
```
Account: acme.corp.training@company.com
  ├─ Admin: HR Manager (Owner)
  │   └─ Dashboard: Manage all employees
  │
  ├─ Member: Employee 1 (Manager)
  │   └─ Profile: "Leader Profile"
  │       └─ Campaign: "Leadership Development Module"
  │
  └─ [Unlimited employees...]
```

---

# Family Account System (Detailed)

## Family Account Setup

### Step 1: Account Creation

```
╔══════════════════════════════════════════════════════╗
║         CREATE YOUR FAMILY ACCOUNT                   ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Parent/Guardian Information:                        ║
║  Name: [________________]                            ║
║  Email: [________________]                           ║
║  Password: [____________]                            ║
║  Date of Birth: [___/___/____]                       ║
║                                                      ║
║  ☑ I am 18+ and the account owner                   ║
║  ☑ I agree to Terms of Service                      ║
║                                                      ║
║  [Create Account]                                    ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

### Step 2: Choose Account Type

```
╔══════════════════════════════════════════════════════╗
║         CHOOSE YOUR ACCOUNT TYPE                     ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  ○ INDIVIDUAL ACCOUNT ($10/month)                    ║
║    Just for you                                      ║
║    • 1 person                                        ║
║    • Multiple characters                             ║
║                                                      ║
║  ● FAMILY ACCOUNT ($25/month) ⭐ BEST VALUE          ║
║    For your whole household                          ║
║    • Up to 6 family members                          ║
║    • Each person has multiple characters             ║
║    • Parental controls included                      ║
║    • Play together in same campaigns                 ║
║    • Save $35/month vs individual accounts!          ║
║                                                      ║
║  [Continue]                                          ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

### Step 3: Add Family Members

```
╔══════════════════════════════════════════════════════╗
║         ADD FAMILY MEMBERS                           ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  You can add up to 5 more family members.           ║
║  (You can always add more later)                     ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ MEMBER 2                                   │    ║
║  │ Name: [________________]                   │    ║
║  │ Relationship: [Spouse ▼]                   │    ║
║  │ Date of Birth: [___/___/____]              │    ║
║  │ Email (optional): [________________]       │    ║
║  │ ☑ Can manage family settings               │    ║
║  │ [Remove]                                    │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ MEMBER 3                                   │    ║
║  │ Name: [________________]                   │    ║
║  │ Relationship: [Child ▼]                    │    ║
║  │ Date of Birth: [___/___/____] (Age: 10)    │    ║
║  │ Email (optional): [________________]       │    ║
║  │                                             │    ║
║  │ Content Restrictions: Auto (Age-based) ▼    │    ║
║  │ • Family-Friendly Universe: ✓              │    ║
║  │ • Middle Grade Universe: ✓                 │    ║
║  │ • Educational Universe: ✓                  │    ║
║  │ • Teen/Adult Universes: ✗ (too young)      │    ║
║  │                                             │    ║
║  │ [Remove]                                    │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  [+ Add Another Member]                              ║
║                                                      ║
║  [Continue to Payment]                               ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

## Family Member Permissions

### Permission Levels

**1. Account Owner (Parent/Guardian)**
- Full account access
- Manage billing
- Add/remove members
- Set parental controls
- View all activity
- Modify any settings

**2. Parent/Co-Parent**
- Add/remove members (if granted)
- Set parental controls for children
- View children's activity
- Cannot modify billing
- Cannot remove account owner

**3. Teen (13-17)**
- Create own player profiles
- Join age-appropriate campaigns
- Invite friends to campaigns (with approval)
- Cannot modify account settings
- Cannot view other members' details

**4. Child (Under 13)**
- Create own player profiles
- Join age-appropriate campaigns
- Cannot invite external players
- All activity visible to parents
- Heavily restricted content

---

## Family Dashboard

### Parent View

```
╔══════════════════════════════════════════════════════╗
║         FAMILY ACCOUNT DASHBOARD                     ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Smith Family Account                                ║
║  Subscription: Family Plan ($25/month)               ║
║  Next Billing: Nov 1, 2025                           ║
║                                                      ║
║  ═══════════════════════════════════════════════    ║
║                                                      ║
║  FAMILY MEMBERS (4 of 6):                            ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ 👤 Sarah (You) - Parent                    │    ║
║  │ Last Active: Today                          │    ║
║  │ Characters: 2 | Active Campaigns: 3         │    ║
║  │ [View Details]                              │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ 👤 Michael - Spouse                         │    ║
║  │ Last Active: Yesterday                      │    ║
║  │ Characters: 2 | Active Campaigns: 2         │    ║
║  │ [View Details] [Manage]                     │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ 👧 Emma - Child (Age 10)                    │    ║
║  │ Last Active: 2 hours ago                    │    ║
║  │ Characters: 2 | Active Campaigns: 2         │    ║
║  │ Screen Time Today: 1h 15m / 2h limit        │    ║
║  │ Content: Family-Friendly ✓                  │    ║
║  │ [View Details] [Manage] [Set Limits]        │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ 👦 Jake - Child (Age 8)                     │    ║
║  │ Last Active: Today                          │    ║
║  │ Characters: 1 | Active Campaigns: 1         │    ║
║  │ Screen Time Today: 45m / 1h 30m limit       │    ║
║  │ Content: Early Learners ✓                   │    ║
║  │ [View Details] [Manage] [Set Limits]        │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  [+ Add Family Member]                               ║
║                                                      ║
║  ═══════════════════════════════════════════════    ║
║                                                      ║
║  FAMILY CAMPAIGNS:                                   ║
║  • "Family Adventure" (All 4 members playing)        ║
║    Last session: Today                               ║
║    [Continue] [View Progress]                        ║
║                                                      ║
║  ═══════════════════════════════════════════════    ║
║                                                      ║
║  QUICK ACTIONS:                                      ║
║  [Start Family Campaign]                             ║
║  [View Family Achievements]                          ║
║  [Account Settings]                                  ║
║  [Billing]                                           ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

# Multi-Character System

## Why Multiple Characters?

### Use Cases:

**1. Genre Variety**
- Play fantasy AND sci-fi simultaneously
- Try different story types
- Experience multiple universes

**2. Campaign Participation**
- Different friend groups play different campaigns
- Solo campaign + multiplayer campaign
- Family campaign + personal campaign

**3. Experimentation**
- Try different character types
- Test different playstyles
- Learn different cognitive approaches

**4. Story Separation**
- Keep storylines distinct
- Different emotional tones
- Different time commitments

---

## Character Creation & Management

### Creating Multiple Characters

```
╔══════════════════════════════════════════════════════╗
║         YOUR PLAYER PROFILES                         ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  You can create up to 10 characters.                 ║
║  Each character has their own story progression.     ║
║  Your cognitive skills transfer to all characters!   ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ 🏰 SERAPHINA DAWNWHISPER                   │    ║
║  │ Universe: Teen Adventures                   │    ║
║  │ World: The Shattered Kingdoms               │    ║
║  │ Type: Fantasy Diplomat                      │    ║
║  │ Created: Jan 15, 2025                       │    ║
║  │ Active Campaigns: 2                         │    ║
║  │ • "The Queen's Quest" (Solo)                │    ║
║  │ • "Northern Alliance" (Multiplayer)         │    ║
║  │ Last Played: Today                          │    ║
║  │ [Play] [Manage] [Delete]                    │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ 🚀 DR. KIRA CHEN                            │    ║
║  │ Universe: Standard RPG                      │    ║
║  │ World: Frontier Beyond                      │    ║
║  │ Type: Sci-Fi Xenobiologist                  │    ║
║  │ Created: Feb 3, 2025                        │    ║
║  │ Active Campaigns: 1                         │    ║
║  │ • "First Contact Protocol" (Solo)           │    ║
║  │ Last Played: Yesterday                      │    ║
║  │ [Play] [Manage] [Delete]                    │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ 👻 DETECTIVE JAMES MERCER                   │    ║
║  │ Universe: Mature Narratives                 │    ║
║  │ World: Whispers in the Veil                 │    ║
║  │ Type: Horror Investigator                   │    ║
║  │ Created: Mar 12, 2025                       │    ║
║  │ Active Campaigns: 1                         │    ║
║  │ • "The Hospital Mystery" (Solo)             │    ║
║  │ Last Played: Last week                      │    ║
║  │ [Play] [Manage] [Delete]                    │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  [+ Create New Character] (7 slots remaining)        ║
║                                                      ║
║  ═══════════════════════════════════════════════    ║
║                                                      ║
║  UNIVERSAL COGNITIVE PROGRESS:                       ║
║  (Shared across ALL your characters)                 ║
║                                                      ║
║  Bloom's Mastery:                                    ║
║  ✅ Remember  ✅ Understand  ✅ Apply                ║
║  🔄 Analyze (78%)  🔒 Evaluate  🔒 Create           ║
║                                                      ║
║  Core Skills:                                        ║
║  💙 Empathy: ████████░░ 8/10                        ║
║  🎯 Strategy: ███████░░░ 7/10                       ║
║  ✨ Creativity: ██████░░░░ 6/10                     ║
║                                                      ║
║  These skills help ALL your characters!              ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

## Cognitive Skills: Universal vs. Character-Specific

### What Transfers (Universal - Shared Across All Characters)

**Bloom's Taxonomy Mastery:**
- Remember tier completion
- Understand tier completion
- Apply tier completion
- Analyze tier progress
- Evaluate tier progress
- Create tier progress

**Core Cognitive Skills:**
- Empathy level (1-10)
- Strategy level (1-10)
- Creativity level (1-10)
- Courage level (1-10)
- Collaboration level (1-10)
- Resilience level (1-10)

**Meta-Cognitive Insights:**
- Problem-solving approaches learned
- Decision-making patterns
- Learning strategies
- Social interaction skills

**Why This Transfers:**
These are YOUR actual cognitive abilities. Whether you're playing a fantasy diplomat or a sci-fi scientist, YOUR strategic thinking transfers because it's YOU thinking strategically.

---

### What's Character-Specific (Does Not Transfer)

**World Knowledge:**
- Fantasy lore (The Shattered Kingdoms history)
- Sci-Fi technology (How FTL drives work)
- Horror entities (What you've learned about The Between)
- Universe-specific facts

**Relationships:**
- NPC relationships (Queen Aria trusts Seraphina)
- Faction standings (Thieves' Guild likes your rogue)
- Reputation scores
- Social connections

**Story Progress:**
- Quest completion
- Campaign advancement
- Discovered locations
- Unlocked content

**Character Stats:**
- Character-specific achievements
- Playtime on that character
- Unique items/artifacts earned

**Why This Doesn't Transfer:**
These are character-specific experiences. Your fantasy diplomat doesn't know sci-fi technology, even though YOU (the player) do. This maintains immersion and replayability.

---

## Campaign Rules & Restrictions

### Multiple Campaigns Per Character

**Allowed:**
- ✅ Character A in Campaign 1 (Solo)
- ✅ Character A in Campaign 2 (Multiplayer)
- ✅ Character A in Campaign 3 (Different universe)
- ✅ Up to 5 active campaigns per character

**Example:**
```
Player: Sarah Smith
  Character: Seraphina (Fantasy Diplomat)
    ├─ Campaign A: "The Queen's Quest" (Solo)
    ├─ Campaign B: "Northern Alliance" (Multiplayer with friends)
    ├─ Campaign C: "Family Adventure" (Family co-play)
    └─ Campaign D: "Guild Politics" (Another solo arc)
```

---

### Multi-Character Restrictions

**NOT Allowed:**
- ❌ Two characters from same member in same campaign (multi-boxing)
- ❌ Switching characters mid-campaign
- ❌ Transferring items between your own characters

**Example of INVALID Setup:**
```
Player: Sarah Smith
  Character A: Seraphina (Fantasy Diplomat)
    └─ Campaign X: "Northern Alliance" ✓
  
  Character B: Sir Gareth (Fantasy Knight)  
    └─ Campaign X: "Northern Alliance" ❌ BLOCKED!
    
Error: "You cannot have multiple characters in the same campaign.
Choose one character for this campaign."
```

**Why This Rule:**
- Prevents "multi-boxing" (unfair advantage)
- Maintains campaign balance
- Ensures genuine multiplayer interaction
- Prevents self-trading exploits

---

### Cross-Member Multiplayer (Allowed & Encouraged)

**Family Co-Play Example:**
```
Campaign: "Family Adventure"

Members Playing:
  ├─ Mom (Sarah) → Character: Lady Seraphina (Diplomat)
  ├─ Dad (Michael) → Character: Sir Michael (Knight)
  ├─ Daughter (Emma, 10) → Character: Princess Emma (Mage)
  └─ Son (Jake, 8) → Character: Jake the Brave (Scout)

✅ This is ALLOWED and encouraged!
Each person controls ONE character in the shared campaign.
```

**Friend Multiplayer Example:**
```
Campaign: "Northern Alliance"

Players:
  ├─ Sarah (Friend 1) → Character: Seraphina (Diplomat)
  ├─ Alex (Friend 2) → Character: Alex the Rogue (Thief)
  ├─ Jamie (Friend 3) → Character: Jamie Ironforge (Warrior)
  └─ Taylor (Friend 4) → Character: Taylor Brightspell (Mage)

✅ Each player brings ONE character from their account.
```

---

## Campaign Management Interface

### Selecting a Campaign

```
╔══════════════════════════════════════════════════════╗
║         SELECT CHARACTER & CAMPAIGN                  ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Choose a character to play:                         ║
║                                                      ║
║  ● 🏰 Seraphina Dawnwhisper (Fantasy Diplomat)       ║
║  ○ 🚀 Dr. Kira Chen (Sci-Fi Scientist)               ║
║  ○ 👻 Detective Mercer (Horror Investigator)         ║
║                                                      ║
║  [Next]                                              ║
║                                                      ║
╚══════════════════════════════════════════════════════╝

Then:

╔══════════════════════════════════════════════════════╗
║         SERAPHINA'S CAMPAIGNS                        ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Active Campaigns for Seraphina:                     ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ 📜 "THE QUEEN'S QUEST"                     │    ║
║  │ Type: Solo Campaign                         │    ║
║  │ Universe: Teen Adventures                   │    ║
║  │ Progress: Chapter 5 of 12                   │    ║
║  │ Last Played: Today                          │    ║
║  │ Next: Investigate disappearances            │    ║
║  │ [Continue]                                   │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ ⚔️ "NORTHERN ALLIANCE"                      │    ║
║  │ Type: Multiplayer (4 players)               │    ║
║  │ Universe: Standard RPG                      │    ║
║  │ Party:                                       │    ║
║  │  • You (Seraphina - Diplomat)               │    ║
║  │  • Alex (Rogue)                             │    ║
║  │  • Jamie (Warrior)                          │    ║
║  │  • Taylor (Mage)                            │    ║
║  │ Progress: Chapter 8 of 15                   │    ║
║  │ Last Played: Yesterday                      │    ║
║  │ Next Session: Scheduled for tonight 8pm     │    ║
║  │ [Join Session] [Party Chat]                 │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  ┌────────────────────────────────────────────┐    ║
║  │ 👨‍👩‍👧‍👦 "FAMILY ADVENTURE"                     │    ║
║  │ Type: Family Co-Play                        │    ║
║  │ Universe: Family-Friendly                   │    ║
║  │ Family Members:                              │    ║
║  │  • You (Lady Seraphina)                     │    ║
║  │  • Michael (Sir Michael)                    │    ║
║  │  • Emma (Princess Emma)                     │    ║
║  │  • Jake (Jake the Brave)                    │    ║
║  │ Progress: Chapter 3 of 10                   │    ║
║  │ Last Played: Last Sunday                    │    ║
║  │ [Continue] [Schedule Next]                  │    ║
║  └────────────────────────────────────────────┘    ║
║                                                      ║
║  [+ Start New Campaign] (2 slots remaining)          ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

# Parental Controls

## Content Filtering

### Automatic Age-Based Restrictions

**System automatically restricts content based on child's age:**

**Ages 5-7 (Early Learners):**
- ✅ Family-Friendly Universe only
- ✅ Early Learners Universe
- ❌ All other universes blocked

**Ages 8-12 (Middle Grade):**
- ✅ Family-Friendly Universe
- ✅ Middle Grade Universe
- ✅ Educational Universe (age-appropriate worlds)
- ❌ Teen, Adult, Mature content blocked

**Ages 13-17 (Teens):**
- ✅ Teen Adventures Universe
- ✅ Young Adult Universe
- ✅ Educational Universe
- ✅ Standard RPG Universe (PG-13 content)
- ❌ Mature Narratives blocked
- ❌ Adult content blocked

**Ages 18+ (Adults):**
- ✅ All universes available (no restrictions)

---

### Custom Parental Controls

Parents can customize beyond automatic settings:

```
╔══════════════════════════════════════════════════════╗
║         PARENTAL CONTROLS: EMMA (AGE 10)             ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  CONTENT ACCESS:                                     ║
║                                                      ║
║  Allowed Universes:                                  ║
║  ✅ Family-Friendly Universe                         ║
║  ✅ Middle Grade Universe                            ║
║  ✅ Educational Universe                             ║
║  ☐ Family Co-Play Universe (Allow family campaigns) ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  TIME LIMITS:                                        ║
║  Daily Screen Time: [2] hours [Set]                 ║
║  Weekday Limit: [1.5] hours                          ║
║  Weekend Limit: [3] hours                            ║
║                                                      ║
║  Quiet Hours: [8:00 PM] to [7:00 AM] [Set]          ║
║  (No play during these hours)                        ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  MULTIPLAYER:                                        ║
║  ☑ Can play with family members                     ║
║  ☐ Can play with approved friends                   ║
║  ☐ Can play with strangers (Not recommended)        ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  COMMUNICATION:                                      ║
║  ☑ Can chat in family campaigns                     ║
║  ☐ Can chat with approved friends                   ║
║  ☐ Can chat with strangers (Blocked)                ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  MONITORING:                                         ║
║  ☑ Parent can view all activity                     ║
║  ☑ Parent receives weekly progress report           ║
║  ☑ Parent notified of new campaigns                 ║
║  ☑ Parent must approve friend requests              ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  NOTIFICATIONS:                                      ║
║  Parent Email: sarah.smith@email.com                 ║
║  ☑ Notify when time limit reached                   ║
║  ☑ Notify when attempting blocked content           ║
║  ☑ Daily activity summary                           ║
║                                                      ║
║  [Save Settings]                                     ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

## Activity Monitoring

### Parent View of Child's Activity

```
╔══════════════════════════════════════════════════════╗
║         EMMA'S ACTIVITY REPORT                       ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Week of Oct 15-21, 2025                             ║
║                                                      ║
║  SCREEN TIME:                                        ║
║  Total this week: 8 hours 45 minutes                 ║
║  Daily average: 1h 15m (under 2h limit ✓)           ║
║                                                      ║
║  Mon: 1h 30m | Tue: 1h 15m | Wed: 1h 0m             ║
║  Thu: 1h 45m | Fri: 1h 30m | Sat: 1h 45m | Sun: 0m  ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  COGNITIVE PROGRESS:                                 ║
║  Bloom's Tier: Remember → Understand (Progressing!)  ║
║                                                      ║
║  Skills Developed:                                   ║
║  • Empathy: 4/10 → 5/10 ⬆️                          ║
║  • Problem-Solving: 3/10 → 4/10 ⬆️                  ║
║  • Memory: 6/10 (stable)                            ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  CAMPAIGNS PLAYED:                                   ║
║  1. "Family Adventure" (Family Co-Play)              ║
║     Time: 4h 30m                                     ║
║     Progress: Chapter 2 → Chapter 3                  ║
║     Playing with: You, Michael, Jake                 ║
║                                                      ║
║  2. "Junior Explorers" (Solo)                        ║
║     Time: 4h 15m                                     ║
║     Progress: Mission 5 → Mission 7                  ║
║     Focus: Science concepts, teamwork                ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  ACHIEVEMENTS THIS WEEK:                             ║
║  🏆 Completed "Understanding Animals" quest          ║
║  🏆 Reached Understand Tier in Empathy               ║
║  🏆 Solved 10 puzzles without hints                  ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  SOCIAL INTERACTIONS:                                ║
║  • Played with family: 4 sessions                    ║
║  • Solo play: 6 sessions                             ║
║  • No interactions with external players             ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  CONCERNS: None                                      ║
║  ✓ All content age-appropriate                       ║
║  ✓ No blocked content attempts                       ║
║  ✓ Healthy play patterns                             ║
║                                                      ║
║  [View Detailed Logs] [Adjust Settings]              ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

# Educational Accounts

## Teacher Dashboard

```
╔══════════════════════════════════════════════════════╗
║         TEACHER DASHBOARD - MRS. JOHNSON             ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Class: 9th Grade World History, Period 3            ║
║  Students: 28 active                                 ║
║  Current Campaign: "Age of Reason: Civics Edition"   ║
║                                                      ║
║  ═══════════════════════════════════════════════    ║
║                                                      ║
║  CLASS PROGRESS:                                     ║
║                                                      ║
║  Learning Objectives:                                ║
║  ✅ Understand Enlightenment Philosophy (95%)        ║
║  🔄 Analyze Revolutionary Causes (67%)               ║
║  🔒 Evaluate Historical Perspectives (15%)           ║
║                                                      ║
║  Bloom's Tier Distribution:                          ║
║  Remember: 100% | Understand: 89% | Apply: 54%      ║
║  Analyze: 32% | Evaluate: 11% | Create: 0%          ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  ACTIVE SESSION:                                     ║
║  Campaign: "The Revolution Begins"                   ║
║  Time Remaining: 35 minutes                          ║
║  Students Online: 26 of 28                           ║
║                                                      ║
║  Groups:                                             ║
║  • Group A (Girondins): 7 students - Chapter 4       ║
║  • Group B (Jacobins): 7 students - Chapter 4        ║
║  • Group C (Monarchists): 6 students - Chapter 4     ║
║  • Group D (Sans-culottes): 6 students - Chapter 3   ║
║                                                      ║
║  [Pause All] [Discussion Mode] [End Session]         ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  STUDENT SPOTLIGHT:                                  ║
║                                                      ║
║  ⭐ Alex Martinez - Breakthrough in Analysis!        ║
║     Just demonstrated Analyze-tier reasoning         ║
║     in political negotiation scenario                ║
║                                                      ║
║  ⚠️ Sam Chen - Struggling with perspective-taking    ║
║     May need additional empathy scaffolding          ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  DISCUSSION PROMPT (Ready):                          ║
║  "Each group has taken different positions on        ║
║  the revolution. In 10 minutes, we'll discuss:       ║
║  What compromises are possible? What principles      ║
║  are non-negotiable?"                                ║
║                                                      ║
║  [Launch Discussion] [Skip]                          ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  QUICK ACTIONS:                                      ║
║  [View All Student Progress]                         ║
║  [Export Grades]                                     ║
║  [Create Assignment]                                 ║
║  [Schedule Next Session]                             ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

# Subscription Models

## Pricing Tiers (Updated)

### Individual Tiers

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0/month | • 1 member<br>• Text-only mode<br>• 1 character<br>• 5 hours/month<br>• Family-Friendly & Educational universes only |
| **Standard** | $10/month | • 1 member<br>• Full visualization<br>• Up to 5 characters<br>• 25 hours/month<br>• Access to most universes |
| **Premium** | $20/month | • 1 member<br>• Everything in Standard<br>• Up to 10 characters<br>• Unlimited hours<br>• All universes<br>• High-res exports<br>• Priority support |

---

### Family Tier

| Tier | Price | Features |
|------|-------|----------|
| **Family** | $25/month | • Up to 6 members<br>• Each member: up to 10 characters<br>• Full visualization<br>• Unlimited hours (total)<br>• All age-appropriate universes<br>• Parental controls<br>• Family co-play campaigns<br>• Activity monitoring<br>• **Save $35/month** vs 6 individual accounts |

**Value Comparison:**
- 6 Individual Standard accounts: $60/month
- 1 Family account: $25/month
- **Savings: $35/month ($420/year)**

---

### Educational Tiers

| Tier | Price | Features |
|------|-------|----------|
| **Classroom** | $50/month | • 1 teacher + up to 30 students<br>• Teacher dashboard<br>• Progress tracking<br>• Assessment tools<br>• Educational universes<br>• Curriculum alignment<br>• Export reports |
| **School** | $400/month | • Up to 10 classrooms<br>• Admin dashboard<br>• School-wide analytics<br>• Teacher training<br>• Dedicated support |
| **District** | Custom | • Unlimited classrooms<br>• District-wide implementation<br>• Custom content<br>• Professional development<br>• Success manager |

---

### Organizational Tiers

| Tier | Price | Features |
|------|-------|----------|
| **Team** | $100/month | • Up to 20 employees<br>• Admin dashboard<br>• Performance analytics<br>• Professional Training universes |
| **Enterprise** | Custom | • Unlimited employees<br>• Custom content creation<br>• API access<br>• White-label options<br>• Dedicated account manager |

---

## Subscription Management

### Family Subscription Billing

```
╔══════════════════════════════════════════════════════╗
║         SUBSCRIPTION & BILLING                       ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  CURRENT PLAN:                                       ║
║  Family Account - $25.00/month                       ║
║                                                      ║
║  Members: 4 of 6 (2 slots available)                 ║
║  • Sarah Smith (Owner)                               ║
║  • Michael Smith                                     ║
║  • Emma Smith (Child, 10)                            ║
║  • Jake Smith (Child, 8)                             ║
║                                                      ║
║  Next Billing Date: November 1, 2025                 ║
║  Payment Method: Visa ending in 4242                 ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  USAGE THIS MONTH:                                   ║
║  Total Hours Played: 47 of ∞                         ║
║  Active Characters: 8 total across family            ║
║  Active Campaigns: 6 total                           ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  VALUE COMPARISON:                                   ║
║  Your Family Plan: $25/month                         ║
║  4 Individual Plans would cost: $40/month            ║
║  💰 You're saving: $15/month ($180/year)             ║
║                                                      ║
║  ─────────────────────────────────────────────────  ║
║                                                      ║
║  ACTIONS:                                            ║
║  [Update Payment Method]                             ║
║  [Change Plan]                                       ║
║  [View Billing History]                              ║
║  [Cancel Subscription]                               ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

# Technical Implementation

## Database Schema

### Accounts Table

```sql
CREATE TABLE accounts (
  account_id VARCHAR(50) PRIMARY KEY,
  account_owner_member_id VARCHAR(50), -- References members table
  account_type ENUM('individual', 'family', 'educational', 'organizational'),
  
  -- Subscription
  subscription_tier VARCHAR(50),
  subscription_status ENUM('active', 'past_due', 'cancelled', 'suspended'),
  billing_cycle ENUM('monthly', 'annual'),
  subscription_start_date DATE,
  next_billing_date DATE,
  
  -- Limits
  max_members INT DEFAULT 1, -- 1 for individual, 6 for family, etc.
  current_member_count INT DEFAULT 1,
  
  -- Payment
  stripe_customer_id VARCHAR(100),
  stripe_subscription_id VARCHAR(100),
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  INDEX idx_owner (account_owner_member_id),
  INDEX idx_type (account_type),
  INDEX idx_status (subscription_status)
);
```

### Members Table

```sql
CREATE TABLE members (
  member_id VARCHAR(50) PRIMARY KEY,
  account_id VARCHAR(50) NOT NULL,
  
  -- Identity
  display_name VARCHAR(100) NOT NULL,
  email VARCHAR(255), -- Optional for children
  date_of_birth DATE NOT NULL,
  age INT GENERATED ALWAYS AS (
    YEAR(CURDATE()) - YEAR(date_of_birth)
  ) STORED,
  
  -- Role & Permissions
  role ENUM('owner', 'parent', 'teen', 'child', 'student', 'employee'),
  can_manage_account BOOLEAN DEFAULT FALSE,
  can_manage_members BOOLEAN DEFAULT FALSE,
  can_view_billing BOOLEAN DEFAULT FALSE,
  
  -- Content Restrictions
  content_restriction_level ENUM('automatic', 'custom'),
  allowed_universes JSON, -- List of universe_ids
  blocked_universes JSON,
  
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
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
  INDEX idx_account (account_id),
  INDEX idx_email (email),
  INDEX idx_age (age),
  INDEX idx_role (role)
);
```

### Player Profiles Table

```sql
CREATE TABLE player_profiles (
  profile_id VARCHAR(50) PRIMARY KEY,
  member_id VARCHAR(50) NOT NULL,
  
  -- Character Info
  character_name VARCHAR(100) NOT NULL,
  universe_id VARCHAR(50) NOT NULL,
  world_id VARCHAR(50) NOT NULL,
  archetype VARCHAR(100),
  
  -- Appearance
  appearance_data JSON, -- Visual customization
  portrait_url VARCHAR(500),
  
  -- Cognitive Progress (Universal - shared across all profiles)
  -- Stored separately in member_cognitive_progress table
  
  -- World-Specific Knowledge (Character-specific)
  world_knowledge_level DECIMAL(3,2) DEFAULT 0.00, -- 0.00 to 1.00
  discovered_locations JSON,
  known_npcs JSON,
  completed_quests JSON,
  
  -- Character Stats
  total_playtime_minutes INT DEFAULT 0,
  character_level INT DEFAULT 1,
  character_achievements JSON,
  
  -- Status
  is_active BOOLEAN DEFAULT TRUE,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_played_at TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  FOREIGN KEY (member_id) REFERENCES members(member_id) ON DELETE CASCADE,
  FOREIGN KEY (universe_id) REFERENCES universes(universe_id),
  FOREIGN KEY (world_id) REFERENCES worlds(world_id),
  
  INDEX idx_member (member_id),
  INDEX idx_universe_world (universe_id, world_id),
  INDEX idx_active (is_active),
  INDEX idx_last_played (last_played_at)
);
```

### Member Cognitive Progress Table

```sql
-- Cognitive skills are tied to MEMBER, not individual player profiles
-- This allows skills to transfer across all characters

CREATE TABLE member_cognitive_progress (
  member_id VARCHAR(50) PRIMARY KEY,
  
  -- Bloom's Taxonomy Mastery
  remember_mastered BOOLEAN DEFAULT FALSE,
  understand_mastered BOOLEAN DEFAULT FALSE,
  apply_mastered BOOLEAN DEFAULT FALSE,
  analyze_progress DECIMAL(3,2) DEFAULT 0.00, -- 0.00 to 1.00
  evaluate_progress DECIMAL(3,2) DEFAULT 0.00,
  create_progress DECIMAL(3,2) DEFAULT 0.00,
  
  -- Core Cognitive Skills (1-10 scale)
  empathy_level INT DEFAULT 1,
  strategy_level INT DEFAULT 1,
  creativity_level INT DEFAULT 1,
  courage_level INT DEFAULT 1,
  collaboration_level INT DEFAULT 1,
  resilience_level INT DEFAULT 1,
  
  -- Meta-Cognitive Insights
  problem_solving_patterns JSON,
  decision_making_patterns JSON,
  learning_strategies JSON,
  
  -- Aggregate Stats
  total_sessions_across_all_profiles INT DEFAULT 0,
  total_playtime_minutes INT DEFAULT 0,
  
  -- Timestamps
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  FOREIGN KEY (member_id) REFERENCES members(member_id) ON DELETE CASCADE
);
```

### Campaigns Table

```sql
CREATE TABLE campaigns (
  campaign_id VARCHAR(50) PRIMARY KEY,
  campaign_name VARCHAR(255) NOT NULL,
  
  -- World Context
  universe_id VARCHAR(50) NOT NULL,
  world_id VARCHAR(50) NOT NULL,
  
  -- Campaign Type
  campaign_type ENUM('solo', 'multiplayer_coop', 'family', 'competitive'),
  max_players INT DEFAULT 1,
  current_player_count INT DEFAULT 0,
  
  -- State
  state_model ENUM('shared', 'instanced', 'hybrid') DEFAULT 'instanced',
  current_chapter INT DEFAULT 1,
  campaign_progress DECIMAL(3,2) DEFAULT 0.00,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_session_at TIMESTAMP,
  completed_at TIMESTAMP NULL,
  
  FOREIGN KEY (universe_id) REFERENCES universes(universe_id),
  FOREIGN KEY (world_id) REFERENCES worlds(world_id),
  
  INDEX idx_universe_world (universe_id, world_id),
  INDEX idx_type (campaign_type),
  INDEX idx_last_session (last_session_at)
);
```

### Campaign Participants Table

```sql
CREATE TABLE campaign_participants (
  participant_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  campaign_id VARCHAR(50) NOT NULL,
  profile_id VARCHAR(50) NOT NULL,
  member_id VARCHAR(50) NOT NULL, -- Denormalized for easy lookups
  
  -- Participation
  role VARCHAR(50), -- party_leader, member, spectator
  joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_active_at TIMESTAMP,
  is_active BOOLEAN DEFAULT TRUE,
  
  -- Session Stats
  sessions_participated INT DEFAULT 0,
  total_playtime_minutes INT DEFAULT 0,
  
  FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
  FOREIGN KEY (profile_id) REFERENCES player_profiles(profile_id) ON DELETE CASCADE,
  FOREIGN KEY (member_id) REFERENCES members(member_id) ON DELETE CASCADE,
  
  -- Constraint: One profile per member per campaign
  UNIQUE KEY unique_member_campaign (campaign_id, member_id),
  
  INDEX idx_campaign (campaign_id),
  INDEX idx_profile (profile_id),
  INDEX idx_member (member_id),
  INDEX idx_active (is_active)
);
```

### Activity Logs Table (For Parental Monitoring)

```sql
CREATE TABLE activity_logs (
  log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  member_id VARCHAR(50) NOT NULL,
  profile_id VARCHAR(50),
  campaign_id VARCHAR(50),
  
  -- Activity Details
  activity_type ENUM(
    'session_start',
    'session_end',
    'character_created',
    'campaign_joined',
    'achievement_earned',
    'content_blocked',
    'time_limit_reached',
    'universe_accessed',
    'multiplayer_interaction'
  ),
  activity_data JSON,
  
  -- Duration (for sessions)
  duration_minutes INT,
  
  -- Content
  universe_id VARCHAR(50),
  content_rating VARCHAR(10),
  
  -- Timestamp
  occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (member_id) REFERENCES members(member_id) ON DELETE CASCADE,
  FOREIGN KEY (profile_id) REFERENCES player_profiles(profile_id) ON DELETE SET NULL,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id) ON DELETE SET NULL,
  
  INDEX idx_member_date (member_id, occurred_at),
  INDEX idx_activity_type (activity_type),
  INDEX idx_occurred (occurred_at)
);
```

---

## API Endpoints

### Account Management

```javascript
// Create account
POST /api/v1/accounts
{
  "account_type": "family",
  "owner": {
    "name": "Sarah Smith",
    "email": "sarah@email.com",
    "date_of_birth": "1987-05-15",
    "password": "***"
  },
  "subscription_tier": "family"
}

// Add family member
POST /api/v1/accounts/{account_id}/members
{
  "name": "Emma Smith",
  "relationship": "child",
  "date_of_birth": "2015-03-20",
  "content_restrictions": "automatic"
}

// Update parental controls
PATCH /api/v1/members/{member_id}/parental-controls
{
  "daily_time_limit_minutes": 120,
  "allowed_universes": ["family_friendly", "educational"],
  "can_play_with_strangers": false
}

// Get family dashboard
GET /api/v1/accounts/{account_id}/dashboard
Response: {
  "account": {...},
  "members": [...],
  "family_campaigns": [...],
  "aggregate_stats": {...}
}
```

### Player Profile Management

```javascript
// Create player profile
POST /api/v1/members/{member_id}/profiles
{
  "character_name": "Seraphina Dawnwhisper",
  "universe_id": "teen_adventures",
  "world_id": "shattered_kingdoms_001",
  "archetype": "diplomat",
  "appearance_data": {...}
}

// List member's profiles
GET /api/v1/members/{member