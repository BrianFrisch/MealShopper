import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CalendarPlus, Check, ChevronDown, ChevronUp, Loader2, Plus, X } from 'lucide-react';
import { DealImageTooltip } from '../components/DealImageTooltip';
import { Header } from '../components/Header';
import { RecipeCard } from '../components/RecipeCard';
import { authApi } from '../services/authApi';
import { mealPlanApi, type MealPlanRecordDto } from '../services/mealPlanApi';
import type { Deal } from '../types/discovery';
import type { MealPlanSynthesisRequest, RecipeCardDto } from '../types/mealPlan';

const formatDefaultMealPlanDate = (date: Date = new Date()) =>
  new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);

const SELECTED_DEALS_STORAGE_KEY = 'mealshopper_selected_deals';
const DIETARY_REQUIREMENTS = ['Keto', 'Gluten Free', 'Paleo', 'Low FODMAP', 'Mediterranean Diet'];
const CUISINE_OPTIONS = [
  'American', 'Mexican', 'Italian', 'Chinese', 'Thai', 'Indian', 'Mediterranean',
  'Japanese', 'Korean', 'Greek', 'Tex-Mex', 'Jamaican', 'Cuban', 'Vietnamese',
  'Filipino', 'Hawaiian', 'Middle Eastern', 'Spanish', 'French', 'Nordic', 'Barbecue'
];
const COLLAPSED_CUISINE_COUNT = 8;

interface StoredDealsState {
  deals: Deal[];
  error: string | null;
}

const readStoredDeals = (): StoredDealsState => {
  try {
    const storedDeals = localStorage.getItem(SELECTED_DEALS_STORAGE_KEY);
    if (storedDeals === null) {
      return { deals: [], error: null };
    }
    const parsedDeals: unknown = JSON.parse(storedDeals);
    if (!Array.isArray(parsedDeals)) {
      throw new Error('Stored deal selections are not a list.');
    }
    return { deals: parsedDeals as Deal[], error: null };
  } catch (error) {
    return {
      deals: [],
      error: error instanceof Error
        ? `Unable to restore selected deals: ${error.message}`
        : 'Unable to restore selected deals.'
    };
  }
};

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

const getDealKey = (deal: Deal) => (
  deal.deal_id || deal.dealId ||
  `${deal.store_id || deal.storeId || ''}:${deal.item_name || deal.itemName || deal.clean_name || ''}:${deal.deal_price ?? deal.dealPrice ?? ''}:${deal.unit || ''}`
);

const getDealStoreKey = (deal: Deal) => (
  deal.store_id || deal.storeId || deal.store_name || deal.storeName || ''
);

const getDealTitle = (deal: Deal) => (
  deal.item_name || deal.itemName || deal.clean_name || deal.cleanName || 'Unnamed item'
);

const getDealPrice = (deal: Deal) => Number(deal.deal_price ?? deal.dealPrice ?? 0);

const formatCurrency = (amount: number) => new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD'
}).format(amount);

const delay = (milliseconds: number) => new Promise(resolve => window.setTimeout(resolve, milliseconds));

