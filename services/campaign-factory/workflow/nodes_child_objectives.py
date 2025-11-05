"""
Child Objectives Generation Node
Generates 4-type child objectives for quest objectives
"""

from typing import Dict, List, Any, Optional
import uuid
import json
from datetime import datetime
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from .utils import add_audit_entry, publish_progress


# Pydantic models for structured output
class ChildObjectiveResponse(BaseModel):
    """Structured response for a child objective"""
    objective_type: str = Field(description="Type: discovery, challenge, event, or conversation")
    description: str = Field(description="Clear, concise description")
    is_required: bool = Field(description="Whether this objective is required")
    is_hidden: bool = Field(default=False, description="Whether objective starts hidden")
    minimum_rubric_score: float = Field(description="Threshold for completion (2.0-3.0)", ge=2.0, le=3.0)
    rubric_criteria: List[str] = Field(description="3-5 evaluation criteria", min_length=3, max_length=5)

    # Optional fields for different types
    scene_location_hint: Optional[str] = Field(default=None, description="Where/how to find (discovery)")
    discovery_subtype: Optional[str] = Field(default=None, description="Subtype for discoveries")
    npc_name_hint: Optional[str] = Field(default=None, description="NPC hint (conversation)")
    conversation_goal: Optional[str] = Field(default=None, description="Goal for conversations")
    required_topics: Optional[List[str]] = Field(default=None, description="Topics to discuss")
    optional_topics: Optional[List[str]] = Field(default=None, description="Optional topics")
    provides_knowledge: Optional[List[str]] = Field(default=None, description="Knowledge provided")
    provides_items: Optional[List[str]] = Field(default=None, description="Items provided")
    can_continue_across_scenes: Optional[bool] = Field(default=None, description="Can span scenes")
    challenge_subtype: Optional[str] = Field(default=None, description="Subtype for challenges")
    solution_approach_hint: Optional[str] = Field(default=None, description="Challenge solution hint")
    event_subtype: Optional[str] = Field(default=None, description="Subtype for events")
    participation_type: Optional[str] = Field(default=None, description="How to participate")
    required_knowledge: Optional[List[str]] = Field(default_factory=list, description="Required knowledge")
    required_items: Optional[List[str]] = Field(default_factory=list, description="Required items")

class ChildObjectivesListResponse(BaseModel):
    """Structured response containing list of child objectives"""
    objectives: List[ChildObjectiveResponse] = Field(description="List of 2-4 child objectives", min_length=2, max_length=4)


