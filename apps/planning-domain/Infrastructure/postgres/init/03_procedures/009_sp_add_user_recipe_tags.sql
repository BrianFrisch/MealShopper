CREATE OR REPLACE PROCEDURE sp_add_user_recipe_tags(
    p_user_id UUID,
    p_recipe_id UUID,
    p_tags TEXT[]
)
LANGUAGE SQL
AS $$
    INSERT INTO user_recipe_tag (user_id, recipe_id, tag)
    SELECT p_user_id, p_recipe_id, tag
    FROM unnest(p_tags) AS tag
    ON CONFLICT (user_id, recipe_id, tag) DO NOTHING;
$$;
