dump1090 Exporter
=================

.. note::

    This exporter currently works with the mutability fork of dump1090, using
    the ``/path/to/dump1090-base-dir/data/aicraft.json`` and
    ``/path/to/dump1090-base-dir/data/receivers.json`` routes as well as
    with the dump1090-fa fork using the ``/run/dump1090-fa/`` route.
    Those are used by the exporter to fetch metrics.

`Dump1090 <https://github.com/mutability/dump1090>`_ is a simple Mode S decoder
for RTLSDR devices that is commonly used for tracking aircraft. Dump1090 makes
a number of operating metrics available to track the performance of the tool
and its environment.

The dump1090exporter collects statistics from dump1090 and exposes it to the
`Prometheus <https://prometheus.io/>`_ monitoring server for aggregation and
later visualisation (e.g. using `Grafana <https://grafana.net/dashboards/768>`_).


Install
-------

The dump1090 exporter is written using Python 3 (Python3.6+) and will not work
with Python 2. The dump1090 exporter can be installed using the Python package
manager *pip*. It is recommended to use a virtual environment.

.. code-block:: console

    $ pip install dump1090exporter

The dump1090exporter is also available as a Docker container from DockerHub.
See the *Docker* section below for more details.


Run
---

Once installed the dump1090 exporter can be easily run from the command
line as the installation script includes a console entry point.

The dump1090 exporter accepts a number of command line arguments. These
can be found by using the standard command line help request.

.. code-block:: console

    $ dump1090exporter -h

Below is an example usage.

.. code-block:: console

    $ dump1090exporter \
      --resource-path=http://192.168.1.201:8080/data \
      --port=9105 \
      --latitude=-34.9285 \
      --longitude=138.6007 \
      --debug

In the example above the exporter is instructed to monitor a dump1090
instance running on a machine with the IP address 192.168.1.201 using
the default port (8080) used by dump1090 tool. The exporter exposes a
service for Prometheus to scrape on port 9105 by default but this can
be changed by specifying it with the *--port* argument.

The example above also instructs the exporter to use a specific receiver
origin (lat, lon). In this case it is for Adelaide, Australia. In most
cases the dump1090 tool is not configured with the receivers position.
By providing the exporter with the receiver location it can calculate
ranges to aircraft. If the receiver position is already set within the
dump1090 tool (and accessible from the *{resource-path}/receivers.json*
resource) then the exporter will use that data as the origin.

The dump1090exporter can also monitor dump1090 status via the file system if
you run it on the same machine. In this scenario you would pass a file system
path to the ``--resource-path`` command line argument. For example:

.. code-block:: console

    $ dump1090exporter \
      --resource-path=/path/to/dump1090-base-dir/data \
      --port=9105 \
      --latitude=-34.9285 \
      --longitude=138.6007 \
      --debug

The exporter fetches aircraft data (from *{resource-path}/aircraft.json*)
every 10 seconds. This can be modified by specifying a new value with the
*--aircraft-interval* argument.

The exporter fetches statistics data (from *{resource-path}/stats.json*)
every 60 seconds, as the primary metrics being exported are extracted from the
*last1min* time period. This too can be modified by specifying a new
value with the *--stats-interval* argument.

The metrics that the dump1090 exporter provides to Prometheus can be
accessed for debug and viewing using curl or a browser by fetching from
the metrics route url. For example:

.. code-block:: console

    $ curl -s http://0.0.0.0:9105/metrics | grep -v "#"
    dump1090_aircraft_recent_max_range{time_period="latest"} 1959.0337385807418
    dump1090_messages_total{time_period="latest"} 90741
    dump1090_recent_aircraft_observed{time_period="latest"} 4
    dump1090_recent_aircraft_with_multilateration{time_period="latest"} 0
    dump1090_recent_aircraft_with_position{time_period="latest"} 1
    dump1090_stats_cpr_airborne{time_period="last1min"} 176
    dump1090_stats_cpr_airborne{time_period="total"} 18293
    ...

The metrics exposed by the dump1090-exporter are all prefixed with the
*dump1090_* string so as to provide a helpful namespacing which makes them
easier to find in visualisation tools such as Grafana.

The exporter exposes generalised metrics for statistics and uses the multi
dimensional label capability of Prometheus metrics to include information
about which group the metric is part of.

To extract information for the peak signal metric that dump1090 aggregated
over the last 1 minute you would specify the time_period for that group:

.. code-block:: console

    dump1090_stats_local_peak_signal{job="dump1090", time_period="last1min"}

