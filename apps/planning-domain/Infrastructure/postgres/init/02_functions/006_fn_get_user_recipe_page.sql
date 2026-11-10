CREATE OR REPLACE FUNCTION fn_get_user_recipe_page(
    p_user_id UUID,
    p_start_index INTEGER,
    p_page_size INTEGER
)
RETURNS TABLE (
    user_id UUID,
    recipe_id UUID,
    associated_at TIMESTAMPTZ,
    user_recipe_created_at TIMESTAMPTZ,
    title VARCHAR(200),
    description TEXT,
    protein_subtype VARCHAR(50),
    cuisine VARCHAR(50),
    image_url TEXT,
    ingredients JSONB,
    directions JSONB,
    created_at TIMESTAMPTZ
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        ur.user_id, ur.recipe_id, ur.associated_at, ur.created_at,
        r.title, r.description, r.protein_subtype, r.cuisine, r.image_url,
        r.ingredients, r.directions, r.created_at
    FROM user_recipe AS ur
    INNER JOIN recipe AS r ON r.recipe_id = ur.recipe_id
    WHERE ur.user_id = p_user_id
    ORDER BY ur.created_at DESC, ur.recipe_id DESC
    OFFSET p_start_index LIMIT p_page_size;
$$;
