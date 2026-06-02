"""
Grok AI generator module for creating engaging YouTube metadata
Uses xAI's Grok API to generate titles, descriptions, and hashtags
"""

import os
import json
import requests
from typing import Optional, List, Dict, Any
import logging
from pathlib import Path

class GrokGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Grok generator

        Args:
            api_key: Grok API key (can also be set via GROK_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('GROK_API_KEY')
        self.logger = logging.getLogger(__name__)
        self.api_url = "https://api.x.ai/v1/chat/completions"
        # Grok API model: if not specified, the API may use a default. We'll try without specifying model first.
        self.model = None

        if not self.api_key:
            self.logger.warning("No Grok API key provided. Falling back to template-based generation.")

    def _call_grok_api(self, prompt: str, max_tokens: int = 150) -> Optional[str]:
        """
        Make a call to the Grok API

        Args:
            prompt: The prompt to send to Grok
            max_tokens: Maximum tokens in response

        Returns:
            Generated text or None if failed
        """
        if not self.api_key:
            return None

        # Try without model specification first (let API use default)
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert social media content creator specializing in creating viral, engaging YouTube Shorts titles, descriptions, and hashtags. You understand what makes content click-worthy and shareable."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": 0.8,
                "stream": False
            }

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                # Log but don't fail hard - we'll fall back to templates
                self.logger.warning(f"Grok API returned {response.status_code}: {response.text[:100]}...")
                return None

        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Grok API request failed: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"Unexpected error calling Grok API: {e}")
            return None

    def generate_engaging_title(self, video_context: str = "") -> str:
        """
        Generate an engaging YouTube title using Grok AI

        Args:
            video_context: Context about the video content

        Returns:
            Engaging title string
        """
        if not self.api_key:
            # Fallback to template-based generation
            return self._fallback_title_generation(video_context)

        import re
        ctx_for_ai = video_context
        if re.match(r'^https?://', ctx_for_ai.strip()):
            ctx_for_ai = "an Instagram reel clip"
        prompt = f"""Create a catchy, click-worthy YouTube Shorts title (under 60 characters) for a video about: {ctx_for_ai}

        Requirements:
        - Under 60 characters
        - Includes emoji(s) for visual appeal
        - Uses power words and curiosity gap
        - Optimized for CTR (Click-Through Rate)
        - Suitable for YouTube Shorts audience
        - No clickbait that misrepresents content

        Return only the title, nothing else."""

        title = self._call_grok_api(prompt, max_tokens=50)
        if title and len(title) <= 100:  # YouTube title limit
            return title.strip('"\'')  # Remove quotes if present
        else:
            return self._fallback_title_generation(video_context)

    def generate_engaging_description(self, video_context: str = "") -> str:
        """
        Generate an engaging YouTube description using Grok AI

        Args:
            video_context: Context about the video content

        Returns:
            Engaging description string with hashtags and CTA
        """
        if not self.api_key:
            # Fallback to template-based generation
            return self._fallback_description_generation(video_context)

        import re
        ctx_for_ai = video_context
        if re.match(r'^https?://', ctx_for_ai.strip()):
            ctx_for_ai = "an Instagram reel clip"
        prompt = f"""Create an engaging YouTube Shorts description for a video about: {ctx_for_ai}

        Requirements:
        - Start with a hook (first 2 lines are critical)
        - Include 2-4 relevant hashtags
        - Have a clear call-to-action (like, comment, subscribe)
        - Encourage engagement
        - Suitable for Shorts format
        - Keep it concise but valuable

        Format:
        [Engaging hook/summary]

        [Relevant hashtags]

        [CTA: Like, Comment, Subscribe, Share]

        Return only the description, nothing else."""

        description = self._call_grok_api(prompt, max_tokens=200)
        if description:
            return description.strip()
        else:
            return self._fallback_description_generation(video_context)

    def generate_hashtags(self, video_context: str = "", count: int = 4) -> List[str]:
        """
        Generate relevant hashtags using Grok AI

        Args:
            video_context: Context about the video content
            count: Number of hashtags to generate

        Returns:
            List of hashtag strings (without # prefix)
        """
        if not self.api_key:
            # Fallback to template-based generation
            return self._fallback_hashtag_generation(video_context, count)

        import re
        ctx_for_ai = video_context
        if re.match(r'^https?://', ctx_for_ai.strip()):
            ctx_for_ai = "an Instagram reel clip"
        prompt = f"""Generate {count} relevant, trending hashtags for a YouTube Shorts video about: {ctx_for_ai}

        Requirements:
        - Mix of broad and niche hashtags
        - Include at least one #Shorts variant
        - Relevant to the content
        - Currently trending or evergreen
        - No spaces or special characters in hashtags
        - Return as a comma-separated list without the # symbol

        Example format: Shorts, Viral, Trending, FYP, Amazing, Clip

        Return only the comma-separated list, nothing else."""

        hashtags_text = self._call_grok_api(prompt, max_tokens=100)
        if hashtags_text:
            # Parse the comma-separated list
            hashtags = [tag.strip().lower() for tag in hashtags_text.split(',') if tag.strip()]
            # Ensure we have the requested count
            hashtags = hashtags[:count]
            # Always include shorts as first tag if not present
            if 'shorts' not in [h.replace('#', '') for h in hashtags]:
                hashtags[0] = 'shorts'
            return hashtags
        else:
            return self._fallback_hashtag_generation(video_context, count)

    def generate_complete_metadata(self, video_context: str = "") -> Dict[str, Any]:
        """
        Generate complete metadata package using Grok AI

        Args:
            video_context: Context about the video content

        Returns:
            Dictionary with title, description, and tags
        """
        if not self.api_key:
            return self._fallback_complete_metadata(video_context)

        # Try to get all three from Grok
        title = self.generate_engaging_title(video_context)
        description = self.generate_engaging_description(video_context)
        hashtags = self.generate_hashtags(video_context)

        # If any failed, fall back to template for that component
        if not title:
            title = self._fallback_title_generation(video_context)
        if not description:
            description = self._fallback_description_generation(video_context)
        if not hashtags:
            hashtags = self._fallback_hashtag_generation(video_context)

        return {
            'title': title,
            'description': description,
            'tags': hashtags
        }

    # Fallback methods (template-based) when Grok is not available
    def _fallback_title_generation(self, video_context: str = "") -> str:
        """Fallback title generation using templates"""
        import random
        import re

        # Never expose raw URLs in titles/descriptions
        if re.match(r'^https?://', video_context.strip()):
            clean_context = "this amazing clip"
        else:
            clean_context = video_context.replace('_', ' ').title() if video_context else "Amazing Moment"

        templates = [
            "Amazing Clip! {} 🔥",
            "You WON'T Believe {} 😱",
            "This {} is INSANE 🤯",
            "Watch This {} 👀",
            "OMG {} 😳",
            "Wait For It... {}",
            "{} Will Blow Your Mind 💥",
            "Nobody Expected {} 😲",
            "This {} Changed Everything",
            "The Truth About {} 🤫"
        ]
        template = random.choice(templates)
        title = template.format(clean_context)

        # Ensure it's not too long and append #Shorts
        title += " #Shorts"
        if len(title) > 100:
            title = title[:97] + "..."

        return title

    def _fallback_description_generation(self, video_context: str = "") -> str:
        """Fallback description generation using templates"""
        import random

        hooks = [
            "Check out this incredible moment!",
            "You have to see this to believe it!",
            "This is going viral for a reason!",
            "Don't miss what happens next!",
            "This broke the internet!",
            "Prepare to be amazed!",
            "This is why we share!",
            "You'll watch this twice!",
            "The internet can't get enough of this!",
            "Save this for later - you'll want to watch it again!"
        ]

        hashtag_sets = [
            ["#Shorts", "#Viral", "#Trending", "#FYP"],
            ["#Shorts", "#Amazing", "#Incredible", "#Wow"],
            ["#Shorts", "#Clip", "#Moment", "#Watch"],
            ["#Shorts", "#MustWatch", "#DidYouSee", "#Reaction"],
            ["#Shorts", "#OMG", "#WTF", "#NoWay"]
        ]

        ctas = [
            "👍 Like if you enjoyed! 💬 Comment your thoughts! 🔔 Subscribe for more!",
            "Smash that Like button! Drop a comment below! Don't forget to Subscribe!",
            "Like this video? Show some love! Comment what you think! Subscribe for daily clips!",
            "Double tap if you like it! Share your thoughts in comments! Hit subscribe!",
            "If this made you smile, tap Like! Comment your reaction! Subscribe for daily uploads!"
        ]

        hook = random.choice(hooks)
        hashtags = ' '.join(random.choice(hashtag_sets))
        cta = random.choice(ctas)

        return f"{hook}\n\n{hashtags}\n\n{cta}"

    def _fallback_hashtag_generation(self, video_context: str = "", count: int = 4) -> List[str]:
        """Fallback hashtag generation"""
        base_hashtags = ["shorts", "viral", "trending", "fyp", "amazing", "incredible", "clip", "moment", "watch", "mustsee", "omg", "wow"]
        import random
        selected = random.sample(base_hashtags, min(count, len(base_hashtags)))
        if "shorts" not in selected:
            selected[0] = "shorts"
        return selected[:count]

    def _fallback_complete_metadata(self, video_context: str = "") -> Dict[str, Any]:
        """Fallback complete metadata"""
        return {
            'title': self._fallback_title_generation(video_context),
            'description': self._fallback_description_generation(video_context),
            'tags': self._fallback_hashtag_generation(video_context)
        }