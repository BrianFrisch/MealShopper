DROP FUNCTION IF EXISTS fn_get_user_recipe_tags(UUID);

CREATE OR REPLACE FUNCTION fn_get_user_recipe_tags(p_user_id UUID)
RETURNS TABLE (
    tag VARCHAR(16),
    recipe_count INTEGER
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        urt.tag,
        COUNT(urt.recipe_id)::INTEGER AS recipe_count
    FROM user_recipe_tag AS urt
    WHERE urt.user_id = p_user_id
    GROUP BY urt.tag
    ORDER BY recipe_count DESC, urt.tag ASC;
$$;
