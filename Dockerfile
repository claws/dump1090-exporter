FROM python:3.5
MAINTAINER Chris Laws <clawsicus@gmail.com>
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
COPY ./dist/dump1090exporter-*.tar.gz /tmp/
WORKDIR /tmp
RUN pip install dump1090exporter-*.tar.gz
EXPOSE 9105
ENTRYPOINT ["dump1090exporter"]
CMD ["--help"]
