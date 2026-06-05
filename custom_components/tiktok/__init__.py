"""TikTok integration for Home Assistant."""
from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TikTokAPI, TikTokAuthError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_KEY,
    CONF_CLIENT_SECRET,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN_EXPIRY,
    CONF_TOP_VIDEOS_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TOP_VIDEOS_COUNT,
    DOMAIN,
)
from .coordinator import TikTokCoordinator

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = TikTokAPI(
        client_key=entry.data[CONF_CLIENT_KEY],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        token_expiry=entry.data[CONF_TOKEN_EXPIRY],
        session=session,
    )
    def _opt(key, default):
        return entry.options.get(key) or entry.data.get(key, default)

    top_videos_count = _opt(CONF_TOP_VIDEOS_COUNT, DEFAULT_TOP_VIDEOS_COUNT)
    scan_interval = _opt(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = TikTokCoordinator(hass, api, top_videos_count, scan_interval)
    try:
        await coordinator.async_config_entry_first_refresh()
    except TikTokAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err

    # Update entry title with the real display name once we have it.
    if coordinator.data and coordinator.data.user.display_name:
        hass.config_entries.async_update_entry(
            entry, title=coordinator.data.user.display_name
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