class ChildObjectivesGenerator:
    """Generates granular child objectives for quests"""

    def __init__(self):
        self.anthropic = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.7,
            max_tokens=4000
        )

    async def design_child_objectives_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main node: Design 4-type child objectives for all quest objectives

        Creates child objectives of types:
        - Discovery (environmental exploration)
        - Challenge (puzzles, riddles)
        - Event (participation in dynamic events)
        - Conversation (NPC interactions)
        """
        print("\n🎯 Designing Child Objectives...")

        try:
            # Extract necessary data from state
            quest_objectives = state.get("quest_objectives", [])
            quests = state.get("quests", [])
            narrative_blueprint = state.get("narrative_blueprint", {})
            campaign_core = state.get("campaign_core", {})

            if not quest_objectives:
                return {
                    "errors": ["No quest objectives found to generate child objectives"],
                    "warnings": ["Skipping child objective generation"]
                }

            all_child_objectives = []
            by_type = {
                "discovery": [],
                "challenge": [],
                "event": [],
                "conversation": []
            }

            # Generate child objectives for each quest objective
            for quest_obj in quest_objectives:
                print(f"\n  📋 Generating child objectives for: {quest_obj['description'][:60]}...")

                # Find the quest this objective belongs to
                quest = self._find_quest_for_objective(quest_obj, quests)
                if not quest:
                    print(f"    ⚠️  Warning: Could not find quest for objective {quest_obj['objective_id']}")
                    continue

                # Get narrative context
                quest_narrative = self._get_quest_narrative(quest, narrative_blueprint)

                # Generate child objectives using AI
                child_objs = await self._generate_child_objectives_for_quest_objective(
                    quest_obj=quest_obj,
                    quest=quest,
                    quest_narrative=quest_narrative,
                    campaign_themes=campaign_core.get("storyline", "")
                )

                # Process and categorize
                for child_obj in child_objs:
                    # Add IDs and relationships
                    child_obj["objective_id"] = f"child_obj_{uuid.uuid4().hex[:8]}"
                    child_obj["quest_id"] = quest["quest_id"]
                    child_obj["quest_objective_id"] = quest_obj["objective_id"]
                    child_obj["campaign_objective_ids"] = quest_obj["campaign_objective_ids"]
                    child_obj["bloom_level"] = quest_obj["bloom_level"]
                    child_obj["status"] = "not_started"

                    # Set defaults
                    child_obj.setdefault("available_in_scenes", [])
                    child_obj.setdefault("appearance_conditions", {})
                    child_obj.setdefault("required_knowledge", [])
                    child_obj.setdefault("required_items", [])
                    child_obj.setdefault("prerequisite_objectives", [])

                    all_child_objectives.append(child_obj)
                    by_type[child_obj["objective_type"]].append(child_obj)

                print(f"    ✅ Generated {len(child_objs)} child objectives")

            # Summary
            print(f"\n✅ Child Objectives Generated:")
            print(f"   - Discovery: {len(by_type['discovery'])}")
            print(f"   - Challenge: {len(by_type['challenge'])}")
            print(f"   - Event: {len(by_type['event'])}")
            print(f"   - Conversation: {len(by_type['conversation'])}")
            print(f"   - Total: {len(all_child_objectives)}\n")

            # Log audit
            add_audit_entry(
                state,
                "design_child_objectives",
                "success",
                f"Generated {len(all_child_objectives)} child objectives"
            )

            # Update state with progress
            state["progress_percentage"] = 35
            state["status_message"] = "Child objectives designed"

            # Publish progress
            await publish_progress(state, "Child objectives designed")

            return {
                "child_objectives": all_child_objectives,
                "discovery_objectives": by_type["discovery"],
                "challenge_objectives": by_type["challenge"],
                "event_objectives": by_type["event"],
                "conversation_objectives": by_type["conversation"],
                "progress_percentage": 35,
                "current_node": "design_child_objectives"
            }

        except Exception as e:
            print(f"\n❌ Error designing child objectives: {e}")
            return {
                "errors": [f"Child objectives design failed: {str(e)}"],
                "retry_count": state.get("retry_count", 0) + 1
            }

    async def _generate_child_objectives_for_quest_objective(
        self,
        quest_obj: Dict[str, Any],
        quest: Dict[str, Any],
        quest_narrative: Dict[str, Any],
        campaign_themes: str
    ) -> List[Dict[str, Any]]:
        """Generate child objectives using Claude"""

        prompt = f"""You are designing granular player objectives for a role-playing game campaign.

QUEST OBJECTIVE TO DECOMPOSE:
{quest_obj['description']}

QUEST CONTEXT:
Quest Name: {quest['name']}
Quest Description: {quest['description']}
Difficulty: {quest['difficulty_level']}

NARRATIVE CONTEXT:
{json.dumps(quest_narrative, indent=2)}

CAMPAIGN THEMES:
{campaign_themes}

TASK:
Create 2-4 granular child objectives that players must complete to achieve the quest objective above.
These objectives should be SPECIFIC, ACHIEVABLE actions that happen within individual scenes.
Focus on quality over quantity - each objective should be essential and meaningful.

Use these 4 objective types (distribute the 2-4 total objectives across types):

