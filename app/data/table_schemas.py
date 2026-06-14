"""示例大宽表结构定义 — 用于问数Agent的SQL生成"""

TABLE_SCHEMAS = """
-- 用户用量统计表
CREATE TABLE user_usage_stats (
    id BIGINT PRIMARY KEY,
    province VARCHAR(20),        -- 省份（如：广东、北京）
    city VARCHAR(20),            -- 城市
    user_type VARCHAR(20),       -- 用户类型：4G/5G/宽带
    age_group VARCHAR(10),       -- 年龄段：18-25/26-35/36-45/46-60/60+
    monthly_data_gb DECIMAL(10,2),  -- 月均流量(GB)
    monthly_voice_min INT,       -- 月均语音(分钟)
    monthly_sms INT,             -- 月均短信(条)
    stat_month VARCHAR(7)        -- 统计月份(YYYY-MM)
);

-- 用户费用统计表
CREATE TABLE user_fee_stats (
    id BIGINT PRIMARY KEY,
    province VARCHAR(20),
    city VARCHAR(20),
    plan_type VARCHAR(50),       -- 套餐类型（如：畅享套餐、冰淇淋套餐）
    user_type VARCHAR(20),       -- 4G/5G/宽带
    monthly_fee DECIMAL(10,2),   -- 月费(元)
    arpu DECIMAL(10,2),          -- ARPU值(元)
    user_count INT,              -- 用户数
    stat_month VARCHAR(7)
);

-- 套餐订购统计表
CREATE TABLE plan_subscription_stats (
    id BIGINT PRIMARY KEY,
    plan_name VARCHAR(100),      -- 套餐名称
    plan_type VARCHAR(50),       -- 套餐类型
    province VARCHAR(20),
    new_subscribers INT,         -- 新增订购数
    cancel_subscribers INT,      -- 退订数
    total_subscribers INT,       -- 累计订购数
    stat_month VARCHAR(7)
);
"""
