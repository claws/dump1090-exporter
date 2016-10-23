'''
This script collects data from a dump1090 service and exposes them to the
Prometheus.io monitoring server for aggregation and later visualisation.
'''

import asyncio
import collections
import datetime
import logging

import aiohttp

from math import asin, cos, radians, sin, sqrt
from aioprometheus import Service, Gauge

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


def build_resources(base_url) -> Dump1090Resources:
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
    with aiohttp.ClientSession(loop=loop) as session:
        logger.debug('fetching %s', url)
        async with session.get(url) as resp:
            if not resp.status == 200:
                raise Exception(
                    'Error fetching {}'.format(url))
            data = await resp.json()
            return data


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

    A Prometheus metrics naming convention used within this class. Each
    metric attribute is prefixed with a character indicating the kind of
    metrics that is referenced. For example, attributes holding a Gauge
    metric reference are prefixed with 'g_'. Similarly, an attribute
    holding a Counter metric reference would use a 'c_'.
    '''

    def __init__(self,
                 url: str,
                 host: str = None,
                 port: int = 9001,
                 aircraft_interval: int = 10,
                 stats_interval: int = 60,
                 time_periods: Sequence[str] = ('last1min',),
                 origin: PositionType = None,
                 loop: AbstractEventLoop = None) -> None:
        '''
        :param url: The base dump1090 web address.
        :param host: The host to expose Prometheus metrics on.
        :param port: The port to expose Prometheus metrics on.
        :param aircraft_interval: number of seconds between processing the
          dump1090 aircraft data.
        :param stats_interval: number of seconds between processing the
          dump1090 stats data.
        :param time_periods: A list of time periods to extract from the
          statistics data. By default this is just the 'last1min' time
          period.
        :param origin: a tuple of (lat, lon) representing the receiver
          location. The origin is used for distance calculations with
          aircraft data.
        '''
        self.dump1090urls = build_resources(url)
        self.loop = loop or asyncio.get_event_loop()
        self.host = host
        self.port = port
        self.aircraft_interval = datetime.timedelta(seconds=aircraft_interval)
        self.stats_interval = datetime.timedelta(seconds=stats_interval)
        self.stats_time_periods = time_periods
        self.origin = Position(*origin) if origin else None
        self.svr = Service(loop=loop)
        self.stats_task = None  # type: asyncio.Task
        self.aircraft_task = None  # type: asyncio.Task
        self.initialise_metrics()
        logger.info('dump1090 url: %s', self.dump1090urls.base)
        logger.info('aircraft refresh interval: %s', self.aircraft_interval)
        logger.info('statistics refresh interval: %s', self.stats_interval)
        logger.info('origin: %s', self.origin)

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
                fetch(self.dump1090urls.receiver), 3.0)
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
        self.g_messages = Gauge(
            'dump1090_messages',
            'Number of Mode-S messages accepted')
        self.svr.registry.register(self.g_messages)

        # aircraft
        self.g_recent_aircraft_observed = Gauge(
            'dump1090_recent_aircraft_observed',
            'Number of aircraft recently observed')
        self.svr.registry.register(self.g_recent_aircraft_observed)
        self.g_recent_aircraft_with_pos = Gauge(
            'dump1090_recent_aircraft_with_position',
            'Number of aircraft recently observed with position')
        self.svr.registry.register(self.g_recent_aircraft_with_pos)
        self.g_recent_aircraft_with_mlat = Gauge(
            'dump1090_recent_aircraft_with_multilateration',
            'Number of aircraft recently observed with multilateration')
        self.svr.registry.register(self.g_recent_aircraft_with_mlat)
        self.g_recent_aircraft_max_range = Gauge(
            'dump1090_aircraft_recent_max_range',
            'Maximum range of recently observed aircraft')
        self.svr.registry.register(self.g_recent_aircraft_max_range)

        # statistics

        # extract statistics about messages received from local SDR dongle
        self.g_stats_local_accepted = Gauge(
            'dump1090_stats_local_accepted',
            'Number of valid Mode S messages accepted with N-bit errors corrected')
        self.svr.registry.register(self.g_stats_local_accepted)
        self.g_stats_local_signal = Gauge(
            'dump1090_stats_local_signal_strength_dbFS',
            'Signal strength dbFS')
        self.svr.registry.register(self.g_stats_local_signal)
        self.g_stats_local_peak_signal = Gauge(
            'dump1090_stats_local_peak_signal_strength_dbFS',
            'Peak signal strength dbFS')
        self.svr.registry.register(self.g_stats_local_peak_signal)
        self.g_stats_local_noise = Gauge(
            'dump1090_stats_local_noise_level_dbFS',
            'Noise level dbFS')
        self.svr.registry.register(self.g_stats_local_noise)
        self.g_stats_local_strong_signals = Gauge(
            'dump1090_stats_local_strong_signals',
            'Number of messages that had a signal power above -3dBFS')
        self.svr.registry.register(self.g_stats_local_strong_signals)
        self.g_stats_local_bad = Gauge(
            'dump1090_stats_local_bad',
            "Number of Mode S preambles that didn't result in a valid message")
        self.svr.registry.register(self.g_stats_local_bad)
        self.g_stats_local_modes = Gauge(
            'dump1090_stats_local_modes',
            'Number of Mode S preambles received')
        self.svr.registry.register(self.g_stats_local_modes)
        self.g_stats_local_modeac = Gauge(
            'dump1090_stats_local_modeac',
            'Number of Mode A/C preambles decoded')
        self.svr.registry.register(self.g_stats_local_modeac)
        self.g_stats_local_samples_dropped = Gauge(
            'dump1090_stats_local_samples_dropped',
            'Number of samples dropped')
        self.svr.registry.register(self.g_stats_local_samples_dropped)
        self.g_stats_local_samples_processed = Gauge(
            'dump1090_stats_local_samples_processed',
            'Number of samples processed')
        self.svr.registry.register(self.g_stats_local_samples_processed)
        self.g_stats_local_unknown_icao = Gauge(
            'dump1090_stats_local_unknown_icao',
            'Number of Mode S preambles containing unrecognized ICAO')
        self.svr.registry.register(self.g_stats_local_unknown_icao)

        # extract statistics about CPU use
        self.g_stats_cpu_background_ms = Gauge(
            'dump1090_stats_cpu_background_milliseconds',
            'Time spent in network I/O, processing and periodic tasks')
        self.svr.registry.register(self.g_stats_cpu_background_ms)
        self.g_stats_cpu_demod_ms = Gauge(
            'dump1090_stats_cpu_demod_milliseconds',
            'Time spent demodulation and decoding data from SDR dongle')
        self.svr.registry.register(self.g_stats_cpu_demod_ms)
        self.g_stats_cpu_reader_ms = Gauge(
            'dump1090_stats_cpu_reader_milliseconds',
            'Time spent reading sample data from SDR dongle')
        self.svr.registry.register(self.g_stats_cpu_reader_ms)

        # extract statistics for Compact Position Report message decoding
        self.g_stats_cpr_airborne = Gauge(
            'dump1090_stats_cpr_airborne',
            'Number of airborne CPR messages received')
        self.svr.registry.register(self.g_stats_cpr_airborne)
        self.g_stats_cpr_surface = Gauge(
            'dump1090_stats_cpr_surface',
            'Number of surface CPR messages received')
        self.svr.registry.register(self.g_stats_cpr_surface)
        self.g_stats_cpr_filtered = Gauge(
            'dump1090_stats_cpr_filtered',
            'number of CPR messages ignored')
        self.svr.registry.register(self.g_stats_cpr_filtered)
        self.g_stats_cpr_global_bad = Gauge(
            'dump1090_stats_cpr_global_bad',
            'Global positions that were rejected')
        self.svr.registry.register(self.g_stats_cpr_global_bad)
        self.g_stats_cpr_global_ok = Gauge(
            'dump1090_stats_cpr_global_ok',
            'Global positions successfuly derived')
        self.svr.registry.register(self.g_stats_cpr_global_ok)
        self.g_stats_cpr_global_range = Gauge(
            'dump1090_stats_cpr_global_range',
            'Global positions rejected due to receiver max range check')
        self.svr.registry.register(self.g_stats_cpr_global_range)
        self.g_stats_cpr_global_skipped = Gauge(
            'dump1090_stats_cpr_global_skipped',
            'Global position attempts skipped due to missing data')
        self.svr.registry.register(self.g_stats_cpr_global_skipped)
        self.g_stats_cpr_global_speed = Gauge(
            'dump1090_stats_cpr_global_speed',
            'Global positions rejected due to speed check')
        self.svr.registry.register(self.g_stats_cpr_global_speed)
        self.g_stats_cpr_local_aircraft_relative = Gauge(
            'dump1090_stats_cpr_local_aircraft_relative',
            'Local positions found relative to a previous aircraft position')
        self.svr.registry.register(self.g_stats_cpr_local_aircraft_relative)
        self.g_stats_cpr_local_ok = Gauge(
            'dump1090_stats_cpr_local_ok',
            'Local (relative) positions successfully found')
        self.svr.registry.register(self.g_stats_cpr_local_ok)
        self.g_stats_cpr_local_range = Gauge(
            'dump1090_stats_cpr_local_range',
            'Local positions rejected due to receiver max range check')
        self.svr.registry.register(self.g_stats_cpr_local_range)
        self.g_stats_cpr_local_receiver_relative = Gauge(
            'dump1090_stats_cpr_local_receiver_relative',
            'Local positions found relative to the receiver position')
        self.svr.registry.register(self.g_stats_cpr_local_receiver_relative)
        self.g_stats_cpr_local_skipped = Gauge(
            'dump1090_stats_cpr_local_skipped',
            'Local (relative) positions skipped due to missing data')
        self.svr.registry.register(self.g_stats_cpr_local_skipped)
        self.g_stats_cpr_local_speed = Gauge(
            'dump1090_stats_cpr_local_speed',
            'Local positions rejected due to speed check')
        self.svr.registry.register(self.g_stats_cpr_local_speed)

        # extract total number of messages accepted by dump1090 from any source
        self.g_stats_messages = Gauge(
            'dump1090_stats_messages',
            'Number of Mode-S messages processed')
        self.svr.registry.register(self.g_stats_messages)

        # extract statistics about messages received from remote clients
        self.g_stats_remote_accepted = Gauge(
            'dump1090_stats_remote_accepted',
            'Number of valid Mode S messages accepted with N-bit errors corrected')
        self.svr.registry.register(self.g_stats_remote_accepted)
        self.g_stats_remote_bad = Gauge(
            'dump1090_stats_remote_bad',
            "Number of Mode S preambles that didn't result in a valid message")
        self.svr.registry.register(self.g_stats_remote_bad)
        self.g_stats_remote_modeac = Gauge(
            'dump1090_stats_remote_modeac',
            'Number of Mode A/C preambles decoded')
        self.svr.registry.register(self.g_stats_remote_modeac)
        self.g_stats_remote_modes = Gauge(
            'dump1090_stats_remote_modes',
            'Number of Mode S preambles received')
        self.svr.registry.register(self.g_stats_remote_modes)
        self.g_stats_remote_unknown_icao = Gauge(
            'dump1090_stats_remote_unknown_icao',
            'Number of Mode S preambles containing unrecognized ICAO')
        self.svr.registry.register(self.g_stats_remote_unknown_icao)

        # extract statistics on aircraft tracks
        self.g_stats_tracks_all = Gauge(
            'dump1090_stats_tracks_all',
            'Number of tracks created')
        self.svr.registry.register(self.g_stats_tracks_all)
        self.g_stats_tracks_single_message = Gauge(
            'dump1090_stats_tracks_single_message',
            'Number of tracks consisting of only a single message')
        self.svr.registry.register(self.g_stats_tracks_single_message)

    async def updater_stats(self) -> None:
        '''
        This long running coroutine task is responsible for fetching current
        statistics from dump1090 and then updating internal metrics.
        '''
        while True:
            start = datetime.datetime.now()
            try:
                stats = await asyncio.wait_for(
                    fetch(self.dump1090urls.stats), 3.0)
            except asyncio.TimeoutError:
                logger.error(
                    'request for dump1090 stats data timed out')
                return

            self.process_stats(
                stats, time_periods=self.stats_time_periods)

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
                    fetch(self.dump1090urls.aircraft), 3.0)
            except asyncio.TimeoutError:
                logger.error(
                    'request for dump1090 aircraft data timed out')
                return

            self.process_aircraft(aircraft)

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

        for time_period in time_periods:
            try:
                tp_stats = stats[time_period]
            except KeyError:
                logger.exception(
                    'Problem extracting time period: {}'.format(time_period))
                continue

            cpr = tp_stats['cpr']
            cpu = tp_stats['cpu']
            local = tp_stats['local']
            remote = tp_stats['remote']
            tracks = tp_stats['tracks']

            labels = dict(time_period=time_period)

            # extract statistics for Compact Position Report message decoding
            try:
                self.g_stats_cpr_airborne.set(labels, cpr['airborne'])
                self.g_stats_cpr_surface.set(labels, cpr['surface'])
                self.g_stats_cpr_filtered.set(labels, cpr['filtered'])
                self.g_stats_cpr_global_bad.set(labels, cpr['global_bad'])
                self.g_stats_cpr_global_ok.set(labels, cpr['global_ok'])
                self.g_stats_cpr_global_range.set(labels, cpr['global_range'])
                self.g_stats_cpr_global_skipped.set(labels, cpr['global_skipped'])
                self.g_stats_cpr_global_speed.set(labels, cpr['global_speed'])
                self.g_stats_cpr_local_aircraft_relative.set(labels, cpr['local_aircraft_relative'])
                self.g_stats_cpr_local_ok.set(labels, cpr['local_ok'])
                self.g_stats_cpr_local_range.set(labels, cpr['local_range'])
                self.g_stats_cpr_local_receiver_relative.set(labels, cpr['local_receiver_relative'])
                self.g_stats_cpr_local_skipped.set(labels, cpr['local_skipped'])
                self.g_stats_cpr_local_speed.set(labels, cpr['local_speed'])
            except Exception:
                logger.exception(
                    'Problem extracting cpr items from: {}'.format(cpr))

            # extract statistics about CPU use
            try:
                self.g_stats_cpu_background_ms.set(labels, cpu['background'])
                self.g_stats_cpu_demod_ms.set(labels, cpu['demod'])
                self.g_stats_cpu_reader_ms.set(labels, cpu['reader'])
            except Exception:
                logger.exception(
                    'Problem extracting cpu items from: {}'.format(cpr))

            # extract statistics about messages received from local SDR dongle
            try:
                self.g_stats_local_signal.set(labels, local['signal'])
                self.g_stats_local_peak_signal.set(labels, local['peak_signal'])
                self.g_stats_local_noise.set(labels, local['noise'])
                self.g_stats_local_strong_signals.set(labels, local['strong_signals'])
                self.g_stats_local_bad.set(labels, local['bad'])
                self.g_stats_local_modes.set(labels, local['modes'])
                self.g_stats_local_modeac.set(labels, local['modeac'])
                self.g_stats_local_samples_dropped.set(labels, local['samples_dropped'])
                self.g_stats_local_samples_processed.set(labels, local['samples_processed'])
            except Exception:
                logger.exception(
                    'Problem extracting local items from: {}'.format(cpr))

            # extract total number of messages accepted by dump1090 from any source
            self.g_stats_messages.set(labels, tp_stats['messages'])

            # extract statistics about messages received from remote clients
            try:
                self.g_stats_remote_accepted.set(labels, remote['accepted'][0])
                self.g_stats_remote_bad.set(labels, remote['bad'])
                self.g_stats_remote_modeac.set(labels, remote['modeac'])
                self.g_stats_remote_modes.set(labels, remote['modes'])
                self.g_stats_remote_unknown_icao.set(labels, remote['unknown_icao'])
            except Exception:
                logger.exception(
                    'Problem extracting remote items from: {}'.format(cpr))

            # extract statistics on aircraft tracks
            try:
                self.g_stats_tracks_all.set(labels, tracks['all'])
                self.g_stats_tracks_single_message.set(labels, tracks['single_message'])
            except Exception:
                logger.exception(
                    'Problem extracting tracks items from: {}'.format(cpr))

    def process_aircraft(self,
                         aircraft: dict,
                         threshold: int = 15) -> None:
        ''' Process aircraft statistics into exported metrics.

        :param aircraft: a dict containing aircraft data.
        :param threshold: only let aircraft seen within this threshold to
          contribute to the metrics.
        '''
        # Ensure aircraft dict always contains all keys
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
        self.g_messages.set(labels, messages)
        self.g_recent_aircraft_observed.set(labels, aircraft_observed)
        self.g_recent_aircraft_with_pos.set(labels, aircraft_with_pos)
        self.g_recent_aircraft_with_mlat.set(labels, aircraft_with_mlat)
        self.g_recent_aircraft_max_range.set(labels, aircraft_max_range)

        logger.debug(
            "aircraft: observed=%i, with_pos=%i, with_mlat=%i, max_range=%i, "
            "messages=%i",
            aircraft_observed, aircraft_with_pos, aircraft_with_mlat,
            aircraft_max_range, messages)
