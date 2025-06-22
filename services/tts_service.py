"""
Text-to-Speech service using OpenAI's high-quality TTS API.

Provides streaming audio playback with minimal latency for natural conversation flow.
"""

import asyncio

import openai

from config.personality import TTS_INSTRUCTIONS
from config.settings import OPENAI_API_KEY, TTS_MODEL, TTS_VOICE

openai.api_key = OPENAI_API_KEY


async def speak_custom(text: str, stop_chime: asyncio.Event | None = None):
    """
    Convert text to speech and play it with streaming audio.

    Uses OpenAI's TTS API to generate high-quality speech audio, then streams
    it directly to the audio output device for minimal latency. Optionally
    signals when audio playback begins.

    Args:
        text: Text content to convert to speech
        stop_chime: Optional event to set when audio playback starts
    """
    SAMPLE_RATE = 24000

    def _play_stream():
        """Internal function to handle TTS generation and audio streaming."""
        resp = openai.audio.speech.create(
            input=text,
            model=TTS_MODEL,
            voice=TTS_VOICE,
            response_format="pcm",
            instructions=TTS_INSTRUCTIONS,
        )

        import time

        import sounddevice as sd

        with sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=0,
        ) as stream:
            first_chunk = True
            for chunk in resp.iter_bytes():
                if chunk:
                    if first_chunk:
                        # Signal that audio is starting and add brief delay
                        if stop_chime is not None:
                            stop_chime.set()
                        time.sleep(0.12)
                        first_chunk = False
                    stream.write(chunk)

    await asyncio.to_thread(_play_stream)
