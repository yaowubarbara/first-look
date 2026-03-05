FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash tester

USER tester
WORKDIR /home/tester

# Agent will receive commands via stdin and execute them
CMD ["bash"]
