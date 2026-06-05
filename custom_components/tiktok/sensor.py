"""TikTok sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import VideoInfo
from .const import CONF_TOP_VIDEOS_COUNT, DEFAULT_TOP_VIDEOS_COUNT, DOMAIN
from .coordinator import TikTokCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: TikTokCoordinator = hass.data[DOMAIN][entry.entry_id]
    top_n = coordinator.top_videos_count

    entities: list[SensorEntity] = [
        TikTokFollowersSensor(coordinator, entry),
        TikTokLikesSensor(coordinator, entry),
        TikTokVideoCountSensor(coordinator, entry),
        TikTokTotalViewsSensor(coordinator, entry),
        TikTokLastVideoSensor(coordinator, entry),
    ]
    for rank in range(1, top_n + 1):
        entities.append(TikTokTopVideoSensor(coordinator, entry, rank))

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class TikTokBaseSensor(CoordinatorEntity[TikTokCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TikTokCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self):
        from homeassistant.helpers.device_registry import DeviceInfo

        username = ""
        if self.coordinator.data:
            username = self.coordinator.data.user.display_name
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"TikTok {username}",
            manufacturer="TikTok",
            model="TikTok Account",
        )

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._attr_translation_key}"


# ---------------------------------------------------------------------------
# Profile sensors
# ---------------------------------------------------------------------------

class TikTokFollowersSensor(TikTokBaseSensor):
    _attr_translation_key = "followers"
    _attr_icon = "mdi:account-group"

    @property
    def native_value(self):
        return self.coordinator.data.user.follower_count if self.coordinator.data else None


class TikTokLikesSensor(TikTokBaseSensor):
    _attr_translation_key = "likes"
    _attr_icon = "mdi:heart"

    @property
    def native_value(self):
        return self.coordinator.data.user.likes_count if self.coordinator.data else None


class TikTokVideoCountSensor(TikTokBaseSensor):
    _attr_translation_key = "video_count"
    _attr_icon = "mdi:video"

    @property
    def native_value(self):
        return self.coordinator.data.user.video_count if self.coordinator.data else None


class TikTokTotalViewsSensor(TikTokBaseSensor):
    _attr_translation_key = "total_views"
    _attr_icon = "mdi:eye"

    @property
    def native_value(self):
        return self.coordinator.data.total_video_views if self.coordinator.data else None


# ---------------------------------------------------------------------------
# Video sensors (shared base)
# ---------------------------------------------------------------------------

class TikTokVideoSensor(TikTokBaseSensor):
    """Base class for single-video sensors."""

    _attr_state_class = None
    _attr_icon = "mdi:video-box"
    _attr_native_unit_of_measurement = None

    def _video(self) -> VideoInfo | None:
        raise NotImplementedError

    @property
    def native_value(self):
        v = self._video()
        return v.view_count if v else None

    @property
    def entity_picture(self) -> str | None:
        v = self._video()
        return v.cover_image_url if v and v.cover_image_url else None

    @property
    def extra_state_attributes(self):
        v = self._video()
        if not v:
            return {}
        return {
            "title": v.title,
            "video_id": v.video_id,
            "view_count": v.view_count,
            "like_count": v.like_count,
            "comment_count": v.comment_count,
            "share_count": v.share_count,
            "thumbnail": v.cover_image_url,
            "create_time": v.create_time,
        }


# ---------------------------------------------------------------------------
# Top Video N
# ---------------------------------------------------------------------------

class TikTokTopVideoSensor(TikTokVideoSensor):
    def __init__(self, coordinator: TikTokCoordinator, entry: ConfigEntry, rank: int) -> None:
        super().__init__(coordinator, entry)
        self._rank = rank

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_top_video_{self._rank}"

    @property
    def name(self) -> str:
        return f"Top Video {self._rank}"

    def _video(self) -> VideoInfo | None:
        if not self.coordinator.data:
            return None
        videos = self.coordinator.data.top_videos
        return videos[self._rank - 1] if len(videos) >= self._rank else None


# ---------------------------------------------------------------------------
# Last Video
# ---------------------------------------------------------------------------

class TikTokLastVideoSensor(TikTokVideoSensor):
    _attr_translation_key = "last_video"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_last_video"

    def _video(self) -> VideoInfo | None:
        return self.coordinator.data.last_video if self.coordinator.data else None
