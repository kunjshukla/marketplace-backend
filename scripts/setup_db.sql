-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    google_id VARCHAR(255) UNIQUE NOT NULL,
    profile_pic TEXT,
    role VARCHAR(50) DEFAULT 'user',
    refresh_token TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create nfts table
CREATE TABLE IF NOT EXISTS nfts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    image_url TEXT NOT NULL,
    price_inr DECIMAL(10, 2) NOT NULL,
    price_usd DECIMAL(10, 2) NOT NULL,
    category VARCHAR(100),
    is_sold BOOLEAN DEFAULT FALSE,
    is_reserved BOOLEAN DEFAULT FALSE,
    reserved_at TIMESTAMP,
    sold_to_user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sold_to_user_id) REFERENCES users(id)
);

-- Create transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    nft_id INTEGER NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    txn_ref VARCHAR(255),
    buyer_currency VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (nft_id) REFERENCES nfts(id)
);

-- Create analytics table
CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nft_id INTEGER,
    user_id INTEGER,
    event_type VARCHAR(50),
    event_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (nft_id) REFERENCES nfts(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_nfts_is_sold ON nfts(is_sold);
CREATE INDEX IF NOT EXISTS idx_nfts_is_reserved ON nfts(is_reserved);
CREATE INDEX IF NOT EXISTS idx_nfts_category ON nfts(category);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_analytics_event_type ON analytics(event_type);

-- Insert sample NFTs (optional)
INSERT OR IGNORE INTO nfts (id, title, image_url, price_inr, price_usd, category) VALUES
(1, 'Digital Sunset #001', 'https://via.placeholder.com/400x400/FF6B6B/FFFFFF?text=Sunset+001', 2500.00, 30.00, 'art'),
(2, 'Abstract Dreams #002', 'https://via.placeholder.com/400x400/4ECDC4/FFFFFF?text=Dreams+002', 1800.00, 22.00, 'art'),
(3, 'Cyber Punk Cat #003', 'https://via.placeholder.com/400x400/45B7D1/FFFFFF?text=Cat+003', 3200.00, 38.00, 'collectible'),
(4, 'Neon Landscape #004', 'https://via.placeholder.com/400x400/96CEB4/FFFFFF?text=Neon+004', 2800.00, 34.00, 'art'),
(5, 'Space Explorer #005', 'https://via.placeholder.com/400x400/FECA57/FFFFFF?text=Space+005', 4500.00, 55.00, 'collectible');
