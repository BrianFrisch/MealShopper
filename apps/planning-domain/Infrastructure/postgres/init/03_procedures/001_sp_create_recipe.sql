DROP PROCEDURE IF EXISTS sp_create_recipe(UUID, TEXT, TEXT, JSONB);

CREATE OR REPLACE PROCEDURE sp_create_recipe(
    INOUT p_recipe_id UUID,
    IN p_title VARCHAR(200),
    IN p_description TEXT,
    IN p_protein_subtype VARCHAR(50),
    IN p_cuisine VARCHAR(50),
    IN p_image_url TEXT,
    IN p_ingredients JSONB,
    IN p_directions JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    p_recipe_id := COALESCE(p_recipe_id, gen_random_uuid());

    INSERT INTO recipe (
        recipe_id,
        title,
        description,
        protein_subtype,
        cuisine,
        image_url,
        ingredients,
        directions
    )
    VALUES (
        p_recipe_id,
        p_title,
        p_description,
        p_protein_subtype,
        p_cuisine,
        p_image_url,
        COALESCE(p_ingredients, '[]'::JSONB),
        COALESCE(p_directions, '[]'::JSONB)
    )
    ON CONFLICT (recipe_id)
    DO UPDATE SET
        title = EXCLUDED.title,
        description = EXCLUDED.description,
        protein_subtype = EXCLUDED.protein_subtype,
        cuisine = EXCLUDED.cuisine,
        image_url = EXCLUDED.image_url,
        ingredients = EXCLUDED.ingredients,
        directions = EXCLUDED.directions
    RETURNING recipe_id INTO p_recipe_id;
END;
$$;
