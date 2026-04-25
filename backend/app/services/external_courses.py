from __future__ import annotations

import time
from abc import ABC, abstractmethod
from urllib.parse import quote_plus

import httpx

from ..config import (
    EXTERNAL_COURSE_PROVIDER,
    LINKEDIN_LEARNING_API_BASE,
    LINKEDIN_LEARNING_CLIENT_ID,
    LINKEDIN_LEARNING_CLIENT_SECRET,
    LINKEDIN_LEARNING_LICENSED_ONLY,
    LINKEDIN_LEARNING_LOCALE_COUNTRY,
    LINKEDIN_LEARNING_LOCALE_LANGUAGE,
    LINKEDIN_LEARNING_TOKEN_URL,
)
from ..models import CourseRecord


def _pick_localized_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("value"), str):
            return value["value"]
        for key in ("localized", "text"):
            nested = value.get(key)
            if isinstance(nested, dict):
                nested_value = nested.get("value")
                if isinstance(nested_value, str):
                    return nested_value
    return ""


def _parse_duration_hours(asset: dict) -> int | None:
    for key in ("timeToComplete", "duration"):
        candidate = asset.get(key)
        if isinstance(candidate, dict):
            for duration_key in ("hours", "value"):
                duration_value = candidate.get(duration_key)
                if isinstance(duration_value, (int, float)) and duration_value > 0:
                    return max(1, round(duration_value))
    details = asset.get("details")
    if isinstance(details, dict):
        return _parse_duration_hours(details)
    return None


def _parse_level(asset: dict) -> str:
    details = asset.get("details")
    if isinstance(details, dict):
        level = details.get("difficultyLevel") or details.get("level")
        if isinstance(level, str) and level:
            return level.lower()
    level = asset.get("difficultyLevel") or asset.get("level")
    if isinstance(level, str) and level:
        return level.lower()
    return "all levels"


def _parse_description(asset: dict) -> str:
    details = asset.get("details")
    if isinstance(details, dict):
        for key in ("shortDescription", "description"):
            text = _pick_localized_text(details.get(key))
            if text:
                return text
    for key in ("description", "summary"):
        text = _pick_localized_text(asset.get(key))
        if text:
            return text
    return "Online course from an external learning provider."


def _parse_url(asset: dict) -> str:
    for key in ("url", "webUrl", "playerUrl"):
        value = asset.get(key)
        if isinstance(value, str) and value:
            return value
    details = asset.get("details")
    if isinstance(details, dict):
        urls = details.get("urls")
        if isinstance(urls, dict):
            for key in ("webLaunch", "landingPage", "player"):
                value = urls.get(key)
                if isinstance(value, str) and value:
                    return value
    return ""


def _parse_classification_names(asset: dict) -> list[str]:
    names: list[str] = []
    for collection_key in ("classifications", "skills"):
        collection = asset.get(collection_key)
        if not isinstance(collection, list):
            continue
        for item in collection:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = _pick_localized_text(item.get("name")) or item.get("displayName") or item.get("slug")
                if isinstance(name, str) and name:
                    names.append(name)
    return names


class ExternalCourseProvider(ABC):
    provider_name = "none"

    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int = 10) -> list[CourseRecord]:
        raise NotImplementedError


class NullExternalCourseProvider(ExternalCourseProvider):
    provider_name = "marketplace_search"

    def configured(self) -> bool:
        return True

    def search(self, query: str, top_k: int = 10) -> list[CourseRecord]:
        topic = query.strip()
        if not topic:
            return []
        encoded = quote_plus(topic)
        providers = [
            (
                "Coursera",
                f"https://www.coursera.org/search?query={encoded}",
                "Browse related university and professional certificate courses.",
            ),
            (
                "Udemy",
                f"https://www.udemy.com/courses/search/?q={encoded}",
                "Explore practical marketplace courses and compare prices before enrolling.",
            ),
            (
                "edX",
                f"https://www.edx.org/search?q={encoded}",
                "Search academic and professional online programs for this topic.",
            ),
        ]
        results: list[CourseRecord] = []
        for index, (provider, url, description) in enumerate(providers[:top_k], start=1):
            results.append(
                CourseRecord(
                    course_id=f"marketplace-{provider.lower().replace(' ', '-')}-{index}-{encoded.lower()}",
                    title=f"{topic} courses on {provider}",
                    provider=provider,
                    category="Marketplace Search",
                    level="all levels",
                    duration_hours=None,
                    skills=[topic],
                    tags=[topic.lower()],
                    description=description,
                    url=url,
                    delivery_mode="external",
                    syllabus=[],
                )
            )
        return results


