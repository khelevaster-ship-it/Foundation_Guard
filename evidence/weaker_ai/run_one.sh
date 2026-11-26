#!/bin/bash
# run_one.sh MODEL TASK N
W=$(cd "$(dirname "$0")" && pwd); M=$1; T=$2; N=$3; R=$W/runs/$M-$T-$N
[ -f "$R/done" ] && exit 0
"$W/mkrun.sh" "$R"
cd "$R/village"
SERVER_LOG="$R/server_log.jsonl" timeout 1500 claude -p "$(cat $W/tasks/$T.txt)" --model "$M" --max-turns 80 \
  --allowedTools "Bash,Read,Edit,Write,Glob,Grep,MultiEdit" --output-format stream-json --verbose > "$R/transcript.jsonl" 2> "$R/stderr.txt"
echo $? > "$R/done"
