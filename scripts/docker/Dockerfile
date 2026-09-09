ARG QGIS_IMAGE=qgis/qgis:3.44.11
FROM ${QGIS_IMAGE}

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends fontconfig fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

# Unmodified open font files, licence and pinned upstream provenance.
COPY fonts/barlow/ /usr/local/share/fonts/qfit/barlow/
RUN fc-cache -f
