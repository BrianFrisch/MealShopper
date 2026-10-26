import { useState } from 'react';
import { Check, ChefHat, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import type { RecipeCardDto, RecipeIngredientDto } from '../types/mealPlan';

interface RecipeCardProps {
  recipe: RecipeCardDto;
  index: number;
  onToggleKeep: (recipeId: string) => void;
  onRegenerate: (recipeId: string) => void;
}

const IngredientDetails = ({ ingredient }: { ingredient: RecipeIngredientDto }) => (
  <li className="min-w-0 break-words rounded-lg border border-stone-100 bg-white p-3">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <span className="font-medium text-stone-800">{ingredient.name}</span>
      {ingredient.dealPriceDescription && (
        <span className="text-sm font-semibold text-[#1E7538]">
          {ingredient.dealPriceDescription}
        </span>
      )}
    </div>
    <p className="mt-1 text-sm text-stone-500">{ingredient.amountDescription}</p>
    {ingredient.storeName && (
      <p className="mt-1 text-xs font-medium text-stone-500">{ingredient.storeName}</p>
    )}
  </li>
);

export const RecipeCard = ({
  recipe,
  index,
  onToggleKeep,
  onRegenerate
}: RecipeCardProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <article className="w-full min-w-0 max-w-full overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
      <button
        type="button"
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded(expanded => !expanded)}
        className="flex w-full items-center gap-3 p-3.5 text-left transition hover:bg-stone-50 sm:gap-4 sm:p-5"
      >
        <span className="flex h-8 w-8 sm:h-9 sm:w-9 shrink-0 items-center justify-center rounded-full bg-[#1E7538] text-xs sm:text-sm font-bold text-white">
          {index + 1}
        </span>

        {recipe.thumbnailUrl ? (
          <img
            src={recipe.thumbnailUrl}
            alt=""
            className="h-14 w-16 sm:h-16 sm:w-20 shrink-0 rounded-lg object-cover"
          />
        ) : (
          <span className="flex h-14 w-16 sm:h-16 sm:w-20 shrink-0 items-center justify-center rounded-lg bg-stone-100 text-stone-400">
            <ChefHat aria-hidden="true" className="h-6 w-6 sm:h-8 sm:w-8" />
          </span>
        )}

        <span className="min-w-0 flex-1">
          <span className="flex min-w-0 flex-wrap items-center gap-1.5 sm:gap-2">
            <span className="min-w-0 max-w-full truncate text-sm sm:text-base font-bold text-stone-900">{recipe.recipeTitle}</span>
            {recipe.proteinSubtype && (
              <span className="rounded-full bg-green-50 px-2 py-0.5 text-[11px] sm:text-xs font-semibold text-[#1E7538]">
                {recipe.proteinSubtype}
              </span>
            )}
          </span>
          <span className="mt-0.5 sm:mt-1 block truncate text-xs sm:text-sm text-stone-500">{recipe.description}</span>
        </span>

        <span
          className={`shrink-0 max-w-[130px] sm:max-w-[200px] truncate rounded-full px-2.5 py-1 text-[11px] sm:text-xs font-semibold ${
            recipe.isKept
              ? 'bg-emerald-100 text-emerald-800'
              : 'bg-stone-100 text-stone-600'
          }`}
          title={recipe.isKept && recipe.mealPlanName ? `Added to ${recipe.mealPlanName}` : undefined}
        >
          {recipe.isKept
            ? (recipe.mealPlanName ? `Added • ${recipe.mealPlanName}` : 'Added')
            : 'Pending'}
        </span>
        <span className="shrink-0 text-stone-500">
          {isExpanded
            ? <ChevronUp aria-hidden="true" className="h-5 w-5" />
            : <ChevronDown aria-hidden="true" className="h-5 w-5" />}
        </span>
      </button>

      {isExpanded && (
        <div className="border-t border-stone-200 p-3.5 sm:p-6">
          {recipe.thumbnailUrl && (
            <img
              src={recipe.thumbnailUrl}
              alt={recipe.recipeTitle}
              className="mb-4 sm:mb-6 max-h-96 w-full rounded-xl object-cover"
            />
          )}

          <div className="grid grid-cols-1 gap-4 sm:gap-6 md:grid-cols-2 [&>section]:min-w-0">
            <section>
              <h3 className="mb-2.5 sm:mb-3 text-sm sm:text-base font-bold text-stone-900">
                Promotional Deals &amp; Fresh Ingredients
              </h3>
              {recipe.ingredientsWithDeals.length > 0 ? (
                <ul className="space-y-2">
                  {recipe.ingredientsWithDeals.map((ingredient, ingredientIndex) => (
                    <IngredientDetails
                      key={`${ingredient.name}-${ingredientIndex}`}
                      ingredient={ingredient}
                    />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-stone-500">No promotional ingredients listed.</p>
              )}
            </section>

            <section>
              <h3 className="mb-2.5 sm:mb-3 text-sm sm:text-base font-bold text-stone-900">Pantry Staples</h3>
              {recipe.pantryIngredients.length > 0 ? (
                <ul className="space-y-2">
                  {recipe.pantryIngredients.map((ingredient, ingredientIndex) => (
                    <IngredientDetails
                      key={`${ingredient.name}-${ingredientIndex}`}
                      ingredient={ingredient}
                    />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-stone-500">No pantry staples listed.</p>
              )}
            </section>
          </div>

          <section className="mt-5 sm:mt-6">
            <h3 className="mb-2.5 sm:mb-3 text-sm sm:text-base font-bold text-stone-900">Preparation Steps</h3>
            <ol className="space-y-2.5 sm:space-y-3">
              {recipe.instructions.map((instruction, instructionIndex) => (
                <li key={`${instructionIndex}-${instruction}`} className="flex gap-3 text-sm text-stone-700">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-stone-100 text-xs font-bold text-stone-700">
                    {instructionIndex + 1}
                  </span>
                  <span className="min-w-0 break-words pt-0.5">{instruction}</span>
                </li>
              ))}
            </ol>
          </section>

          <div className="mt-5 sm:mt-6 flex flex-col sm:flex-row flex-wrap [&>button]:max-w-full gap-2.5 sm:gap-3 border-t border-stone-100 pt-4 sm:pt-5">
            {recipe.isKept ? (
              <span
                role="status"
                className="inline-flex items-center justify-center sm:justify-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm font-semibold text-emerald-800"
              >
                <Check aria-hidden="true" className="h-4 w-4 shrink-0" />
                <span>
                  {recipe.mealPlanName
                    ? `Added to meal plan (${recipe.mealPlanName})`
                    : 'Added to meal plan'}
                </span>
              </span>
            ) : (
              <button
                type="button"
                onClick={() => onToggleKeep(recipe.recipeId)}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#1E7538] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-green-800"
              >
                <Check aria-hidden="true" className="h-4 w-4 shrink-0" />
                <span>Add Recipe to Meal Plan</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => onRegenerate(recipe.recipeId)}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-stone-100 px-4 py-2.5 text-sm font-semibold text-stone-700 transition hover:bg-stone-200"
            >
              <RefreshCw aria-hidden="true" className="h-4 w-4 shrink-0" />
              <span>Regenerate This Meal</span>
            </button>
          </div>
        </div>
      )}
    </article>
  );
};
