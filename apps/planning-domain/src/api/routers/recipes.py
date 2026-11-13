from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.params import Depends as DependsType

from dependencies import get_recipe_service, resolve_request_user_id
from src.models import AddRecipeTagsRequest, PlannedMeal, UpdateRecipeRatingRequest
from src.recipe_tags import normalize_recipe_tag
from src.services.recipe_service import RecipeService

router = APIRouter(prefix="/v1/planner/recipes", tags=["Recipes"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_recipe(
    request: PlannedMeal,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    recipes: RecipeService = Depends(get_recipe_service),
) -> dict[str, str]:
    if isinstance(recipes, DependsType):
        recipes = get_recipe_service()
    user_id = resolve_request_user_id(x_user_id)
    recipe_id = await recipes.create_recipe(request, user_id)
    return {"recipe_id": str(recipe_id)}


@router.get("")
@router.get("/", include_in_schema=False)
async def list_user_recipes(
    start_index: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    tag: Optional[str] = Query(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    recipes: RecipeService = Depends(get_recipe_service),
) -> dict[str, object]:
    if isinstance(recipes, DependsType) or recipes is None:
        recipes = get_recipe_service()

    user_id = resolve_request_user_id(x_user_id)
    if tag:
        normalized_tag = normalize_recipe_tag(tag)
        recipes_page, total_count = await recipes.get_user_recipe_page(
            user_id, start_index, page_size, tag=normalized_tag
        )
    else:
        recipes_page, total_count = await recipes.get_user_recipe_page(
            user_id, start_index, page_size
        )
    return {"recipes": recipes_page, "total_count": total_count}


@router.get("/tags")
@router.get("/tags/", include_in_schema=False)
async def list_user_recipe_tags(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    recipes: RecipeService = Depends(get_recipe_service),
) -> list[dict[str, object]]:
    if isinstance(recipes, DependsType) or recipes is None:
        recipes = get_recipe_service()

    user_id = resolve_request_user_id(x_user_id)
    return await recipes.get_user_recipe_tags(user_id)


get_user_recipe_tags = list_user_recipe_tags


@router.get("/{recipe_id}")
async def get_recipe_by_id(
    recipe_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    recipes: RecipeService = Depends(get_recipe_service),
) -> dict[str, object]:
    if isinstance(recipes, DependsType) or recipes is None:
        recipes = get_recipe_service()

    user_id = resolve_request_user_id(x_user_id)
    recipe = await recipes.get_recipe_for_user(recipe_id, user_id)
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe {recipe_id} not found.",
        )
    return dict(recipe)


@router.delete("/{recipe_id}")
async def remove_user_recipe(
    recipe_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    recipes: RecipeService = Depends(get_recipe_service),
) -> dict[str, str]:
    if isinstance(recipes, DependsType) or recipes is None:
        recipes = get_recipe_service()

    user_id = resolve_request_user_id(x_user_id)
    await recipes.remove_user_recipe(user_id, recipe_id)
    return {
        "status": "removed",
        "recipe_id": str(recipe_id),
    }


@router.post("/{recipe_id}/tags")
async def add_recipe_tags(
    recipe_id: UUID,
    request: AddRecipeTagsRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    recipes: RecipeService = Depends(get_recipe_service),
) -> dict[str, object]:
    if isinstance(recipes, DependsType):
        recipes = get_recipe_service()
    user_id = resolve_request_user_id(x_user_id)
    tags = [normalize_recipe_tag(tag) for tag in request.tags]
    if any(not tag or len(tag) > 16 for tag in tags):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Each normalized tag must contain between 1 and 16 characters.",
        )
    tags = list(dict.fromkeys(tags))
    if await recipes.get_recipe_for_user(recipe_id, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recipe {recipe_id} not found.")
    await recipes.add_recipe_tags(user_id, recipe_id, tags)
    return {"recipe_id": str(recipe_id), "tags": tags}


@router.delete("/{recipe_id}/tags/{tag}")
async def remove_recipe_tag(
    recipe_id: UUID,
    tag: str,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    recipes: RecipeService = Depends(get_recipe_service),
) -> dict[str, str]:
    if isinstance(recipes, DependsType):
        recipes = get_recipe_service()
    user_id = resolve_request_user_id(x_user_id)
    normalized_tag = normalize_recipe_tag(tag)
    if not normalized_tag or len(normalized_tag) > 16:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Normalized tag must contain between 1 and 16 characters.",
        )
    if await recipes.get_recipe_for_user(recipe_id, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recipe {recipe_id} not found.")
    await recipes.delete_recipe_tag(user_id, recipe_id, normalized_tag)
    return {
        "status": "removed",
        "recipe_id": str(recipe_id),
        "tag": normalized_tag,
    }


delete_recipe_tag = remove_recipe_tag


@router.put("/{recipe_id}/rating")
@router.patch("/{recipe_id}/rating")
async def update_recipe_rating(
    recipe_id: UUID,
    request: UpdateRecipeRatingRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    recipes: RecipeService = Depends(get_recipe_service),
) -> dict[str, object]:
    if isinstance(recipes, DependsType) or recipes is None:
        recipes = get_recipe_service()

    user_id = resolve_request_user_id(x_user_id)
    await recipes.update_recipe_rating(user_id, recipe_id, request.rating)
    return {
        "status": "updated",
        "recipe_id": str(recipe_id),
        "rating": request.rating,
    }
