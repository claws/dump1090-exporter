
# Demonstration Test Environment

The following instructions describe a method for creating a local test
environment that demonstrates using the dump1090exporter alongside Prometheus
and Grafana.

It uses containers and Docker-Compose to orchestrate and link together
dump1090exporter, Prometheus and Grafana to facilitate experimentation with
metric collection and graphing.

Pull the containers.

``` console
$ docker pull clawsicus/dump1090exporter
$ docker pull prom/prometheus
$ docker pull grafana/grafana
```

Customize the command line arguments supplied to the dump1090exporter to
configure it for your specific environment. Edit the ``docker-compose.yml``
file in this directory and replace the following block with your specific
settings:

``` yaml
command: [
  "--url=http://192.168.1.201:8080",
  "--latitude=-34.9285",
  "--longitude=138.6007"]
```

Now to start everything up.

.. code-block:: console

    $ docker-compose up [-d]

NOTE: If running in the foreground (i.e. not using ``-d``) and using ctrl+c to
stop everything then remember to also run ``docker-compose down`` to ensure
everything is cleanly shutdown. If not you will likely need to use the
``--force-recreate`` flag on subsequent runs.

Once it all starts the Grafana Dashboard should be accessible at
``http://localhost:3000``. Login with credentials shown below.

``` console
username - admin
password - foobar
```

If you want to change the default Grafana password, it is listed in the
environment Grafana settings file ``grafana/config.monitoring``.

Recent versions of Grafana added the concept of provisioning which assists
with the process of automatically adding Datasources and Dashboards. The
``/grafana/provisioning/`` directory contains the ``datasources`` and
``dashboards`` directories. These directories contain YAML files which
specify which datasource or dashboards should be installed automatically.

The dump1090 dashboard has been added into the ``/grafana/provisioning/dashboards``
so that it will be available by default. You should be able to select and
display it.

You should now have a dump1090exporter, Prometheus and Grafana test instance
and you can experiment with your own charts.
