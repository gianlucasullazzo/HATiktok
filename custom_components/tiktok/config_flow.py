"""Config flow for TikTok integration (OAuth2 PKCE)."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from urllib.parse import quote, urlencode
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TikTokAPI, TikTokAuthError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_KEY,
    CONF_CLIENT_SECRET,
    CONF_REDIRECT_URI,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRY,
    CONF_SCAN_INTERVAL,
    CONF_TOP_VIDEOS_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TOP_VIDEOS_COUNT,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MAX_TOP_VIDEOS_COUNT,
    MIN_SCAN_INTERVAL,
    MIN_TOP_VIDEOS_COUNT,
    OAUTH_SCOPES,
    TIKTOK_AUTH_URL,
)

_LOGGER = logging.getLogger(__name__)

AUTH_CALLBACK_PATH = "/auth/tiktok/callback"
AUTH_CALLBACK_NAME = "auth:tiktok:callback"


def _generate_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


class TikTokConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._client_key: str = ""
        self._client_secret: str = ""
        self._top_videos_count: int = DEFAULT_TOP_VIDEOS_COUNT
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._redirect_uri_override: str = ""
        self._code_verifier: str = ""
        self._state: str = ""
        self._auth_code: str = ""

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            self._client_key = user_input[CONF_CLIENT_KEY].strip()
            self._client_secret = user_input[CONF_CLIENT_SECRET].strip()
            self._top_videos_count = user_input[CONF_TOP_VIDEOS_COUNT]
            self._scan_interval = user_input[CONF_SCAN_INTERVAL]
            self._redirect_uri_override = user_input.get(CONF_REDIRECT_URI, "").strip()
            return await self._async_step_auth()

        schema = vol.Schema(
            {
                vol.Required(CONF_CLIENT_KEY): str,
                vol.Required(CONF_CLIENT_SECRET): str,
                vol.Optional(
                    CONF_TOP_VIDEOS_COUNT, default=DEFAULT_TOP_VIDEOS_COUNT
                ): vol.All(int, vol.Range(min=MIN_TOP_VIDEOS_COUNT, max=MAX_TOP_VIDEOS_COUNT)),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
                vol.Optional(CONF_REDIRECT_URI, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def _async_step_auth(self):
        self._code_verifier, code_challenge = _generate_pkce_pair()
        self._state = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()

        redirect_uri = self._redirect_uri()
        self.hass.http.register_view(TikTokAuthCallbackView(self._handle_callback))

        # TikTok requires comma-separated scopes with literal commas (not %2C).
        params = urlencode({
            "client_key": self._client_key,
            "scope": OAUTH_SCOPES,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": self._state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }, safe=",")
        auth_url = f"{TIKTOK_AUTH_URL}?{params}"
        return self.async_external_step(step_id="auth", url=auth_url)

    async def async_step_auth(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            # Called by _handle_callback via async_configure; advance to token exchange.
            self._auth_code = user_input["code"]
            return self.async_external_step_done(next_step_id="creation")
        return await self._async_step_auth()

    async def async_step_creation(self, user_input: dict[str, Any] | None = None):
        code: str = self._auth_code
        session = async_get_clientsession(self.hass)
        redirect_uri = self._redirect_uri()
        try:
            token_data = await TikTokAPI.exchange_code(
                self._client_key,
                self._client_secret,
                code,
                self._code_verifier,
                redirect_uri,
                session,
            )
        except TikTokAuthError:
            return self.async_abort(reason="auth_failed")

        # Fetch display_name immediately so the entry title is human-readable.
        title = "TikTok"
        try:
            tmp_api = TikTokAPI(
                client_key=self._client_key,
                client_secret=self._client_secret,
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", ""),
                token_expiry=time.time() + token_data.get("expires_in", 86400),
                session=session,
            )
            user_info = await tmp_api.get_user_info()
            if user_info.display_name:
                title = user_info.display_name
        except Exception:
            pass

        return self.async_create_entry(
            title=title,
            data={
                CONF_CLIENT_KEY: self._client_key,
                CONF_CLIENT_SECRET: self._client_secret,
                CONF_TOP_VIDEOS_COUNT: self._top_videos_count,
                CONF_SCAN_INTERVAL: self._scan_interval,
                CONF_REDIRECT_URI: redirect_uri,
                CONF_ACCESS_TOKEN: token_data["access_token"],
                CONF_REFRESH_TOKEN: token_data.get("refresh_token", ""),
                CONF_TOKEN_EXPIRY: time.time() + token_data.get("expires_in", 86400),
            },
        )

    async def _handle_callback(self, code: str, state: str) -> None:
        if state != self._state:
            _LOGGER.warning("TikTok OAuth state mismatch")
            return
        await self.hass.config_entries.flow.async_configure(
            flow_id=self.flow_id,
            user_input={"code": code},
        )

    def _redirect_uri(self) -> str:
        if self._redirect_uri_override:
            return self._redirect_uri_override
        return self._get_auto_redirect_uri()

    def _get_auto_redirect_uri(self) -> str:
        from homeassistant.helpers.network import get_url, NoURLAvailableError

        try:
            base = get_url(self.hass, prefer_external=True)
        except NoURLAvailableError:
            try:
                base = get_url(self.hass, prefer_external=False)
            except NoURLAvailableError:
                return ""
        return f"{base.rstrip('/')}{AUTH_CALLBACK_PATH}"

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TikTokOptionsFlow(config_entry)


class TikTokOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        def _current(key, default):
            return self._config_entry.options.get(key) or self._config_entry.data.get(key, default)

        schema = vol.Schema(
            {
                vol.Optional(CONF_TOP_VIDEOS_COUNT, default=_current(CONF_TOP_VIDEOS_COUNT, DEFAULT_TOP_VIDEOS_COUNT)): vol.All(
                    int, vol.Range(min=MIN_TOP_VIDEOS_COUNT, max=MAX_TOP_VIDEOS_COUNT)
                ),
                vol.Optional(CONF_SCAN_INTERVAL, default=_current(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): vol.All(
                    int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class TikTokAuthCallbackView(HomeAssistantView):
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME
    requires_auth = False

    def __init__(self, callback_fn) -> None:
        self._callback_fn = callback_fn

    async def get(self, request):
        from aiohttp.web import Response

        code = request.query.get("code")
        state = request.query.get("state")
        error = request.query.get("error")

        if error or not code:
            return Response(
                text=f"<html><body><h2>TikTok authorization failed: {error or 'no code'}</h2><p>You can close this window.</p></body></html>",
                content_type="text/html",
            )

        await self._callback_fn(code, state)
        return Response(
            text="<html><body><h2>TikTok authorization successful!</h2><p>You can close this window and return to Home Assistant.</p></body></html>",
            content_type="text/html",
        )
