-- Backfill user_recipe_tag from recipe cuisine and protein_subtype where data does not already exist
INSERT INTO user_recipe_tag (user_id, recipe_id, tag)
SELECT DISTINCT
    ur.user_id,
    ur.recipe_id,
    candidate.tag
FROM user_recipe AS ur
INNER JOIN recipe AS r ON r.recipe_id = ur.recipe_id
CROSS JOIN LATERAL (
    SELECT LEFT(regexp_replace(LOWER(r.protein_subtype), '[^a-z0-9\-]', '', 'g'), 16) AS tag
    WHERE r.protein_subtype IS NOT NULL
    UNION
    SELECT LEFT(regexp_replace(LOWER(r.cuisine), '[^a-z0-9\-]', '', 'g'), 16) AS tag
    WHERE r.cuisine IS NOT NULL
) AS candidate
WHERE LENGTH(candidate.tag) > 0
ON CONFLICT (user_id, recipe_id, tag) DO NOTHING;
