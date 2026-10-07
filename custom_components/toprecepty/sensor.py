"""Sensor platform for Top Recepty integration."""
from __future__ import annotations

import hashlib
import logging
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ALL_RECIPES_URL,
    BASE_URL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_IMAGE_SIZE,
    MAX_RECIPES,
    SENSOR_ICON,
    SENSOR_NAME,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
IMAGE_TIMEOUT = aiohttp.ClientTimeout(total=20)
DAILY_IMAGE_FILENAME = "daily_recipe.jpg"
# Bump to re-parse details of a cached daily recipe after parser changes
DETAIL_PARSER_VERSION = 4

# Attributes holding the real image URL on lazy-loaded <img> tags
IMG_SRC_ATTRS = ("data-src", "data-lazy-src", "data-original", "data-srcset", "srcset", "src")


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
    # Only loads the local cache - network requests run in the background
    # so they never delay Home Assistant startup.
    await coordinator.async_load()

    async_add_entities([DailyRecipeSensor(coordinator)])


# --------------------------------------------------------------------------
# HTML parsing helpers (CPU bound, executed in the executor thread pool)
# --------------------------------------------------------------------------


def _recipe_id(url: str) -> int:
    """Return a stable id for a recipe URL (same across restarts)."""
    return int(hashlib.md5(url.encode("utf-8")).hexdigest()[:10], 16)


def _normalize_url(href: str | None) -> str | None:
    """Convert a relative href to an absolute URL without fragment."""
    if not href:
        return None
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "data:")):
        return None
    return urljoin(BASE_URL + "/", href).split("#", 1)[0]


def _is_recipe_url(url: str | None) -> bool:
    """Return True if URL points to a recipe detail page."""
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.netloc and "toprecepty.cz" not in parsed.netloc:
        return False
    path = parsed.path.lower()
    # Detail pages look like /recept/12345-nazev-receptu/
    if re.search(r"/recept/[^/]+", path):
        return True
    # Fallback for other URL formats containing recipe id
    return "recept" in path and bool(re.search(r"\d", path))


def _img_url(img) -> str | None:
    """Return the real image URL of an <img> (handles lazy loading)."""
    if img is None:
        return None
    for attr in IMG_SRC_ATTRS:
        value = img.get(attr)
        if not value:
            continue
        # srcset: "url1 300w, url2 600w" -> take the last (largest) candidate
        if "srcset" in attr:
            candidates = [c.strip().split(" ")[0] for c in value.split(",") if c.strip()]
            value = candidates[-1] if candidates else None
        url = _normalize_url(value)
        if url and not url.lower().endswith((".svg", ".gif")):
            return url
    return None


def _find_container(link, url: str):
    """Return the biggest ancestor of link that contains only this recipe.

    This guarantees the image and title found inside the container belong
    to the same recipe as the link (previously the first image of a
    container holding several recipes could be used).
    """
    node = link
    for _ in range(6):
        parent = node.parent
        if parent is None or parent.name in ("body", "html", "[document]"):
            break
        other = False
        for a in parent.find_all("a", href=True):
            other_url = _normalize_url(a["href"])
            if _is_recipe_url(other_url) and other_url != url:
                other = True
                break
        if other:
            break
        node = parent
    return node


def parse_listing(html: str) -> list[dict]:
    """Parse the listing page into a list of recipes."""
    soup = BeautifulSoup(html, "html.parser")
    recipes: list[dict] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        url = _normalize_url(link["href"])
        if not _is_recipe_url(url) or url in seen:
            continue
        seen.add(url)

        container = _find_container(link, url)

        title = None
        heading = container.find(["h2", "h3", "h4"])
        if heading:
            title = heading.get_text(" ", strip=True)
        if not title:
            texts = [
                a.get_text(" ", strip=True)
                for a in container.find_all("a", href=True)
                if _normalize_url(a["href"]) == url
            ]
            texts = [t for t in texts if t]
            if texts:
                title = max(texts, key=len)
        if not title:
            title = link.get("title")
        img = container.find("img")
        if not title and img is not None:
            title = img.get("alt")
        if not title:
            continue

        description = ""
        desc = container.find("p")
        if desc:
            description = desc.get_text(" ", strip=True)

        recipes.append(
            {
                "id": _recipe_id(url),
                "title": title.strip(),
                "url": url,
                "image_url": _img_url(img),
                "description": description,
            }
        )
        if len(recipes) >= MAX_RECIPES:
            break

    return recipes


