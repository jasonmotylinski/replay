#!/bin/sh

cd /var/projects/relay
source /var/projects/relay/venv/bin/activate
uvicorn main:app