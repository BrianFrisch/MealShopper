import { useEffect, useState } from 'react';
import { Loader2, Plus, X } from 'lucide-react';
import { AddToMealPlanModal } from '../components/AddToMealPlanModal';
import { Header } from '../components/Header';
import { RecipeCard } from '../components/RecipeCard';
import { authApi } from '../services/authApi';
import { mealPlanApi, type MealPlanRecordDto } from '../services/mealPlanApi';
import type { MealPlanSynthesisRequest, RecipeCardDto } from '../types/mealPlan';

const DIETARY_REQUIREMENTS = ['Keto', 'Gluten Free', 'Paleo', 'Low FODMAP', 'Mediterranean Diet'];
const CUISINE_OPTIONS = [
  'American', 'Mexican', 'Italian', 'Chinese', 'Thai', 'Indian', 'Mediterranean',
  'Japanese', 'Korean', 'Greek', 'Tex-Mex', 'Jamaican', 'Cuban', 'Vietnamese',
  'Filipino', 'Hawaiian', 'Middle Eastern', 'Spanish', 'French', 'Nordic', 'Barbecue'
];
const COLLAPSED_CUISINE_COUNT = 8;
// Shared with the Meal Planning page so preferences carry over between pages.
const PLANNING_REQUIREMENTS_STORAGE_KEY = 'mealshopper_planning_requirements';

interface StoredPlanningRequirements {
  dietaryPreferences: string[];
  cuisines: string[];
  avoidIngredients: string[];
  servingsCount: number;
}

const toStringArray = (value: unknown): string[] => (
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
);

