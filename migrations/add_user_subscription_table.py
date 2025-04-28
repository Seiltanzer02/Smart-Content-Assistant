"""
from yoyo import step

__depends__ = {}

steps = [
    step(
        """
        CREATE TABLE IF NOT EXISTS user_subscription (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id int8 NOT NULL,
            start_date timestamptz NOT NULL DEFAULT NOW(),
            end_date timestamptz NOT NULL,
            is_active bool NOT NULL DEFAULT TRUE,
            payment_id TEXT,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW()
        )
        """,
        """
        DROP TABLE IF EXISTS user_subscription
        """
    ),
    step(
        """
        CREATE TABLE IF NOT EXISTS user_usage_stats (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id int8 NOT NULL,
            analysis_count int4 NOT NULL DEFAULT 0,
            post_generation_count int4 NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW()
        )
        """,
        """
        DROP TABLE IF EXISTS user_usage_stats
        """
    ),
]
""" 