CREATE OR REPLACE PROCEDURE sp_delete_user_recipe_tag(
    p_user_id UUID,
    p_recipe_id UUID,
    p_tag VARCHAR(16)
)
LANGUAGE SQL
AS $$
    DELETE FROM user_recipe_tag
    WHERE user_id = p_user_id
      AND recipe_id = p_recipe_id
      AND tag = p_tag;
$$;

CREATE OR REPLACE PROCEDURE sp_remove_user_recipe_tag(
    p_user_id UUID,
    p_recipe_id UUID,
    p_tag VARCHAR(16)
)
LANGUAGE SQL
AS $$
    DELETE FROM user_recipe_tag
    WHERE user_id = p_user_id
      AND recipe_id = p_recipe_id
      AND tag = p_tag;
$$;
