"""
Content Generation Service
Handles AI-powered content generation and database persistence
"""

import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import Content, ContentPlatform, ContentStatus, MediaType, PostStatus
from app.config import settings
from app.llm.ollama_client import LLMClient
from app.schemas.content import ContentGenerationRequest, ContentMetadata, ContentRegenerateRequest
from app.utils.exceptions import ContentGenerationError
from app.utils.logger import logger


class ContentService:
    """Service for generating and managing content."""

    def __init__(self, db: Session):
        self.db = db
        self.llm_client = LLMClient()
        self.temperature = 0.7  # Balance between creativity and consistency

    def generate_content(
        self,
        request: ContentGenerationRequest,
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
        media_original_name: Optional[str] = None,
    ) -> list[dict]:
        """
        Generate content for multiple platforms based on request.

        Args:
            request: ContentGenerationRequest with generation parameters
            media_path: Optional path to uploaded media file
            media_type: Optional type of media (image/video)
            media_original_name: Optional original filename

        Returns:
            List of generated content records with platform-specific variations
        """
        try:
            logger.info(f"Starting content generation for platforms: {request.platforms}")

            # Normalize media_type to enum if provided
            media_type_enum = None
            if media_type:
                try:
                    media_type_enum = MediaType(media_type)
                except ValueError:
                    logger.warning(f"Unknown media type: {media_type}, ignoring")

            generated_contents = []

            for platform in request.platforms:
                logger.info(f"Generating content for {platform}")

                # Get platform-specific prompt
                prompt = self._build_prompt(platform, request)

                # Generate content via Gemini AI
                ai_response = self.llm_client.generate(prompt, temperature=self.temperature)

                # Parse and structure the response
                title, body = self._parse_response(ai_response, platform)

                # Prepare metadata
                metadata = self._prepare_metadata(request, platform)

                # Save to database with media info
                content_record = self._save_content(
                    platform=platform,
                    title=title,
                    body=body,
                    metadata=metadata,
                    media_path=media_path,
                    media_type=media_type_enum,
                    media_original_name=media_original_name,
                )

                generated_contents.append(
                    {
                        "id": content_record.id,
                        "platform": content_record.platform,
                        "title": content_record.title,
                        "body": content_record.body,
                        "status": content_record.status,
                        "generated_at": content_record.generated_at.isoformat(),
                        "meta_data": content_record.meta_data,
                        "media_path": content_record.media_path,
                        "media_type": content_record.media_type.value if content_record.media_type else None,
                        "media_original_name": content_record.media_original_name,
                    }
                )

            logger.info(f"Content generation completed. Generated {len(generated_contents)} items.")
            return generated_contents

        except Exception as e:
            logger.error(f"Content generation failed: {str(e)}")
            raise ContentGenerationError(f"Failed to generate content: {str(e)}")

    def _build_prompt(self, platform: ContentPlatform, request: ContentGenerationRequest) -> str:
        """
        Build a platform-specific prompt for content generation.

        Args:
            platform: Target social media platform
            request: Generation request with parameters

        Returns:
            Formatted prompt string
        """
        # Platform-specific constraints and styles
        platform_specs = {
            ContentPlatform.LINKEDIN: {
                "max_length": 3000,
                "style": "professional, informative, thought-leadership",
                "format": "paragraph format with clear sections",
            },
            ContentPlatform.TWITTER: {
                "max_length": 280,
                "style": "concise, engaging, conversational",
                "format": "single tweet",
            },
            ContentPlatform.FACEBOOK: {
                "max_length": 5000,
                "style": "engaging, community-focused, conversational",
                "format": "engaging post with line breaks",
            },
            ContentPlatform.INSTAGRAM: {
                "max_length": 2200,
                "style": "visual, creative, trendy, hashtag-friendly",
                "format": "caption with emojis and hashtags",
            },
            ContentPlatform.TIKTOK: {
                "max_length": 2500,
                "style": "trendy, fun, engaging, youthful, casual",
                "format": "short and punchy content",
            },
            ContentPlatform.YOUTUBE: {
                "max_length": 5000,
                "style": "informative, engaging, optimized for discovery",
                "format": "video title and description",
            },
            ContentPlatform.EMAIL: {
                "max_length": 3000,
                "style": "persuasive, professional, benefit-focused",
                "format": "email subject line and body",
            },
            ContentPlatform.WHATSAPP: {
                "max_length": 1000,
                "style": "friendly, direct, concise, personal",
                "format": "conversational message",
            },
        }

        spec = platform_specs.get(
            platform,
            {
                "max_length": 2000,
                "style": "engaging",
                "format": "standard format",
            },
        )

        # Build the prompt
        prompt = f"""You are a professional content creator and social media expert specializing in {platform.value} content.

Generate high-quality, engaging content for {platform.value} with the following specifications:

TOPIC: {request.topic}
BRAND CONTEXT: {request.brand_context}
TARGET AUDIENCE: {request.target_audience}
TONE: {request.tone}
STYLE: {spec['style']}
MAX LENGTH: {spec['max_length']} characters
FORMAT: {spec['format']}

INSTRUCTIONS:
1. Create a compelling, click-worthy title (descriptive is fine, no strict length limit)
2. The BODY caption MUST be SHORT, CONCISE, and PUNCHY — aim for 2-3 sentences max
3. Make the body attention-grabbing for a casual scrolling user — lead with the most interesting hook
4. Include 5-8 relevant hashtags at the end of the body caption, focused on the spice/commodity trading and export industry (e.g., #SpiceTrade #CommodityExport #GlobalTrade #KafiCommodities — be creative and industry-relevant)
5. Ensure the content is original, unique, and meaningful — every word should add value
6. Incorporate relevant keywords naturally into the short body
7. Match the specified tone and style

{"CALL TO ACTION: Include this CTA: " + request.call_to_action if request.call_to_action else ""}
{"ADDITIONAL NOTES: " + request.additional_instructions if request.additional_instructions else ""}

CRITICAL — Respond in EXACTLY this format with NO extra commentary before or after:
TITLE: [Your title here]
BODY: [Your short, punchy caption with hashtags here]

Do NOT include any introductory text, explanations, greetings, or concluding remarks. Only output the TITLE and BODY lines."""
        return prompt

    def _parse_response(self, response: str, platform: ContentPlatform) -> tuple[str, str]:
        """
        Parse AI response into title and body.
        Handles multiple response formats robustly:
        - Strict TITLE:/BODY: format (case-insensitive)
        - Markdown headings (## Title, **Title**)
        - Free-form text (first line = title, rest = body)
        - Responses with extra LLM commentary before/after

        Args:
            response: Raw AI response
            platform: Target platform

        Returns:
            Tuple of (title, body)
        """
        try:
            raw = response.strip()
            if not raw:
                logger.warning("Empty LLM response received")
                return "Generated Content", "Content could not be generated. Please try again."

            # Normalize line endings
            raw = raw.replace("\r\n", "\n").replace("\r", "\n")

            # Strategy 1: Look for TITLE:/BODY: markers (case-insensitive)
            title_match = re.search(r"^TITLE:\s*(.+)$", raw, re.IGNORECASE | re.MULTILINE)
            body_match = re.search(r"^BODY:\s*([\s\S]+)$", raw, re.IGNORECASE | re.MULTILINE)

            if title_match and body_match:
                title = title_match.group(1).strip()[:100]
                body = body_match.group(1).strip()
                return title, body

            # Strategy 2: Look for markdown headings (## Title / ### Title)
            md_title = re.search(r"^#{1,3}\s+(.+)$", raw, re.MULTILINE)
            lines = raw.split("\n")

            if md_title:
                # First heading is the title, everything after is body
                title = md_title.group(1).strip()[:100]
                # Find the heading line index safely
                heading_text = md_title.group(0).strip()
                try:
                    heading_line = next(i for i, l in enumerate(lines) if heading_text in l.strip())
                except StopIteration:
                    heading_line = 0
                body = "\n".join(lines[heading_line + 1:]).strip()
                if body:
                    return title, body

            # Strategy 3: Split by first empty line (title before, body after)
            if len(lines) > 2:
                for i, line in enumerate(lines):
                    if not line.strip() and i > 0 and i < len(lines) - 1:
                        potential_title = "\n".join(lines[:i]).strip()
                        potential_body = "\n".join(lines[i + 1:]).strip()
                        if potential_title and potential_body:
                            return potential_title[:100], potential_body

            # Strategy 4: First line is title, rest is body
            title = lines[0].strip()[:100] if lines else "Generated Content"
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else raw

            # If title is very long (likley not a real title), use first sentence
            if len(title) > 100:
                sentences = title.split(". ")
                title = sentences[0][:100] if sentences else title[:100]

            # If body is empty but title has content, duplicate
            if not body and title and title != "Generated Content":
                body = title
                title = title[:100]

            return title, body

        except Exception as e:
            logger.warning(f"Failed to parse response: {str(e)}, using fallback")
            lines = response.strip().split("\n") if response else []
            title = lines[0][:100] if lines else "Generated Content"
            body = "\n".join(lines[1:]) if len(lines) > 1 else (response or "Content not available")
            return title, body

    def _prepare_metadata(
        self, request: ContentGenerationRequest, platform: ContentPlatform
    ) -> dict:
        """
        Prepare metadata for the content.

        Args:
            request: Generation request
            platform: Target platform

        Returns:
            Metadata dictionary
        """
        return {
            "platform": platform.value,
            "tone": request.tone,
            "target_audience": request.target_audience,
            "hashtags": self._generate_hashtags(request.topic, platform),
            "keywords": self._extract_keywords(request.topic),
            "generation_model": settings.GEMINI_MODEL,
            "llm_provider": settings.LLM_PROVIDER,
        }

    def _generate_hashtags(self, topic: str, platform: ContentPlatform) -> list[str]:
        """
        Generate relevant hashtags based on topic and platform.

        Args:
            topic: Content topic
            platform: Target platform

        Returns:
            List of relevant hashtags
        """
        # Platform-specific hashtag strategy
        hashtag_count = {
            ContentPlatform.INSTAGRAM: 15,
            ContentPlatform.TWITTER: 3,
            ContentPlatform.TIKTOK: 10,
            ContentPlatform.FACEBOOK: 8,
            ContentPlatform.LINKEDIN: 5,
            ContentPlatform.YOUTUBE: 5,
            ContentPlatform.WHATSAPP: 0,
            ContentPlatform.EMAIL: 0,
        }

        count = hashtag_count.get(platform, 5)

        if count == 0:
            return []

        # Spice & commodity exporting industry hashtags (relevant to Kafi Commodities)
        industry_tags = [
            "#SpiceTrade",
            "#CommodityExport",
            "#GlobalTrade",
            "#KafiCommodities",
            "#ExportBusiness",
            "#SpiceIndustry",
            "#B2BTrade",
            "#SupplyChain",
            "#AgricultureExport",
            "#FoodCommodities",
            "#InternationalTrade",
            "#SpiceMarket",
            "#TradeFinance",
            "#CommodityTrading",
            "#SustainableSourcing",
            "#ExportImport",
            "#QualitySpices",
            "#PremiumExport",
            "#GlobalSupplyChain",
            "#AgriCommodities",
        ]

        # Platform-specific extras
        platform_extras = {
            ContentPlatform.INSTAGRAM: ["#reels", "#explore", "#trending", "#businessgrowth"],
            ContentPlatform.TIKTOK: ["#foryou", "#trending", "#business"],
            ContentPlatform.LINKEDIN: ["#linkedinnews", "#businessgrowth", "#export"],
            ContentPlatform.FACEBOOK: ["#business", "#entrepreneur", "#growth"],
        }

        # Combine: start with industry tags, then add platform extras
        result = list(industry_tags)
        if platform in platform_extras:
            result.extend(platform_extras[platform])

        # Shuffle to keep variety, then take `count` tags
        random.shuffle(result)
        return result[:count]

    def _extract_keywords(self, topic: str) -> list[str]:
        """
        Extract keywords from topic.

        Args:
            topic: Content topic

        Returns:
            List of keywords
        """
        # Simple keyword extraction
        stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for"}
        words = topic.lower().split()
        keywords = [word.strip(".,!?;:") for word in words if word.lower() not in stop_words]
        return keywords[:5]

    def _save_content(
        self,
        platform: ContentPlatform,
        title: str,
        body: str,
        metadata: dict,
        media_path: Optional[str] = None,
        media_type: Optional[MediaType] = None,
        media_original_name: Optional[str] = None,
    ) -> Content:
        """
        Save generated content to database with optional media attachment.

        Args:
            platform: Target platform
            title: Content title
            body: Content body
            metadata: Content metadata
            media_path: Path to uploaded media file
            media_type: Type of media
            media_original_name: Original filename

        Returns:
            Saved Content record
        """
        content = Content(
            platform=platform,
            status=ContentStatus.GENERATED,
            title=title,
            body=body,
            meta_data=metadata,
            media_path=media_path,
            media_type=media_type,
            media_original_name=media_original_name,
            generated_at=datetime.utcnow(),
        )

        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)

        logger.info(
            f"Saved content record {content.id} for platform {platform} "
            f"[media={'yes' if media_path else 'no'}]"
        )
        return content

    def regenerate_content(self, content_id: int, request: ContentRegenerateRequest) -> dict:
        """
        Regenerate title and body for an existing content record using user feedback.
        """
        content = self.db.query(Content).filter(Content.id == content_id).first()
        if not content:
            raise ContentGenerationError(f"Content {content_id} not found")

        logger.info(f"Regenerating content {content_id} for platform {content.platform}")

        gen_request = ContentGenerationRequest(
            platforms=[content.platform],
            topic=request.topic,
            brand_context=request.brand_context,
            tone=request.tone,
            target_audience=request.target_audience,
            call_to_action=request.call_to_action,
            additional_instructions=request.additional_instructions,
        )

        prompt = self._build_regeneration_prompt(
            platform=content.platform,
            request=gen_request,
            previous_title=content.title,
            previous_body=content.body,
            regeneration_instructions=request.regeneration_instructions,
        )

        ai_response = self.llm_client.generate(prompt, temperature=self.temperature + 0.1)
        title, body = self._parse_response(ai_response, content.platform)

        metadata = content.meta_data or {}
        metadata.update(
            {
                "tone": request.tone,
                "target_audience": request.target_audience,
                "hashtags": self._generate_hashtags(request.topic, content.platform),
                "keywords": self._extract_keywords(request.topic),
                "regenerated_at": datetime.utcnow().isoformat(),
            }
        )
        if request.regeneration_instructions.strip():
            metadata["last_regeneration_instructions"] = request.regeneration_instructions.strip()

        content.title = title
        content.body = body
        content.meta_data = metadata
        content.status = ContentStatus.GENERATED
        content.generated_at = datetime.utcnow()
        content.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(content)

        logger.info(f"Regenerated content {content_id}")

        return {
            "id": content.id,
            "platform": content.platform,
            "title": content.title,
            "body": content.body,
            "status": content.status,
            "generated_at": content.generated_at.isoformat(),
            "meta_data": content.meta_data,
            "media_path": content.media_path,
            "media_type": content.media_type.value if content.media_type else None,
            "media_original_name": content.media_original_name,
        }

    def _build_regeneration_prompt(
        self,
        platform: ContentPlatform,
        request: ContentGenerationRequest,
        previous_title: str,
        previous_body: str,
        regeneration_instructions: str,
    ) -> str:
        """Build a prompt that asks for a fresh caption variant using user feedback."""
        base_prompt = self._build_prompt(platform, request)

        feedback_block = ""
        if regeneration_instructions.strip():
            feedback_block = f"""
USER FEEDBACK — incorporate this closely in the new version:
{regeneration_instructions.strip()}
"""
        else:
            feedback_block = """
The user was not satisfied with the previous version. Create a noticeably different alternative with a fresh hook and wording while staying on topic.
"""

        return f"""{base_prompt}

REGENERATION TASK:
The user already received a caption they did NOT like. Write a NEW version — do not copy phrasing from the previous caption.

PREVIOUS TITLE (do not reuse):
{previous_title}

PREVIOUS BODY (do not reuse):
{previous_body}
{feedback_block}
CRITICAL — Respond in EXACTLY this format with NO extra commentary before or after:
TITLE: [Your new title here]
BODY: [Your new short, punchy caption with hashtags here]"""

    def get_content(self, content_id: int) -> Optional[dict]:
        """
        Retrieve a content record by ID.

        Args:
            content_id: ID of content to retrieve

        Returns:
            Content record as dictionary or None
        """
        content = self.db.query(Content).filter(Content.id == content_id).first()

        if not content:
            return None

        return {
            "id": content.id,
            "platform": content.platform,
            "title": content.title,
            "body": content.body,
            "status": content.status,
            "generated_at": content.generated_at.isoformat(),
            "created_at": content.created_at.isoformat(),
            "meta_data": content.meta_data,
            "media_path": content.media_path,
            "media_type": content.media_type.value if content.media_type else None,
            "media_original_name": content.media_original_name,
            "linkedin_post_status": content.linkedin_post_status.value if content.linkedin_post_status else "pending",
            "facebook_post_status": content.facebook_post_status.value if content.facebook_post_status else "pending",
            "instagram_post_status": content.instagram_post_status.value if content.instagram_post_status else "pending",
            "youtube_post_status": content.youtube_post_status.value if content.youtube_post_status else "pending",
            "linkedin_post_id": content.linkedin_post_id,
            "facebook_post_id": content.facebook_post_id,
            "instagram_post_id": content.instagram_post_id,
            "youtube_post_id": content.youtube_post_id,
            "linkedin_accounts_results": content.linkedin_accounts_results,
        }

    def list_content(self, platform: Optional[str] = None, limit: int = 20) -> list[dict]:
        """
        List generated content with optional filtering.

        Args:
            platform: Filter by platform (optional)
            limit: Maximum number of records to return

        Returns:
            List of content records
        """
        query = self.db.query(Content).order_by(Content.generated_at.desc()).limit(limit)

        if platform:
            query = query.filter(Content.platform == platform)

        contents = query.all()

        return [
            {
                "id": c.id,
                "platform": c.platform,
                "title": c.title,
                "body": c.body,
                "status": c.status,
                "generated_at": c.generated_at.isoformat(),
                "meta_data": c.meta_data,
                "media_path": c.media_path,
                "media_type": c.media_type.value if c.media_type else None,
                "linkedin_post_status": c.linkedin_post_status.value if c.linkedin_post_status else "pending",
                "facebook_post_status": c.facebook_post_status.value if c.facebook_post_status else "pending",
                "instagram_post_status": c.instagram_post_status.value if c.instagram_post_status else "pending",
                "youtube_post_status": c.youtube_post_status.value if c.youtube_post_status else "pending",
                "linkedin_post_id": c.linkedin_post_id,
                "facebook_post_id": c.facebook_post_id,
                "instagram_post_id": c.instagram_post_id,
                "youtube_post_id": c.youtube_post_id,
                "linkedin_accounts_results": c.linkedin_accounts_results,
            }
            for c in contents
        ]

    def update_content_status(self, content_id: int, status: ContentStatus) -> bool:
        """
        Update content status.

        Args:
            content_id: ID of content to update
            status: New status

        Returns:
            True if successful, False otherwise
        """
        content = self.db.query(Content).filter(Content.id == content_id).first()

        if not content:
            return False

        content.status = status
        content.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Updated content {content_id} status to {status}")
        return True

    def delete_content(self, content_id: int) -> bool:
        """
        Delete a content record.

        Args:
            content_id: ID of content to delete

        Returns:
            True if successful, False otherwise
        """
        content = self.db.query(Content).filter(Content.id == content_id).first()

        if not content:
            return False

        self.db.delete(content)
        self.db.commit()

        logger.info(f"Deleted content {content_id}")
        return True
