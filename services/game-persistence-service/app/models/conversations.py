"""
Conversation models for MongoDB
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from uuid import UUID


class MessageSender(BaseModel):
    """Message sender information"""
    type: Literal["player", "npc", "dm", "system"]
    id: Optional[UUID] = None
    name: str


class MessageRecipient(BaseModel):
    """Message recipient information"""
    type: Literal["player", "all", "party"]
    id: Optional[UUID] = None


class MessageContent(BaseModel):
    """Message content"""
    text: str
    formatted_html: Optional[str] = None
    audio_url: Optional[str] = None
    emotion: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationDocument(BaseModel):
    """Conversation message document for MongoDB"""

    session_id: UUID
    message_id: UUID
    timestamp: datetime
    sequence_number: int

    # Message Classification
    message_type: Literal["dm_narrative", "npc_dialogue", "player_action", "team_chat", "whisper", "ooc", "system"]

    # Participants
    sender: MessageSender
    recipient: MessageRecipient

    # Content
    content: MessageContent

    # Context
    related_event_id: Optional[UUID] = None
    scene_id: Optional[UUID] = None
    quest_id: Optional[UUID] = None

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }
