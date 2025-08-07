-- Fix NFT Marketplace Database Schema
-- Run this script to add missing columns and fix schema issues

-- Add missing category column to nfts table
ALTER TABLE nfts ADD COLUMN IF NOT EXISTS category VARCHAR(100);

-- Add missing description column to nfts table (commonly used)
ALTER TABLE nfts ADD COLUMN IF NOT EXISTS description TEXT;

-- Ensure all required columns exist
-- Note: Run this after connecting to your PostgreSQL database

-- Update existing NFTs with default category if needed
UPDATE nfts SET category = 'art' WHERE category IS NULL;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_nfts_category ON nfts(category);
CREATE INDEX IF NOT EXISTS idx_nfts_is_sold ON nfts(is_sold);
CREATE INDEX IF NOT EXISTS idx_nfts_is_reserved ON nfts(is_reserved);
CREATE INDEX IF NOT EXISTS idx_nfts_created_at ON nfts(created_at);

-- Show current table structure
\d nfts;