1. **DISCOVERY** (Environmental Exploration) - 1 objective recommended
   - Finding specific observations, items, or environmental clues
   - Scene-specific discoveries (hidden in particular locations)
   - Examples: "Find the Ancient Tablet in the Ruins", "Discover the hidden passage beneath the temple"

2. **CHALLENGE** (Puzzles & Riddles) - 0-1 objectives
   - Logic puzzles, riddles, strategic challenges players must solve
   - Scene-specific challenges
   - Examples: "Solve the Crystal Alignment Puzzle", "Decode the ancient cipher"

3. **EVENT** (Participation in Dynamic Events) - 0-1 objectives
   - Ceremonies, gatherings, crises players participate in
   - Can be time-based or player-triggered
   - Examples: "Attend the Council Meeting", "Participate in the Ritual of Binding"

4. **CONVERSATION** (NPC Interactions) - 1-2 objectives recommended
   - Meaningful conversations with NPCs to gather information, build trust, negotiate
   - NPCs can appear in multiple scenes
   - Examples: "Learn about the prophecy from Elder Thorne", "Negotiate with the merchant guild leader"

REQUIREMENTS FOR EACH OBJECTIVE:
- **Description**: Clear, concise, player-facing (1 sentence)
- **Objective Type**: "discovery", "challenge", "event", or "conversation"
- **Is Required**: true/false (at least 70% should be required)
- **Is Hidden**: true/false (starts hidden until discovered)
- **Minimum Rubric Score**: 2.0-3.0 (threshold for completion)
- **Scene Location Hint**: Where/how players might find this (for discoveries)
- **Rubric Criteria**: List 3-5 evaluation criteria for this objective
  - Each criterion should measure a specific aspect of completion
  - Focus on quality of engagement, not just binary completion

For CONVERSATION objectives, also include:
- **NPC Name Hint**: Suggest a role/archetype (e.g., "Village Elder", "Mysterious Scholar")
- **Conversation Goal**: "gather_information", "persuade", "build_trust", or "negotiate"
- **Required Topics**: 2-4 topics that must be discussed
- **Knowledge/Items Provided**: What the NPC can give

For DISCOVERY objectives, also include:
- **Discovery Subtype**: "observation", "item_pickup", or "environmental_clue"
- **Required Knowledge/Items**: What's needed to access this discovery

For CHALLENGE objectives, also include:
- **Challenge Subtype**: "puzzle", "riddle", "logic", or "combat_strategy"
- **Solution Approach Hint**: Brief hint about how to solve

For EVENT objectives, also include:
- **Event Subtype**: "ceremony", "crisis", "gathering", or "natural_phenomenon"
- **Participation Type**: "attend", "intervene", "observe", or "lead"

Return ONLY a JSON array of objectives with this structure:
[
  {{
    "objective_type": "discovery",
    "description": "Find the Ancient Tablet hidden in the eastern alcove of the Ruins",
    "is_required": true,
    "is_hidden": false,
    "minimum_rubric_score": 2.0,
    "scene_location_hint": "Hidden in eastern alcove, requires moving debris",
    "discovery_subtype": "observation",
    "required_knowledge": [],
    "required_items": [],
    "rubric_criteria": [
      "Thoroughness of exploration",
      "Attention to environmental details",
      "Understanding of the tablet's significance"
    ]
  }},
  {{
    "objective_type": "conversation",
    "description": "Learn about the Ancient Prophecy from Elder Thorne",
    "is_required": true,
    "is_hidden": false,
    "minimum_rubric_score": 2.5,
    "npc_name_hint": "Village Elder (wise, respected leader)",
    "conversation_goal": "gather_information",
    "required_topics": ["Ancient Prophecy", "The Fallen Kingdom", "How to find the ruins"],
    "optional_topics": ["Elder's personal history", "Village legends"],
    "provides_knowledge": ["Ancient History: Level 2", "Prophecy Details: Level 1"],
    "provides_items": [],
    "can_continue_across_scenes": true,
    "rubric_criteria": [
      "Active listening and engagement",
      "Asking relevant follow-up questions",
      "Building rapport with the Elder",
      "Understanding of prophecy details"
    ]
  }},
  // ... more objectives
]

