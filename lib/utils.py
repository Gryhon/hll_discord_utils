import aiohttp
import json
import logging
import jmespath
import jsonpath_ng.ext as jpath
from lib.config import config
from datetime import datetime, time

# get Logger for this modul
logger = logging.getLogger(__name__)

async def get_Data_from_Url(url, token, payload=None):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=payload) as response:
                # Check whether the request was successful
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error: {response.status}")
                    logger.info(f"Details: {await response.text()}")
                    return None
                
    except aiohttp.ClientConnectionError as error:
        logger.error(f"Connection error: {error}")
        return None
    
async def post_data_to_Url(url, token, payload):
    headers = {
        'Authorization': f'Bearer {token}',
        "Connection": "keep-alive",
        'Content-Type': 'application/json'
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=json.dumps(payload), headers=headers) as response:
                # Check whether the request was successful
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error: {response.status}")
                    logger.info(f"Details: {await response.text()}")
                    return None
                
    except aiohttp.ClientConnectionError as error:
        logger.error(f"Connection error: {error}")
        return None

async def get_Data (api_url, payload=None):
     # Read URL and token from environment variables
    base_url = config.get("rcon", 0, "api_url")
    bearer_token = config.get("rcon", 0, "bearer_token")

    if not base_url:
        logger.error("API_URL environment variable is not set")
        return {'error': 'API_URL not set'}
    
    if not bearer_token:
        logger.error("BEARER_TOKEN environment variable is not set")
        return {'error': 'BEARER_TOKEN not set'}

    # Retrieve API data
    full_url = base_url + api_url
    data = await get_Data_from_Url(full_url, bearer_token, payload)

    return data

async def post_Data(api_url, payload):
    # Read URL and token from environment variables
    base_url = config.get("rcon", 0, "api_url")
    bearer_token = config.get("rcon", 0, "bearer_token")

    if not base_url:
        logger.error("API_URL environment variable is not set")
        return {'error': 'API_URL not set'}
    
    if not bearer_token:
        logger.error("BEARER_TOKEN environment variable is not set")
        return {'error': 'BEARER_TOKEN not set'}

    # Create full URL for the API endpoint
    full_url = base_url + api_url

    # Sending the data
    response = await post_data_to_Url(full_url, bearer_token, payload)

    return response

