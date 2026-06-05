"""DataUpdateCoordinator for TikTok integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TikTokAPI, TikTokAuthError, TikTokAPIError, TikTokData
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TikTokCoordinator(DataUpdateCoordinator[TikTokData]):
    def __init__(
        self,
        hass: HomeAssistant,
        api: TikTokAPI,
        top_videos_count: int,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.api = api
        self.top_videos_count = top_videos_count

    async def _async_update_data(self) -> TikTokData:
        try:
            return await self.api.fetch_all(self.top_videos_count)
        except TikTokAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except TikTokAPIError as err:
            raise UpdateFailed(f"TikTok API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err
