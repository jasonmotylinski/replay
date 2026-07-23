#!/bin/bash

cd /var/projects/replay
source /var/projects/replay/venv/bin/activate

# Bind the socket that systemd's replay.socket unit created and passed to us
# as fd 3 (socket activation). Do NOT use --uds here: that makes uvicorn try
# to create /run/replay.sock itself, which collides with the systemd socket.
# `exec` so uvicorn becomes the service MAINPID (clean signals / ExecReload).
exec uvicorn main:app --fd 3 --log-level info
