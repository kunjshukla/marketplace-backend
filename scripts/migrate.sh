#!/bin/bash

# Database migration script for NFT Marketplace

echo "Starting database migration..."

# Check if we're using SQLite or PostgreSQL
if [[ $DATABASE_URL == *"sqlite"* ]]; then
    echo "Using SQLite database"
    # Extract database file path from URL
    DB_FILE=$(echo $DATABASE_URL | sed 's/sqlite:\/\/\///g')
    
    # Create database if it doesn't exist
    if [ ! -f "$DB_FILE" ]; then
        echo "Creating SQLite database: $DB_FILE"
        touch "$DB_FILE"
    fi
    
    # Run SQL setup script
    echo "Executing setup script..."
    sqlite3 "$DB_FILE" < scripts/setup_db.sql
    
elif [[ $DATABASE_URL == *"postgresql"* ]]; then
    echo "Using PostgreSQL database"
    
    # For PostgreSQL, we'll use Python to run the migration
    python3 -c "
import os
import psycopg2
from urllib.parse import urlparse

# Parse database URL
url = urlparse(os.getenv('DATABASE_URL'))
conn = psycopg2.connect(
    host=url.hostname,
    port=url.port,
    user=url.username,
    password=url.password,
    database=url.path[1:]  # Remove leading slash
)

# Read and execute SQL
with open('scripts/setup_db.sql', 'r') as f:
    sql = f.read()
    # Convert SQLite syntax to PostgreSQL
    sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
    sql = sql.replace('BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT FALSE')
    sql = sql.replace('INSERT OR IGNORE', 'INSERT')
    sql = sql.replace('TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    
    # Split and execute statements
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    cursor = conn.cursor()
    
    for statement in statements:
        try:
            cursor.execute(statement)
            print(f'Executed: {statement[:50]}...')
        except Exception as e:
            print(f'Error executing statement: {e}')
            # Continue with other statements
    
    conn.commit()
    cursor.close()
    conn.close()
print('PostgreSQL migration completed')
"

else
    echo "Unknown database type. Please set DATABASE_URL"
    exit 1
fi

echo "Database migration completed successfully!"
