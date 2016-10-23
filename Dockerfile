FROM python:3.5
MAINTAINER Chris Laws <clawsicus@gmail.com>
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
COPY . /tmp/
WORKDIR /tmp
RUN pip install .
EXPOSE 9105
ENTRYPOINT ["dump1090exporter"]
CMD ["--help"]
