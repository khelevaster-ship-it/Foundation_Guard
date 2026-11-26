#!/bin/bash
# mkrun.sh RUNDIR : fresh copy of the village project with its own server
set -e
W=$(cd "$(dirname "$0")" && pwd); R=$1
rm -rf "$R"; mkdir -p "$R"
cp -r "$W/template" "$R/village"
git init -q --bare "$R/server.git"
cp "$W/pre_receive.py" "$R/server.git/hooks/pre-receive"
cd "$R/village"
git remote add origin "$R/server.git"
git -C "$R/server.git" fetch -q "$R/village" main:main
git fetch -q origin
git branch -q -u origin/main
: > "$R/server_log.jsonl"
