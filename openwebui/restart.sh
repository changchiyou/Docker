#!/bin/bash
docker compose -f docker-compose.yml -f docker-compose.searxng.yml -f docker-compose.litellm.yml -p openwebui stop
# docker compose -f docker-compose.yml -f docker-compose.searxng.yml -f docker-compose.litellm.yml -p openwebui pull
docker compose -f docker-compose.yml -f docker-compose.searxng.yml -f docker-compose.litellm.yml -p openwebui up -d
