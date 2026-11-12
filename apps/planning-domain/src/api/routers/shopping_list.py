from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.params import Depends as DependsType

from dependencies import get_meal_plan_service, get_shopping_list_service
from src.models import (
    AddShoppingListItemRequest,
    MealPlanIngredientResponse,
    RemoveShoppingListItemResponse,
    UpdateIngredientPurchaseRequest,
)
from src.services.meal_plan_service import MealPlanService
from src.services.shopping_list_service import ShoppingListService

router = APIRouter(
    prefix="/v1/planner/meal-plans/{meal_plan_id}/shopping-list",
    tags=["Shopping List"],
)


@router.get(
    "",
    response_model=list[MealPlanIngredientResponse],
)
@router.get(
    "/",
    response_model=list[MealPlanIngredientResponse],
    include_in_schema=False,
)
async def get_meal_plan_shopping_list(
    meal_plan_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    shopping_list: ShoppingListService = Depends(get_shopping_list_service),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> list[MealPlanIngredientResponse]:
    if isinstance(shopping_list, DependsType):
        shopping_list = get_shopping_list_service()
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    stored = await meal_plans.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this meal plan.",
        )
    ingredients = await shopping_list.get_meal_plan_ingredients(meal_plan_id)
    return [MealPlanIngredientResponse(**ingredient) for ingredient in ingredients]


@router.patch(
    "/{ingredient_id}",
    response_model=MealPlanIngredientResponse,
)
async def update_meal_plan_ingredient_purchase(
    meal_plan_id: UUID,
    ingredient_id: UUID,
    request: UpdateIngredientPurchaseRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    shopping_list: ShoppingListService = Depends(get_shopping_list_service),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> MealPlanIngredientResponse:
    if isinstance(shopping_list, DependsType):
        shopping_list = get_shopping_list_service()
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    stored = await meal_plans.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this meal plan.",
        )

    updated = await shopping_list.update_meal_plan_ingredient_purchase(
        meal_plan_id,
        ingredient_id,
        request.is_purchased,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} was not found in meal plan {meal_plan_id}.",
        )

    ingredients = await shopping_list.get_meal_plan_ingredients(meal_plan_id)
    ingredient = next(
        (item for item in ingredients if item["meal_plan_ingredient_id"] == str(ingredient_id)),
        None,
    )
    if ingredient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} was not found in meal plan {meal_plan_id}.",
        )
    return MealPlanIngredientResponse(**ingredient)


@router.post(
    "/items",
    response_model=MealPlanIngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_meal_plan_shopping_list_item(
    meal_plan_id: UUID,
    request: AddShoppingListItemRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    shopping_list: ShoppingListService = Depends(get_shopping_list_service),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> MealPlanIngredientResponse:
    if isinstance(shopping_list, DependsType):
        shopping_list = get_shopping_list_service()
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    stored = await meal_plans.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this meal plan.",
        )

    ingredient_name = request.ingredient_name.strip()
    ingredient_quantity = request.ingredient_quantity.strip()
    if not ingredient_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingredient name is required.",
        )
    if not ingredient_quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingredient quantity is required.",
        )

    added = await shopping_list.add_shopping_list_item(
        meal_plan_id=meal_plan_id,
        ingredient_name=ingredient_name,
        ingredient_quantity=ingredient_quantity,
    )
    if added is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to add shopping list item.",
        )
    return MealPlanIngredientResponse(**added)


@router.delete(
    "/items/{ingredient_id}",
    response_model=RemoveShoppingListItemResponse,
)
async def remove_meal_plan_shopping_list_item(
    meal_plan_id: UUID,
    ingredient_id: UUID,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    shopping_list: ShoppingListService = Depends(get_shopping_list_service),
    meal_plans: MealPlanService = Depends(get_meal_plan_service),
) -> RemoveShoppingListItemResponse:
    if isinstance(shopping_list, DependsType):
        shopping_list = get_shopping_list_service()
    if isinstance(meal_plans, DependsType):
        meal_plans = get_meal_plan_service()

    stored = await meal_plans.get_meal_plan(meal_plan_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {meal_plan_id} not found.",
        )
    if x_user_id and stored["user_id"].lower() != x_user_id.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this meal plan.",
        )

    removal_status = await shopping_list.remove_shopping_list_item(
        meal_plan_id=meal_plan_id,
        ingredient_id=ingredient_id,
    )
    if removal_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient {ingredient_id} was not found in meal plan {meal_plan_id}.",
        )

    return RemoveShoppingListItemResponse(
        status=removal_status,
        meal_plan_ingredient_id=str(ingredient_id),
    )
