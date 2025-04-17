-- Add author_url column to saved_images table
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'saved_images' AND column_name = 'author_url'
  ) THEN
    ALTER TABLE saved_images ADD COLUMN author_url TEXT;
  END IF;
END $$;

-- Add analyzed_posts_count column to channel_analysis table
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'channel_analysis' AND column_name = 'analyzed_posts_count'
  ) THEN
    ALTER TABLE channel_analysis ADD COLUMN analyzed_posts_count INTEGER DEFAULT 0;
  END IF;
END $$;

-- Create indexes for faster lookups
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_indexes 
    WHERE indexname = 'idx_saved_images_author_url'
  ) THEN
    CREATE INDEX idx_saved_images_author_url ON saved_images(author_url);
  END IF;

  IF NOT EXISTS (
    SELECT FROM pg_indexes 
    WHERE indexname = 'idx_channel_analysis_analyzed_posts_count'
  ) THEN
    CREATE INDEX idx_channel_analysis_analyzed_posts_count ON channel_analysis(analyzed_posts_count);
  END IF;
END $$; 