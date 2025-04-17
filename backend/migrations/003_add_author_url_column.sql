-- Add author_url column to saved_images table
ALTER TABLE IF EXISTS saved_images ADD COLUMN IF NOT EXISTS author_url TEXT;

-- Add analyzed_posts_count column to channel_analysis table
ALTER TABLE IF EXISTS channel_analysis ADD COLUMN IF NOT EXISTS analyzed_posts_count INTEGER DEFAULT 0;

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_saved_images_author_url ON saved_images(author_url);
CREATE INDEX IF NOT EXISTS idx_channel_analysis_analyzed_posts_count ON channel_analysis(analyzed_posts_count); 