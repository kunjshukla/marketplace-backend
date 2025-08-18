-- First identify the files we have (replace with your actual file list if needed)
WITH image_files AS (
  SELECT unnest(ARRAY[
    '/images/1.png',
    '/images/2.png',
    '/images/3.png',
    '/images/4.png',
    '/images/5.png',
    '/images/6.png',
    '/images/7.png',
    '/images/8.png',
    '/images/9.png',
    '/images/10.png',
    '/images/generated-image-1.png',
    '/images/generated-image-3.png',
    '/images/generated-image-4.png',
    '/images/generated-image-5.png',
    '/images/generated-image-6.png',
    '/images/generated-image-7.png',
    '/images/generated-image-8.png',
    '/images/generated-image-9.png',
    '/images/generated-image-10.png',
    '/images/generated-image-11.png',
    '/images/generated-image-12.png',
    '/images/generated-image-13.png',
    '/images/generated-image-14.png',
    '/images/generated-image-15.png',
    '/images/generated-image-16.png',
    '/images/generated-image-17.png',
    '/images/generated-image-18.png',
    '/images/generated-image-19.png',
    '/images/generated-image-20.png',
    '/images/generated-image-21.png'
  ]) AS filename
),

-- Keep only the latest entry for each image file path
latest_entries AS (
  SELECT DISTINCT ON (image_url) 
    id,
    image_url,
    created_at,
    title,
    description
  FROM nfts
  WHERE image_url IN (SELECT filename FROM image_files)
  ORDER BY image_url, created_at DESC
),

-- Delete all duplicate entries (keeping only the latest for each image)
to_delete AS (
  DELETE FROM nfts 
  WHERE id NOT IN (SELECT id FROM latest_entries) 
    AND image_url IN (SELECT filename FROM image_files)
  RETURNING id
)

-- Return the number of deleted rows
SELECT count(*) AS deleted_duplicates FROM to_delete;
