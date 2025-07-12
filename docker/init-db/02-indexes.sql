-- Additional indexes for performance optimization

-- Full text search index
CREATE INDEX IF NOT EXISTS idx_pokemon_cards_fulltext 
ON pokemon_cards USING gin (
    to_tsvector('english', 
        coalesce(name, '') || ' ' || 
        coalesce(set_name, '') || ' ' || 
        coalesce(artist, '')
    )
);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_pokemon_cards_set_number 
ON pokemon_cards(set_id, number);

CREATE INDEX IF NOT EXISTS idx_pokemon_cards_type_rarity 
ON pokemon_cards(card_type, rarity);

-- Index for price queries
CREATE INDEX IF NOT EXISTS idx_pokemon_cards_price 
ON pokemon_cards(tcgplayer_price) 
WHERE tcgplayer_price IS NOT NULL;

-- Index for batch upload queries
CREATE INDEX IF NOT EXISTS idx_upload_items_batch_status 
ON upload_items(batch_id, status);

-- Index for session cleanup
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires 
ON user_sessions(expires_at);

-- Partial index for pending reviews
CREATE INDEX IF NOT EXISTS idx_manual_reviews_pending 
ON manual_reviews(status) 
WHERE status = 'pending';

-- Analyze tables for query optimization
ANALYZE pokemon_cards;
ANALYZE manual_reviews;
ANALYZE batch_uploads;
ANALYZE upload_items;
ANALYZE user_sessions;