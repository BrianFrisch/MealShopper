DROP FUNCTION IF EXISTS fn_get_user_recipe_page(UUID, INTEGER, INTEGER);
DROP FUNCTION IF EXISTS fn_get_user_recipe_page(UUID, INTEGER, INTEGER, VARCHAR(16));
DROP FUNCTION IF EXISTS fn_get_user_recipe_page(UUID, INTEGER, INTEGER, TEXT);

CREATE OR REPLACE FUNCTION fn_get_user_recipe_page(
    p_user_id UUID,
    p_start_index INTEGER,
    p_page_size INTEGER,
    p_tag VARCHAR(16) DEFAULT NULL
)
RETURNS TABLE (
    user_id UUID,
    recipe_id UUID,
    associated_at TIMESTAMPTZ,
    user_recipe_created_at TIMESTAMPTZ,
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
        ur.user_id, ur.recipe_id, ur.associated_at, ur.created_at,
        r.title, r.description, r.protein_subtype, r.cuisine, r.image_url,
        r.ingredients, r.directions, ur.rating, r.created_at,
        ARRAY(
            SELECT urt.tag::TEXT
            FROM user_recipe_tag AS urt
            WHERE urt.user_id = ur.user_id AND urt.recipe_id = ur.recipe_id
            ORDER BY urt.created_at ASC, urt.tag ASC
        ) AS tags
    FROM user_recipe AS ur
    INNER JOIN recipe AS r ON r.recipe_id = ur.recipe_id
    WHERE ur.user_id = p_user_id
      AND (
          p_tag IS NULL
          OR EXISTS (
              SELECT 1
              FROM user_recipe_tag AS urt_filter
              WHERE urt_filter.user_id = ur.user_id
                AND urt_filter.recipe_id = ur.recipe_id
                AND urt_filter.tag = p_tag
          )
      )
    ORDER BY ur.created_at DESC, ur.recipe_id DESC
    OFFSET p_start_index LIMIT p_page_size;
$$;
