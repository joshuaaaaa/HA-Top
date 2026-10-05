"""Constants for Top Recepty integration."""

DOMAIN = "toprecepty"
NAME = "Top Recepty"

# URLs
BASE_URL = "https://www.toprecepty.cz"
ALL_RECIPES_URL = f"{BASE_URL}/vsechny_recepty.php"

# Configuration
CONF_UPDATE_INTERVAL = "update_interval"
DEFAULT_UPDATE_INTERVAL = 24  # hours

# Data storage (.storage/toprecepty_data)
STORAGE_KEY = f"{DOMAIN}_data"
STORAGE_VERSION = 1
MAX_RECIPES = 50
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # bytes

# Sensor
SENSOR_NAME = "Denní recept"
SENSOR_ICON = "mdi:food"
