"""
Text-to-Speech Service using ElevenLabs
Generates audio for Game Master narration
"""
import os
import hashlib
from typing import Optional, Generator, Dict
from collections import OrderedDict
from elevenlabs.client import ElevenLabs
from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class TTSCache:
    """Simple LRU cache for TTS audio"""

    def __init__(self, max_size: int = 20):
        self.cache: OrderedDict[str, bytes] = OrderedDict()
        self.max_size = max_size

    def _make_key(self, text: str, voice_type: str) -> str:
        """Create cache key from text and voice type"""
        content = f"{text}:{voice_type}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, text: str, voice_type: str) -> Optional[bytes]:
        """Get cached audio if available"""
        key = self._make_key(text, voice_type)
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            logger.info("tts_cache_hit", text_length=len(text))
            return self.cache[key]
        return None

    def put(self, text: str, voice_type: str, audio_data: bytes):
        """Store audio in cache"""
        key = self._make_key(text, voice_type)

        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            logger.info("tts_cache_evicted")

        self.cache[key] = audio_data
        logger.info("tts_cache_stored", text_length=len(text), audio_size=len(audio_data))


class TTSService:
    """Text-to-Speech service for game narration"""

    def __init__(self):
        """Initialize ElevenLabs client"""
        self.api_key = os.getenv('ELEVENLABS_API_KEY')
        if not self.api_key:
            logger.warning("elevenlabs_api_key_not_configured")
            self.client = None
        else:
            # Initialize with longer timeout for large texts (default is 60s)
            self.client = ElevenLabs(
                api_key=self.api_key,
                timeout=300.0  # 5 minutes for very long narrations
            )

        # Voice mappings for different narration types
        self.voice_map = {
            "game_master": "iOVaF08dLdP3q4lSrs5M",  # Old British Male - authoritative narrator
            "dramatic": "TxGEqnHWrfWFTfGW9XjX",      # Josh - deep, dramatic
            "friendly": "pFZP5JQG7iQjIQuC4Bku",     # Lily - warm, pleasant
            "mysterious": "nPczCjzI2devNBz1zQrb",   # Brian - calm, mysterious
            "heroic": "TxGEqnHWrfWFTfGW9XjX",       # Josh - strong, commanding
        }

        # Initialize cache
        self.cache = TTSCache(max_size=20)

    def _chunk_text(self, text: str, max_chars: int = 1500) -> list[str]:
        """
        Split text into smaller chunks at sentence boundaries for faster streaming

        Args:
            text: Text to split
            max_chars: Maximum characters per chunk (reduced to 1500 for faster generation)

        Returns:
            List of text chunks
        """
        # For very short texts, no need to chunk
        if len(text) <= 500:
            return [text]

        # For medium texts, use a single chunk if reasonable
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by sentences (enhanced to handle multiple punctuation)
        sentences = []
        current_sentence = ""

        for char in text:
            current_sentence += char
            if char in '.!?' and len(current_sentence.strip()) > 10:  # Min 10 chars per sentence
                sentences.append(current_sentence.strip())
                current_sentence = ""

        # Add any remaining text
        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        for sentence in sentences:
            if not sentence:
                continue

            # If adding this sentence would exceed max, save current chunk
            if len(current_chunk) + len(sentence) + 1 > max_chars and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += (' ' if current_chunk else '') + sentence

        # Add remaining chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # Log chunk sizes for monitoring
        logger.info(
            "text_chunked",
            total_chars=len(text),
            num_chunks=len(chunks),
            chunk_sizes=[len(c) for c in chunks]
        )

        return chunks

    def generate_speech(
        self,
        text: str,
        voice_type: str = "game_master",
        model_id: str = "eleven_multilingual_v2"
    ) -> Optional[Generator[bytes, None, None]]:
        """
        Generate speech audio from text with chunking for long texts

        Args:
            text: Text to convert to speech
            voice_type: Type of voice (game_master, dramatic, friendly, etc.)
            model_id: ElevenLabs model ID

        Returns:
            Generator yielding audio bytes, or None if service unavailable
        """
        if not self.is_available():
            logger.error("tts_service_unavailable", reason="API key not configured")
            return None

        try:
            voice_id = self.voice_map.get(voice_type, self.voice_map["game_master"])

            # Chunk text into smaller pieces for faster streaming (1500 chars)
            chunks = self._chunk_text(text, max_chars=1500)

            logger.info(
                "generating_tts_audio",
                text_length=len(text),
                num_chunks=len(chunks),
                voice_type=voice_type,
                voice_id=voice_id
            )

            # Generator function to stream audio from all chunks
            def audio_stream_generator():
                for i, chunk in enumerate(chunks):
                    logger.info(f"generating_chunk", chunk_num=i+1, total_chunks=len(chunks))
                    try:
                        # Generate audio for this chunk
                        chunk_audio = self.client.generate(
                            text=chunk,
                            voice=voice_id,
                            model=model_id,
                            stream=True
                        )

                        # Yield audio bytes from this chunk
                        for audio_bytes in chunk_audio:
                            yield audio_bytes

                    except Exception as chunk_error:
                        logger.error(
                            "chunk_generation_failed",
                            chunk_num=i+1,
                            error=str(chunk_error)
                        )
                        # Continue with next chunk instead of failing entirely
                        continue

            logger.info("tts_audio_generation_started", voice_type=voice_type)

            return audio_stream_generator()

        except Exception as e:
            logger.error(
                "tts_generation_failed",
                error=str(e),
                voice_type=voice_type
            )
            return None

    def generate_speech_bytes(
        self,
        text: str,
        voice_type: str = "game_master",
        model_id: str = "eleven_multilingual_v2"
    ) -> Optional[bytes]:
        """
        Generate complete speech audio as bytes with caching

        Args:
            text: Text to convert to speech
            voice_type: Type of voice
            model_id: ElevenLabs model ID

        Returns:
            Audio bytes, or None if service unavailable
        """
        # Check cache first
        cached_audio = self.cache.get(text, voice_type)
        if cached_audio:
            return cached_audio

        # Generate if not cached
        audio_generator = self.generate_speech(text, voice_type, model_id)

        if not audio_generator:
            return None

        try:
            # Collect all audio chunks
            audio_data = b''.join(audio_generator)

            # Store in cache
            self.cache.put(text, voice_type, audio_data)

            return audio_data
        except Exception as e:
            logger.error("tts_audio_collection_failed", error=str(e))
            return None

    def is_available(self) -> bool:
        """Check if TTS service is available"""
        return self.client is not None


# Global TTS service instance
tts_service = TTSService()