TIME_RE = re.compile(
    r"(?<![\d,.])(\d+)\s*(?:hod(?:in[ay]?)?|h)\b(?:\s*(\d+)\s*min(?:ut[ay]?)?\b)?"
    r"|(?<![\d,.])(\d+)\s*min(?:ut[ay]?)?\b",
    re.IGNORECASE,
)


DIFFICULTY_RE = re.compile(r"(snadn|střed|nároč|obtížn)\w*", re.IGNORECASE)
DIFFICULTY_MAP = {
    "snadn": "Snadný",
    "střed": "Střední",
    "nároč": "Náročný",
    "obtížn": "Náročný",
}


def _format_duration(match: re.Match) -> str:
    """Format a TIME_RE match as e.g. "140 min" or "1 hod 30 min"."""
    hours, minutes, only_minutes = match.groups()
    if only_minutes:
        return f"{int(only_minutes)} min"
    if minutes:
        return f"{int(hours)} hod {int(minutes)} min"
    return f"{int(hours)} hod"


def _find_duration(text: str) -> str | None:
    match = TIME_RE.search(text)
    return _format_duration(match) if match else None


def _header_nodes(soup, photo_url: str | None) -> list[str]:
    """Return text pieces of the recipe header (title -> description ->
    difficulty / time / rating) - everything between h1 and the photo.

    Small icons (difficulty bars, clock) are skipped, only the recipe
    photo itself ends the header.
    """
    h1 = _title_h1(soup)
    if h1 is None:
        return []
    photo_path = urlparse(photo_url).path if photo_url else None
    photo_name = photo_path.rsplit("/", 1)[-1] if photo_path else None
    nodes: list[str] = []
    for element in h1.next_elements:
        name = getattr(element, "name", None)
        if name == "img":
            # Author avatar, icons etc. are skipped - only the recipe photo
            # ends the header.
            src = _img_url(element)
            if photo_name and src and urlparse(src).path.rsplit("/", 1)[-1] == photo_name:
                break
            continue
        if name is None and element.parent is not None and element.parent.name not in (
            "script",
            "style",
            "noscript",
        ):
            text = " ".join(str(element).split())
            if text:
                nodes.append(text)
                if len(nodes) >= 150:
                    break
    return nodes


def _title_h1(soup):
    """Return the h1 with the recipe title (not a logo in the page header)."""
    headings = soup.find_all("h1")
    if not headings:
        return None
    og_title = soup.find("meta", attrs={"property": "og:title"})
    og_title = (og_title.get("content") or "").lower() if og_title else ""
    for h1 in headings:
        text = h1.get_text(" ", strip=True).lower()
        if text and og_title and (text in og_title or og_title in text):
            return h1
    for h1 in headings:
        if h1.get_text(strip=True) and not h1.find_parent(["header", "nav", "a"]):
            return h1
    return headings[0]


def _schema_duration(soup) -> str | None:
    """Read totalTime/prepTime (ISO 8601, e.g. PT140M) from schema.org data."""
    candidates: list[str] = []
    # totalTime is what the recipe page shows - prefer it over prepTime
    for key in ("totalTime", "prepTime"):
        tag = soup.find(attrs={"itemprop": key})
        if tag is not None:
            candidates.append(tag.get("content") or tag.get("datetime") or "")
        for script in soup.find_all("script", type="application/ld+json"):
            found = re.search(rf'"{key}"\s*:\s*"([^"]+)"', script.string or "")
            if found:
                candidates.append(found.group(1))
    for value in candidates:
        iso = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?", value.strip(), re.IGNORECASE)
        if iso and (iso.group(1) or iso.group(2)):
            total = int(iso.group(1) or 0) * 60 + int(iso.group(2) or 0)
            if total:
                return f"{total} min"
    return None


