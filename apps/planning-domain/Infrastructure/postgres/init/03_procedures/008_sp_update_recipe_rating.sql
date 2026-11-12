CREATE OR REPLACE PROCEDURE sp_update_recipe_rating(
    p_user_id UUID,
    p_recipe_id UUID,
    p_rating INTEGER
)
LANGUAGE SQL
AS $$
    INSERT INTO user_recipe (user_id, recipe_id, rating)
    VALUES (p_user_id, p_recipe_id, p_rating)
    ON CONFLICT (user_id, recipe_id)
    DO UPDATE SET rating = EXCLUDED.rating;
$$;
