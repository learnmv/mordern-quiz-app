#!/bin/bash
# Uninstall cron jobs for automated question generation

echo "Removing Quiz App cron jobs..."

# Check if crontab exists
if ! command -v crontab &> /dev/null; then
    echo "Error: crontab command not found."
    exit 1
fi

# Get current crontab
CURRENT_CRONTAB=$(crontab -l 2>/dev/null || true)

# Check if quiz app cron jobs exist
if ! echo "$CURRENT_CRONTAB" | grep -q "cron_runner.py"; then
    echo "No Quiz App cron jobs found."
    exit 0
fi

# Remove quiz app cron jobs
NEW_CRONTAB=$(echo "$CURRENT_CRONTAB" | grep -v "cron_runner.py" | grep -v "Quiz App - Automated Question Generation")

# Install the updated crontab
echo "$NEW_CRONTAB" | crontab -

echo "Quiz App cron jobs removed successfully!"
echo ""
echo "To verify: crontab -l"
