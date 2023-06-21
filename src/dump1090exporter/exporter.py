"""
This script collects data from a dump1090 service and exposes them to the
Prometheus.io monitoring server for aggregation and later visualisation.
"""

import asyncio
import datetime
import json
import logging
import math
from math import asin, atan, cos, degrees, radians, sin, sqrt
from typing import Any, Dict, NamedTuple, Optional, Sequence, Tuple

import aiohttp
from aioprometheus import Gauge
from aioprometheus.service import Service

from .metrics import Specs

PositionType = Tuple[float, float]
MetricSpecItemType = Tuple[str, str, str]
MetricsSpecGroupType = Sequence[MetricSpecItemType]

logger = logging.getLogger(__name__)


AircraftKeys = (
    "altitude",
    "category",
    "flight",
    "hex",
    "lat",
    "lon",
    "messages",
    "mlat",
    "nucp",
    "rssi",
    "seen",
    "seen_pos",
    "speed",
    "squalk",
    "tisb",
    "track",
    "vert_rate",
    "rel_angle",
    "rel_direction",
)


class Dump1090Resources(NamedTuple):  # pylint: disable=missing-class-docstring
    base: str
    receiver: str
    stats: str
    aircraft: str


class Position(NamedTuple):  # pylint: disable=missing-class-docstring
    latitude: float
    longitude: float


def build_resources(base: str) -> Dump1090Resources:
    """Return a named tuple containing dump1090 resource paths"""
    resources = Dump1090Resources(
        base=base,
        receiver=f"{base}/receiver.json",
        stats=f"{base}/stats.json",
        aircraft=f"{base}/aircraft.json",
    )
    return resources


def relative_angle(pos1: Position, pos2: Position) -> float:
    """
    Calculate the direction pos2 relative to pos1. Returns angle in degrees

    :param pos1: a Position tuple defining (lat, lon) of origin in decimal degrees
    :param pos2: a Position tuple defining (lat, lon) of target in decimal degrees

    :returns: angle in degrees
    :rtype: float
    """
    lat1, lon1, lat2, lon2 = [
        x for x in (*pos1, *pos2)  # pylint: disable=unnecessary-comprehension
    ]

    # Special case - same lat as origin: 90 degrees or 270 degrees
    #
    #    |
    # -x-o-x-
    #    |

    if lat2 == lat1:
        if lon2 > lon1:
            return 90
        else:
            return 270

    deg = degrees(atan((lon2 - lon1) / (lat2 - lat1)))

    # Sign of results from the calculation above
    #
    #  - | +  (lat2>lat1)
    # ---o---
    #  + | -  (lat2<lat1)
    #
    # conversion needed to express in terms of 360 degrees

    if lat2 > lat1:
        return (360 + deg) % 360
    else:
        return 180 + deg


# lookup table for directions - each step is 22.5 degrees
direction_lut = (
    "N",
    "NE",
    "NE",
    "E",
    "E",
    "SE",
    "SE",
    "S",
    "S",
    "SW",
    "SW",
    "W",
    "W",
    "NW",
    "NW",
    "N",
)


def relative_direction(angle: float) -> str:
    """
    Convert relative angle in degrees into direction (N/NE/E/SE/S/SW/W/NW)
    """
    return direction_lut[int(angle / 22.5)]


def haversine_distance(
    pos1: Position, pos2: Position, radius: float = 6371.0e3
) -> float:
    """
    Calculate the distance between two points on a sphere (e.g. Earth).
    If no radius is provided then the default Earth radius, in meters, is
    used.

    The haversine formula provides great-circle distances between two points
    on a sphere from their latitudes and longitudes using the law of
    haversines, relating the sides and angles of spherical triangles.

    `Reference <https://en.wikipedia.org/wiki/Haversine_formula>`_

    :param pos1: a Position tuple defining (lat, lon) in decimal degrees
    :param pos2: a Position tuple defining (lat, lon) in decimal degrees
    :param radius: radius of sphere in meters.

    :returns: distance between two points in meters.
    :rtype: float
    """
    lat1, lon1, lat2, lon2 = [radians(x) for x in (*pos1, *pos2)]

    hav = (
        sin((lat2 - lat1) / 2.0) ** 2
        + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2.0) ** 2
    )
    distance = 2 * radius * asin(sqrt(hav))
    return distance


