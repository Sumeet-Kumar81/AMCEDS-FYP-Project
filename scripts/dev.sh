#!/usr/bin/env bash
# ./scripts/dev.sh up | down | logs | test
case "$1" in
  up)   docker compose up -d postgres && docker compose up --build api ;;
  down) docker compose down ;;
  logs) docker compose logs -f api ;;
  test) (cd backend && pytest -q) ;;
  *)    echo "usage: $0 up|down|logs|test" ;;
esac
