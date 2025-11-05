"""
GM Query Action Handler

Handles GM query actions:
- ask_gm_question: Ask the Game Master a question

Extract from game_loop.py lines 1457-1517
"""

from typing import Dict, Any, Optional
from .base import ActionHandler, ActionResult
from ...services.game_master import gm_agent
from ...services.websocket_manager import connection_manager
from ...core.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)


class GMQueryHandler(ActionHandler):
    """Handles questions directed to the Game Master."""

    async def can_handle(self, action_type: str, state: Dict[str, Any]) -> bool:
        """Check if this handler can process GM query actions."""
        return action_type == "ask_gm_question"

    async def execute(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        state: Dict[str, Any],
        target_id: Optional[str] = None
    ) -> ActionResult:
        """Execute GM query action."""
        return await self._handle_ask_gm_question(parameters, state)

    async def _handle_ask_gm_question(
        self,
        parameters: Dict[str, Any],
        state: Dict[str, Any]
    ) -> ActionResult:
        """
        Handle asking the GM a question.

        Extracted from game_loop.py lines 1478-1537

        Steps:
        1. Get question from parameters
        2. Create streaming callback for real-time response
        3. Call GM agent to answer question
        4. Broadcast answer chunks as they arrive
        5. Add final answer to chat messages
        6. Detect any acquirable opportunities in the answer
        7. Return result
        """
        try:
            # Get question from parameters or player input
            pending_action = state.get("pending_action", {})
            question = parameters.get("question", pending_action.get("player_input", ""))

            logger.info("handling_ask_gm_question", question=question[:100])

            # Define streaming callback to broadcast chunks via WebSocket
            async def stream_answer_chunk(chunk: str):
                """Callback to broadcast streaming answer chunks"""
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "gm_answer_chunk",
                        "chunk": chunk,
                        "is_complete": False
                    }
                )

            # Call GM agent to answer the question with streaming
            answer = await gm_agent.answer_player_question(
                question,
                state,
                stream_callback=stream_answer_chunk
            )

            # Broadcast final completion chunk
            await connection_manager.broadcast_to_session(
                state["session_id"],
                {
                    "event": "gm_answer_chunk",
                    "chunk": "",
                    "is_complete": True
                }
            )

            # Add GM answer to chat
            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": answer,
                "metadata": {"action_type": "question_answer"}
            }
            state["chat_messages"].append(chat_message)

            # Detect opportunities in GM response
            # Import from game_loop for now (will move to helpers later)
            from ..game_loop import detect_acquirable_opportunities
            opportunities = await detect_acquirable_opportunities(answer, state)

            # Broadcast opportunities if any found
            if any(opportunities.values()):
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "action_opportunities",
                        "opportunities": opportunities,
                        "context": "gm_response"
                    }
                )

            return self._create_success_result(
                outcome={"question_answered": True},
                narrative_generated=True
            )

        except Exception as e:
            logger.error(f"Error handling ask_gm_question: {e}", exc_info=True)
            return self._create_error_result(str(e))
