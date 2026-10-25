DROP PROCEDURE IF EXISTS sp_associate_meal_plan_recipe(UUID, UUID);

CREATE PROCEDURE sp_associate_meal_plan_recipe(
    p_meal_plan_id UUID,
    p_recipe_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    association_rows_inserted INTEGER;
BEGIN
    INSERT INTO meal_plan_recipe (meal_plan_id, recipe_id)
    VALUES (p_meal_plan_id, p_recipe_id)
    ON CONFLICT (meal_plan_id, recipe_id) DO NOTHING;

    GET DIAGNOSTICS association_rows_inserted = ROW_COUNT;
    IF association_rows_inserted = 0 THEN
        RETURN;
    END IF;

    INSERT INTO meal_plan_ingredient (
        meal_plan_id,
        recipe_id,
        ingredient_index,
        deal_id,
        is_promotional,
        ingredient_name,
        ingredient_quantity
    )
    SELECT
        p_meal_plan_id,
        p_recipe_id,
        (ingredients.ordinality - 1)::INTEGER,
        CASE
            WHEN COALESCE((ingredients.ingredient->>'is_promotional')::BOOLEAN, FALSE)
                THEN NULLIF(ingredients.ingredient->>'deal_id', '')
            ELSE NULL
        END,
        COALESCE((ingredients.ingredient->>'is_promotional')::BOOLEAN, FALSE),
        COALESCE(ingredients.ingredient->>'name', ''),
        COALESCE(ingredients.ingredient->>'quantity', '')
    FROM recipe AS r
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(r.ingredients, '[]'::JSONB))
        WITH ORDINALITY AS ingredients(ingredient, ordinality)
    WHERE r.recipe_id = p_recipe_id
    ON CONFLICT (meal_plan_id, recipe_id, ingredient_index) DO NOTHING;
END;
$$;