def _schema_rating(soup) -> str | None:
    """Read aggregateRating from schema.org data, e.g. "4,7 (84x)"."""
    value = count = None
    tag = soup.find(attrs={"itemprop": "ratingValue"})
    if tag is not None:
        value = tag.get("content") or tag.get_text(strip=True)
        count_tag = soup.find(attrs={"itemprop": ["ratingCount", "reviewCount"]})
        if count_tag is not None:
            count = count_tag.get("content") or count_tag.get_text(strip=True)
    if not value:
        for script in soup.find_all("script", type="application/ld+json"):
            text = script.string or ""
            found = re.search(r'"ratingValue"\s*:\s*"?([\d.,]+)', text)
            if found:
                value = found.group(1)
                found = re.search(r'"(?:ratingCount|reviewCount)"\s*:\s*"?(\d+)', text)
                count = found.group(1) if found else None
                break
    if not value:
        return None
    try:
        number = float(str(value).replace(",", "."))
    except ValueError:
        return None
    if number <= 0:
        return None
    rating = f"{number:.1f}".replace(".", ",")
    return f"{rating} ({count}×)" if count and count != "0" else rating


def parse_detail(html: str) -> dict:
    """Parse a recipe detail page."""
    details = {
        "image_url": None,
        "description": None,
        "prep_time": None,
        "servings": None,
        "rating": None,
        "difficulty": None,
    }
    soup = BeautifulSoup(html, "html.parser")

    def meta(*keys: str) -> str | None:
        for key in keys:
            tag = soup.find("meta", attrs={"property": key}) or soup.find(
                "meta", attrs={"name": key}
            )
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    # The image of the recipe itself - this is the authoritative source,
    # so the photo always matches the recipe.
    details["image_url"] = _normalize_url(meta("og:image", "twitter:image"))
    if not details["image_url"]:
        details["image_url"] = _img_url(soup.find("img", itemprop="image"))

    details["description"] = meta("description", "og:description")
    if not details["description"]:
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if len(text) > 50:
                details["description"] = text[:300]
                break

    page_text = soup.get_text(" ")
    header = _header_nodes(soup, details["image_url"])

    # Prep time is shown in the header under the description and above the
    # photo as its own element (e.g. "140 min"). Only whole elements are
    # accepted, so times mentioned in the description/steps are ignored.
    for text in header:
        match = TIME_RE.fullmatch(text)
        if match:
            details["prep_time"] = _format_duration(match)
            break
    if not details["prep_time"]:
        details["prep_time"] = _schema_duration(soup)

    for text in header:
        match = DIFFICULTY_RE.fullmatch(text)
        if match:
            details["difficulty"] = DIFFICULTY_MAP[match.group(1).lower()]
            break

    # Rating as shown in the header, e.g. "4,7 (409×)" (× or x)
    rating = re.search(
        r"(?<![\d,.])(\d+[,\.]\d+)\s*\(\s*(\d+)\s*[x×]?\s*\)", " ".join(header), re.IGNORECASE
    )
    if rating:
        details["rating"] = f"{rating.group(1).replace('.', ',')} ({rating.group(2)}×)"
    else:
        details["rating"] = _schema_rating(soup)

    servings = re.search(r"(\d+)\s*porc", page_text, re.IGNORECASE)
    if servings:
        details["servings"] = int(servings.group(1))

    return details


# --------------------------------------------------------------------------
# Coordinator
# --------------------------------------------------------------------------


