-- ========================================
-- СОЗДАНИЕ ТАБЛИЦ
-- ========================================

-- Таблица пользователей (Auth Service)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица заказов (Order Service)
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица отслеживания (Tracking Service)
CREATE TABLE IF NOT EXISTS tracking (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    location VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица уведомлений (Notification Service)
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- НАПОЛНЕНИЕ ДАННЫМИ (100+ записей)
-- ========================================

-- 100 пользователей
INSERT INTO users (username, email, password_hash)
SELECT 
    'user_' || gs,
    'user' || gs || '@example.com',
    '$2b$12$LQv3c1yqBhWi0M5lJ0qZu.X1Y2Z3a4b5c6d7e8f9g0h1i2j3k4l5m'
FROM generate_series(1, 100) AS gs;

-- 150 заказов
INSERT INTO orders (user_id, status, total_amount)
SELECT 
    (random() * 99 + 1)::integer,
    (ARRAY['pending', 'processing', 'shipped', 'delivered', 'cancelled'])[floor(random() * 5 + 1)],
    (random() * 5000 + 100)::decimal(10,2)
FROM generate_series(1, 150);

-- 200 записей отслеживания
INSERT INTO tracking (order_id, location, status)
SELECT 
    (random() * 149 + 1)::integer,
    (ARRAY['Moscow', 'Saint Petersburg', 'Kazan', 'Ekaterinburg', 'Novosibirsk', 'Vladivostok', 'In transit', 'Warehouse'])[floor(random() * 8 + 1)],
    (ARRAY['in_transit', 'at_warehouse', 'out_for_delivery', 'delivered', 'processing'])[floor(random() * 5 + 1)]
FROM generate_series(1, 200);

-- 250 уведомлений
INSERT INTO notifications (user_id, order_id, message, is_read)
SELECT 
    (random() * 99 + 1)::integer,
    (random() * 149 + 1)::integer,
    'Order #' || (random() * 149 + 1)::integer || ': ' || 
    (ARRAY['Your order has been shipped', 'Order delivered', 'Payment confirmed', 'Order is being processed'])[floor(random() * 4 + 1)],
    (random() > 0.5)
FROM generate_series(1, 250);

-- ========================================
-- ИНДЕКСЫ для ускорения запросов
-- ========================================

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_tracking_order_id ON tracking(order_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);