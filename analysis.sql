-- ============================================================================
-- analysis.sql  --  the six questions, in teaching order.
--
-- Runs against readmissions.db (built by clean.py). Tables:
--   hrrp       one row per hospital per condition (cleaned)
--   hospitals  one row per hospital (cleaned, has star_rating, ownership)
--   joined     hrrp INNER JOIN hospitals on facility_id
--
-- Key fact to keep straight: excess_readmission_ratio (ERR) is a RATIO.
--   ERR > 1.0  = MORE readmissions than expected for that patient mix = worse
--   ERR < 1.0  = fewer than expected = better
-- Reading it backwards would invert every finding below.
--
-- The "-- QUERY:" lines are read by run_analysis.py to run each query and name
-- its CSV export. You can also paste any block straight into DB Browser.
-- ============================================================================


-- QUERY: q1 | How many hospitals, and how many rows per condition? | export=-
-- Teaches COUNT, GROUP BY, DISTINCT. The DISTINCT matters: the file has one
-- row per hospital PER condition, so COUNT(*) would be ~4-6x the hospital count.
SELECT
    condition,
    COUNT(*)                        AS rows_for_condition,
    COUNT(DISTINCT facility_id)     AS distinct_hospitals
FROM hrrp
GROUP BY condition
ORDER BY rows_for_condition DESC;


-- QUERY: q2 | Which conditions have the worst average readmission ratio? | export=readmission_by_condition.csv
-- Teaches AVG + ORDER BY. Suppressed rows are NULL and AVG ignores them, but we
-- filter explicitly so the intent is obvious. Worst (highest ERR) at the top.
SELECT
    condition,
    ROUND(AVG(excess_readmission_ratio), 4) AS avg_excess_readmission_ratio,
    COUNT(*)                                AS hospitals_measured
FROM hrrp
WHERE excess_readmission_ratio IS NOT NULL
GROUP BY condition
ORDER BY avg_excess_readmission_ratio DESC;


-- QUERY: q3 | Which states perform best and worst? | export=readmission_by_state.csv
-- Teaches GROUP BY with a filter on sample size. States with very few hospitals
-- produce extreme averages, so we require at least 10 distinct hospitals.
-- Lower average ERR = better, so this is ordered best-first.
SELECT
    state,
    ROUND(AVG(excess_readmission_ratio), 4) AS avg_excess_readmission_ratio,
    COUNT(DISTINCT facility_id)             AS distinct_hospitals
FROM hrrp
WHERE excess_readmission_ratio IS NOT NULL
GROUP BY state
HAVING COUNT(DISTINCT facility_id) >= 10   -- sample-size threshold (chosen: 10)
ORDER BY avg_excess_readmission_ratio ASC;


-- QUERY: q4 | Do bigger hospitals (more discharges) do better or worse? | export=readmission_by_size.csv
-- Teaches CASE WHEN to bucket a continuous number into size bands, then compare.
SELECT
    CASE
        WHEN number_of_discharges < 100  THEN '1. Small (<100)'
        WHEN number_of_discharges < 300  THEN '2. Medium (100-299)'
        WHEN number_of_discharges < 600  THEN '3. Large (300-599)'
        ELSE                                   '4. Very large (600+)'
    END                                       AS size_band,
    ROUND(AVG(excess_readmission_ratio), 4)   AS avg_excess_readmission_ratio,
    COUNT(*)                                  AS rows_measured
FROM hrrp
WHERE excess_readmission_ratio IS NOT NULL
  AND number_of_discharges IS NOT NULL
GROUP BY size_band
ORDER BY size_band;


-- QUERY: q5 | Does ownership type matter? | export=readmission_by_ownership.csv
-- The FIRST join: HRRP (the ratio) + hospitals (the ownership). Practise
-- explaining this one: every row in hrrp that has a matching facility_id in
-- hospitals is kept; rows with no match are dropped (that is the inner join).
SELECT
    g.hospital_ownership,
    ROUND(AVG(h.excess_readmission_ratio), 4) AS avg_excess_readmission_ratio,
    COUNT(DISTINCT h.facility_id)             AS distinct_hospitals
FROM hrrp h
JOIN hospitals g ON h.facility_id = g.facility_id
WHERE h.excess_readmission_ratio IS NOT NULL
GROUP BY g.hospital_ownership
HAVING COUNT(DISTINCT h.facility_id) >= 10
ORDER BY avg_excess_readmission_ratio ASC;


-- QUERY: q6 | Do higher-star-rated hospitals readmit fewer patients? | export=readmission_by_star.csv
-- THE HEADLINE. Join star rating to readmission ratio, group by star, handle
-- nulls (hospitals with no star rating are excluded, not treated as 0).
-- If avg ERR falls as stars rise, CMS's quality rating predicts the outcome
-- it is meant to capture. Whichever way it comes out, it is a finding.
SELECT
    g.star_rating,
    ROUND(AVG(h.excess_readmission_ratio), 4) AS avg_excess_readmission_ratio,
    COUNT(DISTINCT h.facility_id)             AS distinct_hospitals
FROM hrrp h
JOIN hospitals g ON h.facility_id = g.facility_id
WHERE h.excess_readmission_ratio IS NOT NULL
  AND g.star_rating IS NOT NULL
GROUP BY g.star_rating
ORDER BY g.star_rating ASC;
