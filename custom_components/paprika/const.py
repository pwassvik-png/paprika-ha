"""Constants for the Paprika integration."""

from typing import Final

DOMAIN: Final = "paprika"
PLATFORMS: list[str] = ["sensor", "calendar", "todo"]
DEFAULT_UPDATE_INTERVAL_MINUTES: Final = 30
API_BASE_URL: Final = "https://www.paprikaapp.com/api/v2/"
SYNC_PATH: Final = "sync/"
LOGIN_PATH: Final = "account/login/"
# Mirror an official Paprika client user agent; the API rejects unknown clients.
USER_AGENT: Final = (
    "Paprika Recipe Manager 3/3.8.2 "
    "(com.hindsightlabs.paprika.mac.v3; build:39; macOS 12.7.6) "
    "Alamofire/5.2.2"
)

CONF_EMAIL: Final = "email"
CONF_PASSWORD: Final = "password"
CONF_RECEIPT: Final = "receipt"
CONF_UPDATE_INTERVAL: Final = "update_interval"
