# dump1090 Exporter

[Dump1090](https://github.com/mutability/dump1090) is a simple Mode S decoder
for RTLSDR devices that is commonly used for tracking aircraft. Dump1090 makes
a number of operating metrics available to track the performance of the tool
and its environment.

The dump1090exporter collects statistics from dump1090 and exposes it to the
[Prometheus](https://prometheus.io/) monitoring server for aggregation and
later visualisation (e.g. using [Grafana](https://grafana.net/dashboards/768>)).

This exporter has been reported to work with:

  - the dump1090 mutability fork
  - the dump1090-fa fork
  - [readsb](https://github.com/wiedehopf/readsb)

## Install

The dump1090 exporter is implemented as a Python3.6+ package that can be
installed using the Python package manager *pip*. It is recommended to install
this package into a virtual environment.

```shell
$ pip install dump1090exporter
```

The package can optionally make use of the *uvloop* package which provides a
more efficient implementation of the asyncio event loop.

```shell
$ pip install dump1090exporter[uvloop]
```

The dump1090exporter has also been packaged into a Docker container. See the
[Docker](#docker) section below for more details about that.

## Run

The dump1090 exporter can be run from the command line using the console entry
point script configured as part of the installation.

The dump1090 exporter accepts a number of command line arguments which can be
displayed using the standard command line help request.

```shell
$ dump1090exporter -h
```

An example usage is shown below.

```shell
$ dump1090exporter \
  --resource-path=http://192.168.1.201:8080/data \
  --port=9105 \
  --latitude=-34.9285 \
  --longitude=138.6007 \
  --log-level info
```

The ``--resource-path`` argument defines the common base path to the various
dump1090 resources used by the exporter. The resource path can be a URL or a
file system location.

In the example command the exporter is instructed to monitor a dump1090
instance running on a machine with the IP address 192.168.1.201 using the port
8080.

The dump1090exporter can also monitor dump1090 state via the file system if
you run it on the same machine as the dump1090 process. In this scenario you
would pass a file system path to the ``--resource-path`` command line argument.

For example:

```shell
$ dump1090exporter \
  --resource-path=/path/to/dump1090-base-dir/data \
  ...
```

A more concrete example for dump1090-fa would be:

```shell
$ dump1090exporter \
  --resource-path=/run/dump1090-fa/ \
  ...
```

The exporter uses the ``resources-path`` value to construct the following
resources:

  - {resource-path}/receiver.json
  - {resource-path}/aircraft.json
  - {resource-path}/stats.json

Receiver data is read from ``{resource-path}/receiver.json`` every 10 seconds
until a location can be obtained. Once a location has been read from the
resource then it is only polled every 300 seconds. However, in most cases the
dump1090 tool is not configured with the receivers position.

Aircraft data is read from ``{resource-path}/aircraft.json`` every 10 seconds.
This can be modified by specifying a new value with the ``--aircraft-interval``
argument.

Statistics data is read from ``{resource-path}/stats.json`` every 60 seconds,
as the primary metrics being exported are extracted from the *last1min* time
period. This too can be modified by specifying an alternative value with the
``--stats-interval`` argument.

The example command uses the ``--port`` argument to instruct the exporter to
exposes a metrics service on port 9105. This is where Prometheus would scrape
the metrics from. By default the port is configured to use 9105 so it only
needs to be specified if you want to change the port to a different value.

The example command uses the ``--latitude`` and ``--longitude`` arguments
to instruct the exporter to use a specific receiver origin (lat, lon). By
providing the exporter with the receiver's location it can calculate ranges
to aircraft. Note that if the receiver position is set within the dump1090
tool (and accessible from the ``{resource-path}/receivers.json`` resource)
then the exporter will use that data as the origin.

The metrics that the dump1090 exporter provides to Prometheus can be
accessed for debug and viewing using curl or a browser by fetching from
the metrics route url. For example:

```shell
$ curl -s http://0.0.0.0:9105/metrics | grep -v "#"
dump1090_aircraft_recent_max_range{time_period="latest"} 1959.0337385807418
dump1090_messages_total{time_period="latest"} 90741
dump1090_recent_aircraft_observed{time_period="latest"} 4
dump1090_recent_aircraft_with_multilateration{time_period="latest"} 0
dump1090_recent_aircraft_with_position{time_period="latest"} 1
dump1090_stats_cpr_airborne{time_period="last1min"} 176
dump1090_stats_cpr_airborne{time_period="total"} 18293
...
```

The metrics exposed by the dump1090-exporter are all prefixed with the
*dump1090_* string so as to provide a helpful namespacing which makes them
easier to find in visualisation tools such as Grafana.

The exporter exposes generalised metrics for statistics and uses the multi
dimensional label capability of Prometheus metrics to include information
about which group the metric is part of.

To extract information for the peak signal metric that dump1090 aggregated
over the last 1 minute you would specify the ``time_period`` for that group:

```shell
dump1090_stats_local_peak_signal{job="dump1090", time_period="last1min"}
```

In the ``stats.json`` data there are 5 top level keys that contain statistics
for a different time period, defined by the "start" and "end" subkeys. The top
level keys are:

- *latest* which covers the time between the end of the "last1min" period and
  the current time. In my dump1090 setup this is always empty.
- *last1min* which covers a recent 1-minute period. This may be up to 1 minute
  out of date (i.e. "end" may be up to 1 minute old)
- *last5min* which covers a recent 5-minute period. As above, this may be up
  to 1 minute out of date.
- *last15min* which covers a recent 15-minute period. As above, this may be up
  to 1 minute out of date.
- *total* which covers the entire period from when dump1090 was started up to
  the current time.

By default only the *last1min* time period is exported as Prometheus can be
used for accessing historical data.


## Prometheus Configuration

Prometheus needs to be told where to fetch the dump1090 metrics from. The
Prometheus configuration file should be updated with a new entry under the
'scrape_configs' block, that looks something like this:

```yaml
scrape_configs:
  - job_name: 'dump1090'
    scrape_interval: 10s
    scrape_timeout: 5s
    static_configs:
      - targets: ['192.168.1.201:9105']
```

## Visualisation

The Granfana visualisation tool can display nice looking charts and it
supports Prometheus. A [dump1090export](https://grafana.net/dashboards/768)
Grafana dashboard has been created to demonstrate how the data provided by the
exporter can be visualised.

![](https://raw.githubusercontent.com/claws/dump1090-exporter/master/screenshot-grafana.png)

## Docker

The dump1090 exporter has been packaged into a Docker container on DockerHub.
This can simplify running it in some environments. The container is configured
with an entry point that runs the dump1090 exporter application. The default
command argument is ``--help`` which will display help information.

```shell
$ docker run -it --rm clawsicus/dump1090exporter
usage: dump1090exporter [-h] [--resource-path <dump1090 url>]
...
```

To run the dump1090 exporter container in your environment simply pass your
own custom command line arguments to it:

```shell
$ docker run -p 9105:9105 \
  --detach \
  clawsicus/dump1090exporter \
  --resource-path=http://192.168.1.201:8080/data \
  --latitude=-34.9285 \
  --longitude=138.6007
```

You can then check the metrics being exposed to Prometheus by fetching them
using curl.

```shell
$ curl http://127.0.0.1:9105/metrics
```

Next you would configure a Prometheus server to scape the dump1090exporter
container on port 9105.


## Demonstration

A demonstration environment can be found in the ``demo`` directory. It uses
Docker Compose to orchestrate containers running dump1090exporter, Prometheus
and Grafana to facilitate experimentation with metric collection and graphing.

This provides a really quick and easy method for checking out the
dump1090exporter.


## Developer Notes

### Python Release Process

The following steps are used to make a new software release:

- Ensure current branch is set to master and is up to date.

- Create a virtual environment, install dependencies and the dump1090exporter.

  ```shell
  $ make venv
  $ source venv/bin/activate
  (d1090exp) $
  ```

- Ensure all checks are passing.

  ```shell
  (d1090exp) $ make checks
  ```

- Ensure that the version label in ``__init__.py`` has been updated.

- Create the distribution. This project produces an artefact called a pure
  Python wheel. Only Python3 is supported by this package.

  ```shell
  (d1090exp) $ make dist
  ```

- Upload the new release to PyPI.

  ```shell
  (d1090exp) $ make dist-upload
  ```

- Create and push a repo tag to Github.

  ```shell
  $ git tag YY.MM.MICRO -m "A meaningful release tag comment"
  $ git tag  # check release tag is in list
  $ git push --tags origin master
  ```

  - Github will create a release tarball at:

    https://github.com/{username}/{repo}/tarball/{tag}.tar.gz


### Docker Release Process

The following steps are used to make a new software release:

- Generate the dump1090exporter Python package distribution.

  ```shell
  (d1090exp) $ make dist
  ```

- Log in to the Docker user account which will hold the public image.

  ```shell
  (d1090exp) $ docker login
  username
  password
  ```

- Build the dump1090exporter Docker container.

  ```shell
  (d1090exp) $ docker build -t clawsicus/dump1090exporter .
  ```

- Perform a simple test of the container by specifying its full namespace to
  run that container image.

  ```shell
  $ docker run -it --rm clawsicus/dump1090exporter
  usage: dump1090exporter [-h] [--resource-path <dump1090 url>]
  ...
  ```

- Test the container by configuring it to connect to a dump1090 service.

  ```shell
  $ docker run -p 9105:9105 \
    --detach \
    clawsicus/dump1090exporter \
    --resource-path=http://192.168.1.201:8080/data \
    --latitude=-34.9285 \
    --longitude=138.6007
  ```

  Confirm that metrics are being collected and exposed by checking metrics
  are being exposed to Prometheus by fetching them using curl.

  ```shell
  $ curl http://127.0.0.1:9105/metrics
  ```

- Publish the new container to DockerHub using:

  ```shell
  (d1090exp) $ docker push clawsicus/dump1090exporter:<version>
  ```
