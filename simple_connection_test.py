#!/usr/bin/env python3
"""
Simple direct connection test with updated credentials
"""

import asyncio
import asyncpg
import sys
import os

async def test_connection():
    print("Testing direct asyncpg connection with updated credentials...")
    
    try:
        conn = await asyncpg.connect(
            user="postgres",
            password="k0u0n0j0123.",
            database="postgres",
            host="db.jpxxulhgqmcncywxewlq.supabase.co",
            port=5432,
            ssl="require",
            timeout=15
        )
        
        print("✓ Connection successful!")
        
        # Test query
        version = await conn.fetchval("SELECT version()")
        print(f"PostgreSQL version: {version[:100]}...")
        
        # Test user count
        try:
            user_count = await conn.fetchval("SELECT COUNT(*) FROM auth.users")
            print(f"Users in auth.users: {user_count}")
        except:
            print("auth.users table not accessible")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print(f"Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_connection())
    sys.exit(0 if result else 1)