class LinkedInLearningCourseProvider(ExternalCourseProvider):
    provider_name = "linkedin_learning"

    def __init__(self) -> None:
        self._access_token = ""
        self._access_token_expiry = 0.0

    def configured(self) -> bool:
        return bool(LINKEDIN_LEARNING_CLIENT_ID and LINKEDIN_LEARNING_CLIENT_SECRET)

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expiry:
            return self._access_token

        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                LINKEDIN_LEARNING_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": LINKEDIN_LEARNING_CLIENT_ID,
                    "client_secret": LINKEDIN_LEARNING_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            payload = response.json()

        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise ValueError("External course provider did not return an access token")

        expires_in = payload.get("expires_in", 3600)
        if not isinstance(expires_in, (int, float)):
            expires_in = 3600
        self._access_token = token
        self._access_token_expiry = time.time() + max(60, int(expires_in) - 120)
        return token

    def search(self, query: str, top_k: int = 10) -> list[CourseRecord]:
        if not self.configured() or not query.strip():
            return []

        token = self._get_access_token()
        params = {
            "q": "criteria",
            "count": str(top_k),
            "assetFilteringCriteria.keyword": query.strip(),
            "assetFilteringCriteria.assetTypes[0]": "COURSE",
            "assetFilteringCriteria.locales.language[0]": LINKEDIN_LEARNING_LOCALE_LANGUAGE,
            "assetFilteringCriteria.locales.country[0]": LINKEDIN_LEARNING_LOCALE_COUNTRY,
            "assetPresentationCriteria.sortBy": "RELEVANCE",
            "assetPresentationCriteria.targetLocale.language": LINKEDIN_LEARNING_LOCALE_LANGUAGE,
        }
        if LINKEDIN_LEARNING_LICENSED_ONLY:
            params["assetFilteringCriteria.licensedOnly"] = "true"

        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                f"{LINKEDIN_LEARNING_API_BASE}/learningAssets",
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            payload = response.json()

        results: list[CourseRecord] = []
        for asset in payload.get("elements", []):
            if not isinstance(asset, dict):
                continue
            title = _pick_localized_text(asset.get("title"))
            if not title:
                continue
            description = _parse_description(asset)
            url = _parse_url(asset)
            skills = _parse_classification_names(asset)[:6]
            category = "Online Course"
            classifications = asset.get("classifications")
            if isinstance(classifications, list) and classifications:
                first = classifications[0]
                if isinstance(first, dict):
                    category_name = _pick_localized_text(first.get("name")) or first.get("displayName")
                    if isinstance(category_name, str) and category_name:
                        category = category_name

            results.append(
                CourseRecord(
                    course_id=str(asset.get("urn") or asset.get("id") or title),
                    title=title,
                    provider="LinkedIn Learning",
                    category=category,
                    level=_parse_level(asset),
                    duration_hours=_parse_duration_hours(asset),
                    skills=skills or [query.strip()],
                    tags=[query.strip().lower()],
                    description=description,
                    url=url,
                    delivery_mode="external",
                    syllabus=[],
                )
            )
        return results


def build_external_course_provider() -> ExternalCourseProvider:
    provider_name = EXTERNAL_COURSE_PROVIDER.lower().strip()
    if provider_name == "linkedin_learning":
        return LinkedInLearningCourseProvider()
    return NullExternalCourseProvider()
