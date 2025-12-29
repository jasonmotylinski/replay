#!/bin/sh

cd /var/projects/replay
source /var/projects/replay/venv/bin/activate
uvicorn main:app