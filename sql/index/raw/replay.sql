-- Supports finding the newest replay already collected, where each collection run stops paging.
CREATE INDEX replay_uploaded_at_idx ON raw.replay (uploaded_at);
