FROM python:3.5
MAINTAINER Chris Laws <clawsicus@gmail.com>
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
COPY src/dump1090-exporter.py /code/
WORKDIR /code
EXPOSE 9105
ENTRYPOINT [ "python3", "./dump1090-exporter.py"]
CMD ["--help"]
