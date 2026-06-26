CREATE INDEX IF NOT EXISTS papers_verified_citations_year_idx 
ON papers (verified, citation_count DESC, year DESC);

CREATE TABLE IF NOT EXISTS paper_stats (
    paper_type TEXT PRIMARY KEY,
    total_count INTEGER DEFAULT 0
);

-- Reset in case it already has data
DELETE FROM paper_stats;

INSERT INTO paper_stats (paper_type, total_count) 
SELECT coalesce(paper_type, 'Other'), count(*) 
FROM papers 
WHERE verified = 1 
GROUP BY 1;

DROP TRIGGER IF EXISTS update_stats_after_insert;
CREATE TRIGGER update_stats_after_insert 
AFTER INSERT ON papers WHEN NEW.verified = 1 BEGIN
    INSERT INTO paper_stats (paper_type, total_count) 
    VALUES (coalesce(NEW.paper_type, 'Other'), 1)
    ON CONFLICT(paper_type) DO UPDATE SET total_count = total_count + 1;
END;

DROP TRIGGER IF EXISTS update_stats_after_delete;
CREATE TRIGGER update_stats_after_delete 
AFTER DELETE ON papers WHEN OLD.verified = 1 BEGIN
    UPDATE paper_stats 
    SET total_count = total_count - 1 
    WHERE paper_type = coalesce(OLD.paper_type, 'Other');
END;

DROP TRIGGER IF EXISTS update_stats_after_update;
CREATE TRIGGER update_stats_after_update 
AFTER UPDATE ON papers 
WHEN OLD.verified != NEW.verified OR coalesce(OLD.paper_type, 'Other') != coalesce(NEW.paper_type, 'Other') BEGIN
    -- Decrement old if it was verified
    UPDATE paper_stats SET total_count = total_count - 1 
    WHERE paper_type = coalesce(OLD.paper_type, 'Other') AND OLD.verified = 1;
    
    -- Increment new if it is verified
    INSERT INTO paper_stats (paper_type, total_count) 
    VALUES (coalesce(NEW.paper_type, 'Other'), 1)
    ON CONFLICT(paper_type) DO UPDATE SET total_count = total_count + 1
    WHERE NEW.verified = 1;
END;
