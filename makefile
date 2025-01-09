.PHONY: docker

DOCKER_IMG ?= chord-striker
DOCKER_TAG ?= $(shell git rev-parse --short HEAD)
DOCKER_DIR ?= docker

docker:
	docker build -t $(DOCKER_IMG):$(DOCKER_TAG) $(DOCKER_DIR)