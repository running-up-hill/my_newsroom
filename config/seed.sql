-- Starter data. Safe to re-run: every insert ignores rows that already exist.
-- Check each feed URL opens in a browser before relying on it; feeds move.

INSERT OR IGNORE INTO sources (name, feed_url) VALUES
  ('BBC News - Top stories',  'https://feeds.bbci.co.uk/news/rss.xml'),
  ('BBC News - World',        'https://feeds.bbci.co.uk/news/world/rss.xml'),
  ('BBC News - Business',     'https://feeds.bbci.co.uk/news/business/rss.xml'),
  ('BBC News - Science & Environment', 'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml'),
  ('UN News',                 'https://news.un.org/feed/subscribe/en/news/all/rss.xml');

INSERT OR IGNORE INTO topics (slug, name, description) VALUES
  ('energy',         'Energy',         'Oil, gas, power grids, renewables and energy markets'),
  ('sustainability', 'Sustainability', 'Climate, emissions, ESG and the environment'),
  ('war',            'War and conflict', 'Armed conflicts, ceasefires and their humanitarian impact');

INSERT OR IGNORE INTO topic_keywords (topic_id, keyword)
SELECT t.id, k.keyword FROM topics t
JOIN (
  SELECT 'energy' AS slug, 'oil' AS keyword UNION ALL
  SELECT 'energy', 'gas' UNION ALL
  SELECT 'energy', 'renewables' UNION ALL
  SELECT 'energy', 'grid' UNION ALL
  SELECT 'energy', 'electricity' UNION ALL
  SELECT 'energy', 'solar' UNION ALL
  SELECT 'energy', 'nuclear' UNION ALL
  SELECT 'energy', 'wind' UNION ALL
  SELECT 'energy', 'energy' UNION ALL
  SELECT 'energy', 'fuel' UNION ALL
  SELECT 'energy', 'power plant' UNION ALL
  SELECT 'energy', 'fossil' UNION ALL
  SELECT 'sustainability', 'climate*' UNION ALL
  SELECT 'sustainability', 'emissions' UNION ALL
  SELECT 'sustainability', 'net zero' UNION ALL
  SELECT 'sustainability', 'ESG' UNION ALL
  SELECT 'sustainability', 'carbon' UNION ALL
  SELECT 'sustainability', 'biodiversity' UNION ALL
  SELECT 'war', 'war' UNION ALL
  SELECT 'war', 'ceasefire*' UNION ALL
  SELECT 'war', 'troops' UNION ALL
  SELECT 'war', 'missile' UNION ALL
  SELECT 'war', 'airstrike*' UNION ALL
  SELECT 'war', 'iran' UNION ALL
  SELECT 'war', 'ukraine*' UNION ALL
  SELECT 'war', 'drone' UNION ALL
  SELECT 'war', 'conflict' UNION ALL
  SELECT 'war', 'fighting' UNION ALL
  SELECT 'war', 'military' UNION ALL
  SELECT 'war', 'Israel' UNION ALL
  SELECT 'war', 'Israel*' UNION ALL
  SELECT 'war', 'Gaza' UNION ALL
  SELECT 'war', 'West Bank' UNION ALL
  SELECT 'war', 'hostilities' UNION ALL
  SELECT 'war', 'invasion'
) k ON k.slug = t.slug;
