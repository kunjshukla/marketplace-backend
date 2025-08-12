# Supabase Integration Guide

This backend can source NFTs from a live Supabase Postgres table while preserving compatibility with the existing local DB.

What changed
- utilities/supabase_client.py: Cached Supabase v2 client
- api/nft.py: Endpoints prefer Supabase, with automatic fallback to local DB
- config/settings.py: SUPABASE_URL and keys via .env

Required env (.env)
- SUPABASE_URL=https://<project>.supabase.co
- SUPABASE_SERVICE_ROLE_KEY=... (preferred server-side)
- SUPABASE_ANON_KEY=... (fallback)

Supabase table schema (nfts)
- id (int, PK)
- title (text)
- description (text, nullable)
- image_url (text)
- price_inr (numeric)
- price_usd (numeric)
- category (text, nullable)
- is_sold (boolean, default false)
- is_reserved (boolean, default false)
- reserved_at (timestamp with time zone, nullable)
- sold_at (timestamp with time zone, nullable)
- owner_id (int, nullable)
- created_at (timestamp with time zone, default now())

Endpoints affected
- GET /api/nft/list?skip=&limit=&category=
- GET /api/nft/{id}
- GET /api/nft/search?search=&limit=
- GET /api/nft/categories
- GET /api/nft/featured?limit=
- GET /api/nft/stats
- GET /api/nft/my-purchases (local DB only)

Behavior
- If Supabase client initializes, queries are executed against table "nfts"
- On any Supabase error, endpoint logs a warning and falls back to local DB
- Responses keep the same envelope { success, message, data }

Images
- Backend serves /static/* from images/ directory
- Frontend proxies /images/* -> backend /static/*
- Ensure image_url fields point to either absolute URL or backend /static/* path

Testing
- Set SUPABASE_URL and SERVICE_ROLE_KEY in .env
- Start backend: uvicorn main:app --reload
- Query: curl 'http://localhost:8000/api/nft/list?limit=5'

Notes
- Purchase flow still records transactions in local DB
- Optionally mirror Supabase NFTs into local DB for ownership tracking
