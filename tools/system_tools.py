import base64
import io
import time

import mss
import openai
import pyperclip
from PIL import Image, ImageGrab

from config.settings import CHEAP_MODEL


def screen_capture(_: str = "") -> str:
    """
    Capture the primary monitor and describe its contents using AI vision.

    Takes a screenshot, encodes it as base64, and sends it to a vision model
    for analysis. Returns a detailed description of visible elements and text.

    Args:
        _: Unused parameter (tool takes no meaningful input)

    Returns:
        AI-generated description of the screen contents or error message
    """
    print(f"[📸 capture] Screenshot taken at {time.strftime('%H:%M:%S')}")

    try:
        with mss.mss() as sct:
            grab = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", grab.size, grab.bgra, "raw", "BGRX")

        # Encode image for API
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        # Analyze with vision model
        vision_resp = openai.chat.completions.create(
            model=CHEAP_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": "Describe what you are seeing on the user's screen. Extract all visible text, plus visual/conceptual items, in a way that is easy to reference or talk about. If there are no visible items, say so.",
                        },
                    ],
                }
            ],
            max_tokens=1000,
            temperature=0.2,
        )
        return vision_resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[screen_capture-error] {e}"


def clipboard_content(_: str = "") -> str:
    """
    Retrieve and analyze clipboard contents.

    Handles both text and image clipboard content. For images, uses AI vision
    to generate a summary. For text, returns up to 8k characters.

    Args:
        _: Unused parameter (tool takes no meaningful input)

    Returns:
        Text content, AI description of image, or empty clipboard message
    """
    # Check for image content first
    img = ImageGrab.grabclipboard()
    if isinstance(img, Image.Image):
        print("[📋 clipboard] Image detected — generating summary.")
        try:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()

            vision_resp = openai.chat.completions.create(
                model=CHEAP_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                            {
                                "type": "text",
                                "text": "Describe this clipboard image in 5 concise bullet points.",
                            },
                        ],
                    }
                ],
                max_tokens=1000,
                temperature=0.2,
            )
            return vision_resp.choices[0].message.content.strip()
        except Exception as e:
            return f"[clipboard-image-error] {e}"

    # Handle text content
    text = pyperclip.paste()
    if text:
        snippet = (text[:60] + "…") if len(text) > 60 else text
        print(f"[📋 clipboard] Text captured: {snippet}")
        return text[:8000]

    print("[📋 clipboard] Clipboard is empty.")
    return "[clipboard] Clipboard is empty."
