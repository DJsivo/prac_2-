-- ========================================
-- CREATE TABLES
-- ========================================

-- Users/Auth
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    oauth_provider VARCHAR(50),
    oauth_subject VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oauth_states (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    state VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tracking
CREATE TABLE IF NOT EXISTS tracking (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    location VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- SEED DATA (100+ rows)
-- ========================================

INSERT INTO users (username, email, password_hash)
SELECT
    'user_' || gs,
    'user' || gs || '@example.com',
    'pbkdf2_sha256$120000$seedusersalt$76ee2857db6e546e7955d4f9338f965c6b6b268757d6dcce4ed1437180d6755f'
FROM generate_series(1, 100) AS gs
ON CONFLICT (email) DO NOTHING;

INSERT INTO users (username, email, password_hash, role)
VALUES (
    'admin',
    'admin@example.com',
    'pbkdf2_sha256$120000$adminseedsalt$921113908376e580e0f036dd071da7845bf2b66bce040f271237dfc173640e9c',
    'admin'
)
ON CONFLICT (email) DO NOTHING;

INSERT INTO orders (user_id, status, total_amount)
SELECT
    (random() * 99 + 1)::integer,
    (ARRAY['pending', 'processing', 'shipped', 'delivered', 'cancelled'])[floor(random() * 5 + 1)],
    (random() * 5000 + 100)::decimal(10,2)
FROM generate_series(1, 150);

INSERT INTO tracking (order_id, location, status)
SELECT
    (random() * 149 + 1)::integer,
    (ARRAY['Moscow', 'Saint Petersburg', 'Kazan', 'Ekaterinburg', 'Novosibirsk', 'Vladivostok', 'In transit', 'Warehouse'])[floor(random() * 8 + 1)],
    (ARRAY['in_transit', 'at_warehouse', 'out_for_delivery', 'delivered', 'processing'])[floor(random() * 5 + 1)]
FROM generate_series(1, 200);

INSERT INTO notifications (user_id, order_id, message, is_read)
SELECT
    (random() * 99 + 1)::integer,
    (random() * 149 + 1)::integer,
    'Order #' || (random() * 149 + 1)::integer || ': ' ||
    (ARRAY['Your order has been shipped', 'Order delivered', 'Payment confirmed', 'Order is being processed'])[floor(random() * 4 + 1)],
    (random() > 0.5)
FROM generate_series(1, 250);

-- ========================================
-- INDEXES
-- ========================================

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_tracking_order_id ON tracking(order_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
