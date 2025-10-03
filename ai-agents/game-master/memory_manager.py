"""
Long-term Memory Manager using ChromaDB Vector Database
Stores and retrieves campaign memories for contextual narrative generation
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import chromadb
from chromadb.config import Settings

CHROMADB_URL = os.getenv("CHROMADB_URL", "http://chromadb:8000")

class MemoryManager:
    """Manages long-term campaign memories using ChromaDB"""

    def __init__(self):
        # Initialize ChromaDB client with proper settings
        try:
            self.client = chromadb.HttpClient(
                host=CHROMADB_URL.replace("http://", "").split(":")[0],
                port=int(CHROMADB_URL.split(":")[-1]),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            # Get or create collections
            self.campaign_memories = self.client.get_or_create_collection(
                name="campaign_memories",
                metadata={"description": "Player campaign event memories"}
            )

            self.world_knowledge = self.client.get_or_create_collection(
                name="world_knowledge",
                metadata={"description": "World lore and knowledge base"}
            )
        except Exception as e:
            print(f"Warning: Could not connect to ChromaDB: {e}")
            print("Memory features will be disabled")
            self.client = None
            self.campaign_memories = None
            self.world_knowledge = None

    async def store_campaign_event(
        self,
        campaign_id: str,
        profile_id: str,
        event_type: str,
        event_description: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store a campaign event in vector memory"""
        if not self.campaign_memories:
            return

        event_id = f"{campaign_id}_{int(datetime.now().timestamp())}"

        event_metadata = {
            "campaign_id": campaign_id,
            "profile_id": profile_id,
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {})
        }

        self.campaign_memories.add(
            ids=[event_id],
            documents=[event_description],
            metadatas=[event_metadata]
        )

    async def retrieve_relevant_memories(
        self,
        campaign_id: str,
        query: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant campaign memories based on semantic similarity"""
        if not self.campaign_memories:
            return []

        try:
            results = self.campaign_memories.query(
                query_texts=[query],
                n_results=n_results,
                where={"campaign_id": campaign_id}
            )

            memories = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    memories.append({
                        "event": doc,
                        "metadata": results["metadatas"][0][i],
                        "relevance_score": 1.0 - results["distances"][0][i]  # Convert distance to similarity
                    })

            return memories

        except Exception as e:
            print(f"Error retrieving memories: {e}")
            return []

    async def get_campaign_summary(self, campaign_id: str) -> str:
        """Get a summary of all campaign events"""
        if not self.campaign_memories:
            return ""

        try:
            # Get all campaign memories
            results = self.campaign_memories.get(
                where={"campaign_id": campaign_id}
            )

            if not results or not results["documents"]:
                return "No previous campaign history."

            # Create timeline summary
            events = []
            for i, doc in enumerate(results["documents"]):
                timestamp = results["metadatas"][i].get("timestamp", "unknown")
                event_type = results["metadats"][i].get("event_type", "event")
                events.append(f"[{timestamp}] {event_type}: {doc[:100]}...")

            return "\n".join(events[-10:])  # Last 10 events

        except Exception as e:
            print(f"Error getting campaign summary: {e}")
            return "Unable to retrieve campaign history."

    async def store_world_knowledge(
        self,
        world_id: str,
        knowledge_type: str,  # lore, npc, location, quest, item
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store world knowledge for retrieval"""
        if not self.world_knowledge:
            return

        knowledge_id = f"{world_id}_{knowledge_type}_{title.replace(' ', '_')}"

        knowledge_metadata = {
            "world_id": world_id,
            "knowledge_type": knowledge_type,
            "title": title,
            "created_at": datetime.now().isoformat(),
            **(metadata or {})
        }

        self.world_knowledge.add(
            ids=[knowledge_id],
            documents=[content],
            metadatas=[knowledge_metadata]
        )

    async def retrieve_world_knowledge(
        self,
        world_id: str,
        query: str,
        knowledge_type: Optional[str] = None,
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant world knowledge"""
        if not self.world_knowledge:
            return []

        try:
            where_clause = {"world_id": world_id}
            if knowledge_type:
                where_clause["knowledge_type"] = knowledge_type

            results = self.world_knowledge.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause
            )

            knowledge = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    knowledge.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i],
                        "relevance_score": 1.0 - results["distances"][0][i]
                    })

            return knowledge

        except Exception as e:
            print(f"Error retrieving world knowledge: {e}")
            return []

    async def clear_campaign_memories(self, campaign_id: str):
        """Clear all memories for a campaign"""
        if not self.campaign_memories:
            return

        try:
            self.campaign_memories.delete(where={"campaign_id": campaign_id})
        except Exception as e:
            print(f"Error clearing campaign memories: {e}")
