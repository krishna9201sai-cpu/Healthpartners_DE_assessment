-- ============================================
-- FOOD TRUCK COMPANY - ENTITY RELATIONSHIP DESIGN
-- Author: Sai Krishna Valluri
-- Assessment: HealthPartners Data Engineering
-- ============================================

-- 1. FOOD TRUCK TABLE
CREATE TABLE food_truck (
    truck_id        INT PRIMARY KEY,
    truck_name      VARCHAR(100) NOT NULL,
    license_plate   VARCHAR(20) UNIQUE NOT NULL,
    cuisine_type    VARCHAR(50),
    capacity        INT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_date    DATE DEFAULT CURRENT_DATE
);

-- 2. LOCATION TABLE
CREATE TABLE location (
    location_id     INT PRIMARY KEY,
    location_name   VARCHAR(100) NOT NULL,
    address         VARCHAR(200),
    city            VARCHAR(50),
    state           VARCHAR(20),
    zip_code        VARCHAR(10),
    latitude        DECIMAL(9,6),
    longitude       DECIMAL(9,6)
);

-- 3. SCHEDULE TABLE
-- Links truck to location by date/time
CREATE TABLE schedule (
    schedule_id     INT PRIMARY KEY,
    truck_id        INT NOT NULL,
    location_id     INT NOT NULL,
    schedule_date   DATE NOT NULL,
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    FOREIGN KEY (truck_id) REFERENCES food_truck(truck_id),
    FOREIGN KEY (location_id) REFERENCES location(location_id)
);

-- 4. CUSTOMER TABLE
CREATE TABLE customer (
    customer_id     INT PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    email           VARCHAR(100) UNIQUE,
    phone           VARCHAR(20),
    created_date    DATE DEFAULT CURRENT_DATE
);

-- 5. MENU ITEM TABLE
CREATE TABLE menu_item (
    item_id         INT PRIMARY KEY,
    truck_id        INT NOT NULL,
    item_name       VARCHAR(100) NOT NULL,
    description     VARCHAR(300),
    category        VARCHAR(50),
    price           DECIMAL(8,2) NOT NULL,
    is_available    BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (truck_id) REFERENCES food_truck(truck_id)
);

-- 6. ORDER TABLE
CREATE TABLE orders (
    order_id        INT PRIMARY KEY,
    customer_id     INT NOT NULL,
    truck_id        INT NOT NULL,
    schedule_id     INT NOT NULL,
    order_date      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_status    VARCHAR(20) DEFAULT 'PENDING',
    -- status: PENDING, PREPARING, READY, COMPLETED, CANCELLED
    total_amount    DECIMAL(10,2),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    FOREIGN KEY (truck_id) REFERENCES food_truck(truck_id),
    FOREIGN KEY (schedule_id) REFERENCES schedule(schedule_id)
);

-- 7. ORDER ITEMS TABLE
-- Line items for each order
CREATE TABLE order_items (
    order_item_id   INT PRIMARY KEY,
    order_id        INT NOT NULL,
    item_id         INT NOT NULL,
    quantity        INT NOT NULL DEFAULT 1,
    unit_price      DECIMAL(8,2) NOT NULL,
    subtotal        DECIMAL(10,2) GENERATED ALWAYS AS 
                    (quantity * unit_price) STORED,
    special_notes   VARCHAR(200),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (item_id) REFERENCES menu_item(item_id)
);

-- 8. PAYMENT TABLE
CREATE TABLE payment (
    payment_id      INT PRIMARY KEY,
    order_id        INT NOT NULL UNIQUE,
    payment_method  VARCHAR(30),
    -- CASH, CREDIT_CARD, DEBIT_CARD, MOBILE_PAY
    payment_status  VARCHAR(20) DEFAULT 'PENDING',
    -- PENDING, COMPLETED, FAILED, REFUNDED
    amount_paid     DECIMAL(10,2),
    payment_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    transaction_ref VARCHAR(100),
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- ============================================
-- SAMPLE BUSINESS QUERIES
-- ============================================

-- Top selling menu items
SELECT 
    mi.item_name,
    ft.truck_name,
    COUNT(oi.order_item_id)     AS times_ordered,
    SUM(oi.quantity)            AS total_quantity_sold,
    SUM(oi.subtotal)            AS total_revenue
FROM order_items oi
JOIN menu_item mi ON oi.item_id = mi.item_id
JOIN food_truck ft ON mi.truck_id = ft.truck_id
GROUP BY mi.item_name, ft.truck_name
ORDER BY total_revenue DESC
LIMIT 10;

-- Revenue by location
SELECT
    l.location_name,
    l.city,
    COUNT(DISTINCT o.order_id)  AS total_orders,
    SUM(p.amount_paid)          AS total_revenue,
    AVG(p.amount_paid)          AS avg_order_value
FROM orders o
JOIN schedule s ON o.schedule_id = s.schedule_id
JOIN location l ON s.location_id = l.location_id
JOIN payment p ON o.order_id = p.order_id
WHERE p.payment_status = 'COMPLETED'
GROUP BY l.location_name, l.city
ORDER BY total_revenue DESC;

-- Best performing trucks
SELECT
    ft.truck_name,
    ft.cuisine_type,
    COUNT(DISTINCT o.order_id)  AS total_orders,
    SUM(p.amount_paid)          AS total_revenue,
    COUNT(DISTINCT o.customer_id) AS unique_customers
FROM food_truck ft
JOIN orders o ON ft.truck_id = o.truck_id
JOIN payment p ON o.order_id = p.order_id
WHERE p.payment_status = 'COMPLETED'
GROUP BY ft.truck_name, ft.cuisine_type
ORDER BY total_revenue DESC;

-- Daily revenue trend
SELECT
    DATE(o.order_date)          AS order_day,
    COUNT(o.order_id)           AS total_orders,
    SUM(p.amount_paid)          AS daily_revenue
FROM orders o
JOIN payment p ON o.order_id = p.order_id
WHERE p.payment_status = 'COMPLETED'
GROUP BY DATE(o.order_date)
ORDER BY order_day DESC;