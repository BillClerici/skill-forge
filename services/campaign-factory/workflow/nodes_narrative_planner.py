"""
Campaign Narrative Planning Node
Phase 3.5: Plan the entire campaign narrative structure before generating content

This node creates a comprehensive story outline that maps:
- Campaign story arc → Quest chapters
- Quest chapters → Unique narrative beats
- Narrative beats → Locations (places - can be reused across quests)
- Locations → Unique scenes (must be globally unique)

This ensures:
- Places can appear in multiple quests for world coherence
- Every scene is unique across the entire campaign
- Narrative progression through familiar and new locations
"""
import logging
import json
from typing import List, Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .state import CampaignWorkflowState
from .utils import add_audit_entry, publish_progress

logger = logging.getLogger(__name__)

# Pydantic models for structured output
class StoryArcResponse(BaseModel):
    """Structured response for campaign story arc"""
    act_1_setup: str = Field(description="Brief description of campaign beginning")
    act_2_conflict: str = Field(description="Brief description of rising action/complications")
    act_3_resolution: str = Field(description="Brief description of climax and resolution")

class SceneResponse(BaseModel):
    """Structured response for a narrative scene"""
    scene_name: str = Field(description="Specific scene name")
    scene_description: str = Field(description="What happens in this narrative moment")
    story_beat: str = Field(description="Which story beat this scene advances")
    key_interactions: str = Field(description="NPCs, discoveries, or events that occur")
    supports_quest_objectives: List[str] = Field(default_factory=list, description="Quest objective IDs this scene supports")
    provides_knowledge_domains: List[str] = Field(default_factory=list, description="Knowledge domains provided")
    provides_item_categories: List[str] = Field(default_factory=list, description="Item categories provided")
    is_required_for_quest_completion: bool = Field(default=True, description="Whether scene is required")

class PlaceResponse(BaseModel):
    """Structured response for a quest place"""
    place_name: str = Field(description="Specific, unique place name")
    place_description: str = Field(description="What this place is and why it's important")
    narrative_purpose: str = Field(description="Story function this place serves")
    when_visited: str = Field(description="Beginning/middle/end of quest")
    scenes: List[SceneResponse] = Field(description="Scenes at this place", min_length=1, max_length=2)

class QuestChapterResponse(BaseModel):
    """Structured response for a quest chapter"""
    quest_number: int = Field(description="Quest number in sequence")
    chapter_title: str = Field(description="Quest name/chapter title")
    chapter_summary: str = Field(description="What happens in this chapter")
    narrative_purpose: str = Field(description="Why this chapter exists (setup/complication/climax/resolution)")
    story_beats: List[str] = Field(description="Specific story events", min_length=2)
    places: List[PlaceResponse] = Field(description="2-6 places where story events occur", min_length=2)  # Removed max_length, will truncate after parsing

class NarrativeBlueprintResponse(BaseModel):
    """Structured response for complete narrative blueprint"""
    campaign_story_arc: StoryArcResponse = Field(description="Overall campaign story arc")
    quests: List[QuestChapterResponse] = Field(description="Quest chapters", min_length=1)

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    temperature=0.8,
    max_tokens=16384  # Increased for narrative blueprints with many quests
)


def validate_blueprint_uniqueness(blueprint: Dict[str, Any]) -> List[str]:
    """
    Validate that the narrative blueprint has appropriate uniqueness.

    RULES:
    - Places CAN appear in multiple quests (for world coherence)
    - BUT scenes within a place MUST be unique across the entire campaign
    - Each scene name must be globally unique

    Returns list of validation error messages (empty if valid).
    """
    errors = []

    quests = blueprint.get("quests", [])

    # Track places and which quests use them
    place_usage = {}  # place_name -> [quest_nums using it]

    # Track all scene names globally to ensure uniqueness
    scene_name_usage = {}  # scene_name -> "Quest X, Place Y"

    for quest in quests:
        quest_num = quest.get("quest_number", "?")
        places = quest.get("places", [])

        for place in places:
            place_name = place.get("place_name", "").strip().lower()

            if not place_name:
                errors.append(f"Quest {quest_num} has a place with no name")
                continue

            # Track which quests use this place (ALLOWED to be in multiple quests)
            if place_name not in place_usage:
                place_usage[place_name] = []
            place_usage[place_name].append(quest_num)

            # Check scenes within this place
            scenes = place.get("scenes", [])
            for scene in scenes:
                scene_name = scene.get("scene_name", "").strip().lower()

                if not scene_name:
                    errors.append(f"Quest {quest_num}, Place '{place.get('place_name')}' has a scene with no name")
                    continue

                # CRITICAL: Scene names must be GLOBALLY unique across entire campaign
                if scene_name in scene_name_usage:
                    errors.append(
                        f"Duplicate scene '{scene.get('scene_name')}' found in Quest {quest_num}, Place '{place.get('place_name')}' "
                        f"(already used in {scene_name_usage[scene_name]})"
                    )
                else:
                    scene_name_usage[scene_name] = f"Quest {quest_num}, Place '{place.get('place_name')}'"

    # Log statistics about place reuse
    total_place_instances = sum(len(quests) for quests in place_usage.values())
    reused_places = {name: quests for name, quests in place_usage.items() if len(quests) > 1}

    logger.info(f"Blueprint validation: {len(place_usage)} unique places, {total_place_instances} total place instances, {len(scene_name_usage)} unique scenes")

    if reused_places:
        logger.info(f"Places reused across quests: {dict(list(reused_places.items())[:3])}...")  # Show first 3 examples

    return errors


