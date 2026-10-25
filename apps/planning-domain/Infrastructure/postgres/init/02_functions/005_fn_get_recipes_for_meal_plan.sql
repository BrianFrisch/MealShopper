CREATE OR REPLACE FUNCTION fn_get_recipes_for_meal_plan(p_meal_plan_id UUID)
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
    INNER JOIN meal_plan_recipe AS mpr ON mpr.recipe_id = r.recipe_id
    WHERE mpr.meal_plan_id = p_meal_plan_id
    ORDER BY mpr.created_at ASC, r.created_at ASC;
$$;
