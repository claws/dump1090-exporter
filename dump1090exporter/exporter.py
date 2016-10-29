'''
This script collects data from a dump1090 service and exposes them to the
Prometheus.io monitoring server for aggregation and later visualisation.
'''

import asyncio
import collections
import datetime
import logging

import aiohttp
import aiohttp.errors

from math import asin, cos, radians, sin, sqrt
from aioprometheus import Service, Gauge

from . import metrics

# type annotations
from typing import Any, Awaitable, Dict, Sequence, Tuple
from asyncio.events import AbstractEventLoop

PositionType = Tuple[float, float]


logger = logging.getLogger(__name__)


AircraftKeys = (
    'altitude', 'category', 'flight', 'hex', 'lat', 'lon', 'messages', 'mlat',
    'nucp', 'rssi', 'seen', 'seen_pos', 'speed', 'squalk', 'tisb', 'track',
    'vert_rate')

Dump1090Resources = collections.namedtuple(
    'Dump1090Resources', ['base', 'receiver', 'stats', 'aircraft'])

Position = collections.namedtuple(
    'Position', ['latitude', 'longitude'])


def build_resources(base_url: str) -> Dump1090Resources:
    ''' Return a named tuple containing monitored dump1090 URLs '''
    resources = Dump1090Resources(
        base_url,
        '{}/data/receiver.json'.format(base_url),
        '{}/data/stats.json'.format(base_url),
        '{}/data/aircraft.json'.format(base_url))
    return resources


async def fetch(url: str,
                loop: AbstractEventLoop = None) -> Dict[Any, Any]:
    ''' Fetch JSON format data from a web resource and return a dict '''
    loop = loop or asyncio.get_event_loop()
    try:
        with aiohttp.ClientSession(loop=loop) as session:
            logger.debug('fetching %s', url)
            async with session.get(url) as resp:
                if not resp.status == 200:
                    raise Exception('Error fetching {}'.format(url))
                data = await resp.json()
                return data
    except (aiohttp.errors.ClientError, aiohttp.errors.DisconnectedError):
        raise Exception('Error fetching {}'.format(url)) from None


def haversine_distance(pos1: Position,
                       pos2: Position,
                       radius: float = 6371.0e3) -> float:
    '''
    Calculate the distance between two points on a sphere (e.g. Earth).
    If no radius is provided then the default Earth radius, in meters, is
    used.

    The haversine formula provides great-circle distances between two points
    on a sphere from their latitudes and longitudes using a the law of
    haversines, relating the sides and angles of spherical triangles.

    `Reference <https://en.wikipedia.org/wiki/Haversine_formula>`_

    :param pos1: a Position tuple defining (lat, lon) in decimal degrees
    :param pos2: a Position tuple defining (lat, lon) in decimal degrees
    :param radius: radius of sphere in meters.

    :returns: distance between two points in meters.
    :rtype: float
    '''
    lat1, lon1, lat2, lon2 = [radians(x) for x in (*pos1, *pos2)]

    hav = sin((lat2 - lat1) / 2.0)**2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2.0)**2
    distance = 2 * radius * asin(sqrt(hav))
    return distance


