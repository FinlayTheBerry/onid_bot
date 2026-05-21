#!/bin/sh

cd "$(dirname "$0")"

reset
tail -n 200 ./log.txt | while read -r line; do
  if [[ "$line" == *"ERROR - "* ]] || [[ "$line" == *"PY_EX - "* ]]; then
    echo -e "\033[31m$line\033[0m"
  elif [[ "$line" == *"Warning - "* ]]; then
    echo -e "\033[33m$line\033[0m"
  else
    echo -e "$line"
  fi
done
echo ""
./Cluster.py status
echo ""
LAST_BACKUP=$(ls -S ./backups/ | head -n 1 | sed 's/\.json$//')
echo "Last backup - $(date -d @$LAST_BACKUP)" - $(python -c "import time; print(format((time.time() - $LAST_BACKUP) / 86400, '.2f'))") days ago
echo ""
