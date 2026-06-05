"""TikTok Display API v2 client."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    TIKTOK_TOKEN_URL,
    TIKTOK_USER_INFO_URL,
    TIKTOK_VIDEO_LIST_URL,
    TIKTOK_REVOKE_URL,
    USER_INFO_FIELDS,
    VIDEO_FIELDS,
)

_LOGGER = logging.getLogger(__name__)


class TikTokAuthError(Exception):
    pass


class TikTokAPIError(Exception):
    pass


@dataclass
class UserInfo:
    display_name: str
    follower_count: int
    following_count: int
    likes_count: int
    video_count: int
    avatar_url: str
    profile_deep_link: str


@dataclass
class VideoInfo:
    video_id: str
    title: str
    cover_image_url: str
    view_count: int
    like_count: int
    comment_count: int
    share_count: int
    create_time: int


@dataclass
class TikTokData:
    user: UserInfo
    top_videos: list[VideoInfo] = field(default_factory=list)
    last_video: VideoInfo | None = None
    total_video_views: int = 0


class TikTokAPI:
    def __init__(
        self,
        client_key: str,
        client_secret: str,
        access_token: str,
        refresh_token: str,
        token_expiry: float,
        session: aiohttp.ClientSession,
    ) -> None:
        self._client_key = client_key
        self._client_secret = client_secret
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = token_expiry
        self._session = session

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    @property
    def token_expiry(self) -> float:
        return self._token_expiry

    async def _ensure_token(self) -> None:
        if time.time() < self._token_expiry - 60:
            return
        await self._refresh_access_token()

    async def _refresh_access_token(self) -> None:
        payload = {
            "client_key": self._client_key,
            "client_secret": self._client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        async with self._session.post(TIKTOK_TOKEN_URL, data=payload) as resp:
            data = await resp.json()
        if "error" in data:
            raise TikTokAuthError(f"Token refresh failed: {data.get('error_description', data['error'])}")
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._token_expiry = time.time() + data.get("expires_in", 86400)

    async def _get_fields(self, fields: str) -> dict:
        """GET /v2/user/info/ for the given fields; return parsed JSON."""
        url = f"{TIKTOK_USER_INFO_URL}?fields={fields}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with self._session.get(url, headers=headers) as resp:
            data = await resp.json()
        _LOGGER.debug("TikTok user/info response for fields=%s: %s", fields, data)
        return data

    async def get_user_info(self) -> UserInfo:
        await self._ensure_token()

        # Step 1: fetch basic fields (always authorized with user.info.basic)
        basic_fields = "display_name,avatar_url"
        data = await self._get_fields(basic_fields)
        self._check_error(data)
        u = data["data"]["user"]
        user = UserInfo(
            display_name=u.get("display_name", ""),
            follower_count=0,
            following_count=0,
            likes_count=0,
            video_count=0,
            avatar_url=u.get("avatar_url", ""),
            profile_deep_link="",
        )

        # Step 2: try to fetch stats fields separately
        stats_fields = "follower_count,following_count,likes_count,video_count"
        data2 = await self._get_fields(stats_fields)
        err2 = data2.get("error", {})
        if isinstance(err2, dict) and err2.get("code", "ok") == "ok":
            u2 = data2["data"]["user"]
            user.follower_count = u2.get("follower_count", 0)
            user.following_count = u2.get("following_count", 0)
            user.likes_count = u2.get("likes_count", 0)
            user.video_count = u2.get("video_count", 0)
        else:
            _LOGGER.warning(
                "Could not fetch stats fields — TikTok response: %s. "
                "Make sure user.info.stats scope is approved in your TikTok Developer app.",
                err2,
            )

        return user

    async def get_videos(self, max_count: int = 20) -> list[VideoInfo]:
        await self._ensure_token()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"max_count": min(max_count, 20)}
        videos: list[VideoInfo] = []
        cursor: int | None = None

        while len(videos) < max_count:
            if cursor is not None:
                payload["cursor"] = cursor
            url = f"{TIKTOK_VIDEO_LIST_URL}?fields={VIDEO_FIELDS}"
            async with self._session.post(
                url, json=payload, headers=headers
            ) as resp:
                data = await resp.json()
            _LOGGER.debug("TikTok video/list response page: %s", data.get("error"))
            err = data.get("error", {})
            if isinstance(err, dict) and err.get("code", "ok") != "ok":
                _LOGGER.warning(
                    "Could not fetch video list — TikTok response: %s. "
                    "Make sure video.list scope is approved in your TikTok Developer app.",
                    err,
                )
                return []
            self._check_error(data)
            page = data.get("data", {})
            for v in page.get("videos", []):
                videos.append(
                    VideoInfo(
                        video_id=v.get("id", ""),
                        title=v.get("title", ""),
                        cover_image_url=v.get("cover_image_url", ""),
                        view_count=v.get("view_count", 0),
                        like_count=v.get("like_count", 0),
                        comment_count=v.get("comment_count", 0),
                        share_count=v.get("share_count", 0),
                        create_time=v.get("create_time", 0),
                    )
                )
            if not page.get("has_more", False):
                break
            cursor = page.get("cursor")

        return sorted(videos, key=lambda v: v.view_count, reverse=True)

    async def fetch_all(self, top_videos_count: int) -> TikTokData:
        user = await self.get_user_info()
        # Fetch enough videos to cover top-N plus get a meaningful total views sum.
        # user.video_count tells us the real total; cap at 100 to avoid too many API pages.
        fetch_count = min(max(top_videos_count * 2, 20, user.video_count), 100)
        videos = await self.get_videos(max_count=fetch_count)
        top = videos[:top_videos_count]
        last = max(videos, key=lambda v: v.create_time) if videos else None
        total_views = sum(v.view_count for v in videos)
        return TikTokData(user=user, top_videos=top, last_video=last, total_video_views=total_views)

    async def revoke_token(self) -> None:
        payload = {
            "client_key": self._client_key,
            "client_secret": self._client_secret,
            "token": self._access_token,
        }
        try:
            async with self._session.post(TIKTOK_REVOKE_URL, data=payload) as resp:
                await resp.read()
        except Exception:
            pass

    @staticmethod
    def _check_error(data: dict) -> None:
        err = data.get("error", {})
        if isinstance(err, dict) and err.get("code", "ok") != "ok":
            code = err.get("code", "unknown")
            msg = err.get("message", "unknown error")
            if code in ("access_token_invalid", "access_token_expired"):
                raise TikTokAuthError(f"{code}: {msg}")
            raise TikTokAPIError(f"{code}: {msg}")

    @classmethod
    async def exchange_code(
        cls,
        client_key: str,
        client_secret: str,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        session: aiohttp.ClientSession,
    ) -> dict:
        payload = {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        async with session.post(TIKTOK_TOKEN_URL, data=payload) as resp:
            data = await resp.json()
        if "error" in data:
            raise TikTokAuthError(f"Token exchange failed: {data.get('error_description', data['error'])}")
        _LOGGER.info(
            "TikTok token exchange OK — granted scopes: %s, open_id: %s",
            data.get("scope", "not returned"),
            data.get("open_id", "?"),
        )
        return data
