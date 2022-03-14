
# Demonstration Environment

The following instructions describe a method for creating a local test
environment that demonstrates using the dump1090exporter alongside Prometheus
and Grafana.

It uses Docker-Compose to orchestrate dump1090exporter, Prometheus and
Grafana to facilitate experimentation with metric collection and graphing.

Configure the command line arguments supplied to dump1090exporter for your
specific environment. Edit the ``docker-compose.yml`` file in this directory
and replace the following block with settings for your specific dump1090
instance:

``` yaml
command: [
  "--resource-path=http://192.168.1.201:8080",
  "--latitude=-34.9285",
  "--longitude=138.6007"]
```

Build the dump1090exporter Python package and then return to this directory.
```
$ cd ..
$ make venv
$ source venv/bin/activate
(d1090exp) $ make dist
(d1090exp) $ deactivate
$ cd demo
```

Start everything up. This will build a new dump1090exporter container the
first time it is run.

```
$ docker compose up
```

  > To stop everything use ctrl+c and then run ``docker-compose down`` to
  > ensure everything is cleanly shutdown. If you also want to remove the
  > volumes then use ``docker compose down -v``.

You should now have a dump1090exporter, Prometheus and Grafana environment
running that you can experiment with. Grafana should now be accessible at
``http://localhost:3000``. Login to Grafana with credentials shown below.

``` console
username - admin
password - foobar
```

Once logged in you should be able to view the dump1090exporter dashboard. You
may need to click the dashboard selector dropdown ``Home`` to select the
dump1090exporter dashboard.

  > Recent versions of Grafana added the concept of provisioning which assists
  > with the process of automatically adding Datasources and Dashboards. The
  > ``/grafana/provisioning/`` directory contains the ``datasources`` and
  > ``dashboards`` directories. These directories contain YAML files which
  > specify which datasource or dashboards should be installed automatically.
  >
  > The dump1090exporter dashboard has been added into the
  > ``/grafana/provisioning/dashboards`` so that it will be available by
  > default. You should be able to select and display it.
