FROM python:3.8-alpine

# Preventing Python from writing pyc files to disk
ENV PYTHONDONTWRITEBYTECODE 1
# Preventing Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1

# create the app user
RUN addgroup -S d1090exp && adduser -S d1090exp -G d1090exp

COPY ./dist/dump1090exporter-*-py3-none-any.whl /tmp/

# install dump1090exporter (including dependencies and requirements)
RUN \
  apk update && \
  apk add --no-cache --virtual .build-deps musl-dev gcc && \
  pip install pip -U --no-cache-dir && \
  pip install /tmp/dump1090exporter-*-py3-none-any.whl --no-cache-dir && \
  apk --purge del .build-deps && \
  rm -rf /tmp/dump1090exporter-*-py3-none-any.whl

# switch to non-root user
USER d1090exp

WORKDIR /tmp

EXPOSE 9105

ENTRYPOINT ["python", "-m", "dump1090exporter"]
CMD ["--help"]
