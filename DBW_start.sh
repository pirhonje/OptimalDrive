#!/bin/sh
cd /home/optimaldrive/buildtest/DBW && lxterminal -e docker compose up &
firefox --kiosk localhost
