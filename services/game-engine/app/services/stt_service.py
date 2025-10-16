"""
Speech-to-Text Service using OpenAI Whisper
Transcribes player voice input to text
"""
import os
import tempfile
from typing import Optional
from openai import OpenAI
from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class STTService:
    """Speech-to-Text service for player input"""

    def __init__(self):
        """Initialize OpenAI Whisper client"""
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            logger.warning("openai_api_key_not_configured")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)

    async def transcribe_audio(
        self,
        audio_data: bytes,
        language: str = "en",
        filename: str = "audio.webm"
    ) -> Optional[str]:
        """
        Transcribe audio to text

        Args:
            audio_data: Audio file bytes
            language: Language code (default: "en")
            filename: Original filename for format detection

        Returns:
            Transcribed text, or None if service unavailable
        """
        if not self.client:
            logger.error("stt_service_unavailable", reason="API key not configured")
            return None

        try:
            logger.info(
                "transcribing_audio",
                audio_size=len(audio_data),
                language=language,
                filename=filename
            )

            # Write audio to temporary file (Whisper API requires file input)
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_audio:
                temp_audio.write(audio_data)
                temp_audio_path = temp_audio.name

            try:
                # Transcribe using Whisper
                with open(temp_audio_path, "rb") as audio_file:
                    transcript = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language,
                        response_format="text"
                    )

                transcribed_text = transcript if isinstance(transcript, str) else transcript.text

                logger.info(
                    "audio_transcribed_successfully",
                    text_length=len(transcribed_text),
                    language=language
                )

                return transcribed_text

            finally:
                # Clean up temporary file
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)

        except Exception as e:
            logger.error(
                "stt_transcription_failed",
                error=str(e),
                language=language
            )
            return None

    def is_available(self) -> bool:
        """Check if STT service is available"""
        return self.client is not None


# Global STT service instance
stt_service = STTService()
