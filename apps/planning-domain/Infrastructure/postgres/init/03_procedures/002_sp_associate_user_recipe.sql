CREATE OR REPLACE PROCEDURE sp_associate_user_recipe(
    p_user_id UUID,
    p_recipe_id UUID
)
LANGUAGE SQL
AS $$
    INSERT INTO user_recipe (user_id, recipe_id)
    VALUES (p_user_id, p_recipe_id)
    ON CONFLICT (user_id, recipe_id) DO NOTHING;
$$;
