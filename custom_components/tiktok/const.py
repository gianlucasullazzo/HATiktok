DOMAIN = "tiktok"
CONF_CLIENT_KEY = "client_key"
CONF_CLIENT_SECRET = "client_secret"
CONF_TOP_VIDEOS_COUNT = "top_videos_count"
CONF_REDIRECT_URI = "redirect_uri"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_TOKEN_EXPIRY = "token_expiry"

CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_TOP_VIDEOS_COUNT = 5
MIN_TOP_VIDEOS_COUNT = 1
MAX_TOP_VIDEOS_COUNT = 20
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 1440  # 24h

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
TIKTOK_VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"
TIKTOK_REVOKE_URL = "https://open.tiktokapis.com/v2/oauth/revoke/"

USER_INFO_FIELDS = "display_name,follower_count,following_count,likes_count,video_count,profile_deep_link,avatar_url"
VIDEO_FIELDS = "id,title,cover_image_url,view_count,like_count,comment_count,share_count,create_time"

OAUTH_SCOPES = "user.info.basic,user.info.stats,video.list"