In the stats.json data there are 5 top level keys that contain statistics for
a different time period, defined by the "start" and "end" subkeys. The top
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


Prometheus Configuration
------------------------

Prometheus needs to be told where to fetch the dump1090 metrics from. The
Prometheus configuration file should be updated with a new entry under the
'scrape_configs' block, that looks something like this:

.. code-block:: yaml

    scrape_configs:
      - job_name: 'dump1090'
        scrape_interval: 10s
        scrape_timeout: 5s
        static_configs:
          - targets: ['192.168.1.201:9105']


Visualisation
-------------

The Granfana visualisation tool can display nice looking charts and it
supports Prometheus. A `dump1090export <https://grafana.net/dashboards/768>`_
Grafana dashboard has been created to demonstrate how the data provided by the
exporter can be visualised.

.. figure:: screenshot-grafana.png


Docker
------

The dump1090 exporter has been packaged into a Docker container on DockerHub.
This can simplify running it in some environments. The container is configured
with an entry point that runs the dump1090 exporter application. The default
command argument is *--help* which will display help information.

.. code-block:: console

    $ docker run -it --rm clawsicus/dump1090exporter
    usage: dump1090exporter [-h] [--resource-path <dump1090 url>]
    ...

To run the dump1090 exporter container in your environment simply pass your
own custom command line arguments to it:

.. code-block:: console

    $ docker run -p 9105:9105 \
      --detach \
      clawsicus/dump1090exporter \
      --resource-path=http://192.168.1.201:8080/data \
      --latitude=-34.9285 \
      --longitude=138.6007

Once running you can check the metrics being exposed to Prometheus by fetching
them using curl.

.. code-block:: console

    $ curl http://127.0.0.1:9105/metrics

Now you would configure your Prometheus server to scape the dump1090exporter
container on port 9105.


Demonstration
-------------

A demonstration environment can be found in the ``demo`` directory. It uses
Docker Compose to orchestrate containers running dump1090exporter, Prometheus
and Grafana to facilitate experimentation with metric collection and graphing.

This provides a really quick and easy method for checking out the
dump1090exporter.


Developer Notes
---------------

Python Release Process
^^^^^^^^^^^^^^^^^^^^^^

The following steps are used to make a new software release:

- Ensure that the version label in ``__init__.py`` is updated.

- Create a virtual environment, install dependencies and the dump1090exporter.

  .. code-block:: console

      $ make venv
      $ source venv/bin/activate
      (d1090exp) $

- Apply the code style formatter.

  .. code-block:: console

      (d1090exp) $ make style

- Apply the code types checker.

  .. code-block:: console

      (d1090exp) $ make check-types

- Create the distribution. This project produces an artefact called a pure
  Python wheel. Only Python3 is supported by this package.

  .. code-block:: console

      (d1090exp) $ make dist

- Upload the new release to PyPI.

  .. code-block:: console

      (d1090exp) $ make dist-upload

- Create and push a repo tag to Github.

  .. code-block:: console

      $ git tag YY.MM.MICRO -m "A meaningful release tag comment"
      $ git tag  # check release tag is in list
      $ git push --tags origin master

  - Github will create a release tarball at:

    ::

        https://github.com/{username}/{repo}/tarball/{tag}.tar.gz


Docker Release Process
^^^^^^^^^^^^^^^^^^^^^^

The following steps are used to make a new software release:

- Create a new dump1090exporter Python package.

  .. code-block:: console

      (d1090exp) $ make dist

- Log in to the Docker user account which will hold the public image.

  .. code-block:: console

      (d1090exp) $ docker login
      username
      password

- Create the dump1090exporter Docker container.

  .. code-block:: console

      (d1090exp) $ docker build -t clawsicus/dump1090exporter .

- Test the new container by specifying its full namespace to pull
  that image.

  .. code-block:: console

      $ docker run -it --rm clawsicus/dump1090exporter
      usage: dump1090exporter [-h] [--resource-path <dump1090 url>]
      ...

- Test it by running the container and configuring it to connect to a
  dump1090 service.

  .. code-block:: console

      $ docker run -p 9105:9105 \
        --detach \
        clawsicus/dump1090exporter \
        --resource-path=http://192.168.1.201:8080/data \
        --latitude=-34.9285 \
        --longitude=138.6007

  Confirm that metrics are being collected and exposed by checking metrics
  are being exposed to Prometheus by fetching them using curl.

  .. code-block:: console

      $ curl http://127.0.0.1:9105/metrics

- Publish the new container to DockerHub using:

  .. code-block:: console

      (d1090exp) $ docker push clawsicus/dump1090exporter:<verison>
