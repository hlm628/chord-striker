FROM --platform=$BUILDPLATFORM ubuntu:22.04

# Set noninteractive mode to avoid prompt during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /usr/src/app

# Add build arguments to detect architecture
ARG TARGETPLATFORM
ARG BUILDPLATFORM
RUN echo "Building on $BUILDPLATFORM, targeting $TARGETPLATFORM"

# Install basic dependencies and add deadsnakes PPA
RUN apt-get update && \
    apt-get install -y software-properties-common wget curl git && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update

# Install Python 3.11 and dependencies
RUN apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3.11-distutils \
    python3-pip \
    # System packages that might be in requirements.txt
    python3-distro-info \
    # Other dependencies
    libcairo2-dev \
    pkg-config \
    graphviz \
    graphviz-dev \
    libgraphviz-dev \
    build-essential \
    fontconfig \
    uuid-runtime \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for Python 3.11
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.11 /usr/bin/python

# Install pip and setuptools for Python 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 && \
    python3.11 -m pip install setuptools wheel

# Verify Python version
RUN python3 --version && python3 -m pip --version

# Install Lilypond - with architecture support
RUN set -e; \
    # Create temporary directory for installation
    mkdir -p /tmp/lilypond && \
    cd /tmp/lilypond && \
    # Install based on architecture
    if [ "$TARGETPLATFORM" = "linux/amd64" ] && [ "$BUILDPLATFORM" = "linux/amd64" ]; then \
        # x86_64 installation method (only when building natively)
        wget -q https://lilypond.org/download/binaries/linux-64/lilypond-2.24.3-1.linux-64.sh && \
        chmod +x lilypond-2.24.3-1.linux-64.sh && \
        printf "E\n" | ./lilypond-2.24.3-1.linux-64.sh && \
        mkdir -p /usr/local/lilypond/2.24.3 && \
        cp -r ./usr/* /usr/; \
    else \
        # ARM64 and cross-compilation - use apt
        apt-get update && \
        apt-get install -y lilypond && \
        apt-get clean; \
    fi && \
    # Cleanup
    cd / && \
    rm -rf /tmp/lilypond && \
    # Verify installation
    echo "LilyPond version:" && \
    lilypond --version | head -n 1

# Copy requirements file
COPY requirements.txt ./

# Install Python dependencies
RUN python3 -m pip install --no-cache-dir -r requirements.txt

CMD ["/bin/bash"]