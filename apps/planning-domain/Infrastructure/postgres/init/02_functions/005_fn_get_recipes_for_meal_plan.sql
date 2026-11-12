DROP FUNCTION IF EXISTS fn_get_recipes_for_meal_plan(UUID);

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
    rating INTEGER,
    created_at TIMESTAMPTZ,
    tags TEXT[]
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
        r.created_at,
        ARRAY(
            SELECT urt.tag::TEXT
            FROM user_recipe_tag AS urt
            WHERE urt.user_id = mp.user_id AND urt.recipe_id = r.recipe_id
            ORDER BY urt.created_at ASC, urt.tag ASC
        ) AS tags
    FROM recipe AS r
    INNER JOIN meal_plan_recipe AS mpr ON mpr.recipe_id = r.recipe_id
    INNER JOIN meal_plan AS mp ON mp.meal_plan_id = mpr.meal_plan_id
    LEFT JOIN user_recipe AS ur ON ur.recipe_id = r.recipe_id AND ur.user_id = mp.user_id
    WHERE mpr.meal_plan_id = p_meal_plan_id
    ORDER BY mpr.created_at ASC, r.created_at ASC;
$$;