async def plan_campaign_narrative(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Plan the entire campaign narrative structure upfront.

    This creates a detailed story outline that:
    1. Breaks the campaign into quest chapters (story beats)
    2. Identifies unique locations needed for each chapter
    3. Plans distinct scenes within each location
    4. Ensures narrative continuity and progression

    Output: A narrative blueprint that guides all subsequent generation
    """
    try:
        state["current_node"] = "plan_narrative"
        state["current_phase"] = "narrative_planning"
        state["progress_percentage"] = 30
        state["step_progress"] = 0
        state["status_message"] = "Planning campaign narrative structure..."

        await publish_progress(state)

        logger.info(f"Planning narrative structure for {state['num_quests']} quest campaign")

        state["step_progress"] = 15
        state["status_message"] = "Analyzing campaign requirements..."
        await publish_progress(state)

        # Create comprehensive narrative planning prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a master narrative architect and quest designer for RPG campaigns.

Your task is to create a COMPREHENSIVE NARRATIVE BLUEPRINT for the entire campaign.

Think of this as writing a detailed story outline where:
- The CAMPAIGN is the full story
- Each QUEST is a distinct CHAPTER with its own mini-arc
- Each PLACE is a unique LOCATION where specific story events occur
- Each SCENE is a specific MOMENT or INTERACTION within that location

CRITICAL RULES:
1. **PLACES CAN BE REUSED**: Places MAY appear in multiple quests for narrative continuity (e.g., returning to a town)
2. **SCENES MUST BE UNIQUE**: Every scene must be unique across the entire campaign - no duplicate scenes even in the same place
3. **NARRATIVE PROGRESSION**: Each visit to a place should reveal something new or serve a different purpose
4. **STORY COHERENCE**: Quests should flow naturally, with places acting as familiar anchors in an evolving story

QUEST STRUCTURE (Think like a book):
- Quest 1 = Chapter 1: Introduction, inciting incident, setup
- Quest 2 = Chapter 2: Rising action, complications, new discoveries
- Quest 3 = Chapter 3: Climax, confrontation, major revelations
- Final Quest = Conclusion: Resolution, consequences, epilogue

PLACE GUIDELINES:
- Each quest should have 2-4 places where story events occur (max 8 scenes per quest total)
- Places CAN be reused across quests if it serves the narrative (e.g., "The Town Square", "The Royal Palace")
- Reusing places creates world coherence - players return to familiar locations for new purposes
- When a place appears in multiple quests, it MUST have COMPLETELY DIFFERENT scenes each time
- Example: "The Ancient Library" could appear in Quest 1 (researching history) AND Quest 3 (confronting the villain)

SCENE GUIDELINES:
- Scenes are specific narrative moments (e.g., "The Ambush", "The Revelation", "The Negotiation")
- Each scene should advance the plot or develop characters
- Scenes should be UNIQUE - no generic "tavern scene" or "market scene"
- 1-2 scenes per place (max 2), each with a clear narrative purpose
- Keep scenes FOCUSED - players experience these through chat, so simpler is better

OBJECTIVE-DRIVEN DESIGN (CRITICAL):
- Each scene MUST explicitly support at least ONE quest objective
- Specify which quest objectives the scene advances
- Identify what knowledge domains the player should acquire in this scene
- Identify what item categories the player should obtain in this scene
- Create REDUNDANCY: Important objectives should be achievable through multiple scenes (2-3 different scenes)
- Every quest objective must be addressable in at least 2 different scenes

IMPORTANT:
- Be SPECIFIC, not generic
- Place names should be unique and memorable
- Places CAN be reused across quests (e.g., "The Town Square" in Quest 1 and 3)
- Each scene must have a GLOBALLY UNIQUE name across the entire campaign
- Each scene should have a clear narrative purpose
- Think cinematically: each scene is a specific moment in the story"""),
            ("user", """Campaign Context:
Name: {campaign_name}
Plot: {plot}
Primary Objectives: {primary_objectives}

Quest Objectives (decomposed from campaign objectives):
{quest_objectives_breakdown}

Campaign Specifications:
- Number of Quests: {num_quests}
- Difficulty: {difficulty}
- Target Bloom's Level: {blooms_level}

Create a comprehensive narrative blueprint for this {num_quests}-quest campaign.
Make each quest a distinct chapter. Places can be reused across quests, but each scene must be unique.

CRITICAL: Each scene must specify which quest objectives it supports and what knowledge/items it provides.
Ensure every quest objective is addressable in at least 2 different scenes for redundancy.""")
        ])

        # Format primary objectives
        objectives_str = "\n".join([
            f"- {obj['description']} (Bloom's: {obj['blooms_level']})"
            for obj in state["campaign_core"]["primary_objectives"]
        ])

        # Format quest objectives breakdown (from decomposition)
        quest_objectives_breakdown = ""
        if state.get("objective_decompositions"):
            for decomp in state["objective_decompositions"]:
                quest_objectives_breakdown += f"\nCampaign Objective: {decomp['campaign_objective_description']}\n"
                quest_objectives_breakdown += "  Quest-level objectives:\n"
                for qobj in decomp["quest_objectives"]:
                    quest_num = qobj.get("quest_number", "?")
                    quest_objectives_breakdown += f"    Quest {quest_num}: {qobj['objective_id']} - {qobj['description']}\n"
                    quest_objectives_breakdown += f"      Requires knowledge: {', '.join(qobj.get('required_knowledge_domains', []))}\n"
                    quest_objectives_breakdown += f"      Requires items: {', '.join(qobj.get('required_item_categories', []))}\n"
        else:
            # Fallback if decomposition hasn't run yet
            quest_objectives_breakdown = "(No objective decomposition available - using campaign objectives only)"

        # Generate narrative blueprint
        state["step_progress"] = 30
        state["status_message"] = f"Generating {state['num_quests']}-quest story arc with objective awareness..."
        await publish_progress(state)

        # Use structured output - validation will pass since we removed max_length constraint
        structured_llm = anthropic_client.with_structured_output(NarrativeBlueprintResponse, include_raw=False)
        chain = prompt | structured_llm

        response = await chain.ainvoke({
            "campaign_name": state["campaign_core"]["name"],
            "plot": state["campaign_core"]["plot"],
            "primary_objectives": objectives_str,
            "quest_objectives_breakdown": quest_objectives_breakdown,
            "num_quests": state["num_quests"],
            "difficulty": state["quest_difficulty"],
            "blooms_level": state["campaign_core"]["target_blooms_level"]
        })

        # Parse narrative blueprint
        state["step_progress"] = 70
        state["status_message"] = "Parsing narrative blueprint..."
        await publish_progress(state)

        # Response is a Pydantic object
        blueprint_response = response

        # Truncate excess places if any quest has > 6 places (enforce our business rule)
        for quest in blueprint_response.quests:
            if len(quest.places) > 6:
                logger.warning(f"Quest {quest.quest_number} has {len(quest.places)} places, truncating to 6")
                quest.places = quest.places[:6]

        # Convert Pydantic model to dict
        narrative_blueprint = blueprint_response.model_dump()

        # VALIDATE UNIQUENESS before storing
        state["step_progress"] = 85
        state["status_message"] = "Validating narrative structure..."
        await publish_progress(state)

        validation_errors = validate_blueprint_uniqueness(narrative_blueprint)
        if validation_errors:
            logger.error(f"Blueprint validation failed: {validation_errors}")
            raise ValueError(f"Blueprint has duplicate content: {'; '.join(validation_errors)}")

        # Store in state
        state["narrative_blueprint"] = narrative_blueprint

        # Log summary
        total_places = sum(len(q.get("places", [])) for q in narrative_blueprint.get("quests", []))
        total_scenes = sum(
            len(s.get("scenes", []))
            for q in narrative_blueprint.get("quests", [])
            for s in q.get("places", [])
        )

        logger.info(f"Generated narrative blueprint: {state['num_quests']} quests, {total_places} unique places, {total_scenes} unique scenes")

        state["step_progress"] = 100
        state["status_message"] = f"Narrative blueprint complete: {total_places} places, {total_scenes} scenes"
        await publish_progress(state)

        add_audit_entry(
            state,
            "plan_narrative",
            "Created campaign narrative blueprint",
            {
                "num_quests": state['num_quests'],
                "total_places": total_places,
                "total_scenes": total_scenes,
                "story_arc": narrative_blueprint.get("campaign_story_arc", {})
            },
            "success"
        )

        state["errors"] = []
        state["retry_count"] = 0

    except Exception as e:
        error_msg = f"Error planning campaign narrative: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "plan_narrative",
            "Failed to plan narrative",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state
