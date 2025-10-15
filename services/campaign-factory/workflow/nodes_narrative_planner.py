"""
Campaign Narrative Planning Node
Phase 3.5: Plan the entire campaign narrative structure before generating content

This node creates a comprehensive story outline that maps:
- Campaign story arc → Quest chapters
- Quest chapters → Unique narrative beats
- Narrative beats → Required locations (places)
- Locations → Required scenes

This ensures each quest has unique places/scenes that tell a cohesive story.
"""
import logging
import json
from typing import List, Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

from .state import CampaignWorkflowState
from .utils import add_audit_entry, publish_progress

logger = logging.getLogger(__name__)

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    temperature=0.8,
    max_tokens=8192
)


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
        state["status_message"] = "Planning campaign narrative structure..."

        await publish_progress(state)

        logger.info(f"Planning narrative structure for {state['num_quests']} quest campaign")

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
1. **NO DUPLICATE PLACES**: Each quest must have its OWN unique places
2. **NO DUPLICATE SCENES**: Even if a place appears in multiple quests, the scenes must be different
3. **NARRATIVE PROGRESSION**: Each quest should advance the story with new locations and events
4. **STORY COHERENCE**: Quests should flow naturally, building on previous events

QUEST STRUCTURE (Think like a book):
- Quest 1 = Chapter 1: Introduction, inciting incident, setup
- Quest 2 = Chapter 2: Rising action, complications, new discoveries
- Quest 3 = Chapter 3: Climax, confrontation, major revelations
- Final Quest = Conclusion: Resolution, consequences, epilogue

PLACE GUIDELINES:
- Each quest should introduce NEW places (2-4 per quest)
- Places should be specific to that quest's narrative needs
- A place from Quest 1 should NOT appear in Quest 2 unless there's a strong story reason
- If a place MUST reappear, it should have COMPLETELY DIFFERENT scenes

SCENE GUIDELINES:
- Scenes are specific narrative moments (e.g., "The Ambush", "The Revelation", "The Negotiation")
- Each scene should advance the plot or develop characters
- Scenes should be UNIQUE - no generic "tavern scene" or "market scene"
- 1-3 scenes per place, each with a clear narrative purpose

Return a JSON structure with this EXACT format:
{{
  "campaign_story_arc": {{
    "act_1_setup": "Brief description of the campaign's beginning",
    "act_2_conflict": "Brief description of the rising action/complications",
    "act_3_resolution": "Brief description of the climax and resolution"
  }},
  "quests": [
    {{
      "quest_number": 1,
      "chapter_title": "Quest name/chapter title",
      "chapter_summary": "What happens in this chapter of the story",
      "narrative_purpose": "Why this chapter exists (setup/complication/climax/resolution)",
      "story_beats": [
        "Beat 1: Specific story event that happens",
        "Beat 2: Another specific story event",
        "Beat 3: Consequence or revelation"
      ],
      "places": [
        {{
          "place_name": "Specific, unique place name",
          "place_description": "What this place is and why it's important to THIS quest",
          "narrative_purpose": "What story function this place serves in this chapter",
          "when_visited": "Beginning/middle/end of quest",
          "scenes": [
            {{
              "scene_name": "Specific scene name (e.g., 'The Desperate Plea', 'The Hidden Map')",
              "scene_description": "What happens in this specific narrative moment",
              "story_beat": "Which story beat from above this scene advances",
              "key_interactions": "NPCs, discoveries, or events that occur here"
            }}
          ]
        }}
      ]
    }}
  ]
}}

IMPORTANT:
- Be SPECIFIC, not generic
- Each place name should be unique and memorable
- Each scene should have a clear narrative purpose
- NO repetition of places or scenes across quests
- Think cinematically: each scene is a specific moment in the story

Return ONLY the JSON, no other text."""),
            ("user", """Campaign Context:
Name: {campaign_name}
Plot: {plot}
Primary Objectives: {primary_objectives}

Campaign Specifications:
- Number of Quests: {num_quests}
- Difficulty: {difficulty}
- Target Bloom's Level: {blooms_level}

Create a comprehensive narrative blueprint for this {num_quests}-quest campaign.
Make each quest a distinct chapter with unique places and scenes that tell a complete story.""")
        ])

        # Format primary objectives
        objectives_str = "\n".join([
            f"- {obj['description']} (Bloom's: {obj['blooms_level']})"
            for obj in state["campaign_core"]["primary_objectives"]
        ])

        # Generate narrative blueprint
        chain = prompt | anthropic_client
        response = await chain.ainvoke({
            "campaign_name": state["campaign_core"]["name"],
            "plot": state["campaign_core"]["plot"],
            "primary_objectives": objectives_str,
            "num_quests": state["num_quests"],
            "difficulty": state["quest_difficulty"],
            "blooms_level": state["campaign_core"]["target_blooms_level"]
        })

        # Parse narrative blueprint
        narrative_blueprint = json.loads(response.content.strip())

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