class TopReceptyCoordinator:
    """Manage fetching and caching of Top Recepty data."""

    def __init__(self, hass: HomeAssistant, update_interval: int) -> None:
        """Initialize."""
        self.hass = hass
        self.update_interval = timedelta(hours=update_interval)
        self.recipes: list[dict] = []
        self.last_update: datetime | None = None
        # Daily recipe incl. details, fixed for the whole day
        self.daily: dict | None = None
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.www_dir = Path(hass.config.path("www", "toprecepty"))
        self.image_path = self.www_dir / DAILY_IMAGE_FILENAME

    @property
    def _session(self) -> aiohttp.ClientSession:
        return async_get_clientsession(self.hass)

    async def async_load(self) -> None:
        """Load cached data (no network)."""
        await self.hass.async_add_executor_job(
            lambda: self.www_dir.mkdir(parents=True, exist_ok=True)
        )
        try:
            data = await self._store.async_load()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error loading cached recipes: %s", err)
            data = None
        if not data:
            return
        self.recipes = data.get("recipes", [])
        self.daily = data.get("daily")
        if data.get("last_update"):
            try:
                self.last_update = datetime.fromisoformat(data["last_update"])
            except ValueError:
                self.last_update = None
        _LOGGER.debug("Loaded %s recipes from cache", len(self.recipes))

    @callback
    def _async_schedule_save(self) -> None:
        """Save data (debounced, written in executor by Store)."""
        self._store.async_delay_save(
            lambda: {
                "recipes": self.recipes,
                "daily": self.daily,
                "last_update": self.last_update.isoformat() if self.last_update else None,
            },
            5,
        )

    async def _async_get_text(self, url: str) -> str | None:
        try:
            async with self._session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status != 200:
                    _LOGGER.warning("Failed to fetch %s: HTTP %s", url, response.status)
                    return None
                return await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Error fetching %s: %s", url, err)
            return None

    def _list_is_stale(self) -> bool:
        return (
            not self.recipes
            or self.last_update is None
            or dt_util.utcnow() - _as_utc(self.last_update) > self.update_interval
        )

    async def async_refresh_list(self, force: bool = False) -> None:
        """Refresh the recipe list from the web if it is stale."""
        if not force and not self._list_is_stale():
            return
        html = await self._async_get_text(ALL_RECIPES_URL)
        if not html:
            return
        recipes = await self.hass.async_add_executor_job(parse_listing, html)
        if not recipes:
            _LOGGER.warning("No recipes found on %s, keeping cached list", ALL_RECIPES_URL)
            return
        self.recipes = recipes
        self.last_update = dt_util.utcnow()
        self._async_schedule_save()
        _LOGGER.debug("Fetched %s recipes", len(recipes))

    def _pick_recipe(self, day: date) -> dict | None:
        if not self.recipes:
            return None
        # Local Random instance - does not touch the global random state
        rng = random.Random(int(day.strftime("%Y%m%d")))
        candidates = self.recipes
        if self.daily and len(candidates) > 1:
            candidates = [r for r in candidates if r.get("url") != self.daily.get("url")]
        return rng.choice(candidates)

    async def async_ensure_daily(self) -> bool:
        """Make sure today's recipe is selected and complete.

        Returns True if the daily recipe changed.
        """
        today = dt_util.now().date()
        if (
            self.daily
            and self.daily.get("date") == today.isoformat()
            and self.daily.get("details_fetched") == DETAIL_PARSER_VERSION
            and await self._async_image_ok()
        ):
            return False

        if not self.daily or self.daily.get("date") != today.isoformat():
            await self.async_refresh_list()
            recipe = self._pick_recipe(today)
            if recipe is None:
                return False
            self.daily = {**recipe, "date": today.isoformat(), "details_fetched": False}

        daily = self.daily

        if daily.get("details_fetched") != DETAIL_PARSER_VERSION:
            html = await self._async_get_text(daily["url"])
            if html:
                details = await self.hass.async_add_executor_job(parse_detail, html)
                for key in ("prep_time", "servings", "rating", "difficulty"):
                    daily[key] = details.get(key)
                if details.get("description"):
                    daily["description"] = details["description"]
                # Image from the recipe page itself always matches the recipe
                if details.get("image_url"):
                    daily["image_url"] = details["image_url"]
                daily["details_fetched"] = DETAIL_PARSER_VERSION

        daily["local_image"] = await self._async_download_image(
            daily.get("image_url"), daily["id"]
        )

        self._async_schedule_save()
        return True

    async def _async_image_ok(self) -> bool:
        """Check the cached image belongs to the current daily recipe."""
        if not self.daily:
            return False
        if not self.daily.get("image_url"):
            return True
        if not self.daily.get("local_image"):
            return False
        return await self.hass.async_add_executor_job(self.image_path.exists)

    async def _async_download_image(self, image_url: str | None, recipe_id: int) -> str | None:
        """Download image of the daily recipe, return its /local/ URL."""
        if not image_url:
            await self.hass.async_add_executor_job(
                lambda: self.image_path.unlink(missing_ok=True)
            )
            return None
        try:
            async with self._session.get(image_url, timeout=IMAGE_TIMEOUT) as response:
                if response.status != 200:
                    _LOGGER.warning("Image download failed (%s): HTTP %s", image_url, response.status)
                    return None
                if not response.headers.get("Content-Type", "image/").startswith("image/"):
                    _LOGGER.warning("Image URL %s did not return an image", image_url)
                    return None
                if (response.content_length or 0) > MAX_IMAGE_SIZE:
                    _LOGGER.warning("Image %s is too large, skipping", image_url)
                    return None
                content = await response.read()
                if len(content) > MAX_IMAGE_SIZE:
                    _LOGGER.warning("Image %s is too large, skipping", image_url)
                    return None
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Error downloading image %s: %s", image_url, err)
            return None

        await self.hass.async_add_executor_job(self.image_path.write_bytes, content)
        # Version query parameter prevents the browser from showing
        # yesterday's cached photo with today's recipe.
        return f"/local/toprecepty/{DAILY_IMAGE_FILENAME}?v={recipe_id}"


