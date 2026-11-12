DROP FUNCTION IF EXISTS fn_get_recipe(UUID);
DROP FUNCTION IF EXISTS fn_get_recipe(UUID, UUID);

CREATE OR REPLACE FUNCTION fn_get_recipe(p_recipe_id UUID, p_user_id UUID DEFAULT NULL)
RETURNS TABLE (
    recipe_id UUID,
    title VARCHAR(200),
    description TEXT,
    protein_subtype VARCHAR(50),
    cuisine VARCHAR(50),
    image_url TEXT,
    ingredients JSONB,
    directions JSONB,
    rating INTEGER,
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
        COALESCE(ur.rating, 0) AS rating,
        r.created_at
    FROM recipe AS r
    LEFT JOIN user_recipe AS ur ON ur.recipe_id = r.recipe_id AND ur.user_id = p_user_id
    WHERE r.recipe_id = p_recipe_id;
$$;
