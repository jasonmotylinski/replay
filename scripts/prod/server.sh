#!/bin/bash

cd /var/projects/replay
source /var/projects/replay/venv/bin/activate
uvicorn main:app --uds /run/replay.sock \
                 --workers 4 \
                 --log-level info