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


def main():
    """Run the dump1090 Prometheus exporter"""

    parser = argparse.ArgumentParser(
        prog="dump1090exporter", description="dump1090 Prometheus Exporter"
    )
    parser.add_argument(
        "--resource-path",
        metavar="<dump1090 url or dirpath>",
        type=str,
        default="http://localhost:8080",
        help="dump1090 URL or directory path of the dump1090 service",
    )
    parser.add_argument(
        "--host",
        metavar="<exporter host>",
        type=str,
        default="0.0.0.0",
        help="The address to expose collected metrics from. Default is all interfaces.",
    )
    parser.add_argument(
        "--port",
        metavar="<exporter port>",
        type=int,
        default=9105,
        help="The port to expose collected metrics from. Default is 9105",
    )
    parser.add_argument(
        "--aircraft-interval",
        metavar="<aircraft data refresh interval>",
        type=int,
        dest="aircraft_interval",
        default=10,
        help="The number of seconds between updates of the aircraft data. Default is 10 seconds",
    )
    parser.add_argument(
        "--stats-interval",
        metavar="<stats data refresh interval>",
        type=int,
        dest="stats_interval",
        default=60,
        help="The number of seconds between updates of the stats data. Default is 60 seconds",
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
        "--debug", action="store_true", default=False, help="Print debug output"
    )

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

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
