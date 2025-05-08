.PHONY: docker enter run example

DOCKER_IMG ?= chord-striker
DOCKER_TAG ?= $(shell git rev-parse --short HEAD)
DOCKER_DIR ?= docker

# Detect current platform
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

# Map platform to Docker platform
ifeq ($(UNAME_S),Darwin)
    ifeq ($(UNAME_M),arm64)
        DOCKER_PLATFORM := linux/arm64
    else
        DOCKER_PLATFORM := linux/amd64
    endif
else
    ifeq ($(UNAME_M),aarch64)
        DOCKER_PLATFORM := linux/arm64
    else
        DOCKER_PLATFORM := linux/amd64
    endif
endif

# Build Docker image for current platform
docker:
	docker buildx create --name mybuilder --use --driver docker-container --bootstrap || true
	docker buildx build --builder mybuilder \
		--platform $(DOCKER_PLATFORM) \
		-t $(DOCKER_IMG):$(DOCKER_TAG) \
		-t $(DOCKER_IMG):latest \
		$(DOCKER_DIR) \
		--load

# Build Docker image for all platforms (requires registry)
docker-all:
	docker buildx create --name mybuilder --use --driver docker-container --bootstrap || true
	docker buildx build --builder mybuilder \
		--platform linux/arm64,linux/amd64 \
		-t $(DOCKER_IMG):$(DOCKER_TAG) \
		-t $(DOCKER_IMG):latest \
		$(DOCKER_DIR) \
		--push

# Run command with platform detection
RUN_TAG ?= latest
RUN ?= docker run --platform $(DOCKER_PLATFORM) -it --rm -v $(PWD):/app -w /app $(DOCKER_IMG):$(RUN_TAG)
SONG_NAME ?= Example

enter:
	$(RUN) bash

SEED ?= 42
OUTPUT_DIR ?= example

example: chord_striker/hit_maker.py $(OUTPUT_DIR)
	$(RUN) python3 chord_striker/hit_maker.py --song_name $(SONG_NAME) --seed $(SEED) --output_dir $(OUTPUT_DIR)

$(OUTPUT_DIR):
	mkdir -p $(OUTPUT_DIR)

ALBUM_TRACKS ?= 10
run-album: chord_striker/hit_maker.py
	$(RUN) python3 $^ --num_songs $(ALBUM_TRACKS)

# Helper target to show current platform
show-platform:
	@echo "Current platform: $(DOCKER_PLATFORM)"