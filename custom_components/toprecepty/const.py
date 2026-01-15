"""Constants for Top Recepty integration."""

DOMAIN = "toprecepty"
NAME = "Top Recepty"

# URLs
BASE_URL = "https://www.toprecepty.cz"
ALL_RECIPES_URL = f"{BASE_URL}/vsechny_recepty.php"

# Configuration
CONF_UPDATE_INTERVAL = "update_interval"
DEFAULT_UPDATE_INTERVAL = 24  # hours

# Data storage
DATA_FILE = "toprecepty_recipes.json"
IMAGES_DIR = "toprecepty_images"

# Sensor
SENSOR_NAME = "Denní recept"
SENSOR_ICON = "mdi:food"
