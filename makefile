.PHONY: docker enter run example

DOCKER_IMG ?= chord-striker
DOCKER_TAG ?= $(shell git rev-parse --short HEAD)
DOCKER_DIR ?= docker

docker:
	docker buildx create --name mybuilder --use || true
	docker buildx build --builder mybuilder --platform linux/arm64 -t $(DOCKER_IMG):$(DOCKER_TAG) $(DOCKER_DIR) --load
	docker tag $(DOCKER_IMG):$(DOCKER_TAG) $(DOCKER_IMG):latest

# for multi-platform build (when needed)
docker-multi:
	docker buildx create --name mybuilder --use || true
	docker buildx build --builder mybuilder --platform linux/arm64,linux/amd64 -t $(DOCKER_IMG):$(DOCKER_TAG) $(DOCKER_DIR) --push

RUN_TAG ?= latest
RUN ?= docker run --platform linux/arm64 -it --rm -v $(PWD):/app -w /app $(DOCKER_IMG):$(RUN_TAG)
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