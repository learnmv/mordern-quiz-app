#!/bin/bash
# Install cron jobs for automated question generation
# This script adds 9 cron jobs (3 grades x 3 difficulties) that run every 5 minutes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_RUNNER="$SCRIPT_DIR/cron_runner.py"
LOG_DIR="$SCRIPT_DIR/logs"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Check if virtual environment exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at $VENV_PYTHON"
    echo "Please create a virtual environment with: python3 -m venv venv"
    exit 1
fi

# Define the cron jobs - one for each grade/difficulty combination
CRON_JOBS="# Quiz App - Automated Question Generation Cron Jobs
# Grade 6 - cycles through 31 grade-6-specific topics
*/5 * * * * cd $SCRIPT_DIR && $VENV_PYTHON $CRON_RUNNER 6 easy >> $LOG_DIR/cron_grade6_easy.log 2>&1
*/5 * * * * cd $SCRIPT_DIR && $VENV_PYTHON $CRON_RUNNER 6 medium >> $LOG_DIR/cron_grade6_medium.log 2>&1
*/5 * * * * cd $SCRIPT_DIR && $VENV_PYTHON $CRON_RUNNER 6 hard >> $LOG_DIR/cron_grade6_hard.log 2>&1
# Grade 7 - cycles through 34 grade-7-specific topics
*/5 * * * * cd $SCRIPT_DIR && $VENV_PYTHON $CRON_RUNNER 7 easy >> $LOG_DIR/cron_grade7_easy.log 2>&1
*/5 * * * * cd $SCRIPT_DIR && $VENV_PYTHON $CRON_RUNNER 7 medium >> $LOG_DIR/cron_grade7_medium.log 2>&1
*/5 * * * * cd $SCRIPT_DIR && $VENV_PYTHON $CRON_RUNNER 7 hard >> $LOG_DIR/cron_grade7_hard.log 2>&1
# Grade 8 - cycles through 27 grade-8-specific topics
*/5 * * * * cd $SCRIPT_DIR && $VENV_PYTHON $CRON_RUNNER 8 easy >> $LOG_DIR/cron_grade8_easy.log 2>&1
*/5 * * * * cd $SCRIPT_DIR && $VENV_PYTHON $CRON_RUNNER 8 medium >> $LOG_DIR/cron_grade8_medium.log 2>&1
*/5 * * * * cd $SCRIPT_DIR && $VENV_PYTHON $CRON_RUNNER 8 hard >> $LOG_DIR/cron_grade8_hard.log 2>&1
"

echo "Installing Quiz App cron jobs..."
echo "Script directory: $SCRIPT_DIR"
echo "Log directory: $LOG_DIR"
echo "Python: $VENV_PYTHON"
echo ""

# Check if crontab exists
if ! command -v crontab &> /dev/null; then
    echo "Error: crontab command not found. Please install cron."
    exit 1
fi

# Get current crontab (or empty if none exists)
CURRENT_CRONTAB=$(crontab -l 2>/dev/null || true)

# Check if quiz app cron jobs already exist
if echo "$CURRENT_CRONTAB" | grep -q "Quiz App - Automated Question Generation"; then
    echo "Quiz App cron jobs already installed."
    echo ""
    echo "To remove existing jobs and reinstall, run:"
    echo "  ./uninstall_cron.sh"
    echo "  ./install_cron.sh"
    exit 0
fi

# Append new cron jobs to existing crontab
NEW_CRONTAB="${CURRENT_CRONTAB}

$CRON_JOBS"

# Install the new crontab
echo "$NEW_CRONTAB" | crontab -

echo "Cron jobs installed successfully!"
echo ""
echo "Installed jobs:"
echo "  - Grade 6 Easy   (every 5 min, cycles through 31 topics)"
echo "  - Grade 6 Medium (every 5 min, cycles through 31 topics)"
echo "  - Grade 6 Hard   (every 5 min, cycles through 31 topics)"
echo "  - Grade 7 Easy   (every 5 min, cycles through 34 topics)"
echo "  - Grade 7 Medium (every 5 min, cycles through 34 topics)"
echo "  - Grade 7 Hard   (every 5 min, cycles through 34 topics)"
echo "  - Grade 8 Easy   (every 5 min, cycles through 27 topics)"
echo "  - Grade 8 Medium (every 5 min, cycles through 27 topics)"
echo "  - Grade 8 Hard   (every 5 min, cycles through 27 topics)"
echo ""
echo "Logs will be written to: $LOG_DIR/"
echo ""
echo "To view current crontab: crontab -l"
echo "To remove all quiz jobs: ./uninstall_cron.sh"
