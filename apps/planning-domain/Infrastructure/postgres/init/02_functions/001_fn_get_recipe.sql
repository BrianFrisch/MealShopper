DROP FUNCTION IF EXISTS fn_get_recipe(UUID);

CREATE OR REPLACE FUNCTION fn_get_recipe(p_recipe_id UUID)
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
    WHERE r.recipe_id = p_recipe_id;
$$;