class ScheduleManager():

    VALID_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    DAY_INDEX = {d: i for i, d in enumerate(VALID_DAYS)}

    def __init__(self, schedule: list[dict]):
        self.schedule = schedule

    @staticmethod
    def _parse_time(s: str) -> time | None:
        try:
            return datetime.strptime(s, "%H:%M").time()
        except Exception:
            return None

    def _normalize(self):
        errors: list[str] = []
        normalized: list[dict] = []

        for idx, entry in enumerate(self.schedule):
            if not isinstance(entry, dict):
                errors.append(f"Entry {idx}: must be an object/dict")
                continue

            days = entry.get("days")
            on_s = entry.get("on")
            off_s = entry.get("off")

            if not isinstance(days, list) or not days:
                errors.append(f"Entry {idx}: 'days' must be a non-empty list")
                continue

            invalid_days = [d for d in days if d not in self.VALID_DAYS]
            if invalid_days:
                errors.append(f"Entry {idx}: invalid day codes {invalid_days}")

            on_t = self._parse_time(on_s)
            off_t = self._parse_time(off_s)

            if on_t is None:
                errors.append(f"Entry {idx}: invalid 'on' time {on_s!r} (expect HH:MM)")
            if off_t is None:
                errors.append(f"Entry {idx}: invalid 'off' time {off_s!r} (expect HH:MM)")
            if on_t and off_t and on_t == off_t:
                errors.append(f"Entry {idx}: 'on' equals 'off' ({on_s})")

            if invalid_days or on_t is None or off_t is None:
                continue

            # Normale Einträge
            normalized.append({**entry, "idx": idx, "days": days, "on": on_t, "off": off_t})

            # split overnight time windows
            if on_t > off_t:
                for d in days:
                    next_day = self.VALID_DAYS[(self.DAY_INDEX[d] + 1) % 7]
                    normalized.append({
                        **entry,
                        "idx": idx,
                        "days": [next_day],
                        "on": datetime.strptime("00:00", "%H:%M").time(),
                        "off": off_t,
                        "overnight": True
                    })

        return normalized, errors

    def validate(self) -> list[str]:
        normalized, errors = self._normalize()

        def to_min(t: time) -> int:
            return t.hour * 60 + t.minute

        def m2s(m: int) -> str:
            return f"{m // 60:02d}:{m % 60:02d}"

        per_day: dict[str, list[tuple[int, int, int]]] = {d: [] for d in self.VALID_DAYS}

        for item in normalized:
            onm, offm = to_min(item["on"]), to_min(item["off"])
            for d in item["days"]:
                per_day[d].append((onm, offm, item["idx"]))

        # check overlaps
        for d, intervals in per_day.items():
            if len(intervals) < 2:
                continue
            intervals.sort(key=lambda x: x[0])
            prev_start, prev_end, prev_idx = intervals[0]
            for start, end, idx_ in intervals[1:]:
                if idx_ == prev_idx:
                    if end > prev_end:
                        prev_start, prev_end, prev_idx = start, end, idx_
                    continue
                if start < prev_end:
                    errors.append(
                        f"Overlap on {d}: entry {prev_idx} [{m2s(prev_start)}–{m2s(prev_end)}] "
                        f"overlaps entry {idx_} [{m2s(start)}–{m2s(end)}]"
                    )
                if end > prev_end:
                    prev_start, prev_end, prev_idx = start, end, idx_

        return errors

    def is_paused(self, now: datetime | None = None) -> bool:
        if now is None:
            now = datetime.now()
        curr_day = self.VALID_DAYS[now.weekday()]
        now_t = now.time()

        normalized, _ = self._normalize()

        for item in normalized:
            if curr_day not in item["days"]:
                continue
            on_t, off_t = item["on"], item["off"]

            if on_t < off_t and on_t <= now_t < off_t:
                return False
            if on_t > off_t and (now_t >= on_t or now_t < off_t):
                return False

        return True

    def get_active_window(self, now: datetime | None = None) -> dict | None:
        if now is None:
            now = datetime.now()
        curr_day = self.VALID_DAYS[now.weekday()]
        now_t = now.time()
        normalized, _ = self._normalize()

        for item in normalized:
            if curr_day not in item["days"]:
                continue
            on_t, off_t = item["on"], item["off"]
            if on_t < off_t and on_t <= now_t < off_t:
                return item
            if on_t > off_t and (now_t >= on_t or now_t < off_t):
                return item
        return None

    def get_value(self, field: str, now: datetime | None = None) -> any:
        active = self.get_active_window(now)
        if active is None:
            return None
        return active.get(field)

    def get_timeline(self, with_bars: bool = False) -> dict[str, list[tuple[str, str, str]]]:
        normalized, _ = self._normalize()

        def to_min(t: time) -> int:
            return t.hour * 60 + t.minute

        def m2s(m: int) -> str:
            return f"{m // 60:02d}:{m % 60:02d}"

        per_day: dict[str, list[tuple[int, int]]] = {d: [] for d in self.VALID_DAYS}

        for item in normalized:
            onm, offm = to_min(item["on"]), to_min(item["off"])
            for d in item["days"]:
                per_day[d].append((onm, offm))

        timeline: dict[str, list[tuple[str, str, str]]] = {}
        for d, intervals in per_day.items():
            intervals.sort(key=lambda x: x[0])
            dayline: list[tuple[str, str, str]] = []

            prev_end = 0
            for start, end in intervals:
                if prev_end < start:
                    dayline.append((m2s(prev_end), m2s(start), "paused"))
                dayline.append((m2s(start), m2s(end), "active"))
                prev_end = max(prev_end, end)
            if prev_end < 1440:
                dayline.append((m2s(prev_end), "24:00", "paused"))

            timeline[d] = dayline

        if with_bars:
            self._print_bars(timeline)

        return timeline

    def _print_bars(self, timeline: dict[str, list[tuple[str, str, str]]], width: int = 48):
        scale = 1440 / width
        print("\nZeitplan (ASCII-Balken):")
        for d in self.VALID_DAYS:
            line = [" "] * width
            for start, end, state in timeline[d]:
                s = int((int(start[:2])*60 + int(start[3:5])) / scale)
                e = int((1440 if end == "24:00" else int(end[:2])*60 + int(end[3:5])) / scale)
                for i in range(s, e):
                    line[i] = "#" if state == "active" else "-"
            print(f"{d:>3}: {''.join(line)}")

    def get_current_window_times(self, now: datetime | None = None) -> tuple[str, str] | None:
        if now is None:
            now = datetime.now()
        curr_day = self.VALID_DAYS[now.weekday()]
        now_t = now.time()

        normalized, _ = self._normalize()

        # collect all slots of the current day
        slots = [item for item in normalized if curr_day in item["days"]]
        slots.sort(key=lambda i: i["on"])  # nach Startzeit sortieren

        for item in slots:
            on_t, off_t = item["on"], item["off"]

            # normale time window
            if on_t < off_t and on_t <= now_t < off_t:
                return on_t.strftime("%H:%M"), off_t.strftime("%H:%M")

            # overnight time windows
            if on_t > off_t and (now_t >= on_t or now_t < off_t):
                return on_t.strftime("%H:%M"), off_t.strftime("%H:%M")

        # if no interval matches → we are 'between' slots = paused
        # Find the next slot and create the pause interval
        for i, item in enumerate(slots):
            prev_off = slots[i - 1]["off"] if i > 0 else time(0, 0)
            on_t = item["on"]
            if prev_off <= now_t < on_t:
                return prev_off.strftime("%H:%M"), on_t.strftime("%H:%M")

        # If after the last slot → paused until midnight
        if slots:
            last_off = slots[-1]["off"]
            if now_t >= last_off:
                return last_off.strftime("%H:%M"), "24:00"

        return None

# uses jsonpath_ng.ext and uses recrusive search
class J_Path ():
    def get_Match (path, json_string, not_match=""):
        try:
            match = jpath.parse (path).find (json_string)

            if match:
                return match[0].value
            else:
                return not_match
        except:
            logger.error ("Exception while parsing path: " + path + "in json: " + json_string)

    def get_Matches (path, json_string):
        pool = []

        try:
            match = jpath.parse (path).find (json_string)

            for m in match:
                pool.append (m.value)

            return pool
        except:
            logger.error ("Exception while parsing path: " + path + "in json: " + json_string)

# uses jmespath and dos not support recrusive search but and and or operations
class Jmes_Path ():
    def get_Match (path, json_string, not_match=""):
        try:
            match = jmespath.search(path, json_string)

            if match:
                return match
            else:
                return not_match
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return not_match

def is_Integer(string: str, natural_number = True) -> bool:
    try:
        number = int(string)

        if natural_number and number > 0:
            return True
        elif not natural_number:
            return True
        else:
            return False
    except ValueError:
        return False

def is_Time(value: str):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid time format: {value!r}, expected format HH:MM")

