import asyncio
import tempfile
import wave
import queue
import sys
import numpy as np
import sounddevice as sd
import soundfile as sf
from config.settings import (
    RATE, CHUNK, TRAILING_SILENCE_SEC, 
    ENERGY_THRESHOLD, MAX_RECORD_SEC, WAITING_WAV, WAITING_VOLUME,
    DEBUG_AUDIO, VAD_FRAME_MS, VAD_AGGRESSIVENESS
)

import warnings
try:
    import webrtcvad
    from pkg_resources import PkgResourcesDeprecationWarning
    warnings.filterwarnings("ignore", category=PkgResourcesDeprecationWarning)
except ImportError:
    pass

# Initialize Voice Activity Detector
VAD = webrtcvad.Vad(VAD_AGGRESSIVENESS)

# Global audio queue for streaming
audio_q = queue.Queue()

def _callback(indata, frames, time_info, status):
    """Callback function for audio input stream."""
    if status:
        print(status, file=sys.stderr)
    audio_q.put(bytes(indata))

async def record(max_sec: int = MAX_RECORD_SEC, silence: int = ENERGY_THRESHOLD) -> str | None:
    """
    Record audio until the speaker goes silent, using WebRTC VAD for detection.
    
    Uses voice activity detection on fixed-duration frames to determine when
    speech has ended. Trims leading silence and saves to a temporary WAV file.
    
    Args:
        max_sec: Maximum recording duration in seconds
        silence: Energy threshold for silence detection (used for trimming)
        
    Returns:
        Path to temporary WAV file containing the recording, or None if failed
    """
    # VAD frame configuration
    FRAME_MS = VAD_FRAME_MS
    BYTES_PER_MS = RATE * 2 // 1000
    FRAME_BYTES = FRAME_MS * BYTES_PER_MS
    silence_limit_frames = int(TRAILING_SILENCE_SEC * 1000 / FRAME_MS)

    frames = []               # Raw audio buffers for WAV output
    buffer = bytearray()      # Buffer for VAD frame processing
    heard_voice = False       # Track if we've detected any speech
    last_voiced = -1          # Frame index of last detected speech
    frame_index = 0           # Current frame counter

    max_chunks = int(max_sec * RATE / CHUNK)

    try:
        with sd.InputStream(
            channels=1, samplerate=RATE, dtype="int16",
            callback=_callback, blocksize=CHUNK
        ):
            recording_complete = False
            
            for _ in range(max_chunks):
                buf = audio_q.get()
                frames.append(buf)
                buffer.extend(buf)

                # Process complete VAD frames
                while len(buffer) >= FRAME_BYTES:
                    segment = bytes(buffer[:FRAME_BYTES])
                    del buffer[:FRAME_BYTES]
                    
                    try:
                        is_speech = VAD.is_speech(segment, RATE)
                    except Exception:
                        is_speech = False
                        
                    if is_speech:
                        heard_voice = True
                        last_voiced = frame_index
                        
                    # Stop recording after sufficient silence following speech
                    if heard_voice and (frame_index - last_voiced) >= silence_limit_frames:
                        recording_complete = True
                        break
                        
                    frame_index += 1

                if recording_complete:
                    break
                    
    except sd.PortAudioError as e:
        print(f"[mic-error] {e}")
        # Show macOS permission dialog
        import subprocess
        subprocess.run([
            "osascript", "-e",
            'display alert "Mic blocked" message '
            '"Safari\'s helper process has no microphone permission. '
            'Run the shortcut from the Menu Bar or via `shortcuts run`."'
        ])
        return None

    # Optional debug output for troubleshooting
    if DEBUG_AUDIO:
        debug_fn = tempfile.mktemp(suffix="_raw_debug.wav")
        with wave.open(debug_fn, "wb") as wf_debug:
            wf_debug.setnchannels(1)
            wf_debug.setsampwidth(2)
            wf_debug.setframerate(RATE)
            wf_debug.writeframes(b"".join(frames))
        print(f"[audio-debug] Raw audio saved to {debug_fn}")

    # Trim leading silence using energy threshold
    start_idx = 0
    while start_idx < len(frames):
        energy = np.abs(np.frombuffer(frames[start_idx], np.int16)).mean()
        if energy >= silence:
            break
        start_idx += 1
        
    trimmed_frames = frames[start_idx:]

    if len(trimmed_frames) == 0:
        return None

    # Save trimmed audio to temporary file
    output_path = tempfile.mktemp(suffix=".wav")
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(trimmed_frames))
        
    return output_path

async def play_waiting_music(stop_event: asyncio.Event) -> None:
    """
    Play looping background music at low volume until stopped.
    
    Loads the configured waiting music file and loops it continuously
    at reduced volume. Falls back to a simple tone if the file is unavailable.
    
    Args:
        stop_event: Event to signal when playback should stop
    """
    try:
        # Load waiting music file
        data, sample_rate = sf.read(WAITING_WAV, dtype="float32")
        if data.ndim == 1:
            data = data[:, None]  # Ensure stereo format
        data *= WAITING_VOLUME
    except Exception:
        # Fallback: Generate a simple 440Hz tone with silence
        sample_rate = 44100
        t = np.linspace(0, 0.25, int(sample_rate * 0.25), endpoint=False, dtype=np.float32)
        beep = 0.2 * np.sin(2 * np.pi * 440 * t)
        silence = np.zeros(int(sample_rate * 0.75), dtype=np.float32)
        data = np.concatenate([beep, silence])[:, None]

    position = 0
    
    try:
        with sd.RawOutputStream(
            samplerate=sample_rate, 
            channels=data.shape[1],
            dtype="float32", 
            blocksize=0
        ) as output_stream:
            
            while not stop_event.is_set():
                # Calculate chunk size for smooth playback
                chunk_size = int(sample_rate * 0.25)
                end_pos = position + chunk_size
                
                # Handle looping at end of audio
                if end_pos >= len(data):
                    chunk = np.vstack([data[position:], data[:end_pos - len(data)]])
                    position = end_pos - len(data)
                else:
                    chunk = data[position:end_pos]
                    position = end_pos
                    
                output_stream.write(chunk.tobytes())
                await asyncio.sleep(0)  # Yield control to event loop
                
    except asyncio.CancelledError:
        return
