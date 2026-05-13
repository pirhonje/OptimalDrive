#!/bin/sh
cd "path of DBW" && lxterminal -e docker compose up &
firefox --kiosk localhost