export const MealPlanningPage = () => {
  const navigate = useNavigate();
  const [storedDealsState, setStoredDealsState] = useState(readStoredDeals);
  const { deals: selectedDeals } = storedDealsState;
  const [initialRequirements] = useState(readStoredRequirements);
  const [dietaryPreferences, setDietaryPreferences] = useState<string[]>(initialRequirements.dietaryPreferences);
  const [cuisines, setCuisines] = useState<string[]>(initialRequirements.cuisines);
  const [showAllCuisines, setShowAllCuisines] = useState(false);
  const [avoidIngredients, setAvoidIngredients] = useState<string[]>(initialRequirements.avoidIngredients);
  const [ingredientInput, setIngredientInput] = useState('');
  const [servingsCount, setServingsCount] = useState(initialRequirements.servingsCount);
  const [isDealsCollapsed, setIsDealsCollapsed] = useState(false);
  const [isRequirementsCollapsed, setIsRequirementsCollapsed] = useState(false);
  const [recipes, setRecipes] = useState<RecipeCardDto[]>([]);
  const [estimatedTotalTripCost, setEstimatedTotalTripCost] = useState(0);
  const [generationJob, setGenerationJob] = useState<{ jobId: string; token: string } | null>(null);
  const [completedJobId, setCompletedJobId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Add Recipe to Meal Plan modal state
  const [modalRecipeId, setModalRecipeId] = useState<string | null>(null);
  const [userMealPlans, setUserMealPlans] = useState<MealPlanRecordDto[]>([]);
  const [isLoadingMealPlans, setIsLoadingMealPlans] = useState(false);
  const [newMealPlanName, setNewMealPlanName] = useState(() => formatDefaultMealPlanDate());
  const [selectedExistingMealPlanId, setSelectedExistingMealPlanId] = useState<string | null>(null);
  const [lastUsedMealPlan, setLastUsedMealPlan] = useState<MealPlanRecordDto | null>(null);
  const [isSubmittingModal, setIsSubmittingModal] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const storeCount = new Set(selectedDeals.map(getDealStoreKey).filter(Boolean)).size;
  const keptRecipeCount = recipes.filter(recipe => recipe.isKept).length;
  const isGenerating = generationJob !== null;
  const visibleCuisineOptions = showAllCuisines
    ? CUISINE_OPTIONS
    : CUISINE_OPTIONS.filter((option, index) => (
      index < COLLAPSED_CUISINE_COUNT || cuisines.includes(option)
    ));

  useEffect(() => {
    if (modalRecipeId === null) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isSubmittingModal) {
        setModalRecipeId(null);
        setModalError(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [modalRecipeId, isSubmittingModal]);

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
              throw new Error('Meal plan generation completed without a result.');
            }
            setRecipes(status.result.recipes.map((recipe, index) => ({
              ...recipe,
              recipeId: recipe.recipeId || `${status.result?.mealPlanId}-${index + 1}`,
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
            setEstimatedTotalTripCost(status.result.estimatedTotalTripCost);
            setCompletedJobId(generationJob.jobId);
            setGenerationJob(null);
            return;
          }
          if (status.status === 'Failed') {
            throw new Error(status.errorMessage || 'Meal plan generation failed.');
          }
          await delay(2500);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : 'Unable to generate a meal plan.');
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

  const removeSelectedDeal = (dealToRemove: Deal) => {
    const nextDeals = selectedDeals.filter(deal => getDealKey(deal) !== getDealKey(dealToRemove));
    localStorage.setItem(SELECTED_DEALS_STORAGE_KEY, JSON.stringify(nextDeals));
    setStoredDealsState({ deals: nextDeals, error: null });
  };

  const handleGenerate = async () => {
    setErrorMessage(null);
    if (selectedDeals.length === 0) {
      return;
    }

    try {
      localStorage.setItem(PLANNING_REQUIREMENTS_STORAGE_KEY, JSON.stringify({
        dietaryPreferences, cuisines, avoidIngredients, servingsCount
      }));
    } catch {
      // Persistence is best-effort; generation should still proceed.
    }

    const selectedDealLookups = selectedDeals.flatMap(deal => {
      const dealId = deal.deal_id || deal.dealId;
      const storeId = deal.store_id || deal.storeId;
      return dealId && storeId ? [{ dealId, storeId }] : [];
    });
    if (selectedDealLookups.length !== selectedDeals.length) {
      setErrorMessage('Some selected deals are missing a deal or store ID. Return to Discover and select the deals again.');
      return;
    }

    const token = authApi.getToken();
    if (!token) {
      setErrorMessage('Please sign in before generating a meal plan.');
      return;
    }

    const request: MealPlanSynthesisRequest = {
      selectedStoreIds: [...new Set(selectedDealLookups.map(lookup => lookup.storeId))],
      selectedDealIds: [...new Set(selectedDealLookups.map(({ dealId, storeId }) => (
        dealId.startsWith(`${storeId}_`) ? dealId : `${storeId}_${dealId}`
      )))],
      cuisines,
      dietaryPreferences,
      avoidIngredients,
      daysCount: selectedDeals.length,
      servingsCount
    };

    setRecipes([]);
    setEstimatedTotalTripCost(0);
    setCompletedJobId(null);
    setIsDealsCollapsed(true);
    setIsRequirementsCollapsed(true);
    try {
      const { jobId } = await mealPlanApi.startGeneration(request, token);
      setGenerationJob({ jobId, token });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to start meal plan generation.');
    }
  };

  const handleOpenAddToMealPlanModal = async (recipeId: string) => {
    const targetRecipe = recipes.find(recipe => recipe.recipeId === recipeId);
    if (!targetRecipe || targetRecipe.isKept) {
      return;
    }

    const token = authApi.getToken();
    if (!token) {
      setErrorMessage('Please sign in before adding a recipe to a meal plan.');
      return;
    }

    setModalRecipeId(recipeId);
    setModalError(null);
    setNewMealPlanName(formatDefaultMealPlanDate());
    setSelectedExistingMealPlanId(lastUsedMealPlan ? lastUsedMealPlan.meal_plan_id : null);

    setIsLoadingMealPlans(true);
    try {
      const fetchedPlans = await mealPlanApi.getMealPlans(token);
      setUserMealPlans(current => {
        const merged = new Map<string, MealPlanRecordDto>();
        for (const plan of [...fetchedPlans, ...current]) {
          merged.set(plan.meal_plan_id, plan);
        }
        return Array.from(merged.values());
      });
    } catch {
      // Keep any in-session meal plans if loading existing plans fails
    } finally {
      setIsLoadingMealPlans(false);
    }
  };

  const handleCloseMealPlanModal = () => {
    if (isSubmittingModal) {
      return;
    }
    setModalRecipeId(null);
    setModalError(null);
  };

  const completeRecipeAssociation = (recipeId: string, mealPlan: MealPlanRecordDto) => {
    setLastUsedMealPlan(mealPlan);
    setUserMealPlans(current => [
      mealPlan,
      ...current.filter(plan => plan.meal_plan_id !== mealPlan.meal_plan_id),
    ]);
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
    setModalError(null);
  };

  const handleCreateAndAssociateMealPlan = async () => {
    if (!modalRecipeId) {
      return;
    }
    const trimmedName = newMealPlanName.trim();
    if (!trimmedName) {
      setModalError('Please enter a name for the new meal plan.');
      return;
    }

    const token = authApi.getToken();
    if (!token) {
      setModalError('Please sign in to create a meal plan.');
      return;
    }

    setIsSubmittingModal(true);
    setModalError(null);
    try {
      const createdPlan = await mealPlanApi.createMealPlan(trimmedName, token);
      await mealPlanApi.associateRecipeToMealPlan(
        createdPlan.meal_plan_id,
        modalRecipeId,
        token
      );
      completeRecipeAssociation(modalRecipeId, createdPlan);
    } catch (error) {
      setModalError(
        error instanceof Error
          ? error.message
          : 'Unable to create meal plan and add recipe.'
      );
    } finally {
      setIsSubmittingModal(false);
    }
  };

  const handleAssociateWithExistingMealPlan = async (plan: MealPlanRecordDto) => {
    if (!modalRecipeId) {
      return;
    }

    const token = authApi.getToken();
    if (!token) {
      setModalError('Please sign in to add this recipe to a meal plan.');
      return;
    }

    setIsSubmittingModal(true);
    setModalError(null);
    try {
      await mealPlanApi.associateRecipeToMealPlan(
        plan.meal_plan_id,
        modalRecipeId,
        token
      );
      completeRecipeAssociation(modalRecipeId, plan);
    } catch (error) {
      setModalError(
        error instanceof Error
          ? error.message
          : 'Unable to add recipe to the selected meal plan.'
      );
    } finally {
      setIsSubmittingModal(false);
    }
  };

  const handleSave = async () => {
    if (!completedJobId) {
      setErrorMessage('Generate a meal plan before saving it.');
      return;
    }
    const token = authApi.getToken();
    if (!token) {
      setErrorMessage('Please sign in before saving your meal plan.');
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    try {
      await mealPlanApi.confirmMealPlan(
        completedJobId,
        recipes.filter(recipe => recipe.isKept).map(recipe => recipe.recipeId),
        token
      );
      navigate(`/shopping-list/${completedJobId}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to save the meal plan.');
      setIsSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFDF9] pb-36 text-stone-900">
      <Header />
      <main className="mx-auto max-w-7xl space-y-8 px-4 py-8">
        <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-lg font-bold tracking-wide text-stone-900">
                YOUR SELECTED DEALS ({selectedDeals.length} Items across {storeCount} Stores)
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <Link
                to="/discover"
                className="font-semibold text-[#1E7538] underline hover:text-green-800"
              >
                ← Back to Discover
              </Link>
              <button
                type="button"
                aria-expanded={!isDealsCollapsed}
                aria-label={isDealsCollapsed ? 'Expand selected deals' : 'Collapse selected deals'}
                onClick={() => setIsDealsCollapsed(collapsed => !collapsed)}
                className="rounded-full p-1.5 text-stone-500 transition hover:bg-stone-100"
              >
                {isDealsCollapsed
                  ? <ChevronDown aria-hidden="true" className="h-5 w-5" />
                  : <ChevronUp aria-hidden="true" className="h-5 w-5" />}
              </button>
            </div>
          </div>

          {isDealsCollapsed ? null : selectedDeals.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-stone-200 text-xs uppercase tracking-wide text-stone-500">
                  <tr>
                    <th className="px-3 py-2">Del</th>
                    <th className="px-3 py-2">Store</th>
                    <th className="px-3 py-2">Subtype</th>
                    <th className="px-3 py-2">Item Name</th>
                    <th className="px-3 py-2">Price / Unit</th>
                    <th className="px-3 py-2">Image</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {selectedDeals.map(deal => {
                    const title = getDealTitle(deal);
                    return (
                      <tr key={getDealKey(deal)} className="align-middle">
                        <td className="px-3 py-3">
                          <button
                            type="button"
                            aria-label={`Remove ${title}`}
                            onClick={() => removeSelectedDeal(deal)}
                            className="rounded px-2 text-lg font-bold leading-none text-rose-600 hover:bg-rose-50"
                          >
                            ×
                          </button>
                        </td>
                        <td className="px-3 py-3 font-medium text-stone-800">
                          {deal.store_name || deal.storeName || 'Unknown store'}
                        </td>
                        <td className="px-3 py-3">
                          <span className="rounded-full bg-green-50 px-2 py-1 text-xs font-semibold text-[#1E7538]">
                            {deal.protein_subtype || 'Other'}
                          </span>
                        </td>
                        <td className="px-3 py-3 font-medium text-stone-800">{title}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-stone-700">
                          {formatCurrency(getDealPrice(deal))} / {deal.unit || 'each'}
                        </td>
                        <td className="px-3 py-3">
                          <DealImageTooltip imageUrl={deal.image_url} itemName={title} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-stone-500">
              No deals selected. <Link to="/discover" className="font-semibold text-[#1E7538] underline">Discover deals</Link> to start planning.
            </p>
          )}
        </section>

        {storedDealsState.error && (
          <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            {storedDealsState.error}
          </p>
        )}
        {errorMessage && (
          <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            {errorMessage}
          </p>
        )}

        <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(300px,0.85fr)_minmax(0,1.5fr)]">
          <section className="min-w-0 space-y-6 rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-stone-900">Planning Requirements</h2>
                <p className="mt-1 text-sm text-stone-500">Personalize your meals before the chef gets started.</p>
              </div>
              <button
                type="button"
                aria-expanded={!isRequirementsCollapsed}
                aria-label={isRequirementsCollapsed ? 'Expand planning requirements' : 'Collapse planning requirements'}
                onClick={() => setIsRequirementsCollapsed(collapsed => !collapsed)}
                className="shrink-0 rounded-full p-1.5 text-stone-500 transition hover:bg-stone-100"
              >
                {isRequirementsCollapsed
                  ? <ChevronDown aria-hidden="true" className="h-5 w-5" />
                  : <ChevronUp aria-hidden="true" className="h-5 w-5" />}
              </button>
            </div>

            <div className={isRequirementsCollapsed ? 'hidden' : 'space-y-6'}>
            <fieldset>
              <legend className="mb-3 text-sm font-bold text-stone-800">Dietary Requirements</legend>
              <div className="flex flex-wrap gap-2">
                {DIETARY_REQUIREMENTS.map(option => (
                  <button
                    type="button"
                    key={option}
                    aria-pressed={dietaryPreferences.includes(option)}
                    onClick={() => toggleOption(option, dietaryPreferences, setDietaryPreferences)}
                    className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
                      dietaryPreferences.includes(option)
                        ? 'border-[#1E7538] bg-green-50 text-[#1E7538]'
                        : 'border-stone-200 bg-white text-stone-600 hover:border-stone-400'
                    }`}
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
                    className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
                      cuisines.includes(option)
                        ? 'border-[#1E7538] bg-green-50 text-[#1E7538]'
                        : 'border-stone-200 bg-white text-stone-600 hover:border-stone-400'
                    }`}
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
            </div>

            <button
              type="button"
              disabled={selectedDeals.length === 0 || isGenerating}
              onClick={handleGenerate}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#E66E1D] px-4 py-3 font-bold text-white shadow-sm transition hover:bg-[#d25f12] disabled:cursor-not-allowed disabled:bg-stone-300"
            >
              {isGenerating && <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />}
              {isGenerating ? 'Generating Meal Plan...' : 'Generate Meal Plan'}
            </button>
          </section>

          <section className="min-w-0 space-y-4">
            <div>
              <h2 className="text-2xl font-bold text-stone-900">Chef-Synthesized Meals</h2>
              <p className="mt-1 text-sm text-stone-500">Choose which recipes you want to keep in your plan.</p>
            </div>

            {isGenerating ? (
              <div role="status" className="space-y-4 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3 text-[#1E7538]">
                  <Loader2 aria-hidden="true" className="h-6 w-6 animate-spin" />
                  <span className="font-semibold">The chef is building your personalized meal plan...</span>
                </div>
                {[0, 1, 2].map(item => (
                  <div key={item} className="h-24 animate-pulse rounded-xl bg-stone-100" />
                ))}
              </div>
            ) : recipes.length > 0 ? (
              recipes.map((recipe, index) => (
                <RecipeCard
                  key={recipe.recipeId}
                  recipe={recipe}
                  index={index}
                  onToggleKeep={recipeId => { void handleOpenAddToMealPlanModal(recipeId); }}
                  onRegenerate={() => { void handleGenerate(); }}
                />
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-stone-300 bg-white p-10 text-center">
                <h3 className="font-semibold text-stone-800">Your meal ideas will appear here</h3>
                <p className="mx-auto mt-2 max-w-md text-sm text-stone-500">
                  Choose your dietary needs, favorite cuisines, and meal size, then generate a plan grounded in your selected deals.
                </p>
              </div>
            )}
          </section>
        </div>
      </main>

      {modalRecipeId !== null && (() => {
        const modalRecipe = recipes.find(recipe => recipe.recipeId === modalRecipeId);
        const selectedPlan = userMealPlans.find(
          plan => plan.meal_plan_id === selectedExistingMealPlanId
        ) || (lastUsedMealPlan?.meal_plan_id === selectedExistingMealPlanId ? lastUsedMealPlan : null);

        return (
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-to-meal-plan-title"
            className="fixed inset-0 z-50 flex items-end justify-center bg-stone-900/60 p-0 backdrop-blur-xs sm:items-center sm:p-4"
            onClick={handleCloseMealPlanModal}
          >
            <div
              className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-stone-200 bg-white p-4 sm:p-6 shadow-2xl"
              onClick={event => event.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-3 border-b border-stone-100 pb-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="shrink-0 rounded-xl bg-[#1E7538]/10 p-2 text-[#1E7538]">
                    <CalendarPlus aria-hidden="true" className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <h2 id="add-to-meal-plan-title" className="text-base sm:text-lg font-bold text-stone-900">
                      Add Recipe to Meal Plan
                    </h2>
                    {modalRecipe && (
                      <p className="truncate text-xs sm:text-sm text-stone-500">
                        {modalRecipe.recipeTitle}
                      </p>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  aria-label="Close modal"
                  disabled={isSubmittingModal}
                  onClick={handleCloseMealPlanModal}
                  className="shrink-0 rounded-full p-1.5 text-stone-400 transition hover:bg-stone-100 hover:text-stone-700 disabled:opacity-50"
                >
                  <X aria-hidden="true" className="h-5 w-5" />
                </button>
              </div>

              {modalError && (
                <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-2.5 text-xs sm:text-sm text-rose-800">
                  {modalError}
                </p>
              )}

              <div className="mt-4 space-y-5">
                {selectedPlan && (
                  <div className="rounded-xl border border-[#1E7538]/30 bg-green-50/70 p-3.5">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                      <div className="min-w-0">
                        <span className="block text-[11px] font-semibold uppercase tracking-wider text-[#1E7538]">
                          Selected Meal Plan
                        </span>
                        <span className="block truncate text-sm sm:text-base font-bold text-stone-900">
                          {selectedPlan.meal_plan_name}
                        </span>
                      </div>
                      <button
                        type="button"
                        disabled={isSubmittingModal}
                        onClick={() => { void handleAssociateWithExistingMealPlan(selectedPlan); }}
                        className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#1E7538] px-4 py-2 text-xs sm:text-sm font-bold text-white shadow-xs transition hover:bg-green-800 disabled:opacity-50"
                      >
                        {isSubmittingModal ? (
                          <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                        ) : (
                          <Check aria-hidden="true" className="h-4 w-4" />
                        )}
                        <span>Add to "{selectedPlan.meal_plan_name}"</span>
                      </button>
                    </div>
                  </div>
                )}

                <div>
                  <label
                    htmlFor="new-meal-plan-name"
                    className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-stone-600"
                  >
                    Create New Meal Plan
                  </label>
                  <div className="flex flex-col xs:flex-row sm:flex-row gap-2">
                    <input
                      id="new-meal-plan-name"
                      type="text"
                      value={newMealPlanName}
                      disabled={isSubmittingModal}
                      autoFocus={lastUsedMealPlan === null}
                      onChange={event => setNewMealPlanName(event.target.value)}
                      onKeyDown={event => {
                        if (event.key === 'Enter') {
                          event.preventDefault();
                          void handleCreateAndAssociateMealPlan();
                        }
                      }}
                      placeholder="e.g. Oct 24, 2026"
                      className="min-w-0 flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-900 outline-none focus:border-[#1E7538] focus:ring-2 focus:ring-green-100"
                    />
                    <button
                      type="button"
                      disabled={isSubmittingModal || !newMealPlanName.trim()}
                      onClick={() => { void handleCreateAndAssociateMealPlan(); }}
                      className={`inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                        selectedPlan
                          ? 'border border-[#1E7538] bg-white text-[#1E7538] hover:bg-green-50'
                          : 'bg-[#1E7538] text-white shadow-xs hover:bg-green-800'
                      }`}
                    >
                      {isSubmittingModal && !selectedPlan && (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      )}
                      <span>Create</span>
                    </button>
                  </div>
                </div>

                <div>
                  <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-stone-600">
                    Existing Meal Plans
                  </span>
                  {isLoadingMealPlans && userMealPlans.length === 0 ? (
                    <div className="flex items-center justify-center gap-2 rounded-xl border border-stone-200 py-6 text-xs sm:text-sm text-stone-500">
                      <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin text-[#1E7538]" />
                      <span>Loading your meal plans...</span>
                    </div>
                  ) : userMealPlans.length > 0 ? (
                    <ul className="max-h-52 divide-y divide-stone-100 overflow-y-auto rounded-xl border border-stone-200">
                      {userMealPlans.map(plan => {
                        const isSelected = selectedExistingMealPlanId === plan.meal_plan_id;
                        const isRecent = lastUsedMealPlan?.meal_plan_id === plan.meal_plan_id;

                        return (
                          <li key={plan.meal_plan_id}>
                            <div
                              onClick={() => setSelectedExistingMealPlanId(plan.meal_plan_id)}
                              className={`flex cursor-pointer items-center justify-between gap-2 px-3 py-2.5 text-left transition ${
                                isSelected ? 'bg-green-50/80' : 'hover:bg-stone-50'
                              }`}
                            >
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="truncate text-sm font-semibold text-stone-900">
                                    {plan.meal_plan_name}
                                  </span>
                                  {isRecent && (
                                    <span className="shrink-0 rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-bold text-[#1E7538]">
                                      Recent
                                    </span>
                                  )}
                                </div>
                              </div>
                              <button
                                type="button"
                                disabled={isSubmittingModal}
                                onClick={event => {
                                  event.stopPropagation();
                                  void handleAssociateWithExistingMealPlan(plan);
                                }}
                                className="shrink-0 rounded-lg bg-[#1E7538] px-3 py-1.5 text-xs font-bold text-white transition hover:bg-green-800 disabled:opacity-50"
                              >
                                Select
                              </button>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="rounded-xl border border-dashed border-stone-200 px-3 py-4 text-center text-xs sm:text-sm text-stone-500">
                      No existing meal plans yet. Create one above to get started.
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-5 flex justify-end border-t border-stone-100 pt-3.5">
                <button
                  type="button"
                  disabled={isSubmittingModal}
                  onClick={handleCloseMealPlanModal}
                  className="rounded-lg px-4 py-2 text-sm font-semibold text-stone-600 transition hover:bg-stone-100 hover:text-stone-900 disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {recipes.length > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-stone-200 bg-white/95 shadow-[0_-8px_24px_rgba(28,25,23,0.08)] backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4">
            <div>
              <p className="font-bold text-stone-900">
                {keptRecipeCount} of {recipes.length} meals kept
              </p>
              <p className="text-sm text-stone-500">
                Estimated trip cost: {formatCurrency(estimatedTotalTripCost)}
              </p>
            </div>
            <button
              type="button"
              disabled={keptRecipeCount === 0 || isSaving}
              onClick={() => { void handleSave(); }}
              className="rounded-full bg-[#1E7538] px-6 py-3 font-bold text-white shadow-sm transition hover:bg-green-800 disabled:cursor-not-allowed disabled:bg-stone-300"
            >
              {isSaving ? 'Saving Meal Plan...' : 'Save & Complete Meal Plan'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