Make sure:
- Create only 2-4 total objectives (quality over quantity)
- At least 50% of objectives are required (is_required: true)
- Mix of hidden and visible objectives (not all visible)
- Discovery and Challenge objectives are scene-specific
- Conversation objectives can span multiple scenes
- Each objective has clear, measurable rubric criteria
- Objectives build toward completing the quest objective
- Each objective should be essential - avoid creating "filler" objectives
"""

        try:
            # Use structured output for guaranteed valid JSON
            structured_llm = self.anthropic.with_structured_output(ChildObjectivesListResponse, include_raw=False)
            prompt_template = ChatPromptTemplate.from_messages([
                ("user", prompt)
            ])
            chain = prompt_template | structured_llm

            response: ChildObjectivesListResponse = await chain.ainvoke({})

            # Convert Pydantic model to dict list
            child_objectives = [obj.model_dump() for obj in response.objectives]

            return child_objectives

        except Exception as e:
            print(f"    ⚠️  Error generating child objectives with AI: {e}")
            # Fallback: Create basic objectives
            return self._create_fallback_objectives(quest_obj)

    def _find_quest_for_objective(
        self,
        quest_obj: Dict[str, Any],
        quests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Find the quest that contains this objective"""
        quest_id = quest_obj.get("quest_id")
        quest_number = quest_obj.get("quest_number")

        for quest in quests:
            if quest_id and quest.get("quest_id") == quest_id:
                return quest
            if quest_number and quest.get("order_sequence") == quest_number:
                return quest

        return None

    def _get_quest_narrative(
        self,
        quest: Dict[str, Any],
        narrative_blueprint: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get narrative context for a quest"""
        quest_number = quest.get("order_sequence", 1)
        quests_data = narrative_blueprint.get("quests", [])

        if quest_number <= len(quests_data):
            return quests_data[quest_number - 1]

        return {}

    def _create_fallback_objectives(
        self,
        quest_obj: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create basic fallback objectives if AI generation fails"""
        description = quest_obj["description"]

        return [
            {
                "objective_type": "discovery",
                "description": f"Discover key information related to: {description}",
                "is_required": True,
                "is_hidden": False,
                "minimum_rubric_score": 2.0,
                "scene_location_hint": "To be determined during scene generation",
                "discovery_subtype": "observation",
                "required_knowledge": [],
                "required_items": [],
                "rubric_criteria": [
                    "Thoroughness of exploration",
                    "Understanding of discovered information"
                ]
            },
            {
                "objective_type": "conversation",
                "description": f"Speak with an NPC about: {description}",
                "is_required": True,
                "is_hidden": False,
                "minimum_rubric_score": 2.5,
                "npc_name_hint": "Quest-relevant NPC",
                "conversation_goal": "gather_information",
                "required_topics": [description],
                "optional_topics": [],
                "provides_knowledge": [],
                "provides_items": [],
                "can_continue_across_scenes": True,
                "rubric_criteria": [
                    "Active listening",
                    "Relevant questions",
                    "Information gathering"
                ]
            },
            {
                "objective_type": "challenge",
                "description": f"Complete a challenge to advance: {description}",
                "is_required": True,
                "is_hidden": False,
                "minimum_rubric_score": 2.0,
                "challenge_subtype": "puzzle",
                "solution_approach_hint": "Use gathered knowledge to solve",
                "required_knowledge": [],
                "required_items": [],
                "rubric_criteria": [
                    "Problem-solving approach",
                    "Use of available knowledge",
                    "Creativity in solution"
                ]
            }
        ]


# Export the main function
async def design_child_objectives_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node entry point"""
    generator = ChildObjectivesGenerator()
    return await generator.design_child_objectives_node(state)
