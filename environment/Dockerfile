FROM eclipse-temurin:17-jdk

WORKDIR /app

# Install Maven, GnuCOBOL, Python, and other dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        maven \
        gnucobol \
        bash \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /logs/verifier

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

COPY app/ /app/
COPY app/validate.cbl /baseline/validate.cbl

CMD ["mvn", "test"]
