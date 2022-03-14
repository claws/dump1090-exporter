import argparse
import asyncio
import logging

from .exporter import Dump1090Exporter

# try to import uvloop - optional
try:
    import uvloop

    uvloop.install()
except ImportError:
    pass


DEFAULT_RESOURCE_PATH = "http://localhost:8080/data"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9105
DEFAULT_RECEIVER_REFRESH_INTERVAL = 10
DEFAULT_AIRCRAFT_REFRESH_INTERVAL = 10
DEFAULT_STATISTICS_REFRESH_INTERVAL = 60
LOGGING_CHOICES = ["error", "warning", "info", "debug"]
DEFAULT_LOGGING_LEVEL = "info"


def main():
    """Run the dump1090 Prometheus exporter"""

    parser = argparse.ArgumentParser(
        prog="dump1090exporter", description="dump1090 Prometheus Exporter"
    )
    parser.add_argument(
        "--resource-path",
        metavar="<dump1090 url or dirpath>",
        type=str,
        default=DEFAULT_RESOURCE_PATH,
        help=f"dump1090 data URL or file system path. Default value is {DEFAULT_RESOURCE_PATH}",
    )
    parser.add_argument(
        "--host",
        metavar="<exporter host>",
        type=str,
        default=DEFAULT_HOST,
        help=(
            "The address to expose collected metrics from. "
            f"Default is all interfaces ({DEFAULT_HOST})."
        ),
    )
    parser.add_argument(
        "--port",
        metavar="<exporter port>",
        type=int,
        default=DEFAULT_PORT,
        help=f"The port to expose collected metrics from. Default is {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--aircraft-interval",
        metavar="<aircraft data refresh interval>",
        type=int,
        default=DEFAULT_AIRCRAFT_REFRESH_INTERVAL,
        help=(
            "The number of seconds between updates of the aircraft data. "
            f"Default is {DEFAULT_AIRCRAFT_REFRESH_INTERVAL} seconds"
        ),
    )
    parser.add_argument(
        "--stats-interval",
        metavar="<stats data refresh interval>",
        type=int,
        default=DEFAULT_STATISTICS_REFRESH_INTERVAL,
        help=(
            "The number of seconds between updates of the stats data. "
            f"Default is {DEFAULT_STATISTICS_REFRESH_INTERVAL} seconds"
        ),
    )
    parser.add_argument(
        "--receiver-interval",
        metavar="<receiver data refresh interval>",
        type=int,
        default=DEFAULT_RECEIVER_REFRESH_INTERVAL,
        help=(
            "The number of seconds between updates of the receiver data. "
            f"Default is {DEFAULT_RECEIVER_REFRESH_INTERVAL} seconds"
        ),
    )
    parser.add_argument(
        "--latitude",
        metavar="<receiver latitude>",
        type=float,
        default=None,
        help="The latitude of the receiver position to use as the origin.",
    )
    parser.add_argument(
        "--longitude",
        metavar="<receiver longitude>",
        type=float,
        default=None,
        help="The longitude of the receiver position to use as the origin.",
    )
    parser.add_argument(
        "--log-level",
        choices=LOGGING_CHOICES,
        default=DEFAULT_LOGGING_LEVEL,
        type=str,
        help=f"A logging level from {LOGGING_CHOICES}. Default value is '{DEFAULT_LOGGING_LEVEL}'.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s.%(msecs)03.0f [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=getattr(logging, args.log_level.upper()),
    )

    args.origin = None
    if args.latitude and args.longitude:
        args.origin = (args.latitude, args.longitude)

    loop = asyncio.get_event_loop()
    mon = Dump1090Exporter(
        resource_path=args.resource_path,
        host=args.host,
        port=args.port,
        aircraft_interval=args.aircraft_interval,
        stats_interval=args.stats_interval,
        receiver_interval=args.receiver_interval,
        origin=args.origin,
    )
    loop.run_until_complete(mon.start())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(mon.stop())
    loop.stop()
    loop.close()


if __name__ == "__main__":
    main()
