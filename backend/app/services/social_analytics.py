"""
Social media analytics service.

Fetches account-level analytics from Facebook, Instagram, and YouTube
and normalizes them into one response shape for the dashboard.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any, Optional

import requests

from app.config import settings
from app.utils.logger import logger


PlatformStatus = str


class SocialAnalyticsService:
    """Account-level analytics client for all supported social platforms."""

    YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    YOUTUBE_ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
    REQUEST_TIMEOUT = 10  # seconds — keep dashboard loads snappy

    def get_summary(self, days: int = 30) -> dict:
        """Fetch analytics for all platforms."""
        platforms = ["facebook", "instagram", "youtube"]
        with ThreadPoolExecutor(max_workers=len(platforms)) as pool:
            results = list(pool.map(lambda p: self.get_platform(p, days), platforms))

        total_views = 0
        total_engagements = 0
        configured_count = 0

        for result in results:
            if result["status"] == "ok":
                configured_count += 1
                totals = result.get("totals", {})
                total_views += self._number(
                    totals.get("views")
                    or totals.get("reach")
                    or totals.get("impressions")
                )
                total_engagements += self._number(totals.get("engagements"))

        return {
            "range": self._range_payload(days),
            "totals": {
                "views": total_views,
                "engagements": total_engagements,
                "configured_platforms": configured_count,
                "total_platforms": len(platforms),
            },
            "platforms": results,
        }

    def get_platform(self, platform: str, days: int = 30) -> dict:
        """Fetch analytics for a single platform."""
        platform = platform.lower()
        fetchers = {
            "facebook": self._facebook_analytics,
            "instagram": self._instagram_analytics,
            "youtube": self._youtube_analytics,
        }

        if platform not in fetchers:
            return self._response(
                platform=platform,
                days=days,
                status="api_error",
                message=f"Unsupported analytics platform: {platform}",
            )

        try:
            return fetchers[platform](days)
        except requests.exceptions.RequestException as exc:
            logger.error(f"{platform.title()} analytics request failed: {str(exc)}")
            return self._response(
                platform=platform,
                days=days,
                status="api_error",
                message=f"{platform.title()} analytics request failed: {str(exc)}",
            )
        except Exception as exc:
            logger.error(f"{platform.title()} analytics failed: {str(exc)}")
            return self._response(
                platform=platform,
                days=days,
                status="api_error",
                message=f"{platform.title()} analytics failed: {str(exc)}",
            )

    def _facebook_analytics(self, days: int) -> dict:
        page_id = settings.FACEBOOK_PAGE_ID.strip()
        access_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN.strip()

        if not page_id or not access_token:
            return self._response(
                platform="facebook",
                days=days,
                status="not_configured",
                message=(
                    "Facebook analytics needs FACEBOOK_PAGE_ID and "
                    "FACEBOOK_PAGE_ACCESS_TOKEN with Page insights permissions."
                ),
            )

        graph_url = self._meta_graph_url()
        start, end = self._range_dates(days)

        # Meta's /insights endpoint fails the WHOLE request with error #100 if any
        # single metric is invalid, and it keeps deprecating metrics. page_impressions
        # / page_impressions_unique were retired in 2025; their replacements are
        # page_media_view (views) and page_total_media_view_unique (reach).
        # Engagement is fetched separately as best-effort below so a rejected
        # engagement metric can never break the core Facebook analytics.
        core_metrics = "page_media_view,page_total_media_view_unique"

        insights_response = requests.get(
            f"{graph_url}/{page_id}/insights",
            params={
                "metric": core_metrics,
                "period": "day",
                "since": start.isoformat(),
                "until": end.isoformat(),
                "access_token": access_token,
            },
            timeout=self.REQUEST_TIMEOUT,
        )

        expired = self._meta_token_expired_error(insights_response)
        if expired:
            repaired = self._repair_meta_token()
            if repaired:
                access_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN.strip()
                insights_response = requests.get(
                    f"{graph_url}/{page_id}/insights",
                    params={
                        "metric": core_metrics,
                        "period": "day",
                        "since": start.isoformat(),
                        "until": end.isoformat(),
                        "access_token": access_token,
                    },
                    timeout=self.REQUEST_TIMEOUT,
                )
                expired = self._meta_token_expired_error(insights_response)
            if expired:
                return self._response(
                    platform="facebook",
                    days=days,
                    status="token_expired",
                    message=(
                        "Facebook Page access token is invalid. "
                        "Visit the Railway Meta auth URL once "
                        "(…/api/v1/auth/meta) — tokens are saved automatically "
                        "and renewed daily afterward."
                    ),
                )

        error = self._platform_error("facebook", insights_response, days)
        if error:
            return error

        profile_response = requests.get(
            f"{graph_url}/{page_id}",
            params={
                "fields": "fan_count,followers_count",
                "access_token": access_token,
            },
            timeout=self.REQUEST_TIMEOUT,
        )
        profile = profile_response.json() if profile_response.ok else {}

        metric_values = self._meta_insights_by_date(insights_response.json())
        engagement_by_date = self._facebook_engagement_by_date(
            graph_url, page_id, access_token, start, end
        )

        totals = {
            "views": sum(item.get("page_media_view", 0) for item in metric_values.values()),
            "impressions": sum(item.get("page_media_view", 0) for item in metric_values.values()),
            "reach": sum(
                item.get("page_total_media_view_unique", 0) for item in metric_values.values()
            ),
            "engagements": sum(engagement_by_date.values()),
            "followers": self._number(profile.get("followers_count") or profile.get("fan_count")),
        }
        series = [
            {
                "date": day,
                "views": values.get("page_media_view", 0),
                "engagements": engagement_by_date.get(day, 0),
            }
            for day, values in sorted(metric_values.items())
        ]

        return self._response(
            platform="facebook",
            days=days,
            status="ok",
            totals=totals,
            series=series,
            message="Facebook Page analytics fetched successfully.",
        )

    def _facebook_engagement_by_date(
        self,
        graph_url: str,
        page_id: str,
        access_token: str,
        start: date,
        end: date,
    ) -> dict[str, int]:
        """Best-effort daily Page engagement (total post reactions).

        Returns {} on any failure (e.g. Meta deprecates the metric) so that a
        rejected engagement metric never breaks the core Facebook analytics.
        """
        try:
            response = requests.get(
                f"{graph_url}/{page_id}/insights",
                params={
                    "metric": "page_actions_post_reactions_total",
                    "period": "day",
                    "since": start.isoformat(),
                    "until": end.isoformat(),
                    "access_token": access_token,
                },
                timeout=self.REQUEST_TIMEOUT,
            )
            if not response.ok:
                logger.warning(
                    f"Facebook engagement metric unavailable "
                    f"({response.status_code}): {response.text[:200]}"
                )
                return {}

            by_date: dict[str, int] = {}
            for date_key, metrics in self._meta_insights_by_date(response.json()).items():
                by_date[date_key] = self._number(
                    metrics.get("page_actions_post_reactions_total")
                )
            return by_date
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Facebook engagement fetch failed: {exc}")
            return {}

    def _instagram_analytics(self, days: int) -> dict:
        account_id = settings.INSTAGRAM_ACCOUNT_ID.strip()
        access_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN.strip()

        if not account_id or not access_token:
            return self._response(
                platform="instagram",
                days=days,
                status="not_configured",
                message=(
                    "Instagram analytics needs INSTAGRAM_ACCOUNT_ID and a Meta token "
                    "with instagram_manage_insights."
                ),
            )

        graph_url = self._meta_graph_url()
        instagram_days = self._instagram_insights_days(days)
        start, end = self._range_dates(instagram_days)
        insights_response = requests.get(
            f"{graph_url}/{account_id}/insights",
            params={
                # Meta deprecated the account-level "impressions" metric; "views"
                # is its replacement in the current Graph API.
                "metric": "reach,views,total_interactions,likes,comments,shares",
                "period": "day",
                "metric_type": "total_value",
                "since": start.isoformat(),
                "until": end.isoformat(),
                "access_token": access_token,
            },
            timeout=self.REQUEST_TIMEOUT,
        )

        expired = self._meta_token_expired_error(insights_response)
        if expired:
            repaired = self._repair_meta_token()
            if repaired:
                access_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN.strip()
                insights_response = requests.get(
                    f"{graph_url}/{account_id}/insights",
                    params={
                        "metric": "reach,views,total_interactions,likes,comments,shares",
                        "period": "day",
                        "metric_type": "total_value",
                        "since": start.isoformat(),
                        "until": end.isoformat(),
                        "access_token": access_token,
                    },
                    timeout=self.REQUEST_TIMEOUT,
                )
                expired = self._meta_token_expired_error(insights_response)
            if expired:
                return self._response(
                    platform="instagram",
                    days=days,
                    status="token_expired",
                    message=(
                        "Instagram access token is invalid. "
                        "Visit the Railway Meta auth URL once "
                        "(…/api/v1/auth/meta) — tokens are saved automatically "
                        "and renewed daily afterward."
                    ),
                )

        error = self._platform_error("instagram", insights_response, days)
        if error:
            return error

        profile_response = requests.get(
            f"{graph_url}/{account_id}",
            params={
                "fields": "followers_count,media_count",
                "access_token": access_token,
            },
            timeout=self.REQUEST_TIMEOUT,
        )
        profile = profile_response.json() if profile_response.ok else {}

        metric_values = self._meta_total_value_insights(insights_response.json())
        totals = {
            "views": metric_values.get("views", 0) or metric_values.get("impressions", 0),
            "reach": metric_values.get("reach", 0),
            "engagements": metric_values.get("total_interactions", 0),
            "likes": metric_values.get("likes", 0),
            "comments": metric_values.get("comments", 0),
            "shares": metric_values.get("shares", 0),
            "followers": self._number(profile.get("followers_count")),
        }
        series = [
            {"date": start.isoformat(), "views": 0, "engagements": 0},
            {
                "date": end.isoformat(),
                "views": totals["views"],
                "engagements": totals["engagements"],
            },
        ]

        return self._response(
            platform="instagram",
            days=instagram_days,
            status="ok",
            totals=totals,
            series=series,
            message=self._instagram_insights_message(
                instagram_days, days, "Instagram account analytics fetched successfully."
            ),
        )

    def _youtube_analytics(self, days: int) -> dict:
        if not (
            settings.YOUTUBE_CLIENT_ID.strip()
            and settings.YOUTUBE_CLIENT_SECRET.strip()
            and settings.YOUTUBE_REFRESH_TOKEN.strip()
        ):
            return self._response(
                platform="youtube",
                days=days,
                status="not_configured",
                message=(
                    "YouTube analytics needs YOUTUBE_CLIENT_ID, "
                    "YOUTUBE_CLIENT_SECRET, and a refresh token with "
                    "yt-analytics.readonly."
                ),
            )

        access_token, refresh_error = self._youtube_access_token()
        if not access_token:
            if refresh_error == "expired_or_revoked":
                message = (
                    "YouTube refresh token expired or was revoked. "
                    "Reconnect on Railway at …/api/v1/auth/youtube — the new token "
                    "is saved automatically. Then publish the Google OAuth consent "
                    "screen (In production) so Testing-mode 7-day expiry stops."
                )
                status = "token_expired"
            elif refresh_error == "invalid_credentials":
                message = (
                    "YouTube client credentials do not match the refresh token. "
                    "Confirm YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET match "
                    "the Google Cloud project that issued YOUTUBE_REFRESH_TOKEN."
                )
                status = "permission_error"
            else:
                message = (
                    "Could not refresh YouTube token. Reconnect on Railway at "
                    "…/api/v1/auth/youtube and ensure yt-analytics.readonly is granted."
                )
                status = "permission_error"
            return self._response(
                platform="youtube",
                days=days,
                status=status,
                message=message,
            )

        start, end = self._range_dates(days)
        response = requests.get(
            self.YOUTUBE_ANALYTICS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "ids": "channel==MINE",
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "metrics": (
                    "views,likes,comments,shares,subscribersGained,"
                    "estimatedMinutesWatched"
                ),
                "dimensions": "day",
                "sort": "day",
            },
            timeout=self.REQUEST_TIMEOUT,
        )

        error = self._platform_error("youtube", response, days)
        if error:
            return error

        payload = response.json()
        headers = [column["name"] for column in payload.get("columnHeaders", [])]
        totals = {
            "views": 0,
            "engagements": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "subscribers": 0,
            "watch_time_minutes": 0,
        }
        series = []

        for row in payload.get("rows", []):
            row_data = dict(zip(headers, row))
            likes = self._number(row_data.get("likes"))
            comments = self._number(row_data.get("comments"))
            shares = self._number(row_data.get("shares"))
            engagements = likes + comments + shares
            views = self._number(row_data.get("views"))

            totals["views"] += views
            totals["engagements"] += engagements
            totals["likes"] += likes
            totals["comments"] += comments
            totals["shares"] += shares
            totals["subscribers"] += self._number(row_data.get("subscribersGained"))
            totals["watch_time_minutes"] += self._number(
                row_data.get("estimatedMinutesWatched")
            )
            series.append(
                {
                    "date": str(row_data.get("day", "")),
                    "views": views,
                    "engagements": engagements,
                }
            )

        return self._response(
            platform="youtube",
            days=days,
            status="ok",
            totals=totals,
            series=series,
            message="YouTube channel analytics fetched successfully.",
        )

    def _repair_meta_token(self) -> bool:
        """Try to auto-refresh Meta tokens when analytics hits an expiry error."""
        try:
            from app.services.meta_token_service import ensure_valid_page_token

            return ensure_valid_page_token()
        except Exception as exc:
            logger.warning(f"Meta token auto-repair failed: {exc}")
            return False

    def _youtube_access_token(self) -> tuple[Optional[str], str]:
        """Refresh YouTube access token. Returns (token, error_code)."""
        response = requests.post(
            self.YOUTUBE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.YOUTUBE_CLIENT_ID.strip(),
                "client_secret": settings.YOUTUBE_CLIENT_SECRET.strip(),
                "refresh_token": settings.YOUTUBE_REFRESH_TOKEN.strip(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.REQUEST_TIMEOUT,
        )

        if not response.ok:
            logger.error(
                f"YouTube analytics token refresh failed: {response.status_code} "
                f"{response.text[:500]}"
            )
            try:
                err = response.json()
                error = err.get("error", "")
                if error == "invalid_grant":
                    return None, "expired_or_revoked"
                if error in ("invalid_client", "unauthorized_client"):
                    return None, "invalid_credentials"
            except Exception:
                pass
            return None, "refresh_failed"

        return response.json().get("access_token"), ""

    def _meta_token_expired_error(self, response: requests.Response) -> bool:
        """Return True when Meta returns a token-expired OAuthException (code 190)."""
        if response.status_code not in (400, 401):
            return False
        try:
            err = response.json().get("error", {})
            # code 190: invalid/expired token; subcode 463/467: session expired
            return err.get("code") == 190 or err.get("error_subcode") in (463, 467)
        except Exception:
            return False

    def _platform_error(self, platform: str, response: requests.Response, days: int) -> Optional[dict]:
        if response.ok:
            return None

        response_text = response.text.lower()
        auth_error_terms = (
            "permission",
            "access token",
            "authentication",
            "auth",
            "expired",
            "insufficient",
            "scope",
            "oauth",
        )

        status = "permission_error" if response.status_code in (401, 403) else "api_error"
        if response.status_code == 400 and any(term in response_text for term in auth_error_terms):
            status = "permission_error"

        return self._response(
            platform=platform,
            days=days,
            status=status,
            message=(
                f"{platform.title()} analytics API returned "
                f"{response.status_code}: {response.text[:500]}"
            ),
        )

    def _response(
        self,
        platform: str,
        days: int,
        status: PlatformStatus,
        totals: Optional[dict[str, Any]] = None,
        series: Optional[list[dict[str, Any]]] = None,
        message: str = "",
    ) -> dict:
        return {
            "platform": platform,
            "status": status,
            "range": self._range_payload(days),
            "totals": totals or {},
            "series": series or [],
            "message": message,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    def _range_payload(self, days: int) -> dict:
        start, end = self._range_dates(days)
        return {"start": start.isoformat(), "end": end.isoformat(), "days": days}

    def _range_dates(self, days: int) -> tuple[date, date]:
        safe_days = max(1, min(days, 90))
        end = date.today()
        start = end - timedelta(days=safe_days - 1)
        return start, end

    # Instagram Graph /insights: since and until cannot span more than 30 days.
    INSTAGRAM_INSIGHTS_MAX_DAYS = 30

    def _instagram_insights_days(self, days: int) -> int:
        return max(1, min(days, self.INSTAGRAM_INSIGHTS_MAX_DAYS))

    def _instagram_insights_message(
        self, instagram_days: int, requested_days: int, success_message: str
    ) -> str:
        if requested_days > instagram_days:
            return (
                f"{success_message} Instagram limits insights to the last "
                f"{self.INSTAGRAM_INSIGHTS_MAX_DAYS} days; showing {instagram_days} days."
            )
        return success_message

    def _meta_graph_url(self) -> str:
        version = settings.META_GRAPH_API_VERSION.strip() or "v18.0"
        return f"https://graph.facebook.com/{version}"

    def _meta_insights_by_date(self, payload: dict) -> dict[str, dict[str, int]]:
        by_date: dict[str, dict[str, int]] = {}
        for metric in payload.get("data", []):
            metric_name = metric.get("name")
            if not metric_name:
                continue
            for value in metric.get("values", []):
                date_key = str(value.get("end_time", ""))[:10]
                if not date_key:
                    continue
                by_date.setdefault(date_key, {})[metric_name] = self._number(
                    value.get("value")
                )
        return by_date

    def _meta_total_value_insights(self, payload: dict) -> dict[str, int]:
        totals: dict[str, int] = {}
        for metric in payload.get("data", []):
            metric_name = metric.get("name")
            if not metric_name:
                continue

            total_value = metric.get("total_value")
            if isinstance(total_value, dict):
                totals[metric_name] = self._number(total_value.get("value"))
                continue

            values = metric.get("values", [])
            if values:
                totals[metric_name] = sum(
                    self._number(value.get("value")) for value in values
                )
        return totals

    def _number(self, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, dict):
            return sum(self._number(item) for item in value.values())
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
