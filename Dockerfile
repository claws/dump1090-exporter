FROM python:3.6
MAINTAINER Chris Laws <clawsicus@gmail.com>
COPY requirements.txt /tmp/
RUN pip install pip -U
RUN pip install -r /tmp/requirements.txt
COPY ./dist/dump1090exporter-*-py3-none-any.whl /tmp/
WORKDIR /tmp
RUN pip install dump1090exporter-*-py3-none-any.whl
EXPOSE 9105
ENTRYPOINT ["dump1090exporter"]
CMD ["--help"]