const readStoredRequirements = (): StoredPlanningRequirements => {
  const defaults: StoredPlanningRequirements = {
    dietaryPreferences: [], cuisines: [], avoidIngredients: [], servingsCount: 4
  };
  try {
    const raw = localStorage.getItem(PLANNING_REQUIREMENTS_STORAGE_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Partial<Record<keyof StoredPlanningRequirements, unknown>> | null;
    if (!parsed || typeof parsed !== 'object') return defaults;
    const servings = Number(parsed.servingsCount);
    return {
      dietaryPreferences: toStringArray(parsed.dietaryPreferences),
      cuisines: toStringArray(parsed.cuisines),
      avoidIngredients: toStringArray(parsed.avoidIngredients),
      servingsCount: Number.isFinite(servings) && servings > 0 ? servings : defaults.servingsCount
    };
  } catch {
    return defaults;
  }
};

const delay = (milliseconds: number) => new Promise(resolve => window.setTimeout(resolve, milliseconds));

export const CustomRecipePage = () => {
  const [initialRequirements] = useState(readStoredRequirements);
  const [mainIngredient, setMainIngredient] = useState('');
  const [dietaryPreferences, setDietaryPreferences] = useState<string[]>(initialRequirements.dietaryPreferences);
  const [cuisines, setCuisines] = useState<string[]>(initialRequirements.cuisines);
  const [showAllCuisines, setShowAllCuisines] = useState(false);
  const [avoidIngredients, setAvoidIngredients] = useState<string[]>(initialRequirements.avoidIngredients);
  const [ingredientInput, setIngredientInput] = useState('');
  const [servingsCount, setServingsCount] = useState(initialRequirements.servingsCount);
  const [recipes, setRecipes] = useState<RecipeCardDto[]>([]);
  const [generationJob, setGenerationJob] = useState<{ jobId: string; token: string } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [modalRecipeId, setModalRecipeId] = useState<string | null>(null);

  const isGenerating = generationJob !== null;
  const trimmedMainIngredient = mainIngredient.trim();
  const visibleCuisineOptions = showAllCuisines
    ? CUISINE_OPTIONS
    : CUISINE_OPTIONS.filter((option, index) => (
      index < COLLAPSED_CUISINE_COUNT || cuisines.includes(option)
    ));
  const modalRecipe = recipes.find(recipe => recipe.recipeId === modalRecipeId) ?? null;

  useEffect(() => {
    if (!generationJob) {
      return;
    }

    let cancelled = false;
    const pollForGeneration = async () => {
      try {
        while (!cancelled) {
          const status = await mealPlanApi.pollGeneration(generationJob.jobId, generationJob.token);
          if (status.status === 'Completed') {
            if (!status.result) {
              throw new Error('Recipe generation completed without a result.');
            }
            const mealPlanId = status.result.mealPlanId;
            setRecipes(status.result.recipes.map((recipe, index) => ({
              ...recipe,
              recipeId: recipe.recipeId || `${mealPlanId}-${index + 1}`,
              isKept: recipe.isKept ?? false,
              ingredientsWithDeals: recipe.ingredientsWithDeals.map(ingredient => ({
                ...ingredient,
                isPromotional: ingredient.isPromotional ?? true
              })),
              pantryIngredients: recipe.pantryIngredients.map(ingredient => ({
                ...ingredient,
                isPromotional: ingredient.isPromotional ?? false
              }))
            })));
            setGenerationJob(null);
            return;
          }
          if (status.status === 'Failed') {
            throw new Error(status.errorMessage || 'Recipe generation failed.');
          }
          await delay(2500);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : 'Unable to generate a recipe.');
          setGenerationJob(null);
        }
      }
    };

    void pollForGeneration();
    return () => {
      cancelled = true;
    };
  }, [generationJob]);

  const toggleOption = (
    option: string,
    selectedOptions: string[],
    updateOptions: (options: string[]) => void
  ) => {
    updateOptions(selectedOptions.includes(option)
      ? selectedOptions.filter(selected => selected !== option)
      : [...selectedOptions, option]);
  };

  const addAvoidIngredient = (value: string) => {
    const ingredients = value.split(/[,\n]/).map(ingredient => ingredient.trim()).filter(Boolean);
    if (ingredients.length > 0) {
      setAvoidIngredients(current => {
        const existing = new Set(current.map(ingredient => ingredient.toLowerCase()));
        return [...current, ...ingredients.filter(ingredient => {
          const key = ingredient.toLowerCase();
          if (existing.has(key)) {
            return false;
          }
          existing.add(key);
          return true;
        })];
      });
    }
    setIngredientInput('');
  };

  const handleGenerate = async () => {
    setErrorMessage(null);
    if (!trimmedMainIngredient || isGenerating) {
      return;
    }

    try {
      localStorage.setItem(PLANNING_REQUIREMENTS_STORAGE_KEY, JSON.stringify({
        dietaryPreferences, cuisines, avoidIngredients, servingsCount
      }));
    } catch {
      // Persistence is best-effort; generation should still proceed.
    }

    const token = authApi.getToken();
    if (!token) {
      setErrorMessage('Please sign in before generating a recipe.');
      return;
    }

    const request: MealPlanSynthesisRequest = {
      selectedStoreIds: [],
      selectedDealIds: [],
      mainIngredient: trimmedMainIngredient,
      cuisines,
      dietaryPreferences,
      avoidIngredients,
      daysCount: 1,
      servingsCount
    };

    setRecipes([]);
    try {
      const { jobId } = await mealPlanApi.startGeneration(request, token);
      setGenerationJob({ jobId, token });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to start recipe generation.');
    }
  };

  const handleRecipeAdded = (recipeId: string, mealPlan: MealPlanRecordDto) => {
    setRecipes(current => current.map(recipe => (
      recipe.recipeId === recipeId
        ? {
            ...recipe,
            isKept: true,
            mealPlanId: mealPlan.meal_plan_id,
            mealPlanName: mealPlan.meal_plan_name,
          }
        : recipe
    )));
    setModalRecipeId(null);
  };

  const handleOpenModal = (recipeId: string) => {
    const target = recipes.find(recipe => recipe.recipeId === recipeId);
    if (target && !target.isKept) {
      setModalRecipeId(recipeId);
    }
  };

  const chipClass = (selected: boolean) => `rounded-full border px-3 py-1.5 text-sm font-medium transition ${
    selected
      ? 'border-[#1E7538] bg-green-50 text-[#1E7538]'
      : 'border-stone-200 bg-white text-stone-600 hover:border-stone-400'
  }`;

  return (
    <div className="min-h-screen bg-[#FDFDF9] pb-16 text-stone-900">
      <Header />
      <main className="mx-auto max-w-7xl space-y-8 px-4 py-8">
        <h1 className="text-lg font-bold tracking-wide text-stone-900">CUSTOM RECIPE</h1>

        {errorMessage && (
          <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            {errorMessage}
          </p>
        )}

        <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(300px,0.85fr)_minmax(0,1.5fr)]">
          <section className="min-w-0 space-y-6 rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
            <div>
              <h2 className="text-xl font-bold text-stone-900">Recipe Requirements</h2>
              <p className="mt-1 text-sm text-stone-500">Tell the chef what to build the meal around.</p>
            </div>

            <div>
              <label htmlFor="main-ingredient" className="mb-2 block text-sm font-bold text-stone-800">
                Main ingredient
              </label>
              <input
                id="main-ingredient"
                value={mainIngredient}
                onChange={event => setMainIngredient(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    void handleGenerate();
                  }
                }}
                maxLength={200}
                placeholder="e.g. Chicken thighs"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-[#1E7538] focus:ring-2 focus:ring-green-100"
              />
            </div>

            <fieldset>
              <legend className="mb-3 text-sm font-bold text-stone-800">Dietary Requirements</legend>
              <div className="flex flex-wrap gap-2">
                {DIETARY_REQUIREMENTS.map(option => (
                  <button
                    type="button"
                    key={option}
                    aria-pressed={dietaryPreferences.includes(option)}
                    onClick={() => toggleOption(option, dietaryPreferences, setDietaryPreferences)}
                    className={chipClass(dietaryPreferences.includes(option))}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend className="mb-3 text-sm font-bold text-stone-800">Cuisines to Include</legend>
              <div className="flex flex-wrap gap-2">
                {visibleCuisineOptions.map(option => (
                  <button
                    type="button"
                    key={option}
                    aria-pressed={cuisines.includes(option)}
                    onClick={() => toggleOption(option, cuisines, setCuisines)}
                    className={chipClass(cuisines.includes(option))}
                  >
                    {option}
                  </button>
                ))}
              </div>
              {CUISINE_OPTIONS.length > COLLAPSED_CUISINE_COUNT && (
                <button
                  type="button"
                  aria-expanded={showAllCuisines}
                  onClick={() => setShowAllCuisines(current => !current)}
                  className="mt-3 text-sm font-semibold text-[#1E7538] underline hover:text-green-800"
                >
                  {showAllCuisines ? 'Show Less' : 'Show More'}
                </button>
              )}
            </fieldset>

            <div>
              <label htmlFor="avoid-ingredients" className="mb-2 block text-sm font-bold text-stone-800">
                Ingredients to Avoid
              </label>
              <div className="flex gap-2">
                <input
                  id="avoid-ingredients"
                  value={ingredientInput}
                  onChange={event => setIngredientInput(event.target.value)}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ',') {
                      event.preventDefault();
                      addAvoidIngredient(ingredientInput);
                    }
                  }}
                  placeholder="Type an ingredient and press Enter"
                  className="min-w-0 flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-[#1E7538] focus:ring-2 focus:ring-green-100"
                />
                <button
                  type="button"
                  aria-label="Add ingredient to avoid"
                  onClick={() => addAvoidIngredient(ingredientInput)}
                  className="rounded-lg bg-stone-100 px-3 text-stone-700 hover:bg-stone-200"
                >
                  <Plus aria-hidden="true" className="h-5 w-5" />
                </button>
              </div>
              {avoidIngredients.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-2">
                  {avoidIngredients.map(ingredient => (
                    <li key={ingredient}>
                      <button
                        type="button"
                        onClick={() => setAvoidIngredients(current => current.filter(item => item !== ingredient))}
                        className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-3 py-1 text-sm text-stone-700 hover:bg-stone-200"
                      >
                        {ingredient}
                        <X aria-hidden="true" className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <label htmlFor="servings-count" className="mb-2 block text-sm font-bold text-stone-800">
                Servings per Meal
              </label>
              <select
                id="servings-count"
                value={servingsCount}
                onChange={event => setServingsCount(Number(event.target.value))}
                className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8].map(count => <option key={count} value={count}>{count}</option>)}
              </select>
            </div>

            <button
              type="button"
              disabled={!trimmedMainIngredient || isGenerating}
              onClick={() => { void handleGenerate(); }}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#E66E1D] px-4 py-3 font-bold text-white shadow-sm transition hover:bg-[#d25f12] disabled:cursor-not-allowed disabled:bg-stone-300"
            >
              {isGenerating && <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />}
              {isGenerating ? 'Generating Meal...' : 'Generate Meal'}
            </button>
          </section>

          <section className="min-w-0 space-y-4">
            <div>
              <h2 className="text-2xl font-bold text-stone-900">Chef-Synthesized Meal</h2>
              <p className="mt-1 text-sm text-stone-500">Add the recipe to a meal plan or regenerate it.</p>
            </div>

            {isGenerating ? (
              <div role="status" className="space-y-4 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3 text-[#1E7538]">
                  <Loader2 aria-hidden="true" className="h-6 w-6 animate-spin" />
                  <span className="font-semibold">The chef is building your custom recipe...</span>
                </div>
                <div className="h-24 animate-pulse rounded-xl bg-stone-100" />
              </div>
            ) : recipes.length > 0 ? (
              recipes.map((recipe, index) => (
                <RecipeCard
                  key={recipe.recipeId}
                  recipe={recipe}
                  index={index}
                  onToggleKeep={handleOpenModal}
                  onRegenerate={() => { void handleGenerate(); }}
                />
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-stone-300 bg-white p-10 text-center">
                <h3 className="font-semibold text-stone-800">Your recipe will appear here</h3>
                <p className="mx-auto mt-2 max-w-md text-sm text-stone-500">
                  Enter a main ingredient, set your preferences, and generate a custom meal.
                </p>
              </div>
            )}
          </section>
        </div>
      </main>

      <AddToMealPlanModal
        recipe={modalRecipe}
        onClose={() => setModalRecipeId(null)}
        onAdded={handleRecipeAdded}
      />
    </div>
  );
};
