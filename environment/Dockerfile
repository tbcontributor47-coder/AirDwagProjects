FROM maven:3.9-eclipse-temurin-17-alpine

WORKDIR /app

RUN apk add --no-cache gnucobol python3 py3-pip bash curl \
    && mkdir -p /logs/verifier

COPY app/ /app/

CMD ["mvn", "test"]
