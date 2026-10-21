export interface MealPlanSynthesisRequest {
  selectedStoreIds: string[];
  selectedDealIds: string[];
  cuisines: string[];
  dietaryPreferences: string[];
  avoidIngredients: string[];
  daysCount: number;
  servingsCount: number;
}

export interface RecipeIngredientDto {
  name: string;
  amountDescription: string;
  storeName?: string | null;
  dealPriceDescription?: string | null;
  isPromotional: boolean;
}

export interface RecipeCardDto {
  recipeId: string;
  recipeTitle: string;
  description: string;
  proteinSubtype?: string;
  thumbnailUrl?: string | null;
  ingredientsWithDeals: RecipeIngredientDto[];
  pantryIngredients: RecipeIngredientDto[];
  instructions: string[];
  isKept: boolean;
}

export interface MealPlanSynthesisResponse {
  mealPlanId: string;
  estimatedTotalTripCost: number;
  recipes: RecipeCardDto[];
}
