"""Sensor platform for Top Recepty integration."""
import json
import logging
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ALL_RECIPES_URL,
    BASE_URL,
    CONF_UPDATE_INTERVAL,
    DATA_FILE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    IMAGES_DIR,
    SENSOR_ICON,
    SENSOR_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Top Recepty sensor."""
    update_interval = config_entry.data.get(
        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
    )

    coordinator = TopReceptyCoordinator(hass, update_interval)
    await coordinator.async_fetch_recipes()

    async_add_entities([DailyRecipeSensor(coordinator)], True)


class TopReceptyCoordinator:
    """Class to manage fetching Top Recepty data."""

    def __init__(self, hass: HomeAssistant, update_interval: int) -> None:
        """Initialize."""
        self.hass = hass
        self.update_interval = timedelta(hours=update_interval)
        self.recipes = []
        self.data_dir = Path(hass.config.path("custom_components", DOMAIN, "data"))
        self.data_file = self.data_dir / DATA_FILE
        # Store daily recipe image in www folder for Lovelace access
        self.www_dir = Path(hass.config.path("www", "toprecepty"))
        self.daily_image_filename = "daily_recipe.jpg"
        self.last_update = None

        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.www_dir.mkdir(parents=True, exist_ok=True)

    async def async_fetch_recipes(self) -> None:
        """Fetch recipes from toprecepty.cz."""
        try:
            session = async_get_clientsession(self.hass)

            # Fetch the main page with all recipes
            async with session.get(ALL_RECIPES_URL, timeout=30) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to fetch recipes: HTTP %s", response.status
                    )
                    return

                html = await response.text()

            # Parse HTML
            soup = BeautifulSoup(html, "html.parser")
            recipes_list = []

            # Find all recipe items
            # Structure may vary, this is a common pattern for recipe listings
            recipe_items = soup.find_all("div", class_=lambda x: x and "recept" in x.lower())

            if not recipe_items:
                # Try alternative selectors
                recipe_items = soup.find_all("article")

            if not recipe_items:
                # Try to find links with recipe patterns
                recipe_items = soup.find_all("a", href=lambda x: x and "recept" in x)

            _LOGGER.info(f"Found {len(recipe_items)} recipe items")

            for item in recipe_items[:50]:  # Limit to 50 recipes
                try:
                    recipe_data = await self._parse_recipe_item(item, session)
                    if recipe_data:
                        recipes_list.append(recipe_data)
                except Exception as err:
                    _LOGGER.error(f"Error parsing recipe item: {err}")
                    continue

            if recipes_list:
                self.recipes = recipes_list
                self.last_update = datetime.now()
                await self._save_recipes()
                _LOGGER.info(f"Successfully fetched {len(recipes_list)} recipes")
            else:
                _LOGGER.warning("No recipes found, loading from cache")
                await self._load_recipes()

        except Exception as err:
            _LOGGER.error(f"Error fetching recipes: {err}")
            # Try to load from cache
            await self._load_recipes()

    async def _parse_recipe_item(self, item, session) -> dict | None:
        """Parse a single recipe item."""
        try:
            # Try to find recipe link
            link = None
            if item.name == "a":
                link = item
            else:
                link = item.find("a")

            if not link or not link.get("href"):
                return None

            url = link.get("href")
            if not url.startswith("http"):
                url = BASE_URL + url if url.startswith("/") else f"{BASE_URL}/{url}"

            # Find recipe title
            title = None
            title_elem = item.find(["h2", "h3", "h4"])
            if title_elem:
                title = title_elem.get_text(strip=True)
            elif link:
                title = link.get_text(strip=True)

            if not title:
                return None

            # Find image
            image_url = None
            img = item.find("img")
            if img:
                image_url = img.get("src") or img.get("data-src")
                if image_url and not image_url.startswith("http"):
                    image_url = BASE_URL + image_url if image_url.startswith("/") else f"{BASE_URL}/{image_url}"

            # Try to get description
            description = ""
            desc_elem = item.find("p")
            if desc_elem:
                description = desc_elem.get_text(strip=True)

            recipe = {
                "id": abs(hash(url)) % (10 ** 10),
                "title": title,
                "url": url,
                "image_url": image_url,
                "description": description,
                "prep_time": None,  # Will be fetched when recipe becomes daily recipe
                "servings": None,
                "rating": None,
                "difficulty": None,
                "fetched_at": datetime.now().isoformat(),
            }

            return recipe

        except Exception as err:
            _LOGGER.error(f"Error parsing recipe item: {err}")
            return None

    async def download_daily_recipe_image(self, image_url: str) -> str | None:
        """Download daily recipe image and save as daily_recipe.jpg."""
        if not image_url:
            return None

        try:
            session = async_get_clientsession(self.hass)
            filepath = self.www_dir / self.daily_image_filename

            async with session.get(image_url, timeout=10) as response:
                if response.status == 200:
                    content = await response.read()
                    filepath.write_bytes(content)
                    # Return path accessible from Lovelace
                    return f"/local/toprecepty/{self.daily_image_filename}"

        except Exception as err:
            _LOGGER.error(f"Error downloading daily recipe image {image_url}: {err}")

        return None

    async def fetch_recipe_details(self, recipe_url: str) -> dict:
        """Fetch additional details from recipe page."""
        details = {"prep_time": None, "servings": None, "rating": None, "difficulty": None}

        try:
            session = async_get_clientsession(self.hass)

            async with session.get(recipe_url, timeout=15) as response:
                if response.status != 200:
                    return details

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                # Try to find prep time
                # Common patterns: "Čas přípravy:", "Příprava:", etc.
                prep_time_keywords = ["čas přípravy", "příprava", "čas"]

                for keyword in prep_time_keywords:
                    # Try to find in text
                    text_elements = soup.find_all(text=lambda t: t and keyword in t.lower())

                    for elem in text_elements:
                        # Look for time patterns (e.g., "30 min", "1 hod", "45 minut")
                        import re
                        time_pattern = r'(\d+)\s*(min|minut|hod|hodin)'

                        # Check the element and its parent
                        parent = elem.parent if hasattr(elem, 'parent') else None
                        if parent:
                            parent_text = parent.get_text()
                            match = re.search(time_pattern, parent_text, re.IGNORECASE)
                            if match:
                                details["prep_time"] = match.group(0)
                                break

                    if details["prep_time"]:
                        break

                # Try to find servings/portions
                servings_keywords = ["porce", "porcí", "porci"]
                for keyword in servings_keywords:
                    text_elements = soup.find_all(text=lambda t: t and keyword in t.lower())

                    for elem in text_elements:
                        import re
                        servings_pattern = r'(\d+)\s*porc'

                        parent = elem.parent if hasattr(elem, 'parent') else None
                        if parent:
                            parent_text = parent.get_text()
                            match = re.search(servings_pattern, parent_text, re.IGNORECASE)
                            if match:
                                details["servings"] = int(match.group(1))
                                break

                    if details["servings"]:
                        break

                # Try to find rating (e.g., "4,7 (83x)")
                rating_pattern = r'(\d+,\d+)\s*\((\d+)x?\)'
                rating_matches = soup.find_all(text=lambda t: t and re.search(rating_pattern, str(t)))
                if rating_matches:
                    for match_text in rating_matches:
                        match = re.search(rating_pattern, str(match_text))
                        if match:
                            rating_value = match.group(1)
                            rating_count = match.group(2)
                            details["rating"] = f"{rating_value} ({rating_count}x)"
                            break

                # Try to find difficulty
                difficulty_keywords = ["snadný", "snadná", "střední", "středně", "náročný", "náročná", "obtížný", "obtížná"]
                for keyword in difficulty_keywords:
                    text_elements = soup.find_all(text=lambda t: t and keyword in t.lower())
                    if text_elements:
                        # Get the text and clean it
                        difficulty_text = text_elements[0].strip()
                        # Normalize to single word
                        if "snadn" in difficulty_text.lower():
                            details["difficulty"] = "Snadný"
                        elif "střed" in difficulty_text.lower():
                            details["difficulty"] = "Střední"
                        elif "nároč" in difficulty_text.lower() or "obtíž" in difficulty_text.lower():
                            details["difficulty"] = "Náročný"
                        break

                _LOGGER.debug(f"Fetched details for recipe: {details}")

        except Exception as err:
            _LOGGER.error(f"Error fetching recipe details from {recipe_url}: {err}")

        return details

    async def _save_recipes(self) -> None:
        """Save recipes to JSON file."""
        try:
            data = {
                "recipes": self.recipes,
                "last_update": self.last_update.isoformat() if self.last_update else None,
            }

            with open(self.data_file, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)

            _LOGGER.debug(f"Saved {len(self.recipes)} recipes to {self.data_file}")

        except Exception as err:
            _LOGGER.error(f"Error saving recipes: {err}")

    async def _load_recipes(self) -> None:
        """Load recipes from JSON file."""
        try:
            if not self.data_file.exists():
                _LOGGER.warning("No cached recipes found")
                return

            with open(self.data_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            self.recipes = data.get("recipes", [])
            last_update_str = data.get("last_update")
            if last_update_str:
                self.last_update = datetime.fromisoformat(last_update_str)

            _LOGGER.info(f"Loaded {len(self.recipes)} recipes from cache")

        except Exception as err:
            _LOGGER.error(f"Error loading recipes: {err}")
            self.recipes = []

    def get_daily_recipe(self) -> dict | None:
        """Get the daily recipe based on current date."""
        if not self.recipes:
            return None

        # Use date as seed for consistent daily recipe
        today = datetime.now().date()
        seed = int(today.strftime("%Y%m%d"))
        random.seed(seed)

        return random.choice(self.recipes)


class DailyRecipeSensor(SensorEntity):
    """Representation of a Daily Recipe Sensor."""

    def __init__(self, coordinator: TopReceptyCoordinator) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._attr_name = SENSOR_NAME
        self._attr_unique_id = f"{DOMAIN}_daily_recipe"
        self._attr_icon = SENSOR_ICON
        self._current_recipe_id = None
        self._local_image_path = None

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        recipe = self._coordinator.get_daily_recipe()
        if recipe:
            return recipe.get("title")
        return "Žádný recept"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        recipe = self._coordinator.get_daily_recipe()
        if not recipe:
            return {}

        attributes = {
            "recipe_id": recipe.get("id"),
            "title": recipe.get("title"),
            "url": recipe.get("url"),
            "image_url": recipe.get("image_url"),
            "local_image": self._local_image_path,
            "description": recipe.get("description"),
            "prep_time": recipe.get("prep_time"),
            "servings": recipe.get("servings"),
            "rating": recipe.get("rating"),
            "difficulty": recipe.get("difficulty"),
            "last_update": self._coordinator.last_update.isoformat()
            if self._coordinator.last_update
            else None,
        }

        return attributes

    async def async_update(self) -> None:
        """Update the sensor."""
        # Check if we need to refresh recipes
        if self._coordinator.last_update is None or (
            datetime.now() - self._coordinator.last_update
            > self._coordinator.update_interval
        ):
            await self._coordinator.async_fetch_recipes()

        # Download image and fetch details for daily recipe if it changed
        recipe = self._coordinator.get_daily_recipe()
        if recipe:
            recipe_id = recipe.get("id")
            # Download image and fetch details only if recipe changed
            if recipe_id != self._current_recipe_id:
                self._current_recipe_id = recipe_id

                # Download image
                image_url = recipe.get("image_url")
                if image_url:
                    self._local_image_path = await self._coordinator.download_daily_recipe_image(image_url)
                    _LOGGER.info(f"Downloaded daily recipe image: {self._local_image_path}")
                else:
                    self._local_image_path = None

                # Fetch recipe details (prep time, servings, rating, difficulty)
                recipe_url = recipe.get("url")
                if recipe_url and not recipe.get("prep_time"):
                    details = await self._coordinator.fetch_recipe_details(recipe_url)
                    recipe["prep_time"] = details.get("prep_time")
                    recipe["servings"] = details.get("servings")
                    recipe["rating"] = details.get("rating")
                    recipe["difficulty"] = details.get("difficulty")
                    # Save updated recipe data
                    await self._coordinator._save_recipes()
                    _LOGGER.info(f"Fetched recipe details: prep_time={details.get('prep_time')}, servings={details.get('servings')}, rating={details.get('rating')}, difficulty={details.get('difficulty')}")
