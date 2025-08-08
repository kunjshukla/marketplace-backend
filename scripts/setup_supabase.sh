#!/bin/bash

# Database Migration Script for Supabase Integration
# Run this after setting up your Supabase project

echo "🚀 Setting up NFT Marketplace Database..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL environment variable not set!"
    echo "Please set your Supabase PostgreSQL connection string in .env file"
    exit 1
fi

# Install/upgrade Alembic
echo "📦 Installing dependencies..."
pip install alembic psycopg2-binary supabase

# Initialize Alembic if not already done
if [ ! -d "alembic/versions" ]; then
    echo "🔧 Initializing Alembic..."
    alembic init alembic
fi

# Generate initial migration
echo "📝 Generating initial migration..."
alembic revision --autogenerate -m "Initial NFT marketplace schema"

# Apply migrations
echo "⬆️  Applying migrations to Supabase database..."
alembic upgrade head

echo "✅ Database setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Check your Supabase dashboard to verify tables were created"
echo "2. Configure Row Level Security (RLS) if needed"
echo "3. Set up any additional Supabase features (Storage, Edge Functions, etc.)"
