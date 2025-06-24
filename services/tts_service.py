"""
Text-to-Speech service using OpenAI's high-quality TTS API.

Provides streaming audio playback with minimal latency for natural conversation flow.
"""

import asyncio
import re
import time

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

async def speak_parallel(text: str, stop_chime: asyncio.Event | None = None):
    """
    Convert text to speech using parallel generation and sequential playback.
    
    Splits text into chunks, generates TTS for all chunks in parallel,
    then plays them sequentially for faster overall processing.
    
    Returns:
        dict: Timing measurements with 'first_chunk' and 'total' keys
    """
    start_time = time.time()
    
    # Split text into sentences, keeping reasonable chunk sizes
    chunks = _split_text_into_chunks(text)
    
    if len(chunks) <= 1:
        # Fall back to regular implementation for short text
        await speak_custom(text, stop_chime)
        total_time = time.time() - start_time
        return {"first_chunk": total_time, "total": total_time}
    
    # Generate all TTS audio in parallel, tracking first chunk
    first_chunk_time = None
    
    async def generate_with_timing(chunk, index):
        nonlocal first_chunk_time
        chunk_start = time.time()
        result = await _generate_tts_chunk(chunk)
        if index == 0:
            first_chunk_time = time.time() - chunk_start
        return result
    
    audio_chunks = await asyncio.gather(
        *[generate_with_timing(chunk, i) for i, chunk in enumerate(chunks)]
    )
    
    # Play chunks sequentially
    await _play_audio_chunks(audio_chunks, stop_chime)
    
    total_time = time.time() - start_time
    return {"first_chunk": first_chunk_time, "total": total_time}

def _split_text_into_chunks(text: str, max_chunk_length: int = 200) -> list[str]:
    """Split text into reasonable chunks for parallel TTS generation."""
    # Split on sentence boundaries - be more aggressive about splitting
    sentences = re.split(r'(?<=[.!?:])\s+', text.strip())  # Added colon for better splitting
    
    if len(sentences) <= 1:
        return [text]
    
    chunks = []
    
    # Always make the first sentence its own chunk, but limit its length
    first_sentence = sentences[0]
    if len(first_sentence) > 100:  # If first sentence is too long, split on other punctuation
        # Try splitting on comma, dash, or semicolon within the first sentence
        sub_parts = re.split(r'(?<=[,;—])\s+', first_sentence)
        if len(sub_parts) > 1:
            first_sentence = sub_parts[0]
            # Add remaining parts back to sentences list
            sentences = sub_parts[1:] + sentences[1:]
    
    chunks.append(first_sentence)
    
    # Process remaining sentences
    current_chunk = ""
    for sentence in sentences[1:]:
        if len(current_chunk) + len(sentence) <= max_chunk_length:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

async def _generate_tts_chunk(text: str) -> bytes:
    """Generate TTS audio for a single text chunk."""
    def _generate():
        resp = openai.audio.speech.create(
            input=text,
            model=TTS_MODEL,
            voice=TTS_VOICE,
            response_format="pcm",
            instructions=TTS_INSTRUCTIONS,
        )
        return b''.join(resp.iter_bytes())
    
    return await asyncio.to_thread(_generate)

async def _play_audio_chunks(audio_chunks: list[bytes], stop_chime: asyncio.Event | None = None):
    """Play pre-generated audio chunks sequentially."""
    import sounddevice as sd
    import time
    
    SAMPLE_RATE = 24000
    
    def _play_all_chunks():
        with sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=0,
        ) as stream:
            first_chunk = True
            for audio_data in audio_chunks:
                if first_chunk:
                    if stop_chime is not None:
                        stop_chime.set()
                    time.sleep(0.12)
                    first_chunk = False
                stream.write(audio_data)
    
    await asyncio.to_thread(_play_all_chunks)
