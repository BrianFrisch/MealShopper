CREATE OR REPLACE PROCEDURE sp_remove_user_recipe(
    p_user_id UUID,
    p_recipe_id UUID
)
LANGUAGE SQL
AS $$
    DELETE FROM user_recipe
    WHERE user_id = p_user_id
      AND recipe_id = p_recipe_id;
$$;