def create_gauge_metric(label: str, doc: str, prefix: str = "") -> Gauge:
    """Create a Gauge metric

    :param label: A label for the metric.

    :param doc: A help string for the metric.

    :param prefix: An optional prefix for the metric label that applies a
        common start string to the metric which simplifies locating the
        metrics in Prometheus because they will all be grouped together when
        searching.
    """
    gauge = Gauge(f"{prefix}{label}", doc)
    return gauge


class Dump1090Exporter:
    """
    This class is responsible for fetching, parsing and exporting dump1090
    metrics to Prometheus.
    """

    def __init__(
        self,
        resource_path: str,
        host: str = "",
        port: int = 9105,
        aircraft_interval: int = 10,
        stats_interval: int = 60,
        receiver_interval: int = 10,
        receiver_interval_origin_ok: int = 300,
        time_periods: Sequence[str] = ("last1min",),
        origin: PositionType = None,
        fetch_timeout: float = 2.0,
    ) -> None:
        """
        :param resource_path: The base dump1090 resource address. This can be
          a web address or a directory path.
        :param host: The host to expose Prometheus metrics on. Defaults
          to listen on all interfaces.
        :param port: The port to expose Prometheus metrics on. Defaults to
          port 9105.
        :param receiver_interval: number of seconds between probing the
          dump1090 receiver config if an origin is not yet set. Defaults to
          10 seconds.
        :param receiver_interval_origin_ok: number of seconds between probing
          dump1090 receiver config if an origin is already set. Defaults to
          300 seconds.
        :param aircraft_interval: number of seconds between processing the
          dump1090 aircraft data. Defaults to 10 seconds.
        :param stats_interval: number of seconds between processing the
          dump1090 stats data. Defaults to 60 seconds as the data only
          seems to be updated at 60 second intervals.
        :param time_periods: A list of time period keys to extract from the
          statistics data. By default this is just the 'last1min' time
          period as Prometheus can provide the historical access.
        :param origin: a tuple of (lat, lon) representing the receiver
          location. The origin is used for distance calculations with
          aircraft data. If it is not provided then range calculations
          can not be performed and the maximum range metric will always
          be zero.
        :param fetch_timeout: The number of seconds to wait for a response
          from dump1090.
        """
        self.resources = build_resources(resource_path)
        self.loop = asyncio.get_event_loop()
        self.host = host
        self.port = port
        self.prefix = "dump1090_"
        self.receiver_interval = datetime.timedelta(seconds=receiver_interval)
        self.receiver_interval_origin_ok = datetime.timedelta(
            seconds=receiver_interval_origin_ok
        )
        self.aircraft_interval = datetime.timedelta(seconds=aircraft_interval)
        self.stats_interval = datetime.timedelta(seconds=stats_interval)
        self.stats_time_periods = time_periods
        self.origin = Position(*origin) if origin else None
        self.fetch_timeout = fetch_timeout
        self.svr = Service()
        self.receiver_task = None  # type: Optional[asyncio.Task]
        self.stats_task = None  # type: Optional[asyncio.Task]
        self.aircraft_task = None  # type: Optional[asyncio.Task]
        self.initialise_metrics()
        logger.info(f"Monitoring dump1090 resources at: {self.resources.base}")
        logger.info(
            f"Refresh rates: aircraft={self.aircraft_interval}, statstics={self.stats_interval}"
        )
        logger.info(f"Origin: {self.origin}")

    async def start(self) -> None:
        """Start the monitor"""
        await self.svr.start(addr=self.host, port=self.port)
        logger.info(f"serving dump1090 prometheus metrics on: {self.svr.metrics_url}")

        # fmt: off
        self.receiver_task = asyncio.ensure_future(self.updater_receiver())  # type: ignore
        self.stats_task = asyncio.ensure_future(self.updater_stats())  # type: ignore
        self.aircraft_task = asyncio.ensure_future(self.updater_aircraft())  # type: ignore
        # fmt: on

    async def stop(self) -> None:
        """Stop the monitor"""

        if self.receiver_task:
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass
            self.receiver_task = None

        if self.stats_task:
            self.stats_task.cancel()
            try:
                await self.stats_task
            except asyncio.CancelledError:
                pass
            self.stats_task = None

        if self.aircraft_task:
            self.aircraft_task.cancel()
            try:
                await self.aircraft_task
            except asyncio.CancelledError:
                pass
            self.aircraft_task = None

        await self.svr.stop()

    def initialise_metrics(self) -> None:
        """Create metrics

        This method initialises a dict as the metrics attribute.

        The metrics dict has two str keys; one is `aircraft` and the other
        is `stats`.
        The `aircraft` key stores aircraft summary metrics using a value
        of Dict[str, Gauge].

        The `stats` key stores metrics under group keys. It has a value
        of Dict[str, Dict[str, Gauge]]
        """
        self.metrics = {"aircraft": {}, "stats": {}}  # type: ignore

        # aircraft
        d = self.metrics["aircraft"]
        for (name, label, doc) in Specs["aircraft"]:  # type: ignore
            d[name] = create_gauge_metric(label, doc, prefix=self.prefix)

        # statistics
        for group, metrics_specs in Specs["stats"].items():  # type: ignore
            d = self.metrics["stats"].setdefault(group, {})
            for name, label, doc in metrics_specs:
                d[name] = create_gauge_metric(label, doc, prefix=self.prefix)

    async def _fetch(
        self,
        resource: str,
    ) -> Dict[Any, Any]:
        """Fetch JSON data from a web or file resource and return a dict"""
        logger.debug(f"fetching {resource}")
        if resource.startswith("http"):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        resource, timeout=self.fetch_timeout
                    ) as resp:
                        if not resp.status == 200:
                            raise Exception(f"Fetch failed {resp.status}: {resource}")
                        data = await resp.json(content_type=None)
            except asyncio.TimeoutError:
                raise Exception(f"Request timed out to {resource}") from None
            except aiohttp.ClientError as exc:
                raise Exception(f"Client error {exc}, {resource}") from None
        else:
            with open(resource, "rt") as fd:  # pylint: disable=unspecified-encoding
                data = json.loads(fd.read())

        return data

    async def updater_receiver(self) -> None:
        """
        This long running coroutine task is responsible for fetching current
        dump1090 receiver configuration such as the lat/lon and updating
        internal config
        """
        while True:
            start = datetime.datetime.now()
            try:
                receiver = await self._fetch(self.resources.receiver)
                if receiver:
                    if "lat" in receiver and "lon" in receiver:
                        self.origin = Position(receiver["lat"], receiver["lon"])
                        logger.info(
                            f"Origin successfully extracted from receiver data: {self.origin}"
                        )
            except Exception as exc:  # pylint: disable=broad-except
                logger.error(f"Error fetching dump1090 receiver data: {exc}")

            # wait until next collection time
            end = datetime.datetime.now()
            if self.origin:
                wait_seconds = (
                    start + self.receiver_interval_origin_ok - end
                ).total_seconds()
            else:
                wait_seconds = (start + self.receiver_interval - end).total_seconds()
            await asyncio.sleep(wait_seconds)

    async def updater_stats(self) -> None:
        """
        This long running coroutine task is responsible for fetching current
        statistics from dump1090 and then updating internal metrics.
        """
        while True:
            start = datetime.datetime.now()
            try:
                stats = await self._fetch(self.resources.stats)
                self.process_stats(stats, time_periods=self.stats_time_periods)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error(f"Error fetching dump1090 stats data: {exc}")

            # wait until next collection time
            end = datetime.datetime.now()
            wait_seconds = (start + self.stats_interval - end).total_seconds()
            await asyncio.sleep(wait_seconds)

    async def updater_aircraft(self) -> None:
        """
        This long running coroutine task is responsible for fetching current
        statistics from dump1090 and then updating internal metrics.
        """
        while True:
            start = datetime.datetime.now()
            try:
                aircraft = await self._fetch(self.resources.aircraft)
                self.process_aircraft(aircraft)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error(f"Error fetching dump1090 aircraft data: {exc}")

            # wait until next collection time
            end = datetime.datetime.now()
            wait_seconds = (start + self.aircraft_interval - end).total_seconds()
            await asyncio.sleep(wait_seconds)

    def process_stats(
        self, stats: dict, time_periods: Sequence[str] = ("last1min",)
    ) -> None:
        """Process dump1090 statistics into exported metrics.

        :param stats: a dict containing dump1090 statistics data.
        """
        metrics = self.metrics["stats"]  # type: Dict[str, Dict[str, Gauge]]

        for time_period in time_periods:
            try:
                tp_stats = stats[time_period]
            except KeyError:
                logger.exception(f"Problem extracting time period: {time_period}")
                continue

            labels = dict(time_period=time_period)

            for key, gauge in metrics.items():
                d = tp_stats[key] if key else tp_stats
                for name, metric in gauge.items():
                    try:
                        value = d[name]
                        # 'accepted' values are in a list
                        if isinstance(value, list):
                            value = value[0]
                    except KeyError:
                        # 'signal' and 'peak_signal' are not present if
                        # there are no aircraft.
                        if name not in ["peak_signal", "signal"]:
                            key_str = f" {key} " if key else " "
                            logger.warning(
                                f"Problem extracting{key_str}item '{name}' from: {d}"
                            )
                        value = math.nan
                    metric.set(labels, value)

    def process_aircraft(self, aircraft: dict, threshold: int = 15) -> None:
        """Process aircraft statistics into exported metrics.

        :param aircraft: a dict containing aircraft data.
        :param threshold: only let aircraft seen within this threshold to
          contribute to the metrics.
        """
        # Ensure aircraft dict always contains all keys, as optional
        # items are not always present.
        for entry in aircraft["aircraft"]:
            for key in AircraftKeys:
                entry.setdefault(key, None)

        messages = aircraft["messages"]

        # 'seen' shows how long ago (in seconds before "now") a message
        # was last received from an aircraft.
        # 'seen_pos' shows how long ago (in seconds before "now") the
        # position was last updated
        aircraft_observed = 0
        aircraft_with_pos = 0
        aircraft_with_mlat = 0
        aircraft_max_range = 0.0
        aircraft_direction = {
            "N": 0,
            "NE": 0,
            "E": 0,
            "SE": 0,
            "S": 0,
            "SW": 0,
            "W": 0,
            "NW": 0,
        }
        aircraft_direction_max_range = {
            "N": 0.0,
            "NE": 0.0,
            "E": 0.0,
            "SE": 0.0,
            "S": 0.0,
            "SW": 0.0,
            "W": 0.0,
            "NW": 0.0,
        }
        # Filter aircraft to only those that have been seen within the
        # last n seconds to minimise contributions from aged observations.
        for a in aircraft["aircraft"]:
            if a["seen"] < threshold:
                aircraft_observed += 1
            if a["seen_pos"] and a["seen_pos"] < threshold:
                aircraft_with_pos += 1
                if self.origin:
                    distance = haversine_distance(
                        self.origin, Position(a["lat"], a["lon"])
                    )
                    if distance > aircraft_max_range:
                        aircraft_max_range = distance

                    a["rel_angle"] = relative_angle(
                        self.origin, Position(a["lat"], a["lon"])
                    )
                    a["rel_direction"] = relative_direction(a["rel_angle"])
                    aircraft_direction[a["rel_direction"]] += 1
                    if distance > aircraft_direction_max_range[a["rel_direction"]]:
                        aircraft_direction_max_range[a["rel_direction"]] = distance

                if a["mlat"] and "lat" in a["mlat"]:
                    aircraft_with_mlat += 1

        # Add any current data into the 'latest' time_period bucket
        labels = dict(time_period="latest")
        d = self.metrics["aircraft"]
        d["observed"].set(labels, aircraft_observed)
        d["observed_with_pos"].set(labels, aircraft_with_pos)
        d["observed_with_mlat"].set(labels, aircraft_with_mlat)
        d["max_range"].set(labels, aircraft_max_range)
        d["messages_total"].set(labels, messages)

        for direction, value in aircraft_direction.items():
            labels = dict(time_period="latest", direction=direction)
            d["observed_with_direction"].set(labels, value)
            d["max_range_by_direction"].set(
                labels, aircraft_direction_max_range[direction]
            )

        logger.debug(
            f"aircraft: observed={aircraft_observed}, "
            f"with_pos={aircraft_with_pos}, with_mlat={aircraft_with_mlat}, "
            f"max_range={aircraft_max_range}, messages={messages}"
        )
