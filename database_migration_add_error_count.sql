-- Migration: Add error_count column to processing_records
-- Execute this in Supabase SQL Editor if the column is missing

-- Add error_count column if it doesn't exist
ALTER TABLE processing_records 
ADD COLUMN IF NOT EXISTS error_count INTEGER DEFAULT 0;

-- Verify the column was added
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'processing_records'
ORDER BY ordinal_position;
