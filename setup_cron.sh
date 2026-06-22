#!/bin/bash
# Setup cron job for automated WhatsApp notifications
# Run this once on the server: bash setup_cron.sh

CRON_CMD="0 * * * * docker exec order-taking-app-web-1 python /code/manage.py send_notifications >> /var/log/ea_notifications.log 2>&1"

# Add to crontab if not already there
(crontab -l 2>/dev/null | grep -v "send_notifications"; echo "$CRON_CMD") | crontab -

echo "✅ Cron job set up — runs every hour"
echo "Logs: /var/log/ea_notifications.log"
crontab -l | grep send_notifications