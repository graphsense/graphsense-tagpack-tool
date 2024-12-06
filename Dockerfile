FROM  python:3.11-alpine3.20
LABEL org.opencontainers.image.title="graphsense-tagpack-tool"
LABEL org.opencontainers.image.maintainer="contact@ikna.io"
LABEL org.opencontainers.image.url="https://www.ikna.io/"
LABEL org.opencontainers.image.description="Dockerized Graphsense tagpack tool"
LABEL org.opencontainers.image.source="https://github.com/graphsense/graphsense-tagpack-tool"

RUN apk --no-cache --update --virtual buld-deps add \
    gcc \
    make \
    musl-dev \
    linux-headers \
    python3-dev \
    libuv-dev

RUN apk --no-cache --update add \
    bash \
    shadow \
    git \
    openssh \
    libuv

RUN mkdir -p /opt/graphsense/
ADD ./src/ /opt/graphsense/tool/src
ADD ./.git/ /opt/graphsense/tool/.git
ADD ./Makefile /opt/graphsense/tool/
ADD ./pyproject.toml /opt/graphsense/tool/
ADD ./setup.py /opt/graphsense/tool/
ADD ./setup.cfg /opt/graphsense/tool/
ADD ./tox.ini /opt/graphsense/tool/


WORKDIR /opt/graphsense/tool/
RUN pip install .

RUN apk del buld-deps
RUN rm -rf /opt/graphsense/

# RUN useradd -r -m -u 10000 graphsense
# USER graphsense
RUN mkdir /opt/graphsense
WORKDIR /opt/graphsense/