class Dump1090Exporter(object):
    '''
    This class is responsible for fetching, parsing and exporting dump1090
    metrics to Prometheus.
    '''

    def __init__(self,
                 url: str,
                 host: str = None,
                 port: int = 9105,
                 aircraft_interval: int = 10,
                 stats_interval: int = 60,
                 time_periods: Sequence[str] = ('last1min', ),
                 origin: PositionType = None,
                 fetch_timeout: float = 2.0,
                 loop: AbstractEventLoop = None) -> None:
        '''
        :param url: The base dump1090 web address.
        :param host: The host to expose Prometheus metrics on. Defaults
          to listen on all interfaces.
        :param port: The port to expose Prometheus metrics on. Defaults to
          port 9105.
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
        :param loop: the event loop.
        '''
        self.dump1090urls = build_resources(url)
        self.loop = loop or asyncio.get_event_loop()
        self.host = host
        self.port = port
        self.aircraft_interval = datetime.timedelta(seconds=aircraft_interval)
        self.stats_interval = datetime.timedelta(seconds=stats_interval)
        self.stats_time_periods = time_periods
        self.origin = Position(*origin) if origin else None
        self.fetch_timeout = fetch_timeout
        self.svr = Service(loop=loop)
        self.stats_task = None  # type: asyncio.Task
        self.aircraft_task = None  # type: asyncio.Task
        self.initialise_metrics()
        logger.info('Monitoring dump1090 at url: %s', self.dump1090urls.base)
        logger.info('Refresh rates: aircraft=%s, statstics=%s',
                    self.aircraft_interval, self.stats_interval)
        logger.info('Origin: %s', self.origin)

    async def start(self) -> None:
        ''' Start the monitor '''
        await self.svr.start(addr=self.host, port=self.port)
        logger.info(
            'serving dump1090 prometheus metrics on: %s', self.svr.url)

        # Attempt to retrieve the optional lat and lon position from
        # the dump1090 receiver data. If present this data will override
        # command line configuration.
        try:
            receiver = await asyncio.wait_for(
                fetch(self.dump1090urls.receiver), self.fetch_timeout)
            if receiver:
                if 'lat' in receiver and 'lon' in receiver:
                    self.origin = Position(receiver['lat'], receiver['lon'])
                    logger.info(
                        'Origin successfully extracted from receiver data: %s',
                        self.origin)
        except asyncio.TimeoutError:
            logger.error(
                'request for dump1090 receiver data timed out')

        self.stats_task = asyncio.ensure_future(self.updater_stats())
        self.aircraft_task = asyncio.ensure_future(self.updater_aircraft())

    async def stop(self) -> None:
        ''' Stop the monitor '''
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
        ''' Create metrics '''
        self.metrics = {'aircraft': {}, 'stats': {}}

        # aircraft
        d = self.metrics['aircraft']
        for name, label, doc in metrics.Specs['aircraft']:
            d[name] = self._create_gauge_metric(label, doc)

        # statistics
        for group, metrics_specs in metrics.Specs['stats'].items():
            d = self.metrics['stats'].setdefault(group, {})
            for name, label, doc in metrics_specs:
                d[name] = self._create_gauge_metric(label, doc)

    def _create_gauge_metric(self, label, doc):
        gauge = Gauge('dump1090_{}'.format(label), doc)
        self.svr.registry.register(gauge)
        return gauge

    async def updater_stats(self) -> None:
        '''
        This long running coroutine task is responsible for fetching current
        statistics from dump1090 and then updating internal metrics.
        '''
        while True:
            start = datetime.datetime.now()
            try:
                stats = await asyncio.wait_for(
                    fetch(self.dump1090urls.stats), self.fetch_timeout)
                self.process_stats(
                    stats, time_periods=self.stats_time_periods)
            except asyncio.TimeoutError:
                logger.error(
                    'request for dump1090 stats data timed out')
            except Exception:
                logger.exception(
                    'error requesting dump1090 stats data')

            # wait until next collection time
            end = datetime.datetime.now()
            wait_seconds = (start + self.stats_interval - end).total_seconds()
            await asyncio.sleep(wait_seconds)

    async def updater_aircraft(self) -> None:
        '''
        This long running coroutine task is responsible for fetching current
        statistics from dump1090 and then updating internal metrics.
        '''
        while True:
            start = datetime.datetime.now()
            try:
                aircraft = await asyncio.wait_for(
                    fetch(self.dump1090urls.aircraft), self.fetch_timeout)
                self.process_aircraft(aircraft)
            except asyncio.TimeoutError:
                logger.error(
                    'request for dump1090 aircraft data timed out')
            except Exception:
                logger.exception(
                    'error requesting dump1090 aircraft data')

            # wait until next collection time
            end = datetime.datetime.now()
            wait_seconds = (start + self.aircraft_interval - end).total_seconds()
            await asyncio.sleep(wait_seconds)

    def process_stats(self,
                      stats: dict,
                      time_periods: Sequence[str] = ('last1min', )) -> None:
        ''' Process dump1090 statistics into exported metrics.

        :param stats: a dict containing dump1090 statistics data.
        '''
        metrics = self.metrics['stats']

        for time_period in time_periods:
            try:
                tp_stats = stats[time_period]
            except KeyError:
                logger.exception(
                    'Problem extracting time period: {}'.format(time_period))
                continue

            labels = dict(time_period=time_period)

            for key in metrics:
                d = tp_stats[key] if key else tp_stats
                for name, metric in metrics[key].items():
                    try:
                        value = d[name]
                        # 'accepted' values are in a list
                        if isinstance(value, list):
                            value = value[0]
                    except KeyError:
                        logger.warning(
                            "Problem extracting{}item '{}' from: {}".format(
                                '{}'.format(key) if key else ' ', name, d))
                        value = None
                    metric.set(labels, value)

    def process_aircraft(self,
                         aircraft: dict,
                         threshold: int = 15) -> None:
        ''' Process aircraft statistics into exported metrics.

        :param aircraft: a dict containing aircraft data.
        :param threshold: only let aircraft seen within this threshold to
          contribute to the metrics.
        '''
        # Ensure aircraft dict always contains all keys, as optional
        # items are not always present.
        for entry in aircraft['aircraft']:
            for key in AircraftKeys:
                entry.setdefault(key, None)

        messages = aircraft['messages']

        # 'seen' shows how long ago (in seconds before "now") a message
        # was last received from an aircraft.
        # 'seen_pos' shows how long ago (in seconds before "now") the
        # position was last updated
        aircraft_observed = 0
        aircraft_with_pos = 0
        aircraft_with_mlat = 0
        aircraft_max_range = 0.0
        # Filter aircraft to only those that have been seen within the
        # last n seconds to minimise contributions from aged obsevations.
        for a in aircraft['aircraft']:
            if a['seen'] < threshold:
                aircraft_observed += 1
            if a['seen_pos'] and a['seen_pos'] < threshold:
                aircraft_with_pos += 1
                if self.origin:
                    distance = haversine_distance(
                        self.origin, Position(a['lat'], a['lon']))
                    if distance > aircraft_max_range:
                        aircraft_max_range = distance
                if a['mlat'] and 'lat' in a['mlat']:
                    aircraft_with_mlat += 1

        # Add any current data into the 'latest' time_period bucket
        labels = dict(time_period='latest')
        d = self.metrics['aircraft']
        d['observed'].set(labels, aircraft_observed)
        d['observed_with_pos'].set(labels, aircraft_with_pos)
        d['observed_with_mlat'].set(labels, aircraft_with_mlat)
        d['max_range'].set(labels, aircraft_max_range)
        d['messages_total'].set(labels, messages)

        logger.debug(
            "aircraft: observed=%i, with_pos=%i, with_mlat=%i, max_range=%i, "
            "messages=%i",
            aircraft_observed, aircraft_with_pos, aircraft_with_mlat,
            aircraft_max_range, messages)
