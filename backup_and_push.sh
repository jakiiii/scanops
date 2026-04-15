#!/bin/bash

# ----------------------------------------------
# AUTOMATED DB BACKUP + GIT PUSH SCRIPT
# ----------------------------------------------

ENV_FILE=".env"

# Step 01: .env থেকে DB নাম পড়া
echo "🔍 Reading database name from .env ..."

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ .env file not found!"
    exit 1
fi

DB_NAME=$(grep -oP '^JTRO_DEV_DATABASE_NAME="\K[^"]+' "$ENV_FILE")

if [ -z "$DB_NAME" ]; then
    echo "❌ Could not read database name from .env"
    exit 1
fi

echo "✅ Database found: $DB_NAME"

# Step 02: backup ফোল্ডার তৈরি করা
BACKUP_DIR="backup"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "📁 Creating backup folder..."
    mkdir "$BACKUP_DIR"
    echo "✅ backup folder created."
fi

# Step 03: pg_dump দিয়ে ব্যাকআপ নেওয়া
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql"

echo "💾 Taking database backup..."
pg_dump -h localhost -p 5432 -U postgres -d "$DB_NAME" -f "$BACKUP_FILE"

if [ $? -ne 0 ]; then
    echo "❌ Failed to take database backup!"
    exit 1
fi

echo "✅ Backup saved at: $BACKUP_FILE"

# Step 04: git branch check
CURRENT_BRANCH=$(git branch --show-current)

echo "🔀 Current git branch: $CURRENT_BRANCH"

# Step 05: git add, commit, push
echo "📤 Pushing backup to Git..."

git add .
git commit -m "Database backup: $DB_NAME"
git push origin "$CURRENT_BRANCH"

if [ $? -eq 0 ]; then
    echo "🎉 Backup & Git push completed successfully!"
else
    echo "❌ Git push failed!"
fi
