DROP FUNCTION IF EXISTS fn_get_recipes_for_user(UUID);

CREATE OR REPLACE FUNCTION fn_get_recipes_for_user(p_user_id UUID)
RETURNS TABLE (
    recipe_id UUID,
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
        r.recipe_id,
        r.title,
        r.description,
        r.protein_subtype,
        r.cuisine,
        r.image_url,
        r.ingredients,
        r.directions,
        r.created_at
    FROM recipe AS r
    INNER JOIN user_recipe AS ur ON ur.recipe_id = r.recipe_id
    WHERE ur.user_id = p_user_id
    ORDER BY ur.associated_at DESC, r.created_at DESC;
$$;