def _as_utc(value: datetime) -> datetime:
    """Return datetime as aware UTC (old caches stored naive local time)."""
    if value.tzinfo is None:
        return dt_util.as_utc(value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))
    return dt_util.as_utc(value)


# --------------------------------------------------------------------------
# Sensor
# --------------------------------------------------------------------------


class DailyRecipeSensor(SensorEntity):
    """Representation of a Daily Recipe Sensor."""

    # No polling - updated once a day (just after midnight) and on startup
    _attr_should_poll = False
    _attr_name = SENSOR_NAME
    _attr_unique_id = f"{DOMAIN}_daily_recipe"
    _attr_icon = SENSOR_ICON

    def __init__(self, coordinator: TopReceptyCoordinator) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._update_from_daily()

    async def async_added_to_hass(self) -> None:
        """Schedule updates."""
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_midnight, hour=0, minute=1, second=0
            )
        )
        # Fetch in the background so startup is not delayed
        self.hass.async_create_task(self._async_refresh())

    async def _async_midnight(self, _now) -> None:
        await self._async_refresh()

    async def _async_refresh(self) -> None:
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the sensor (also called by homeassistant.update_entity)."""
        try:
            await self._coordinator.async_ensure_daily()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error updating daily recipe")
        self._update_from_daily()

    def _update_from_daily(self) -> None:
        recipe = self._coordinator.daily
        if not recipe:
            self._attr_native_value = "Žádný recept"
            self._attr_extra_state_attributes = {}
            return

        last_update = self._coordinator.last_update
        self._attr_native_value = recipe.get("title")
        self._attr_extra_state_attributes = {
            "recipe_id": recipe.get("id"),
            "title": recipe.get("title"),
            "url": recipe.get("url"),
            "image_url": recipe.get("image_url"),
            "local_image": recipe.get("local_image"),
            "description": recipe.get("description"),
            "prep_time": recipe.get("prep_time"),
            "servings": recipe.get("servings"),
            "rating": recipe.get("rating"),
            "difficulty": recipe.get("difficulty"),
            "last_update": last_update.isoformat() if last_update else None,
        }
