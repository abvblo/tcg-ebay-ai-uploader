-- Initialize Pokemon Cards Database

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS pokemon;

-- Set search path
SET search_path TO pokemon, public;

-- Create tables if they don't exist
CREATE TABLE IF NOT EXISTS pokemon_cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    card_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    set_name VARCHAR(255),
    set_id VARCHAR(50),
    number VARCHAR(20),
    rarity VARCHAR(50),
    card_type VARCHAR(50),
    hp INTEGER,
    types TEXT[],
    subtypes TEXT[],
    supertype VARCHAR(50),
    artist VARCHAR(255),
    image_url TEXT,
    tcgplayer_price DECIMAL(10,2),
    market_price DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster searches
CREATE INDEX IF NOT EXISTS idx_pokemon_cards_name ON pokemon_cards USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_pokemon_cards_set ON pokemon_cards(set_name);
CREATE INDEX IF NOT EXISTS idx_pokemon_cards_rarity ON pokemon_cards(rarity);
CREATE INDEX IF NOT EXISTS idx_pokemon_cards_types ON pokemon_cards USING gin (types);

-- Create manual review table
CREATE TABLE IF NOT EXISTS manual_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    confidence_score DECIMAL(5,2),
    identified_card_id VARCHAR(50),
    notes TEXT,
    reviewed_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create batch upload table
CREATE TABLE IF NOT EXISTS batch_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    total_cards INTEGER DEFAULT 0,
    processed_cards INTEGER DEFAULT 0,
    successful_cards INTEGER DEFAULT 0,
    failed_cards INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create upload items table
CREATE TABLE IF NOT EXISTS upload_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID REFERENCES batch_uploads(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    card_id VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',
    ebay_item_id VARCHAR(50),
    listing_price DECIMAL(10,2),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user sessions table (for web UI)
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_token VARCHAR(255) UNIQUE NOT NULL,
    user_ip VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_pokemon_cards_updated_at BEFORE UPDATE ON pokemon_cards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_manual_reviews_updated_at BEFORE UPDATE ON manual_reviews
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_upload_items_updated_at BEFORE UPDATE ON upload_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA pokemon TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA pokemon TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA pokemon TO CURRENT_USER;