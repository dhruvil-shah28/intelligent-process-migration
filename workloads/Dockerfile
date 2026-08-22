FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        criu \
        python3 \
        python3-venv \
        procps \
        iproute2 \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workload

COPY workload.py /workload/workload.py

CMD ["python3", "/workload/workload.py"]
