# SkillForge Game Playing Engine - Comprehensive Architecture

## Executive Summary

This document defines a comprehensive Game Playing Engine for SkillForge that orchestrates real-time gameplay using LangGraph workflows, AI Agents, MCP servers, RabbitMQ messaging, and a living world persistence layer. The engine creates dynamic, educational experiences that assess and develop players across 7 human dimensions using Bloom's Taxonomy.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Architecture](#core-architecture)
3. [Chat Interface & User Experience](#chat-interface--user-experience)
4. [Campaign & Session Management](#campaign--session-management)
5. [Data Model & Campaign Structure](#data-model--campaign-structure)
6. [Game Master Agent System](#game-master-agent-system)
7. [Game Loop & State Management](#game-loop--state-management)
8. [NPC Interaction System](#npc-interaction-system)
9. [Assessment & Progression System](#assessment--progression-system)
10. [Living World Persistence](#living-world-persistence)
11. [Multiplayer Architecture](#multiplayer-architecture)
12. [Implementation Roadmap](#implementation-roadmap)

---

## 1. System Overview

### Design Principles

1. **AI-Driven Gameplay**: Game Master agent orchestrates all game activity
2. **Educational Assessment**: Every interaction evaluates Bloom's Taxonomy levels
3. **Living World**: All actions, conversations, and events are persisted
4. **Dimensional Growth**: Players develop across 7 human dimensions
5. **Adaptive Difficulty**: Content adjusts to player Bloom's maturity level
6. **Multiplayer Ready**: Supports single-player and multiplayer sessions

### Technology Stack

- **Workflow Orchestration**: LangGraph (state machines for game loops)
- **AI Agents**: LangChain + Anthropic Claude (Game Master, NPC controllers)
- **Context Protocol**: MCP Servers (player-data, npc-personality, world-universe, quest-mission, item-equipment)
- **Message Bus**: RabbitMQ (event distribution, multiplayer coordination)
- **Data Stores**:
  - MongoDB: Campaign content, game sessions, interaction history
  - Neo4j: World graph, relationships, knowledge/item dependencies
  - PostgreSQL: Player profiles, analytics, Bloom's progression
  - Redis: Real-time state, session cache, player presence

---

## 2. Core Architecture

### High-Level Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     Game Playing Engine                       │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │         Game Master Agent (Orchestrator)               │  │
│  │  - Campaign narrative flow                              │  │
│  │  - Scene transitions & pacing                           │  │
│  │  - Player action interpretation                         │  │
│  │  - Dynamic event generation                             │  │
│  └───────────┬────────────────────────────────┬───────────┘  │
│              │                                │                │
│    ┌─────────┴─────────┐          ┌─────────┴──────────┐    │
│    │  NPC Controller   │          │  Assessment Engine │    │
│    │  Agent            │          │  Agent             │    │
│    │  - Dialogue gen   │          │  - Rubric scoring  │    │
│    │  - Personality    │          │  - Bloom's eval    │    │
│    │  - Affinity       │          │  - Rewards         │    │
│    └─────────┬─────────┘          └─────────┬──────────┘    │
│              │                                │                │
│    ┌─────────┴────────────────────────────────┴──────────┐  │
│    │           LangGraph Game Loop Workflow              │  │
│    │  (State machine for turn-based/real-time play)      │  │
│    └──────────────────────┬──────────────────────────────┘  │
│                            │                                  │
└────────────────────────────┼──────────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                  │
   ┌────────┴─────────┐           ┌──────────┴────────┐
   │  MCP Servers     │           │  RabbitMQ Bus     │
   │  - player-data   │           │  - game.events    │
   │  - npc-person    │           │  - game.actions   │
   │  - world-univ    │           │  - multiplayer.*  │
   │  - quest-miss    │           │  - session.state  │
   │  - item-equip    │           └────────┬──────────┘
   └────────┬─────────┘                    │
            │                              │
   ┌────────┴──────────────────────────────┴──────────┐
   │           Data Persistence Layer                  │
   │  MongoDB    Neo4j    PostgreSQL    Redis          │
   └───────────────────────────────────────────────────┘
```

### Service Components

#### Game Engine Service (NEW)
- **Location**: `services/game-engine`
- **Language**: Python 3.11
- **Framework**: FastAPI + LangGraph
- **Purpose**: Real-time gameplay orchestration
- **Ports**: 9500 (HTTP API), 9501 (WebSocket)

#### Game Master Agent (NEW)
- **Location**: `ai-agents/game-master`
- **Language**: Python 3.11
- **Framework**: LangChain + LangGraph
- **Purpose**: Narrative control, scene management, player interpretation
- **Integration**: Uses all MCP servers

#### Session Manager Service (NEW)
- **Location**: `services/session-manager`
- **Language**: Python 3.11
- **Purpose**: Multi-player session coordination, turn management
- **Ports**: 9600

---

## 3. Chat Interface & User Experience

### Overview

The **Interactive Chat Window** is the primary interface for gameplay, managed entirely by the Game Master agent. Players interact with the game through a rich, conversational interface that feels like having a personal Game Master guiding them through their adventure.

### Design Philosophy

1. **Chat-First Gameplay**: All interactions happen through natural conversation
2. **GM as Guide**: The Game Master speaks in second person, creating immersion
3. **Rich Media**: Support for images, videos, and audio enhances storytelling
4. **Complete History**: Every message is persisted for context and replay
5. **Accessibility**: Text-based with future STT/TTS support

---

### Chat Message Types

```python
class ChatMessageType(Enum):
    """Types of messages in the chat"""
    GM_NARRATIVE = "gm_narrative"          # Scene descriptions, story narration
    GM_NPC_DIALOGUE = "gm_npc_dialogue"    # NPC speaking (quoted dialogue)
    GM_SYSTEM = "gm_system"                # Game mechanics, notifications
    GM_ASSESSMENT = "gm_assessment"        # Performance feedback
    PLAYER_ACTION = "player_action"        # Player's input/action
    PLAYER_OOC = "player_ooc"             # Out-of-character player message
    MEDIA_SCENE = "media_scene"            # Scene image/video
    MEDIA_AUDIO = "media_audio"            # Background music, sound effects
    LEVEL_UP = "level_up"                  # Dimensional level up notification
    QUEST_UPDATE = "quest_update"          # Quest progress update
```

### Chat Message Schema

```python
class ChatMessage(TypedDict):
    """Single message in the game chat"""

    # Message Identity
    message_id: str
    session_id: str
    timestamp: str  # ISO 8601

    # Message Type & Sender
    message_type: ChatMessageType
    sender: str  # "gm", "player_{id}", "npc_{id}", "system"
    sender_display_name: str  # "Game Master", "Player Name", "NPC Name"

    # Content
    content: str  # Main text content (Markdown supported)
    formatted_content: Optional[str]  # HTML-formatted version

    # Rich Media Attachments
    media_attachments: List[MediaAttachment]

    # Context & Metadata
    related_entity_id: Optional[str]  # NPC ID, challenge ID, etc.
    related_entity_type: Optional[str]  # "npc", "challenge", "discovery", etc.
    scene_id: Optional[str]  # Which scene this message relates to
    quest_id: Optional[str]  # Which quest this message relates to

    # Game State References
    triggered_by_action: Optional[str]  # Action ID that caused this message
    assessment_id: Optional[str]  # If this is assessment feedback

    # Display Properties
    importance: str  # "critical", "high", "normal", "low"
    style: Optional[str]  # CSS class for custom styling
    collapse_after: Optional[int]  # Seconds before message can be collapsed

    # Player-specific (for multiplayer)
    visible_to_players: List[str]  # Empty = all players
    player_id: Optional[str]  # If player-sent

    # Interaction
    requires_response: bool  # GM is waiting for player input
    available_actions: List[str]  # Suggested actions (optional)
    quick_replies: List[str]  # Quick reply buttons (optional)


class MediaAttachment(TypedDict):
    """Media embedded in a chat message"""
    media_id: str
    media_type: str  # "image", "video", "audio", "document"
    url: str  # URL or data URI
    thumbnail_url: Optional[str]
    caption: Optional[str]
    alt_text: str  # For accessibility
    width: Optional[int]
    height: Optional[int]
    duration: Optional[int]  # For audio/video (seconds)
    size_bytes: Optional[int]
    mime_type: str
```

---

### Message Flow Examples

#### 1. Scene Description (GM Narrative)

```json
{
  "message_id": "msg_001",
  "session_id": "session_abc",
  "timestamp": "2025-10-15T10:30:00Z",
  "message_type": "gm_narrative",
  "sender": "gm",
  "sender_display_name": "Game Master",
  "content": "You find yourself standing in the **Harmonic Research Institute**, a sleek facility filled with humming machinery. The air vibrates with an almost imperceptible frequency. Dr. Elena Voss looks up from her console, her expression a mix of hope and exhaustion.",
  "media_attachments": [
    {
      "media_id": "img_001",
      "media_type": "image",
      "url": "/media/scenes/harmonic_institute.jpg",
      "alt_text": "Interior of Harmonic Research Institute",
      "caption": "The Harmonic Research Institute"
    }
  ],
  "scene_id": "scene_001",
  "quest_id": "quest_001",
  "importance": "high",
  "requires_response": true,
  "available_actions": [
    "Talk to Dr. Voss",
    "Examine the machinery",
    "Look around the room",
    "Check your equipment"
  ]
}
```

#### 2. NPC Dialogue (GM Speaking as NPC)

```json
{
  "message_id": "msg_002",
  "session_id": "session_abc",
  "timestamp": "2025-10-15T10:31:15Z",
  "message_type": "gm_npc_dialogue",
  "sender": "npc_dr_voss",
  "sender_display_name": "Dr. Elena Voss",
  "content": "\"Thank goodness someone is here! The sonic dampeners are failing faster than we anticipated. I've documented everything in my research logs, but I need someone who can actually *understand* what's happening. Have you had any experience with harmonic resonance systems?\"",
  "related_entity_id": "npc_dr_voss",
  "related_entity_type": "npc",
  "scene_id": "scene_001",
  "importance": "high",
  "requires_response": true,
  "quick_replies": [
    "Tell me more about the dampeners",
    "I've studied harmonic systems before",
    "I'm here to help, but I'll need guidance"
  ]
}
```

#### 3. Player Action

```json
{
  "message_id": "msg_003",
  "session_id": "session_abc",
  "timestamp": "2025-10-15T10:32:00Z",
  "message_type": "player_action",
  "sender": "player_123",
  "sender_display_name": "Aria Stormwind",
  "content": "I approach Dr. Voss with a calm demeanor and say, 'I've studied harmonic resonance in my engineering courses. Can you show me the dampener configuration? Maybe we can identify the failure point together.'",
  "player_id": "player_123",
  "importance": "normal"
}
```

#### 4. Assessment Feedback (GM)

```json
{
  "message_id": "msg_004",
  "session_id": "session_abc",
  "timestamp": "2025-10-15T10:33:30Z",
  "message_type": "gm_assessment",
  "sender": "gm",
  "sender_display_name": "Game Master",
  "content": "**Your Approach**: You demonstrated excellent rapport building and showed intellectual confidence without arrogance. Dr. Voss visibly relaxes.\n\n**Strengths**:\n- Calming presence (Emotional dimension: +25 XP)\n- Collaborative approach (Social dimension: +20 XP)\n- Applied prior knowledge (Intellectual dimension: +30 XP)\n\n**Growth Opportunity**: Consider asking about her emotional state and the team's morale to show deeper empathy.\n\n**Knowledge Gained**: *Dampener Configuration Basics* (Level 2/4)",
  "assessment_id": "assessment_001",
  "importance": "high",
  "style": "assessment-feedback",
  "collapse_after": 30
}
```

#### 5. Level Up Notification

```json
{
  "message_id": "msg_005",
  "session_id": "session_abc",
  "timestamp": "2025-10-15T10:33:35Z",
  "message_type": "level_up",
  "sender": "system",
  "sender_display_name": "SkillForge",
  "content": "🎉 **Level Up!** Your **Intellectual** dimension has advanced to **Bloom's Level 4: Analyze**.\n\nYou can now break down complex systems, identify patterns, and draw connections between ideas with greater sophistication.",
  "media_attachments": [
    {
      "media_id": "audio_levelup",
      "media_type": "audio",
      "url": "/media/sfx/level_up.mp3",
      "duration": 3,
      "mime_type": "audio/mpeg"
    }
  ],
  "importance": "critical",
  "style": "celebration"
}
```

---

### Chat History Persistence

#### MongoDB Collection: `chat_history`

```python
{
    "_id": "chat_msg_uuid",
    "session_id": "session_uuid",
    "campaign_id": "campaign_uuid",
    "message_sequence": 42,  # Order within session

    # Full message data (as defined in ChatMessage schema)
    "message_id": "msg_004",
    "timestamp": "ISO timestamp",
    "message_type": "gm_narrative",
    "sender": "gm",
    "sender_display_name": "Game Master",
    "content": "...",
    "formatted_content": "<p>...</p>",
    "media_attachments": [...],

    # Indexing & Search
    "scene_id": "scene_001",
    "quest_id": "quest_001",
    "keywords": ["dampener", "research", "sonic"],  # Auto-extracted
    "entities_mentioned": ["npc_dr_voss", "harmonic_institute"],

    # Analytics
    "player_read": true,  # Player scrolled past this message
    "player_reaction": "helpful",  # Optional player feedback

    # Retention
    "expires_at": null,  # null = keep forever, for temporary messages
    "archived": false
}
```

#### Indexes

```python
# MongoDB indexes for chat_history
db.chat_history.createIndex({"session_id": 1, "message_sequence": 1})
db.chat_history.createIndex({"session_id": 1, "timestamp": 1})
db.chat_history.createIndex({"player_id": 1, "timestamp": -1})
db.chat_history.createIndex({"related_entity_id": 1})
db.chat_history.createIndex({"scene_id": 1})
```

---

### WebSocket Protocol

#### Connection

```javascript
// Client connects to WebSocket
ws = new WebSocket("wss://skillforge.com/ws/game/session/{session_id}?token={auth_token}")

// Authenticate
ws.send(JSON.stringify({
  type: "auth",
  player_id: "player_123",
  token: "jwt_token_here"
}))
```

#### Message Events

```typescript
// Server -> Client: New chat message
{
  "event": "chat_message",
  "data": ChatMessage  // Full ChatMessage object
}

// Server -> Client: GM is typing
{
  "event": "gm_typing",
  "data": {
    "typing": true,
    "estimated_delay_seconds": 3
  }
}

// Server -> Client: NPC is typing
{
  "event": "npc_typing",
  "data": {
    "npc_id": "npc_dr_voss",
    "npc_name": "Dr. Elena Voss",
    "typing": true
  }
}

// Client -> Server: Player sends message
{
  "event": "player_message",
  "data": {
    "content": "I want to examine the dampeners closely",
    "message_type": "player_action"
  }
}

// Server -> Client: Message delivered confirmation
{
  "event": "message_delivered",
  "data": {
    "temp_id": "temp_msg_123",  // Client's temporary ID
    "message_id": "msg_456",     // Server-assigned permanent ID
    "timestamp": "ISO timestamp"
  }
}

// Server -> Client: Batch of history messages (on reconnect or scroll)
{
  "event": "history_batch",
  "data": {
    "messages": [ChatMessage, ChatMessage, ...],
    "has_more": true,
    "next_cursor": "msg_100"
  }
}
```

---

### Rich Media Integration

#### Image Generation for Scenes

```python
class SceneImageGenerator:
    """
    Generate scene images using DALL-E or Stable Diffusion
    Triggered during campaign generation or dynamically during gameplay
    """

    async def generate_scene_image(
        self,
        scene_description: str,
        style: str = "fantasy_realism"
    ) -> str:
        """
        Generate and return URL to scene image

        Args:
            scene_description: Text description of scene
            style: Art style (fantasy_realism, sci_fi, anime, etc.)

        Returns:
            URL to generated image (stored in S3/Cloud Storage)
        """

        # Generate prompt for image model
        image_prompt = self._build_image_prompt(scene_description, style)

        # Call image generation API (DALL-E, Stable Diffusion, etc.)
        image_url = await self.image_api.generate(image_prompt)

        # Store in cloud storage with CDN
        permanent_url = await self.storage.upload(image_url)

        # Cache association
        await self.cache_scene_image(scene_id, permanent_url)

        return permanent_url
```

#### Audio Support

```python
# Background music for scenes
{
  "media_type": "audio",
  "url": "/media/music/mysterious_laboratory.mp3",
  "loop": true,
  "volume": 0.3,
  "fade_in": 2  # seconds
}

# Sound effects for actions
{
  "media_type": "audio",
  "url": "/media/sfx/door_creak.mp3",
  "volume": 0.7,
  "autoplay": true
}

# Voice-acted NPC dialogue (future)
{
  "media_type": "audio",
  "url": "/media/voice/npc_dr_voss/greeting_001.mp3",
  "caption": "Dr. Voss speaking"
}
```

#### Video Support

```python
# Cutscenes or important events
{
  "media_type": "video",
  "url": "/media/videos/dampener_failure.mp4",
  "thumbnail_url": "/media/videos/dampener_failure_thumb.jpg",
  "caption": "The dampeners begin to overload",
  "autoplay": false,
  "width": 800,
  "height": 450
}
```

---

### Speech-to-Text (STT) & Text-to-Speech (TTS) Roadmap

#### Phase 1: Text-Only (Current)
- ✅ Full text-based interaction
- ✅ Markdown formatting
- ✅ Quick reply buttons
- ✅ Rich media display

#### Phase 2: Text-to-Speech (Months 3-4)
- [ ] **GM Voice**: TTS for all GM narration
  - Use ElevenLabs or Azure TTS
  - Multiple voice options (narrative style, friendly, dramatic)
  - Adjustable speed & pitch
- [ ] **NPC Voices**: Unique voice per NPC
  - Voice assigned during NPC creation
  - Personality-matched voice characteristics
  - Consistent across sessions
- [ ] **Accessibility**: Audio descriptions for visual elements

```python
class TextToSpeechService:
    """
    Converts chat messages to speech
    """

    async def synthesize_message(
        self,
        message: ChatMessage,
        voice_id: str = "default_gm"
    ) -> str:
        """
        Convert message content to speech

        Returns:
            URL to audio file (MP3)
        """

        # Strip markdown for speech
        text = self._strip_formatting(message["content"])

        # Select voice based on sender
        if message["sender"].startswith("npc_"):
            voice_id = await self.get_npc_voice(message["related_entity_id"])
        elif message["sender"] == "gm":
            voice_id = await self.get_gm_voice_preference(message["session_id"])

        # Synthesize speech
        audio_url = await self.tts_api.synthesize(
            text=text,
            voice_id=voice_id,
            speed=1.0,
            pitch=0
        )

        return audio_url
```

#### Phase 3: Speech-to-Text (Months 5-6)
- [ ] **Voice Input**: Players can speak their actions
  - Use Whisper AI or Azure STT
  - Real-time transcription
  - Confidence scoring
  - Fallback to text if unclear
- [ ] **Voice Commands**: Special commands ("pause game", "show inventory")
- [ ] **Multilingual**: Support for multiple languages

```python
class SpeechToTextService:
    """
    Converts player speech to text actions
    """

    async def transcribe_player_audio(
        self,
        audio_data: bytes,
        player_id: str,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe player audio input

        Returns:
            TranscriptionResult with text and confidence
        """

        # Transcribe using Whisper/Azure
        transcription = await self.stt_api.transcribe(
            audio=audio_data,
            language=language,
            model="whisper-large-v3"
        )

        # Check confidence
        if transcription["confidence"] < 0.7:
            return TranscriptionResult(
                text=transcription["text"],
                confidence=transcription["confidence"],
                requires_confirmation=True
            )

        return TranscriptionResult(
            text=transcription["text"],
            confidence=transcription["confidence"],
            requires_confirmation=False
        )
```

#### Phase 4: Full Voice Interaction (Months 7+)
- [ ] **Voice-First Mode**: Entire game playable via voice
- [ ] **Interrupt Handling**: Player can interrupt GM narration
- [ ] **Emotional Recognition**: Detect player emotion from voice
- [ ] **Ambient Listening**: Wake word activation ("Hey Game Master")

---

### Chat UI Components

```typescript
// React component structure

<GameChatWindow>
  <ChatHeader>
    <SessionInfo />
    <ProgressIndicator />
    <PlayerStatus />
  </ChatHeader>

  <ChatMessageList>
    {messages.map(message => (
      <ChatMessage
        key={message.message_id}
        message={message}
        onAction={handlePlayerAction}
      >
        {message.media_attachments && (
          <MediaAttachmentList attachments={message.media_attachments} />
        )}
        {message.quick_replies && (
          <QuickReplyButtons replies={message.quick_replies} />
        )}
      </ChatMessage>
    ))}

    {gmTyping && <TypingIndicator sender="Game Master" />}
  </ChatMessageList>

  <ChatInput>
    <TextInput
      placeholder="Describe your action..."
      onSubmit={sendMessage}
      suggestions={availableActions}
    />
    <VoiceInputButton /> {/* Phase 3 */}
    <MediaUploadButton /> {/* For player-submitted content */
  </ChatInput>

  <ChatSidebar>
    <QuestTracker />
    <InventoryPanel />
    <CharacterSheet />
    <DimensionalProgress />
  </ChatSidebar>
</GameChatWindow>
```

---

### Chat History API

```python
# GET /api/game/session/{session_id}/chat/history
{
  "messages": [ChatMessage, ChatMessage, ...],
  "total_count": 250,
  "page": 1,
  "page_size": 50,
  "has_next": true,
  "cursors": {
    "before": "msg_100",
    "after": "msg_150"
  }
}

# GET /api/game/session/{session_id}/chat/search
{
  "query": "dampener configuration",
  "filters": {
    "message_type": ["dm_narrative", "dm_npc_dialogue"],
    "sender": "npc_dr_voss",
    "date_range": {"start": "2025-10-15", "end": "2025-10-16"}
  },
  "results": [ChatMessage, ChatMessage, ...],
  "total_matches": 12
}

# POST /api/game/session/{session_id}/chat/export
{
  "format": "pdf",  # or "txt", "markdown", "html"
  "include_media": true,
  "include_timestamps": true,
  "filters": {...}
}
# Returns: Download URL for chat transcript
```

---

### Message Formatting Examples

#### Markdown Support in Content

```markdown
**Bold text** for emphasis
*Italic text* for thoughts
> Quoted text for recalled information
`Code formatting` for technical terms

- Bulleted lists
- For inventory items
- Or options

1. Numbered lists
2. For steps
3. In a process
```

#### GM Narration Styles

```python
# Scene Setting (Descriptive)
"You find yourself in a vast chamber, the walls lined with crystalline formations
that pulse with an otherworldly light. The air is thick with energy, making your
skin tingle."

# Action Narration (Dynamic)
"As you reach for the lever, the ground begins to shake. Dust falls from the
ceiling, and you hear a deep rumble echoing through the corridors."

# NPC Dialogue (Quoted)
Dr. Voss looks up, her eyes widening. "Wait! Don't touch that! If you adjust
the dampener without recalibrating the harmonics first, we'll trigger a
cascade failure!"

# Thought Prompts (Introspective)
"You pause, considering your options. Elena seems desperate, but something
in her expression suggests she's not telling you everything. Do you trust her?"
```

---

### Team Chat System

#### Overview

In addition to the GM-managed game chat, players need dedicated **team chat channels** for coordination, strategy discussions, and social interaction. The team chat system runs parallel to the game chat and supports multiple communication modes.

#### Team Chat Channels

```python
class TeamChatChannel(Enum):
    """Types of team chat channels"""
    PARTY = "party"              # All players in the session
    WHISPER = "whisper"          # Private 1-on-1 between two players
    OOC = "ooc"                  # Out-of-character chat (full party)
    STRATEGY = "strategy"        # In-character strategy discussion
    SYSTEM = "system"            # System notifications about players
```

#### Team Chat Message Schema

```python
class TeamChatMessage(TypedDict):
    """Message in team chat (player-to-player communication)"""

    # Message Identity
    message_id: str
    session_id: str
    channel: TeamChatChannel
    timestamp: str  # ISO 8601

    # Sender & Recipients
    sender_id: str
    sender_character_name: str
    sender_display_name: str
    recipient_ids: List[str]  # Empty = all party members

    # Content
    content: str  # Markdown supported
    formatted_content: Optional[str]

    # Metadata
    is_edited: bool
    edited_at: Optional[str]
    replied_to_message_id: Optional[str]  # Threading support

    # Mentions
    mentioned_player_ids: List[str]  # @mentions
    is_urgent: bool  # Highlighted message

    # Reactions (emoji reactions to messages)
    reactions: Dict[str, List[str]]  # emoji -> [player_ids]

    # Visibility & Moderation
    visible_to_gm: bool  # Can GM see this message?
    deleted: bool
    deleted_at: Optional[str]

    # Rich features
    attachments: List[str]  # URLs to files/images
    poll: Optional[PollData]  # For voting
```

---

#### Team Chat Channels Explained

##### 1. Party Channel (Primary Team Chat)

```python
# All players in the session can see and participate
{
  "channel": "party",
  "sender_id": "player_123",
  "sender_character_name": "Aria Stormwind",
  "content": "I think we should talk to Dr. Voss before examining the machinery. We might learn something useful.",
  "recipient_ids": [],  # Empty = all party
  "visible_to_gm": true  # GM can see party chat
}
```

**Use Cases**:
- Coordinating actions before taking them
- Discussing quest objectives
- Sharing knowledge and items
- Planning approach to challenges

##### 2. Whisper Channel (Private Messages)

```python
# Private 1-on-1 conversation between two players
{
  "channel": "whisper",
  "sender_id": "player_123",
  "sender_character_name": "Aria Stormwind",
  "content": "I don't trust Dr. Voss. Did you notice how she avoided answering my question?",
  "recipient_ids": ["player_456"],  # Only this player sees it
  "visible_to_gm": false  # Private, GM cannot see
}
```

**Use Cases**:
- Private strategy discussions
- Sharing suspicions
- Coordinating secret actions
- Building character relationships

##### 3. Out-of-Character (OOC) Channel

```python
# Breaks the fourth wall - players talking as themselves
{
  "channel": "ooc",
  "sender_id": "player_123",
  "sender_display_name": "Sarah",  # Real name, not character name
  "content": "Gotta step away for 5 minutes, brb!",
  "recipient_ids": [],
  "visible_to_gm": true
}
```

**Use Cases**:
- Real-life interruptions ("BRB", "AFK")
- Out-of-game discussions
- Scheduling ("Can we play tomorrow?")
- Complimenting another player's roleplay

##### 4. Strategy Channel (In-Character Planning)

```python
# In-character strategic discussion
{
  "channel": "strategy",
  "sender_id": "player_123",
  "sender_character_name": "Aria Stormwind",
  "content": "**Battle Plan**: I'll distract the guards while @Kael sneaks around to disable the alarm. @Lyra, can you provide cover with your sonic shield?",
  "mentioned_player_ids": ["player_456", "player_789"],
  "recipient_ids": [],
  "visible_to_dm": true
}
```

**Use Cases**:
- Tactical planning
- Combat strategy
- Role assignment
- Resource allocation

---

#### Team Chat Persistence

##### MongoDB Collection: `team_chat_history`

```python
{
    "_id": "team_msg_uuid",
    "session_id": "session_uuid",
    "campaign_id": "campaign_uuid",
    "message_sequence": 15,

    # Full team chat message
    "message_id": "tmsg_456",
    "timestamp": "ISO timestamp",
    "channel": "party",
    "sender_id": "player_123",
    "sender_character_name": "Aria Stormwind",
    "content": "...",
    "recipient_ids": [],
    "mentioned_player_ids": ["player_456"],

    # Reactions
    "reactions": {
        "👍": ["player_456", "player_789"],
        "❤️": ["player_789"]
    },

    # Moderation
    "visible_to_dm": true,
    "deleted": false,
    "is_edited": false,

    # Analytics
    "read_by_players": ["player_123", "player_456", "player_789"],
    "delivered_to_players": ["player_123", "player_456", "player_789"]
}
```

##### Indexes

```python
db.team_chat_history.createIndex({"session_id": 1, "message_sequence": 1})
db.team_chat_history.createIndex({"session_id": 1, "channel": 1, "timestamp": 1})
db.team_chat_history.createIndex({"sender_id": 1, "timestamp": -1})
db.team_chat_history.createIndex({"recipient_ids": 1})
db.team_chat_history.createIndex({"mentioned_player_ids": 1})
```

---

#### WebSocket Events for Team Chat

```typescript
// Client -> Server: Send team message
{
  "event": "team_message",
  "data": {
    "channel": "party",
    "content": "Let's check the machinery first",
    "recipient_ids": [],  // Empty = all party
    "mentioned_player_ids": ["player_456"]
  }
}

// Server -> Client: New team message received
{
  "event": "team_message_received",
  "data": TeamChatMessage  // Full message object
}

// Client -> Server: Player is typing in team chat
{
  "event": "team_typing",
  "data": {
    "channel": "party",
    "typing": true
  }
}

// Server -> Client: Another player is typing
{
  "event": "team_typing_indicator",
  "data": {
    "channel": "party",
    "player_id": "player_456",
    "character_name": "Kael Darkblade",
    "typing": true
  }
}

// Client -> Server: Add reaction to team message
{
  "event": "team_message_react",
  "data": {
    "message_id": "tmsg_456",
    "emoji": "👍"
  }
}

// Server -> Client: Reaction added
{
  "event": "team_message_reaction_update",
  "data": {
    "message_id": "tmsg_456",
    "emoji": "👍",
    "player_ids": ["player_123", "player_456"]
  }
}

// Client -> Server: Mark team messages as read
{
  "event": "team_messages_read",
  "data": {
    "channel": "party",
    "last_read_message_id": "tmsg_500"
  }
}

// Server -> Client: Player joined/left session
{
  "event": "team_player_status",
  "data": {
    "player_id": "player_789",
    "character_name": "Lyra Windsong",
    "status": "joined",  // or "left", "disconnected"
    "timestamp": "ISO timestamp"
  }
}
```

---

#### Team Chat UI Components

```typescript
// React component structure

<TeamChatPanel>
  <TeamChatTabs>
    <Tab id="party" badge={unreadCount}>
      Party (3)
    </Tab>
    <Tab id="whispers" badge={unreadWhispers}>
      Whispers
    </Tab>
    <Tab id="ooc">
      OOC
    </Tab>
    <Tab id="strategy">
      Strategy
    </Tab>
  </TeamChatTabs>

  <TeamChatMessageList channel={selectedChannel}>
    {messages.map(message => (
      <TeamChatMessage
        key={message.message_id}
        message={message}
        onReply={handleReply}
        onReact={handleReact}
        onWhisper={handleWhisper}
      >
        {message.reactions && (
          <ReactionBar reactions={message.reactions} onAddReaction={handleReact} />
        )}
        {message.poll && (
          <PollWidget poll={message.poll} onVote={handleVote} />
        )}
      </TeamChatMessage>
    ))}

    {typingPlayers.map(player => (
      <TypingIndicator key={player.player_id} playerName={player.character_name} />
    ))}
  </TeamChatMessageList>

  <TeamChatInput channel={selectedChannel}>
    <MentionAutocomplete players={partyMembers} />
    <TextInput
      placeholder={getPlaceholder(selectedChannel)}
      onSubmit={sendTeamMessage}
    />
    <EmojiPicker />
    <AttachFileButton />
    <CreatePollButton />
  </TeamChatInput>

  <TeamChatPartyList>
    {partyMembers.map(member => (
      <PartyMemberCard
        key={member.player_id}
        member={member}
        onWhisper={() => openWhisper(member.player_id)}
        onViewCharacter={() => showCharacterSheet(member)}
      />
    ))}
  </TeamChatPartyList>
</TeamChatPanel>
```

---

#### Integrated Chat Layout

The game UI combines both GM game chat and team chat:

```
┌─────────────────────────────────────────────────────────┐
│                    Game Header                          │
│  Quest: The Harmonic Crisis     Session: 2h 15m         │
└─────────────────────────────────────────────────────────┘
┌──────────────────────────┬──────────────────────────────┐
│                          │                              │
│   Main Game Chat (GM)    │      Team Chat Panel         │
│                          │  ┌──────────────────────┐    │
│  GM: You find yourself   │  │ Party │ Whispers │OOC│    │
│  in the Harmonic Inst.   │  └──────────────────────┘    │
│                          │                              │
│  Dr. Voss: "Thank        │  Aria: "Let's talk to Dr.   │
│  goodness you're here!"  │  Voss first before we do    │
│                          │  anything else"              │
│  [Your turn...]          │                              │
│                          │  Kael: "Agreed. I'll keep   │
│  ┌──────────────────┐    │  an eye on the machinery"   │
│  │ Describe action  │    │  👍 (Aria, Lyra)            │
│  └──────────────────┘    │                              │
│                          │  Lyra is typing...          │
│                          │                              │
│                          │  ┌─────────────────────┐    │
│                          │  │ Type message...     │    │
│                          │  └─────────────────────┘    │
│                          │                              │
│                          │  Party Members:             │
│                          │  • Aria Stormwind (You)     │
│                          │  • Kael Darkblade           │
│                          │  • Lyra Windsong            │
└──────────────────────────┴──────────────────────────────┘
```

---

#### Mention System (@mentions)

```python
# Player types: "Hey @Kael, can you check the console?"
# System auto-detects mention and notifies Kael

{
  "content": "Hey @Kael, can you check the console?",
  "mentioned_player_ids": ["player_456"],
  "notifications": [
    {
      "player_id": "player_456",
      "type": "mention",
      "from_player": "player_123",
      "from_character": "Aria Stormwind",
      "message_preview": "Hey @Kael, can you check the console?"
    }
  ]
}

# Kael receives:
# - Browser notification (if enabled)
# - Sound alert
# - Visual highlight in chat
# - Unread badge on Team Chat tab
```

---

#### Team Chat Polls & Voting

```python
class PollData(TypedDict):
    """Poll/vote within team chat"""
    poll_id: str
    question: str
    options: List[str]
    votes: Dict[str, str]  # player_id -> selected_option
    allow_multiple: bool
    closes_at: Optional[str]  # ISO timestamp
    is_anonymous: bool

# Example: Strategy vote
{
  "channel": "strategy",
  "sender_id": "player_123",
  "content": "How should we approach this?",
  "poll": {
    "poll_id": "poll_001",
    "question": "Approach strategy?",
    "options": [
      "Talk to Dr. Voss first",
      "Examine machinery first",
      "Search the room for clues"
    ],
    "votes": {
      "player_123": "Talk to Dr. Voss first",
      "player_456": "Talk to Dr. Voss first",
      "player_789": "Search the room for clues"
    },
    "allow_multiple": false,
    "is_anonymous": false
  }
}
```

---

#### Team Chat Moderation & Safety

##### Parental Controls Integration

```python
# For family accounts with children
class TeamChatControls(TypedDict):
    player_id: str

    # Restrictions
    can_send_whispers: bool  # Can send private messages
    can_receive_whispers: bool
    can_use_ooc_chat: bool
    requires_approval: bool  # Messages need parent approval

    # Filtering
    profanity_filter_enabled: bool
    allowed_words_only: bool

    # Monitoring
    parent_can_view_all: bool  # Parent sees all team chat
    chat_log_sent_to_parent: bool
```

##### GM Oversight

```python
# GM can see party chat and strategy chat (configurable)
# GM cannot see whispers (private player-to-player)
# GM can intervene if needed:

{
  "event": "gm_team_chat_message",
  "data": {
    "message_id": "gmsg_001",
    "sender": "gm",
    "sender_display_name": "Game Master",
    "channel": "party",
    "content": "Great teamwork, everyone! Remember, Dr. Voss is waiting for your decision.",
    "is_gm_message": true,
    "style": "gm-intervention"
  }
}
```

---

#### Team Chat Features

##### 1. Message Threading

```python
# Reply to specific messages
{
  "message_id": "tmsg_789",
  "content": "That's a good point!",
  "replied_to_message_id": "tmsg_456",  # Creates thread
  "thread_depth": 1
}

# UI shows threaded conversation
```

##### 2. Emoji Reactions

```python
# Quick reactions without typing
{
  "message_id": "tmsg_456",
  "reactions": {
    "👍": ["player_123", "player_789"],
    "🎯": ["player_456"],
    "🔥": ["player_123"]
  }
}
```

##### 3. Typing Indicators

```typescript
// Shows "Kael is typing..." in party chat
// Shows "2 people are typing..." if multiple
```

##### 4. Read Receipts

```python
# Track who has read messages (optional feature)
{
  "message_id": "tmsg_456",
  "read_by_players": ["player_123", "player_456"],
  "unread_by": ["player_789"]
}
```

##### 5. Message Editing

```python
# Player can edit their own messages within 5 minutes
{
  "message_id": "tmsg_456",
  "content": "Let's talk to Dr. Voss first (edited)",
  "is_edited": true,
  "edited_at": "ISO timestamp",
  "edit_history": [
    {"content": "Let's talk to Dr. Vos first", "timestamp": "..."}
  ]
}
```

---

#### Team Chat API Endpoints

```python
# GET /api/game/session/{session_id}/team-chat/history
{
  "channel": "party",  # or "whispers", "ooc", "strategy"
  "messages": [TeamChatMessage, ...],
  "total_count": 150,
  "page": 1,
  "has_next": true
}

# POST /api/game/session/{session_id}/team-chat/message
{
  "channel": "party",
  "content": "Let's do this!",
  "mentioned_player_ids": ["player_456"]
}

# POST /api/game/session/{session_id}/team-chat/whisper
{
  "recipient_id": "player_456",
  "content": "I think we should be careful"
}

# POST /api/game/session/{session_id}/team-chat/react
{
  "message_id": "tmsg_456",
  "emoji": "👍"
}

# DELETE /api/game/session/{session_id}/team-chat/message/{message_id}
# Soft delete - marks message as deleted

# PUT /api/game/session/{session_id}/team-chat/message/{message_id}
{
  "content": "Updated message content"
}
# Only allowed within 5 minutes of sending

# GET /api/game/session/{session_id}/team-chat/unread
{
  "party": 5,
  "whispers": 2,
  "ooc": 0,
  "strategy": 1,
  "total": 8
}
```

---

#### Notifications

```python
class TeamChatNotification(TypedDict):
    notification_id: str
    player_id: str
    type: str  # "mention", "whisper", "poll", "dm_message"

    # Source
    from_player_id: str
    from_character_name: str
    message_id: str
    message_preview: str  # First 50 chars

    # Delivery
    timestamp: str
    read: bool
    channel: str

# Notification triggers:
# - @mention in any channel
# - New whisper (private message)
# - Poll created in party/strategy
# - GM sends message to team chat
# - Player joins/leaves session
```

---

#### Team Chat Best Practices

##### For Players
1. **Use Party Chat** for general coordination
2. **Use Whispers** for private strategy or character moments
3. **Use OOC** for real-life interruptions ("BRB")
4. **Use Strategy** for tactical planning and combat coordination
5. **@mention players** when you need their specific attention
6. **React with emojis** for quick acknowledgment

##### For GMs
1. **Monitor Party Chat** to understand player intentions
2. **Respect Whispers** - don't read private messages unless needed
3. **Intervene sparingly** - let players coordinate naturally
4. **Use polls** to gauge party consensus
5. **Celebrate teamwork** in party chat

---

## 4. Campaign & Session Management

### Overview

Players need a comprehensive system to discover campaigns, start game sessions, manage multiplayer experiences, and control their gameplay flow. This system bridges the gap between campaign generation and active gameplay.

### Design Philosophy

1. **Seamless Discovery**: Browse and preview campaigns effortlessly
2. **Flexible Modes**: Support solo and multiplayer sessions
3. **Social Integration**: Easy invitations and party formation
4. **Session Continuity**: Pause, resume, and save progress reliably
5. **Transparency**: Clear campaign information and requirements

---

### Campaign Discovery & Browsing

#### Campaign Catalog

```python
class CampaignMetadata(TypedDict):
    """Campaign information for browsing"""

    # Identity
    campaign_id: str
    name: str
    description: str
    cover_image_url: str
    thumbnail_url: str

    # Classification
    universe_id: str
    universe_name: str
    world_id: str
    world_name: str
    region_id: str
    region_name: str
    genre: str  # sci-fi, fantasy, mystery, etc.

    # Difficulty & Scope
    difficulty_level: str  # Easy, Medium, Hard, Expert
    estimated_duration_hours: int
    target_blooms_level: int  # Primary target (1-6)
    primary_dimension: str  # Main dimension developed

    # Content Stats
    num_quests: int
    num_scenes: int
    num_npcs: int
    num_challenges: int

    # Requirements
    min_player_level: int  # Minimum Bloom's level
    max_players: int  # 1 for solo, 4 for party
    required_knowledge: List[str]  # Prerequisites

    # Metadata
    created_at: str
    created_by: str  # "system" or user_id
    tags: List[str]  # ["puzzle-heavy", "combat-light", "story-rich"]
    is_published: bool
    is_featured: bool

    # Engagement
    total_plays: int
    average_rating: float
    completion_rate: float
    average_playtime_hours: float
```

#### Campaign Browser UI

```typescript
// Campaign Browser Component

<CampaignBrowser>
  <CampaignFilters>
    <GenreFilter options={["All", "Sci-Fi", "Fantasy", "Mystery", "Horror"]} />
    <DifficultyFilter options={["Easy", "Medium", "Hard", "Expert"]} />
    <DurationFilter options={["< 5 hours", "5-10 hours", "10-20 hours", "20+ hours"]} />
    <DimensionFilter dimensions={["Intellectual", "Social", "Emotional", etc.]} />
    <PlayerCountFilter options={["Solo", "2 Players", "3-4 Players"]} />
  </CampaignFilters>

  <SortOptions>
    <SortButton value="featured">Featured</SortButton>
    <SortButton value="new">Newest</SortButton>
    <SortButton value="popular">Most Popular</SortButton>
    <SortButton value="rating">Highest Rated</SortButton>
    <SortButton value="duration">Duration</SortButton>
  </SortOptions>

  <CampaignGrid>
    {campaigns.map(campaign => (
      <CampaignCard
        campaign={campaign}
        onClick={() => openCampaignDetails(campaign.campaign_id)}
      >
        <CampaignThumbnail src={campaign.thumbnail_url} />
        <CampaignTitle>{campaign.name}</CampaignTitle>
        <CampaignStats>
          <Duration>{campaign.estimated_duration_hours}h</Duration>
          <Difficulty>{campaign.difficulty_level}</Difficulty>
          <Players>{campaign.max_players} players</Players>
          <Rating>{campaign.average_rating} ★</Rating>
        </CampaignStats>
        <CampaignTags tags={campaign.tags} />
      </CampaignCard>
    ))}
  </CampaignGrid>
</CampaignBrowser>
```

---

### Campaign Details & Preview

```python
class CampaignDetails(TypedDict):
    """Detailed campaign information"""

    # All metadata from CampaignMetadata
    metadata: CampaignMetadata

    # Story Preview
    story_summary: str  # Spoiler-free overview
    opening_scene: str  # First 2-3 paragraphs
    plot_hook: str  # What draws players in

    # Learning Outcomes
    learning_objectives: List[str]
    blooms_progression: Dict[str, int]  # dimension -> target level
    key_skills: List[str]

    # Quest Overview (Spoiler-free)
    quest_summaries: List[Dict[str, str]]  # [{title, description, estimated_time}]

    # Sample Content
    featured_npcs: List[Dict[str, str]]  # [{name, role, personality_snippet}]
    sample_challenges: List[str]

    # Player Reviews
    reviews: List[PlayerReview]

    # Progress (if player started before)
    player_progress: Optional[PlayerCampaignProgress]
```

#### Campaign Detail View

```typescript
<CampaignDetailView>
  <CampaignHeader>
    <CoverImage src={campaign.cover_image_url} />
    <CampaignInfo>
      <Title>{campaign.name}</Title>
      <Description>{campaign.description}</Description>
      <Stats>
        <Duration>{campaign.estimated_duration_hours} hours</Duration>
        <Difficulty>{campaign.difficulty_level}</Difficulty>
        <Rating>{campaign.average_rating} ★ ({campaign.total_plays} plays)</Rating>
      </Stats>
    </CampaignInfo>
    <ActionButtons>
      <StartSoloButton onClick={startSoloCampaign}>
        Play Solo
      </StartSoloButton>
      <StartPartyButton onClick={createPartySession}>
        Play with Friends
      </StartPartyButton>
      {playerProgress && (
        <ResumeButton onClick={resumeSession}>
          Resume (Quest {playerProgress.current_quest_number}/
                  {campaign.num_quests})
        </ResumeButton>
      )}
    </ActionButtons>
  </CampaignHeader>

  <Tabs>
    <Tab name="Story">
      <StorySummary>{campaign.story_summary}</StorySummary>
      <PlotHook>{campaign.plot_hook}</PlotHook>
      <OpeningScene>{campaign.opening_scene}</OpeningScene>
    </Tab>

    <Tab name="Learning">
      <LearningObjectives objectives={campaign.learning_objectives} />
      <BloomsProgression progression={campaign.blooms_progression} />
      <KeySkills skills={campaign.key_skills} />
    </Tab>

    <Tab name="Content">
      <QuestList quests={campaign.quest_summaries} />
      <FeaturedNPCs npcs={campaign.featured_npcs} />
      <SampleChallenges challenges={campaign.sample_challenges} />
    </Tab>

    <Tab name="Reviews">
      <ReviewList reviews={campaign.reviews} />
    </Tab>
  </Tabs>
</CampaignDetailView>
```

---

### Session Creation & Starting

#### Solo Session Creation

```python
# POST /api/game/session/start-solo
{
  "campaign_id": "campaign_uuid",
  "character_id": "character_uuid",
  "settings": {
    "difficulty_override": null,  # null = use campaign default
    "enable_hints": true,
    "dm_personality": "friendly",  # friendly, dramatic, humorous
    "pacing": "normal"  # relaxed, normal, fast
  }
}

# Response
{
  "session_id": "session_uuid",
  "campaign_id": "campaign_uuid",
  "status": "initializing",  # initializing -> active
  "websocket_url": "wss://skillforge.com/ws/game/session/{session_id}",
  "estimated_init_time_seconds": 5,
  "starting_scene_id": "scene_001",
  "dm_greeting": "Welcome! Let me prepare your adventure..."
}
```

#### Multiplayer Party Session

```python
class PartySessionRequest(TypedDict):
    """Request to create multiplayer session"""
    campaign_id: str
    host_character_id: str
    invited_player_ids: List[str]  # Can be empty (invite later)

    # Session Settings
    max_players: int  # 2-4
    is_public: bool  # Allow join requests from friends
    game_mode: str  # "turn_based" or "cooperative"

    # Scheduling
    scheduled_start: Optional[str]  # ISO timestamp (null = start now)
    estimated_session_duration_minutes: Optional[int]

    # Settings
    settings: Dict[str, Any]

# POST /api/game/session/create-party
{
  "campaign_id": "campaign_uuid",
  "host_character_id": "character_uuid",
  "invited_player_ids": ["player2_uuid", "player3_uuid"],
  "max_players": 4,
  "is_public": false,
  "game_mode": "turn_based",
  "settings": {
    "difficulty_override": "Hard",
    "enable_hints": true,
    "turn_time_limit_seconds": 300  # 5 minutes per turn
  }
}

# Response
{
  "session_id": "session_uuid",
  "party_id": "party_uuid",
  "status": "waiting_for_players",
  "host_player_id": "player1_uuid",
  "invited_players": [
    {
      "player_id": "player2_uuid",
      "status": "invited",  # invited, accepted, declined
      "invited_at": "ISO timestamp"
    },
    {
      "player_id": "player3_uuid",
      "status": "invited",
      "invited_at": "ISO timestamp"
    }
  ],
  "current_player_count": 1,
  "max_players": 4,
  "invite_links": {
    "player2_uuid": "https://skillforge.com/join/{invite_token_2}",
    "player3_uuid": "https://skillforge.com/join/{invite_token_3}"
  },
  "can_start": false  # true when min players ready
}
```

---

### Player Invitations & Joining

#### Invitation System

```python
class SessionInvitation(TypedDict):
    """Invitation to join a game session"""
    invitation_id: str
    session_id: str
    party_id: str

    # Sender
    invited_by_player_id: str
    invited_by_player_name: str

    # Recipient
    invited_player_id: str

    # Campaign Info
    campaign_id: str
    campaign_name: str
    campaign_thumbnail_url: str

    # Session Info
    game_mode: str
    current_player_count: int
    max_players: int
    scheduled_start: Optional[str]

    # Invitation Status
    status: str  # pending, accepted, declined, expired
    expires_at: str
    created_at: str

    # Invitation Link
    invite_token: str
    invite_url: str

# GET /api/player/{player_id}/invitations
{
  "pending_invitations": [SessionInvitation, ...],
  "accepted_invitations": [SessionInvitation, ...],
  "total_pending": 3
}
```

#### Joining Flow

```python
# Accept Invitation
# POST /api/game/session/{session_id}/accept-invite
{
  "invitation_id": "invite_uuid",
  "character_id": "character_uuid"
}

# Response
{
  "status": "accepted",
  "session_id": "session_uuid",
  "party_id": "party_uuid",
  "websocket_url": "wss://...",
  "current_players": [
    {
      "player_id": "player1_uuid",
      "character_name": "Aria",
      "status": "ready"
    },
    {
      "player_id": "player2_uuid",
      "character_name": "Kael",
      "status": "ready"
    }
  ],
  "waiting_for": ["player3_uuid"],
  "can_start": true  # If minimum players met
}

# Decline Invitation
# POST /api/game/session/{session_id}/decline-invite
{
  "invitation_id": "invite_uuid",
  "reason": "Schedule conflict"  # Optional
}
```

#### Party Lobby UI

```typescript
<PartyLobby>
  <CampaignBanner campaign={campaign} />

  <PlayerList>
    <PlayerSlot status="ready">
      <PlayerAvatar character={host} />
      <PlayerName>{host.name}</PlayerName>
      <HostBadge>Host</HostBadge>
      <ReadyIndicator>Ready ✓</ReadyIndicator>
    </PlayerSlot>

    <PlayerSlot status="waiting">
      <InviteIndicator>Waiting for Player 2...</InviteIndicator>
      {isHost && <ResendInviteButton />}
    </PlayerSlot>

    <PlayerSlot status="open">
      <EmptySlot>
        {isHost && <InvitePlayerButton onClick={openInviteDialog} />}
      </EmptySlot>
    </PlayerSlot>
  </PlayerList>

  <SessionSettings>
    <GameMode>{session.game_mode}</GameMode>
    <Difficulty>{session.settings.difficulty_override}</Difficulty>
    {session.game_mode === "turn_based" && (
      <TurnTimeLimit>{session.settings.turn_time_limit_seconds}s</TurnTimeLimit>
    )}
  </SessionSettings>

  <ChatPreview>
    {/* Pre-game chat for coordination */}
  </ChatPreview>

  <ActionButtons>
    {isHost && (
      <StartGameButton
        disabled={!session.can_start}
        onClick={startSession}
      >
        Start Adventure
      </StartGameButton>
    )}
    <LeaveLobbyButton onClick={leaveLobby}>
      Leave
    </LeaveLobbyButton>
  </ActionButtons>
</PartyLobby>
```

---

### Session Lifecycle Management

#### Session States

```python
class SessionStatus(Enum):
    INITIALIZING = "initializing"      # Creating world state
    WAITING_FOR_PLAYERS = "waiting_for_players"  # Multiplayer lobby
    ACTIVE = "active"                  # Game in progress
    PAUSED = "paused"                  # Temporarily paused
    COMPLETED = "completed"            # Campaign finished
    ABANDONED = "abandoned"            # Players quit without finishing
    ERROR = "error"                    # Fatal error occurred
```

#### Pause Session

```python
# POST /api/game/session/{session_id}/pause
{
  "reason": "break"  # break, disconnect, emergency
}

# Response
{
  "status": "paused",
  "paused_at": "ISO timestamp",
  "paused_by_player_id": "player_uuid",
  "state_snapshot_id": "snapshot_uuid",  # For resuming
  "resume_token": "resume_token_123"
}

# System Actions on Pause:
# 1. Capture complete state snapshot
# 2. Persist chat history up to pause point
# 3. Save player positions, inventory, knowledge
# 4. Store DM's planned events
# 5. Close WebSocket connections gracefully
# 6. Send pause notifications to all players
```

#### Resume Session

```python
# POST /api/game/session/{session_id}/resume
{
  "resume_token": "resume_token_123"  # Security token
}

# Response
{
  "status": "active",
  "resumed_at": "ISO timestamp",
  "session_id": "session_uuid",
  "websocket_url": "wss://...",
  "state_restored": true,
  "gm_greeting": "Welcome back! You were at the Harmonic Institute...",
  "current_scene_id": "scene_003",
  "reconnected_players": ["player1", "player2"],
  "waiting_for_players": ["player3"]  # Who hasn't reconnected yet
}

# System Actions on Resume:
# 1. Load state snapshot
# 2. Restore chat history
# 3. Reconnect active players via WebSocket
# 4. GM provides "recap" message
# 5. Resume workflow from paused node
# 6. Re-enable player input
```

#### Save & Load

```python
# Manual Save (checkpoint)
# POST /api/game/session/{session_id}/save
{
  "save_name": "Before entering the ruins",
  "is_auto_save": false
}

# Response
{
  "save_id": "save_uuid",
  "save_name": "Before entering the ruins",
  "saved_at": "ISO timestamp",
  "campaign_progress": {
    "current_quest": 2,
    "total_quests": 5,
    "completion_percentage": 40
  },
  "player_levels": {
    "intellectual": 3,
    "social": 4,
    "emotional": 3
  }
}

# List Saves
# GET /api/game/session/{session_id}/saves
{
  "saves": [
    {
      "save_id": "save_uuid_1",
      "save_name": "Auto-save (Quest 2 Complete)",
      "is_auto_save": true,
      "saved_at": "ISO timestamp",
      "thumbnail_url": "/saves/save_uuid_1_thumb.jpg"
    },
    {
      "save_id": "save_uuid_2",
      "save_name": "Before entering the ruins",
      "is_auto_save": false,
      "saved_at": "ISO timestamp"
    }
  ]
}

# Load Save
# POST /api/game/session/load
{
  "save_id": "save_uuid_2"
}

# Creates new session from save point
```

#### End Session

```python
# POST /api/game/session/{session_id}/end
{
  "end_reason": "completed",  # completed, quit, timeout
  "final_feedback": "Great adventure!"  # Optional
}

# Response
{
  "status": "completed",
  "ended_at": "ISO timestamp",
  "session_duration_minutes": 180,
  "campaign_completed": true,
  "final_stats": {
    "quests_completed": 5,
    "scenes_explored": 23,
    "npcs_met": 12,
    "challenges_faced": 18,
    "total_xp_earned": 1250,
    "dimensional_progress": {
      "intellectual": {"start": 2, "end": 4},
      "social": {"start": 3, "end": 5},
      "emotional": {"start": 2, "end": 3}
    }
  },
  "achievements_unlocked": [
    "First Campaign Complete",
    "Master Negotiator",
    "Knowledge Seeker"
  ],
  "chat_transcript_url": "/api/game/session/{session_id}/transcript"
}
```

---

### Player Progress Tracking

```python
class PlayerCampaignProgress(TypedDict):
    """Track player's progress in a campaign"""

    player_id: str
    campaign_id: str

    # Session History
    sessions: List[str]  # session_ids
    current_session_id: Optional[str]
    total_playtime_minutes: int

    # Campaign Progress
    current_quest_number: int
    total_quests: int
    completed_quest_ids: List[str]
    current_scene_id: str
    completed_scene_ids: List[str]
    completion_percentage: float

    # Character State
    character_id: str
    inventory_item_ids: List[str]
    acquired_knowledge: Dict[str, int]  # knowledge_id -> level (1-4)

    # Dimensional Progress
    dimensional_start_levels: Dict[str, int]
    dimensional_current_levels: Dict[str, int]
    total_xp_earned: int

    # Relationships
    npc_affinities: Dict[str, int]  # npc_id -> affinity (-100 to 100)

    # Achievements
    achievements: List[str]

    # Metadata
    started_at: str
    last_played_at: str
    status: str  # in_progress, completed, abandoned
```

#### Progress Dashboard

```typescript
<CampaignProgressDashboard>
  <ProgressHeader>
    <CampaignTitle>{campaign.name}</CampaignTitle>
    <OverallProgress>
      <ProgressBar value={progress.completion_percentage} />
      <ProgressText>{progress.completion_percentage}% Complete</ProgressText>
    </OverallProgress>
  </ProgressHeader>

  <QuestProgress>
    <QuestTitle>Quest {progress.current_quest_number}/{progress.total_quests}</QuestTitle>
    {campaign.quest_summaries.map((quest, idx) => (
      <QuestItem
        key={idx}
        completed={progress.completed_quest_ids.includes(quest.id)}
        current={idx === progress.current_quest_number - 1}
      >
        <QuestName>{quest.title}</QuestName>
        <QuestStatus>{getQuestStatus(quest, progress)}</QuestStatus>
      </QuestItem>
    ))}
  </QuestProgress>

  <DimensionalGrowth>
    <SectionTitle>Your Growth</SectionTitle>
    {Object.entries(progress.dimensional_current_levels).map(([dimension, level]) => (
      <DimensionProgress key={dimension}>
        <DimensionName>{dimension}</DimensionName>
        <LevelChange>
          Level {progress.dimensional_start_levels[dimension]} →
          Level {level} (Bloom's: {BLOOMS_LEVELS[level]})
        </LevelChange>
        <ProgressIndicator value={level} max={6} />
      </DimensionProgress>
    ))}
  </DimensionalGrowth>

  <SessionHistory>
    <SectionTitle>Play Sessions</SectionTitle>
    <TotalPlaytime>{progress.total_playtime_minutes} minutes</TotalPlaytime>
    <SessionList sessions={progress.sessions} />
  </SessionHistory>

  <Achievements>
    <SectionTitle>Achievements</SectionTitle>
    <AchievementBadges badges={progress.achievements} />
  </Achievements>

  <ActionButtons>
    <ContinueButton onClick={resumeCampaign}>
      Continue Adventure
    </ContinueButton>
    <ViewTranscriptButton onClick={viewChatHistory}>
      View Story So Far
    </ViewTranscriptButton>
    <ShareProgressButton onClick={shareProgress}>
      Share Progress
    </ShareProgressButton>
  </ActionButtons>
</CampaignProgressDashboard>
```

---

### Campaign Management APIs

#### Complete API Specification

```python
# ============================================
# Campaign Discovery & Selection
# ============================================

# Browse Campaigns
GET    /api/campaigns
Query: ?genre=sci-fi&difficulty=Medium&max_players=4&sort=popular&page=1

# Get Campaign Details
GET    /api/campaigns/{campaign_id}

# Get Campaign Preview Content
GET    /api/campaigns/{campaign_id}/preview
Returns: Story summary, sample NPCs, spoiler-free content

# Search Campaigns
GET    /api/campaigns/search
Query: ?q=mystery+detective&min_duration=5&max_duration=20

# Get Featured Campaigns
GET    /api/campaigns/featured

# Get Player's Campaign Library
GET    /api/player/{player_id}/campaigns
Returns: Started, completed, bookmarked campaigns

# ============================================
# Session Creation & Management
# ============================================

# Start Solo Session
POST   /api/game/session/start-solo
Body: {campaign_id, character_id, settings}

# Create Party Session
POST   /api/game/session/create-party
Body: {campaign_id, host_character_id, invited_player_ids, settings}

# Get Session Details
GET    /api/game/session/{session_id}

# Update Session Settings (host only)
PUT    /api/game/session/{session_id}/settings
Body: {difficulty_override, turn_time_limit, etc.}

# ============================================
# Invitations & Joining
# ============================================

# Send Invitation
POST   /api/game/session/{session_id}/invite
Body: {player_ids: ["player2", "player3"]}

# Get Player's Invitations
GET    /api/player/{player_id}/invitations
Query: ?status=pending

# Accept Invitation
POST   /api/game/session/{session_id}/accept-invite
Body: {invitation_id, character_id}

# Decline Invitation
POST   /api/game/session/{session_id}/decline-invite
Body: {invitation_id, reason}

# Join via Link
GET    /api/game/join/{invite_token}
Redirects to party lobby or returns session info

# ============================================
# Session Lifecycle
# ============================================

# Start Session (from lobby)
POST   /api/game/session/{session_id}/start

# Pause Session
POST   /api/game/session/{session_id}/pause
Body: {reason}

# Resume Session
POST   /api/game/session/{session_id}/resume
Body: {resume_token}

# Save Session
POST   /api/game/session/{session_id}/save
Body: {save_name, is_auto_save}

# Load Session
POST   /api/game/session/load
Body: {save_id}

# End Session
POST   /api/game/session/{session_id}/end
Body: {end_reason, final_feedback}

# Get Session State
GET    /api/game/session/{session_id}/state

# ============================================
# Progress & History
# ============================================

# Get Player's Campaign Progress
GET    /api/player/{player_id}/campaign/{campaign_id}/progress

# Get Session History
GET    /api/game/session/{session_id}/history
Returns: Chat history, actions, events

# Get Session Stats
GET    /api/game/session/{session_id}/stats

# Export Session Transcript
POST   /api/game/session/{session_id}/export
Body: {format: "pdf|txt|markdown", include_media: true}

# ============================================
# Active Sessions
# ============================================

# Get Player's Active Sessions
GET    /api/player/{player_id}/sessions/active

# Get Player's Session History
GET    /api/player/{player_id}/sessions/history
Query: ?status=completed&limit=10

# Get Save Files
GET    /api/game/session/{session_id}/saves
```

---

### WebSocket Events for Session Management

```typescript
// Session State Changes
{
  "event": "session_state_changed",
  "data": {
    "session_id": "session_uuid",
    "old_status": "waiting_for_players",
    "new_status": "active",
    "timestamp": "ISO timestamp"
  }
}

// Player Joined Party
{
  "event": "player_joined",
  "data": {
    "player_id": "player2_uuid",
    "character_name": "Kael",
    "current_player_count": 2,
    "max_players": 4
  }
}

// Player Left Party
{
  "event": "player_left",
  "data": {
    "player_id": "player3_uuid",
    "reason": "disconnect",
    "remaining_players": ["player1", "player2"]
  }
}

// Session Starting
{
  "event": "session_starting",
  "data": {
    "countdown_seconds": 5,
    "dm_greeting": "Gathering around the table..."
  }
}

// Session Paused
{
  "event": "session_paused",
  "data": {
    "paused_by": "player1_uuid",
    "reason": "break",
    "resume_token": "token_123"
  }
}

// Session Resumed
{
  "event": "session_resumed",
  "data": {
    "resumed_at": "ISO timestamp",
    "dm_recap": "Welcome back! When we left off..."
  }
}

// Turn Changed (turn-based mode)
{
  "event": "turn_changed",
  "data": {
    "current_turn_player_id": "player2_uuid",
    "turn_number": 15,
    "time_limit_seconds": 300
  }
}
```

---

### Auto-Save System

```python
class AutoSaveManager:
    """
    Automatically saves session progress at key points
    """

    AUTOSAVE_TRIGGERS = [
        "quest_completed",
        "scene_changed",
        "major_decision",
        "level_up",
        "every_15_minutes"
    ]

    async def trigger_autosave(
        self,
        session_id: str,
        trigger_type: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Create autosave checkpoint

        Returns:
            save_id
        """

        # Generate save name
        save_name = self._generate_autosave_name(trigger_type, context)

        # Capture state
        state = await self.capture_session_state(session_id)

        # Persist to MongoDB
        save_id = await self.persist_save(
            session_id=session_id,
            save_name=save_name,
            state=state,
            is_auto_save=True,
            trigger=trigger_type
        )

        # Cleanup old autosaves (keep last 10)
        await self.cleanup_old_autosaves(session_id, keep_count=10)

        logger.info(f"Autosave created: {save_id} ({trigger_type})")

        return save_id

    def _generate_autosave_name(self, trigger: str, context: Dict) -> str:
        """Generate descriptive autosave name"""

        if trigger == "quest_completed":
            return f"Auto-save: Quest {context['quest_number']} Complete"
        elif trigger == "scene_changed":
            return f"Auto-save: Entered {context['scene_name']}"
        elif trigger == "level_up":
            return f"Auto-save: {context['dimension']} Level Up"
        else:
            return f"Auto-save: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
```

---

## 5. Data Model & Campaign Structure

### Campaign Hierarchy (Existing)

```
Campaign (MongoDB + Neo4j)
  ├── Quest 1
  │     ├── Place 1 (Level 2 Location)
  │     │     ├── Scene 1 (Level 3 Location)
  │     │     │     ├── NPCs
  │     │     │     ├── Knowledge Entities
  │     │     │     ├── Items
  │     │     │     ├── Discoveries
  │     │     │     ├── Events
  │     │     │     ├── Challenges
  │     │     │     └── Rubrics (evaluation criteria)
  │     │     └── Scene 2...
  │     └── Place 2...
  └── Quest 2...
```

### Game Session State (NEW)

```python
class GameSessionState(TypedDict):
    """Game session state for LangGraph workflow"""

    # Session metadata
    session_id: str
    campaign_id: str
    started_at: str
    status: str  # active, paused, completed

    # Player(s)
    players: List[PlayerSessionData]  # Supports multi-player
    current_turn_player_id: Optional[str]  # For turn-based

    # Campaign progress
    current_quest_id: str
    current_place_id: str
    current_scene_id: str
    completed_quest_ids: List[str]
    completed_scene_ids: List[str]

    # Scene context
    scene_description: str
    available_npcs: List[NPCData]
    available_actions: List[str]  # what player can do
    visible_items: List[str]
    active_events: List[EventData]
    active_challenges: List[ChallengeData]

    # Interaction history (living world memory)
    conversation_history: List[ConversationTurn]
    action_history: List[PlayerAction]
    event_log: List[GameEvent]

    # Player state
    player_inventories: Dict[str, List[str]]  # player_id -> item_ids
    player_knowledge: Dict[str, Dict[str, int]]  # player_id -> {knowledge_id: level}
    player_locations: Dict[str, str]  # player_id -> location_id
    player_dimensional_progress: Dict[str, DimensionalMaturity]

    # World state (living world)
    npc_states: Dict[str, NPCState]  # npc_id -> current state
    world_changes: List[WorldChange]  # permanent changes to world
    time_of_day: str
    elapsed_game_time: int  # minutes

    # GM context
    gm_narrative_notes: List[str]
    gm_planned_events: List[Dict[str, Any]]
    gm_difficulty_adjustments: Dict[str, Any]

    # Workflow state
    current_node: str
    pending_action: Optional[str]
    awaiting_player_input: bool
    last_updated: str
```

### Player Session Data

```python
class PlayerSessionData(TypedDict):
    player_id: str
    character_id: str
    character_name: str

    # Real-time Bloom's tracking
    current_blooms_levels: Dict[str, int]  # dimension -> level (1-6)
    session_interactions: int
    session_dimensional_xp: Dict[str, int]

    # Cognitive profile (from MCP)
    cognitive_profile: CognitiveProfile

    # Connection status (for multiplayer)
    is_connected: bool
    last_action_timestamp: str
```

---

## 4. Game Master Agent System

### Game Master Responsibilities

The GM Agent is the **central orchestrator** of gameplay. It:

1. **Narrates the Story**: Generates scene descriptions, narrative transitions
2. **Interprets Player Actions**: Converts natural language to game mechanics
3. **Controls All NPCs**: Generates dialogue, determines NPC reactions
4. **Manages Pacing**: Triggers events, adjusts difficulty, introduces challenges
5. **Evaluates Performance**: Works with Assessment Engine to score player actions
6. **Maintains Immersion**: Ensures consistency with world lore and character knowledge

### GM Agent Architecture

```python
class GameMasterAgent:
    """
    AI Agent that orchestrates all gameplay using LangChain
    """

    def __init__(self):
        self.llm = ChatAnthropic(model="claude-sonnet-4-5")
        self.memory = ConversationBufferWindowMemory(k=20)
        self.mcp_clients = {
            "player_data": MCPClient("http://mcp-player-data:8001"),
            "npc_personality": MCPClient("http://mcp-npc-personality:8004"),
            "world_universe": MCPClient("http://mcp-world-universe:8002"),
            "quest_mission": MCPClient("http://mcp-quest-mission:8003"),
            "item_equipment": MCPClient("http://mcp-item-equipment:8005"),
        }

    async def generate_scene_description(
        self,
        state: GameSessionState
    ) -> str:
        """Generate immersive scene description for current location"""

    async def interpret_player_action(
        self,
        player_input: str,
        state: GameSessionState,
        player: PlayerSessionData
    ) -> ActionInterpretation:
        """
        Convert natural language to structured game action

        Returns:
            ActionInterpretation with:
            - action_type: move, talk, examine, use_item, attempt_challenge
            - target_id: NPC ID, item ID, etc.
            - parameters: Additional action params
            - success_probability: GM's estimation
        """

    async def generate_npc_dialogue(
        self,
        npc_id: str,
        context: Dict[str, Any],
        player_statement: str,
        state: GameSessionState
    ) -> NPCDialogueResponse:
        """
        Generate NPC response using:
        - NPC personality (from MCP)
        - Conversation history
        - Quest context
        - Player's Bloom's level (to adapt complexity)
        """

    async def trigger_dynamic_event(
        self,
        state: GameSessionState
    ) -> Optional[EventData]:
        """
        Decide if a dynamic event should occur based on:
        - Elapsed time
        - Player actions
        - Campaign objectives
        - Pacing requirements
        """

    async def adjust_difficulty(
        self,
        state: GameSessionState,
        player: PlayerSessionData
    ) -> Dict[str, Any]:
        """
        Adapt challenge difficulty based on:
        - Player's Bloom's maturity
        - Recent performance
        - Dimensional balance
        """

    async def provide_feedback(
        self,
        assessment: AssessmentResult,
        player: PlayerSessionData
    ) -> str:
        """
        Generate constructive feedback on:
        - What player did well
        - Areas for improvement
        - Bloom's dimension growth opportunities
        """
```

### GM System Prompt Template

```
You are the Game Master for SkillForge, an AI-powered educational RPG.

Your responsibilities:
1. Guide players through {campaign_name} with engaging narrative
2. Control all NPCs with authentic personalities
3. Assess player actions using Bloom's Taxonomy
4. Provide constructive feedback for growth
5. Adapt difficulty to player maturity levels

Current Context:
- Campaign: {campaign_name}
- Quest: {current_quest_name}
- Scene: {current_scene_name}
- Players: {player_names}

Player Cognitive Profiles:
{player_cognitive_summaries}

Scene Elements:
- NPCs Present: {npc_list}
- Available Items: {item_list}
- Active Challenges: {challenge_list}

Your Goals:
- Develop {primary_dimension} dimension (target Bloom's level: {target_blooms_level})
- Support quest objectives: {objectives}
- Maintain engagement and challenge

Remember:
- Speak in second person ("You see...")
- Adapt language complexity to player Bloom's level
- Encourage dimensional balance
- Create memorable, educational moments
```

---

## 5. Game Loop & State Management

### LangGraph Game Loop Workflow

```python
def create_game_loop_workflow() -> StateGraph:
    """
    LangGraph workflow for real-time game loop

    Workflow Nodes:
    1. initialize_session - Load campaign, set starting location
    2. generate_scene - GM describes current scene
    3. await_player_input - Wait for player action
    4. interpret_action - GM converts input to game action
    5. execute_action - Process action (talk, move, use, challenge)
    6. assess_performance - Evaluate with rubric (if applicable)
    7. update_world - Apply consequences, persist changes
    8. check_objectives - Check quest/campaign completion
    9. provide_feedback - GM gives Bloom's feedback
    10. check_session_end - Continue or end session
    """

    workflow = StateGraph(GameSessionState)

    # Add nodes
    workflow.add_node("initialize_session", initialize_session_node)
    workflow.add_node("generate_scene", generate_scene_node)
    workflow.add_node("await_player_input", await_player_input_node)
    workflow.add_node("interpret_action", interpret_action_node)
    workflow.add_node("execute_action", execute_action_node)
    workflow.add_node("assess_performance", assess_performance_node)
    workflow.add_node("update_world", update_world_state_node)
    workflow.add_node("check_objectives", check_quest_objectives_node)
    workflow.add_node("provide_feedback", provide_bloom_feedback_node)
    workflow.add_node("check_session_end", check_session_end_node)

    # Set entry point
    workflow.set_entry_point("initialize_session")

    # Define flow
    workflow.add_edge("initialize_session", "generate_scene")
    workflow.add_edge("generate_scene", "await_player_input")
    workflow.add_conditional_edges(
        "await_player_input",
        route_after_input,
        {
            "interpret": "interpret_action",
            "paused": END,
            "timeout": "generate_scene"  # re-describe scene
        }
    )
    workflow.add_edge("interpret_action", "execute_action")
    workflow.add_conditional_edges(
        "execute_action",
        route_after_execution,
        {
            "assess": "assess_performance",
            "no_assessment": "update_world"
        }
    )
    workflow.add_edge("assess_performance", "update_world")
    workflow.add_edge("update_world", "check_objectives")
    workflow.add_conditional_edges(
        "check_objectives",
        route_after_objectives,
        {
            "feedback": "provide_feedback",
            "continue": "generate_scene",
            "quest_complete": "generate_scene",  # Start next quest
            "campaign_complete": END
        }
    )
    workflow.add_edge("provide_feedback", "generate_scene")

    return workflow.compile()
```

### Node Implementation Examples

```python
async def generate_scene_node(state: GameSessionState) -> GameSessionState:
    """Generate scene description"""
    gm_agent = get_gm_agent()

    # Get scene data from MongoDB
    scene = await get_scene_data(state["current_scene_id"])

    # Get NPC states (living world)
    npc_states = await get_npc_current_states(scene["npc_ids"])

    # GM generates narrative
    scene_description = await gm_agent.generate_scene_description(
        scene_data=scene,
        npc_states=npc_states,
        player_history=state["conversation_history"][-5:],  # Recent context
        time_of_day=state["time_of_day"]
    )

    state["scene_description"] = scene_description
    state["available_npcs"] = [npc for npc in scene["npc_ids"] if npc_states[npc]["is_present"]]
    state["awaiting_player_input"] = True

    # Publish scene to players via RabbitMQ
    await publish_scene_update(state["session_id"], scene_description)

    return state


async def execute_action_node(state: GameSessionState) -> GameSessionState:
    """Execute interpreted player action"""
    action = state["pending_action"]
    gm_agent = get_gm_agent()

    if action["action_type"] == "talk_to_npc":
        # NPC Conversation
        npc_id = action["target_id"]
        player_statement = action["player_input"]

        # Generate NPC response
        npc_response = await gm_agent.generate_npc_dialogue(
            npc_id=npc_id,
            context={
                "scene": state["current_scene_id"],
                "quest": state["current_quest_id"],
                "player_profile": state["players"][0]["cognitive_profile"]
            },
            player_statement=player_statement,
            state=state
        )

        # Record conversation turn
        conversation_turn = {
            "player_id": state["current_turn_player_id"],
            "npc_id": npc_id,
            "player_statement": player_statement,
            "npc_response": npc_response["dialogue"],
            "timestamp": datetime.utcnow().isoformat(),
            "affinity_change": npc_response["affinity_change"]
        }

        state["conversation_history"].append(conversation_turn)

        # Update NPC affinity (living world)
        await update_npc_affinity(npc_id, state["current_turn_player_id"], npc_response["affinity_change"])

        # Publish response to player
        await publish_npc_response(state["session_id"], npc_response)

        # Mark for assessment (rubric evaluation)
        state["requires_assessment"] = True
        state["assessment_context"] = {
            "rubric_id": npc_response["rubric_id"],
            "interaction_type": "npc_conversation",
            "entity_id": npc_id,
            "performance_data": conversation_turn
        }

    elif action["action_type"] == "move_to_location":
        # Scene transition
        new_scene_id = action["target_id"]

        # Check if scene is unlocked
        scene = await get_scene_data(new_scene_id)
        can_enter = check_scene_requirements(
            scene,
            state["player_knowledge"][state["current_turn_player_id"]],
            state["player_inventories"][state["current_turn_player_id"]]
        )

        if can_enter:
            state["current_scene_id"] = new_scene_id
            state["completed_scene_ids"].append(state["current_scene_id"])
            await publish_scene_transition(state["session_id"], new_scene_id)
        else:
            # GM explains why can't enter
            explanation = await gm_agent.explain_locked_scene(scene, state)
            await publish_message(state["session_id"], explanation)

        state["requires_assessment"] = False

    elif action["action_type"] == "attempt_challenge":
        # Challenge interaction
        challenge_id = action["target_id"]
        challenge = await get_challenge_data(challenge_id)

        # GM narrates challenge attempt
        challenge_narration = await gm_agent.narrate_challenge_attempt(
            challenge,
            action["approach"],  # How player described their attempt
            state
        )

        await publish_message(state["session_id"], challenge_narration)

        # Mark for assessment
        state["requires_assessment"] = True
        state["assessment_context"] = {
            "rubric_id": challenge["rubric_id"],
            "interaction_type": "challenge",
            "entity_id": challenge_id,
            "performance_data": {
                "approach": action["approach"],
                "required_knowledge": challenge["required_knowledge"],
                "difficulty": challenge["difficulty"]
            }
        }

    return state


async def assess_performance_node(state: GameSessionState) -> GameSessionState:
    """Assess player performance using rubrics"""
    if not state.get("requires_assessment"):
        return state

    assessment_engine = get_assessment_engine()
    context = state["assessment_context"]

    # Get rubric
    rubric = await get_rubric_data(context["rubric_id"])

    # AI-powered assessment (GM evaluates performance)
    assessment_result = await assessment_engine.evaluate_performance(
        rubric=rubric,
        interaction_data=context["performance_data"],
        player_profile=state["players"][0]["cognitive_profile"],
        state=state
    )

    # Update player progression
    player_id = state["current_turn_player_id"]

    # Award dimensional XP
    for dimension, xp in assessment_result["dimensional_xp"].items():
        state["player_dimensional_progress"][player_id][dimension]["experience_points"] += xp

        # Check for level up
        if check_dimension_level_up(state["player_dimensional_progress"][player_id][dimension]):
            await handle_dimension_level_up(player_id, dimension, state)

    # Award knowledge (partial levels)
    for kg_reward in assessment_result["knowledge_rewards"]:
        current_level = state["player_knowledge"][player_id].get(kg_reward["knowledge_id"], 0)
        new_level = min(4, current_level + kg_reward["level_gain"])
        state["player_knowledge"][player_id][kg_reward["knowledge_id"]] = new_level

    # Award items
    for item_reward in assessment_result["item_rewards"]:
        state["player_inventories"][player_id].append(item_reward["item_id"])

    # Store assessment for feedback
    state["last_assessment"] = assessment_result

    # Persist to database (living world)
    await persist_interaction_assessment(
        session_id=state["session_id"],
        player_id=player_id,
        assessment=assessment_result,
        timestamp=datetime.utcnow().isoformat()
    )

    return state
```

---

## 6. NPC Interaction System

### NPC State Management (Living World)

```python
class NPCState(TypedDict):
    """Runtime state for NPCs in game session"""
    npc_id: str
    current_location: str  # Can move around
    current_mood: str  # Can change based on interactions
    is_present: bool  # Can appear/disappear
    affinity_with_players: Dict[str, int]  # player_id -> affinity (-100 to 100)
    recent_interactions: List[str]  # Last 5 interaction IDs
    knowledge_shared: Dict[str, List[str]]  # player_id -> knowledge_ids revealed
    active_quest_status: Dict[str, str]  # quest_id -> status
```

### NPC Controller Sub-Agent

```python
class NPCControllerAgent:
    """
    Sub-agent that generates authentic NPC dialogue and behavior
    Works under Game Master supervision
    """

    async def generate_dialogue(
        self,
        npc_id: str,
        npc_personality: NPCData,  # From MCP
        player_statement: str,
        conversation_history: List[ConversationTurn],
        quest_context: Dict[str, Any],
        player_bloom_level: int
    ) -> NPCDialogueResponse:
        """
        Generate contextual NPC response

        Factors:
        - NPC personality traits (openness, extraversion, etc.)
        - Dialogue style (formality, verbosity, humor)
        - Current mood
        - Affinity with player
        - Quest objectives (what info to reveal)
        - Player Bloom's level (adjust complexity)
        """

        prompt = self._build_npc_prompt(
            npc_personality,
            player_statement,
            conversation_history,
            quest_context,
            player_bloom_level
        )

        response = await self.llm.ainvoke(prompt)

        # Parse response for:
        # - Dialogue text
        # - Affinity change
        # - Knowledge revealed
        # - Quest progress hints
        # - Rubric criteria performance hints

        return NPCDialogueResponse(
            dialogue=response["dialogue"],
            affinity_change=response["affinity_change"],
            knowledge_revealed=response["knowledge_revealed"],
            rubric_id=npc_personality["rubric_id"],
            performance_indicators=response["performance_indicators"]
        )
```

---

## 7. Assessment & Progression System

### Assessment Engine Agent

```python
class AssessmentEngineAgent:
    """
    AI agent that evaluates player performance using rubrics
    """

    async def evaluate_performance(
        self,
        rubric: RubricData,
        interaction_data: Dict[str, Any],
        player_profile: CognitiveProfile,
        state: GameSessionState
    ) -> AssessmentResult:
        """
        Evaluate player performance on rubric criteria

        Process:
        1. Analyze interaction data (conversation, challenge attempt, etc.)
        2. Score each rubric criterion (1-4 scale)
        3. Calculate weighted average
        4. Determine knowledge/item rewards
        5. Calculate dimensional XP
        6. Generate feedback
        """

        # Build evaluation prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_evaluator_system_prompt()),
            ("user", """
Evaluate the following player performance:

Rubric: {rubric_name}
Interaction Type: {interaction_type}
Primary Dimension: {primary_dimension}
Target Bloom's Level: {target_blooms_level}

Evaluation Criteria:
{criteria_descriptions}

Player Action/Response:
{interaction_data}

Player Cognitive Profile:
{player_profile}

For each criterion, provide:
1. Score (1=Poor, 2=Fair, 3=Good, 4=Excellent)
2. Evidence from player action
3. Specific feedback

Return as JSON:
{{
  "criterion_scores": {{
    "criterion_name": {{"score": 3, "evidence": "...", "feedback": "..."}}
  }},
  "overall_score": 3.2,
  "performance_level": 3,
  "strengths": ["..."],
  "growth_areas": ["..."]
}}
            """)
        ])

        response = await (prompt | self.llm).ainvoke({
            "rubric_name": rubric["interaction_name"],
            "interaction_type": rubric["rubric_type"],
            "primary_dimension": rubric["primary_dimension"],
            "target_blooms_level": self._get_target_blooms(rubric),
            "criteria_descriptions": self._format_criteria(rubric),
            "interaction_data": json.dumps(interaction_data, indent=2),
            "player_profile": self._format_player_profile(player_profile)
        })

        evaluation = json.loads(response.content)

        # Calculate rewards based on performance level
        rewards = self._calculate_rewards(
            rubric,
            evaluation["performance_level"],
            evaluation["overall_score"]
        )

        # Calculate dimensional XP
        dimensional_xp = self._calculate_dimensional_xp(
            rubric,
            evaluation["criterion_scores"]
        )

        return AssessmentResult(
            rubric_id=rubric["rubric_id"],
            criterion_scores=evaluation["criterion_scores"],
            overall_score=evaluation["overall_score"],
            performance_level=evaluation["performance_level"],
            strengths=evaluation["strengths"],
            growth_areas=evaluation["growth_areas"],
            knowledge_rewards=rewards["knowledge"],
            item_rewards=rewards["items"],
            dimensional_xp=dimensional_xp,
            timestamp=datetime.utcnow().isoformat()
        )
```

### Bloom's Taxonomy Progression Tracking

```python
class DimensionalMaturityTracker:
    """
    Tracks player growth across 7 dimensions using Bloom's Taxonomy
    """

    DIMENSIONS = [
        "physical",      # Body coordination, reflexes, endurance
        "emotional",     # Self-awareness, empathy, stress management
        "intellectual",  # Critical thinking, analysis, problem-solving
        "social",        # Communication, cooperation, leadership
        "spiritual",     # Purpose, values, ethics, meaning
        "vocational",    # Skill mastery, craftsmanship, competence
        "environmental"  # Ecological awareness, resource management
    ]

    BLOOMS_LEVELS = {
        1: "Remember",    # Recall facts, recognize concepts
        2: "Understand",  # Explain ideas, interpret information
        3: "Apply",       # Use knowledge in new situations
        4: "Analyze",     # Break down complex ideas, find patterns
        5: "Evaluate",    # Make judgments, critique, assess
        6: "Create",      # Produce original work, synthesize
    }

    XP_THRESHOLDS = {
        1: 0,      # Remember
        2: 100,    # Understand
        3: 300,    # Apply
        4: 700,    # Analyze
        5: 1500,   # Evaluate
        6: 3000    # Create
    }

    async def add_experience(
        self,
        player_id: str,
        dimension: str,
        xp_amount: int,
        source: str
    ) -> LevelUpResult:
        """
        Add XP to a dimension and check for level up
        """
        current = await self.get_dimensional_maturity(player_id, dimension)

        new_xp = current["experience_points"] + xp_amount
        current_level = current["current_level"]

        # Check for level up
        next_threshold = self.XP_THRESHOLDS.get(current_level + 1)
        leveled_up = False

        if next_threshold and new_xp >= next_threshold:
            current_level += 1
            leveled_up = True

            # Log achievement
            await self.log_level_up(
                player_id,
                dimension,
                current_level,
                self.BLOOMS_LEVELS[current_level]
            )

        # Update database
        await self.update_dimensional_maturity(
            player_id,
            dimension,
            {
                "current_level": current_level,
                "bloom_level": self.BLOOMS_LEVELS[current_level],
                "experience_points": new_xp,
                "next_level_threshold": self.XP_THRESHOLDS.get(current_level + 1, 99999)
            }
        )

        return LevelUpResult(
            leveled_up=leveled_up,
            new_level=current_level,
            bloom_level=self.BLOOMS_LEVELS[current_level],
            dimension=dimension,
            new_xp=new_xp
        )

    async def get_balanced_recommendations(
        self,
        player_id: str
    ) -> List[str]:
        """
        Recommend dimensions to work on for balanced growth
        """
        all_dimensions = {}
        for dim in self.DIMENSIONS:
            all_dimensions[dim] = await self.get_dimensional_maturity(player_id, dim)

        # Sort by level (ascending)
        sorted_dims = sorted(
            all_dimensions.items(),
            key=lambda x: (x[1]["current_level"], x[1]["experience_points"])
        )

        # Return bottom 3 dimensions
        return [dim for dim, _ in sorted_dims[:3]]
```

---

## 8. Living World Persistence

### Interaction History Storage

All game interactions are persisted to create a living, evolving world:

```python
# MongoDB Collections (NEW)

# game_sessions
{
    "_id": "session_uuid",
    "campaign_id": "campaign_id",
    "player_ids": ["player1", "player2"],
    "started_at": "ISO timestamp",
    "ended_at": "ISO timestamp",
    "status": "active|completed|abandoned",
    "final_state": {...}  # Complete GameSessionState snapshot
}

# interaction_history
{
    "_id": "interaction_uuid",
    "session_id": "session_uuid",
    "timestamp": "ISO timestamp",
    "interaction_type": "npc_conversation|challenge|discovery|event",
    "player_id": "player_uuid",
    "entity_id": "npc_id|challenge_id|etc",
    "interaction_data": {
        "player_input": "...",
        "entity_response": "...",
        "context": {...}
    },
    "assessment": {
        "rubric_id": "rubric_uuid",
        "scores": {...},
        "rewards": {...}
    }
}

# npc_interaction_memory (living memory for NPCs)
{
    "_id": "memory_uuid",
    "npc_id": "npc_uuid",
    "player_id": "player_uuid",
    "interactions": [
        {
            "session_id": "...",
            "timestamp": "...",
            "summary": "Player asked about the ancient ruins",
            "affinity_change": 5,
            "knowledge_shared": ["ancient_history"],
            "player_perception": "Player seems curious and respectful"
        }
    ],
    "total_affinity": 45,
    "relationship_status": "friendly",
    "secrets_revealed": ["secret_1", "secret_2"]
}

# player_progression_log
{
    "_id": "log_uuid",
    "player_id": "player_uuid",
    "timestamp": "ISO timestamp",
    "event_type": "xp_gain|level_up|knowledge_acquired|item_obtained",
    "dimension": "intellectual",
    "details": {
        "xp_gained": 35,
        "source": "npc_conversation_with_elder",
        "rubric_score": 3.5
    }
}

# world_changes (permanent changes to world)
{
    "_id": "change_uuid",
    "session_id": "session_uuid",
    "timestamp": "ISO timestamp",
    "change_type": "npc_moved|item_taken|location_unlocked|event_triggered",
    "affected_entity_id": "entity_uuid",
    "before_state": {...},
    "after_state": {...},
    "caused_by_player": "player_uuid"
}
```

### Neo4j Living World Graph

```cypher
// Player progression relationships
(Player)-[:AT_BLOOMS_LEVEL {dimension: "intellectual", level: 4}]->(BloomsLevel:BloomsLevel {level: 4, name: "Analyze"})
(Player)-[:ACQUIRED_KNOWLEDGE {level: 3, session_id: "..."}]->(Knowledge)
(Player)-[:POSSESSES_ITEM {quantity: 1, acquired_at: "..."}]->(Item)
(Player)-[:COMPLETED_QUEST {completed_at: "..."}]->(Quest)
(Player)-[:COMPLETED_SCENE {completed_at: "..."}]->(Scene)

// NPC relationships (evolve over time)
(Player)-[:HAS_RELATIONSHIP {affinity: 45, last_interaction: "...", relationship_type: "friendly"}]->(NPC)
(NPC)-[:SHARED_KNOWLEDGE {session_id: "..."}]->(Knowledge)
(NPC)-[:GAVE_ITEM {session_id: "..."}]->(Item)

// Campaign progress
(Player)-[:PLAYING_CAMPAIGN]->(Campaign)
(Player)-[:CURRENT_LOCATION]->(Scene)

// World memory
(Session)-[:OCCURRED_IN]->(Campaign)
(Session)-[:INVOLVED_PLAYER]->(Player)
(Interaction)-[:PART_OF_SESSION]->(Session)
(Interaction)-[:ASSESSED_BY]->(Rubric)
```

---

## 9. Multiplayer Architecture

### Session Coordination

```python
class MultiplayerSessionManager:
    """
    Manages multiplayer game sessions with turn-based or real-time play
    """

    async def create_multiplayer_session(
        self,
        campaign_id: str,
        player_ids: List[str],
        mode: str  # "turn_based" or "cooperative"
    ) -> str:
        """Create a multiplayer session"""

    async def handle_player_action(
        self,
        session_id: str,
        player_id: str,
        action: str
    ) -> GameSessionState:
        """
        Process player action in multiplayer context

        Turn-based: Queue action, wait for turn
        Cooperative: Process immediately if no conflicts
        """

    async def synchronize_state(
        self,
        session_id: str
    ) -> GameSessionState:
        """
        Ensure all players have consistent view of game state
        """
```

### RabbitMQ Event Architecture

```python
# Exchange: game.events
# Routing keys:
- session.{session_id}.scene_update      # New scene description
- session.{session_id}.npc_response      # NPC dialogue
- session.{session_id}.player_action     # Player took action
- session.{session_id}.assessment        # Performance assessment
- session.{session_id}.state_change      # World state change
- session.{session_id}.turn_change       # Turn-based: next player's turn

# Exchange: multiplayer.sync
# Routing keys:
- session.{session_id}.state_snapshot    # Full state sync
- session.{session_id}.player_joined     # Player connected
- session.{session_id}.player_left       # Player disconnected

# Example: Publishing scene update to all players
await rabbitmq_client.publish(
    exchange="game.events",
    routing_key=f"session.{session_id}.scene_update",
    message={
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "scene_description": scene_text,
        "available_actions": actions,
        "available_npcs": npcs
    }
)
```

---

## 10. Implementation Roadmap

### Phase 1: Core Game Engine (4-6 weeks)

**Week 1-2: Foundation**
- [ ] Create game-engine service skeleton (FastAPI)
- [ ] Implement GameSessionState TypedDict
- [ ] Create LangGraph game loop workflow with basic nodes
- [ ] Set up RabbitMQ exchanges and queues
- [ ] Create Redis session state management

**Week 3-4: Game Master Agent**
- [ ] Implement GameMasterAgent class
- [ ] Build scene description generator
- [ ] Build player action interpreter
- [ ] Integrate with all 5 MCP servers
- [ ] Create GM system prompt templates

**Week 5-6: Basic Gameplay Loop**
- [ ] Implement game loop nodes:
  - initialize_session
  - generate_scene
  - await_player_input
  - interpret_action
  - execute_action (talk, move, examine)
- [ ] Create WebSocket API for real-time play
- [ ] Test single-player gameplay

### Phase 2: NPC & Assessment Systems (3-4 weeks)

**Week 7-8: NPC Controller**
- [ ] Implement NPCControllerAgent
- [ ] Create dialogue generation system
- [ ] Implement NPC state management (living world)
- [ ] Integrate with npc-personality MCP
- [ ] Test multi-turn conversations

**Week 9-10: Assessment Engine**
- [ ] Implement AssessmentEngineAgent
- [ ] Create rubric evaluation logic
- [ ] Build reward distribution system
- [ ] Implement dimensional XP calculation
- [ ] Create feedback generation

### Phase 3: Living World Persistence (2-3 weeks)

**Week 11-12: Data Persistence**
- [ ] Create MongoDB collections:
  - game_sessions
  - interaction_history
  - npc_interaction_memory
  - player_progression_log
  - world_changes
- [ ] Implement persistence functions in all nodes
- [ ] Create Neo4j relationship updates
- [ ] Build interaction history API

**Week 13: Session Replay & Analytics**
- [ ] Create session replay functionality
- [ ] Build progression analytics
- [ ] Create Bloom's growth visualizations

### Phase 4: Advanced Features (3-4 weeks)

**Week 14-15: Dynamic Events & Challenges**
- [ ] Implement challenge execution node
- [ ] Create dynamic event triggering
- [ ] Build adaptive difficulty system
- [ ] Test complex challenge scenarios

**Week 16-17: Multiplayer Support**
- [ ] Implement MultiplayerSessionManager
- [ ] Create turn-based coordination
- [ ] Build cooperative mode
- [ ] Test 2-4 player sessions

### Phase 5: Polish & Production (2-3 weeks)

**Week 18-19: Optimization**
- [ ] Performance optimization
- [ ] Redis caching strategies
- [ ] Load testing (concurrent sessions)
- [ ] Error handling & recovery

**Week 20: Launch Preparation**
- [ ] Documentation
- [ ] Admin tools
- [ ] Monitoring & alerts
- [ ] Production deployment

---

## Technical Specifications

### API Endpoints (Game Engine Service)

```python
# Session Management
POST   /api/game/session/start
POST   /api/game/session/{session_id}/pause
POST   /api/game/session/{session_id}/resume
POST   /api/game/session/{session_id}/end
GET    /api/game/session/{session_id}/state

# Player Actions
POST   /api/game/session/{session_id}/action
GET    /api/game/session/{session_id}/available-actions

# History & Replay
GET    /api/game/session/{session_id}/history
GET    /api/game/session/{session_id}/replay

# Multiplayer
POST   /api/game/session/{session_id}/invite
POST   /api/game/session/{session_id}/join
GET    /api/game/session/{session_id}/players

# WebSocket
WS     /ws/game/session/{session_id}
```

### Performance Targets

- **Scene Generation Latency**: < 3 seconds (95th percentile)
- **NPC Response Latency**: < 2 seconds (95th percentile)
- **Assessment Latency**: < 5 seconds (95th percentile)
- **Concurrent Sessions**: 100+ per game-engine instance
- **State Persistence Latency**: < 500ms

### Resource Requirements

**Game Engine Service**
- CPU: 4 cores
- RAM: 8GB
- Storage: 20GB (logs + temp state)

**Game Master Agent**
- CPU: 4 cores
- RAM: 8GB
- LLM API: Claude Sonnet 4.5 (high throughput)

**Session Manager**
- CPU: 2 cores
- RAM: 4GB

---

## Success Metrics

### Player Engagement
- Average session duration
- Sessions per week
- Campaign completion rate

### Educational Impact
- Bloom's level progression rate per dimension
- Dimensional balance score
- Knowledge retention (tracked via assessments)

### System Performance
- Average scene generation time
- Assessment accuracy (validated against human evaluators)
- Session concurrency achieved

---

## Conclusion

This Game Playing Engine transforms SkillForge from a campaign generation platform into a fully interactive, AI-driven educational RPG. By leveraging LangGraph workflows, AI agents, and comprehensive MCP integrations, the engine creates dynamic, memorable experiences that develop players across all 7 human dimensions while maintaining a persistent living world that remembers every action.

The architecture is designed to scale from single-player to multiplayer, from simple conversations to complex moral dilemmas, all while continuously assessing and providing constructive feedback using Bloom's Taxonomy.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-15
**Authors**: Claude (Anthropic) & SkillForge Team
