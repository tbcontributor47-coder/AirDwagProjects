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
# Compile hidden oracle and remove source
COPY app/.oracle_ref.cbl /tmp/.oracle_ref.cbl
RUN cobc -x -O2 -o /usr/bin/insurance_validator_ref /tmp/.oracle_ref.cbl \
    && rm /tmp/.oracle_ref.cbl

CMD ["mvn", "test"]
