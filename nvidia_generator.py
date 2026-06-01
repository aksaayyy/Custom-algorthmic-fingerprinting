"""
NVIDIA API content generator for creating engaging YouTube metadata
Uses NVIDIA's hosted models (Kimi K2.6) for titles, descriptions, and hashtags
"""

import os
import json
import re
import requests
from typing import Optional, List, Dict, Any
import logging

from config import NVIDIA_API_KEY, NVIDIA_API_URL, NVIDIA_MODEL


class NvidiaGenerator:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or NVIDIA_API_KEY
        self.api_url = NVIDIA_API_URL
        self.model = NVIDIA_MODEL
        self.logger = logging.getLogger(__name__)
        self._cached_metadata: Optional[Dict[str, Any]] = None

        if not self.api_key:
            self.logger.warning("No NVIDIA API key provided. Falling back to template-based generation.")

    def _call_api(self, prompt: str, max_tokens: int = 1024) -> Optional[str]:
        if not self.api_key:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 1.00,
                "top_p": 1.00,
                "stream": False,
            }

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                self.logger.warning(f"NVIDIA API returned {response.status_code}: {response.text[:200]}...")
                return None

        except requests.exceptions.RequestException as e:
            self.logger.warning(f"NVIDIA API request failed: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"Unexpected error calling NVIDIA API: {e}")
            return None

    def generate_complete_metadata(self, video_context: str = "") -> Dict[str, Any]:
        if self._cached_metadata:
            return self._cached_metadata

        if not self.api_key:
            result = self._fallback_complete_metadata(video_context)
            self._cached_metadata = result
            return result

        prompt = f"""Create a YouTube Shorts title, description (with CTAs), and tags for this content: {video_context}

Return ONLY a JSON object with these fields. No markdown, no code blocks, no explanation:

{{
  "title": "catchy title under 80 chars with emojis and #Shorts",
  "description": "engaging description with hook, CTAs (Like, Comment, Subscribe, Share), #Shorts",
  "tags": ["Shorts", "Viral", "Trending", "FYP", "Amazing"]
}}"""

        result = self._call_api(prompt, max_tokens=800)
        if result:
            try:
                cleaned = result.strip()
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
                metadata = json.loads(cleaned.strip())
                title = metadata.get("title", "")
                description = metadata.get("description", "")
                tags = metadata.get("tags", [])

                if "#Shorts" not in title:
                    title = title.rstrip() + " #Shorts"
                if "#Shorts" not in description:
                    description = "#Shorts\n" + description
                if not tags or tags[0].lower() != "shorts":
                    tags = ["Shorts"] + [t for t in tags if t.lower() != "shorts"]

                result = {"title": title[:100], "description": description, "tags": tags}
                self._cached_metadata = result
                return result
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                self.logger.warning(f"Failed to parse NVIDIA JSON response: {e}")

        return self._fallback_complete_metadata(video_context)

    def _fallback_complete_metadata(self, video_context: str = "") -> Dict[str, Any]:
        import random
        clean_context = video_context.replace('_', ' ').title() if video_context else "Amazing Moment"

        title_templates = [
            f"OMG {clean_context} 😳 #Shorts",
            f"You WON'T Believe {clean_context} 😱 #Shorts",
            f"Watch This {clean_context} 👀 #Shorts",
            f"{clean_context} Will Blow Your Mind 💥 #Shorts",
            f"This {clean_context} is INSANE 🤯 #Shorts",
        ]
        title = random.choice(title_templates)[:100]

        hooks = [
            "Check out this incredible moment!",
            "You have to see this to believe it!",
            "This is going viral for a reason!",
            "Prepare to be amazed!",
        ]
        ctas = [
            "👍 Like if you enjoyed!\n💬 Comment your thoughts below!\n🔔 Subscribe for more!\n🔄 Share with your friends!",
            "Smash that Like button!\nDrop a comment below!\nSubscribe for daily uploads!",
        ]
        description = f"#Shorts\n\n{random.choice(hooks)}\n\n{random.choice(ctas)}\n\n#Shorts #Viral #Trending #FYP"

        tags = ["Shorts", "Viral", "Trending", "FYP", "Amazing", "Clip"]

        return {"title": title, "description": description, "tags": tags}
