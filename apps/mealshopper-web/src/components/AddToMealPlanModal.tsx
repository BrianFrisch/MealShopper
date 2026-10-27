import { useEffect, useState } from 'react';
import { CalendarPlus, Check, Loader2, X } from 'lucide-react';
import { authApi } from '../services/authApi';
import { mealPlanApi, type MealPlanRecordDto } from '../services/mealPlanApi';
import type { RecipeCardDto } from '../types/mealPlan';

const formatDefaultMealPlanDate = (date: Date = new Date()) =>
  new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);

interface AddToMealPlanModalProps {
  recipe: RecipeCardDto | null;
  onClose: () => void;
  onAdded: (recipeId: string, mealPlan: MealPlanRecordDto) => void;
}

export const AddToMealPlanModal = ({ recipe, onClose, onAdded }: AddToMealPlanModalProps) => {
  const recipeId = recipe?.recipeId ?? null;
  const [userMealPlans, setUserMealPlans] = useState<MealPlanRecordDto[]>([]);
  const [isLoadingMealPlans, setIsLoadingMealPlans] = useState(false);
  const [newMealPlanName, setNewMealPlanName] = useState(() => formatDefaultMealPlanDate());
  const [selectedExistingMealPlanId, setSelectedExistingMealPlanId] = useState<string | null>(null);
  const [lastUsedMealPlan, setLastUsedMealPlan] = useState<MealPlanRecordDto | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (recipeId === null) {
      return;
    }

    setError(null);
    setNewMealPlanName(formatDefaultMealPlanDate());
    setSelectedExistingMealPlanId(lastUsedMealPlan ? lastUsedMealPlan.meal_plan_id : null);

    const token = authApi.getToken();
    if (!token) {
      setError('Please sign in before adding a recipe to a meal plan.');
      return;
    }

    let cancelled = false;
    setIsLoadingMealPlans(true);
    mealPlanApi.getMealPlans(token)
      .then(fetchedPlans => {
        if (cancelled) return;
        setUserMealPlans(current => {
          const merged = new Map<string, MealPlanRecordDto>();
          for (const plan of [...fetchedPlans, ...current]) {
            merged.set(plan.meal_plan_id, plan);
          }
          return Array.from(merged.values());
        });
      })
      .catch(() => {
        // Keep any in-session meal plans if loading existing plans fails
      })
      .finally(() => {
        if (!cancelled) setIsLoadingMealPlans(false);
      });

    return () => {
      cancelled = true;
    };
    // Only reload when a different recipe is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recipeId]);

  useEffect(() => {
    if (recipeId === null) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isSubmitting) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [recipeId, isSubmitting, onClose]);

  if (recipe === null || recipeId === null) {
    return null;
  }

  const selectedPlan = userMealPlans.find(
    plan => plan.meal_plan_id === selectedExistingMealPlanId
  ) || (lastUsedMealPlan?.meal_plan_id === selectedExistingMealPlanId ? lastUsedMealPlan : null);

  const handleClose = () => {
    if (!isSubmitting) {
      onClose();
    }
  };

  const complete = (mealPlan: MealPlanRecordDto) => {
    setLastUsedMealPlan(mealPlan);
    setUserMealPlans(current => [
      mealPlan,
      ...current.filter(plan => plan.meal_plan_id !== mealPlan.meal_plan_id),
    ]);
    setError(null);
    onAdded(recipeId, mealPlan);
  };

  const handleCreate = async () => {
    const trimmedName = newMealPlanName.trim();
    if (!trimmedName) {
      setError('Please enter a name for the new meal plan.');
      return;
    }
    const token = authApi.getToken();
    if (!token) {
      setError('Please sign in to create a meal plan.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const createdPlan = await mealPlanApi.createMealPlan(trimmedName, token);
      await mealPlanApi.associateRecipeToMealPlan(createdPlan.meal_plan_id, recipeId, token);
      complete(createdPlan);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create meal plan and add recipe.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAssociate = async (plan: MealPlanRecordDto) => {
    const token = authApi.getToken();
    if (!token) {
      setError('Please sign in to add this recipe to a meal plan.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await mealPlanApi.associateRecipeToMealPlan(plan.meal_plan_id, recipeId, token);
      complete(plan);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to add recipe to the selected meal plan.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-to-meal-plan-title"
      className="fixed inset-0 z-50 flex items-end justify-center bg-stone-900/60 p-0 backdrop-blur-xs sm:items-center sm:p-4"
      onClick={handleClose}
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
              <p className="truncate text-xs sm:text-sm text-stone-500">{recipe.recipeTitle}</p>
            </div>
          </div>
          <button
            type="button"
            aria-label="Close modal"
            disabled={isSubmitting}
            onClick={handleClose}
            className="shrink-0 rounded-full p-1.5 text-stone-400 transition hover:bg-stone-100 hover:text-stone-700 disabled:opacity-50"
          >
            <X aria-hidden="true" className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-2.5 text-xs sm:text-sm text-rose-800">
            {error}
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
                  disabled={isSubmitting}
                  onClick={() => { void handleAssociate(selectedPlan); }}
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#1E7538] px-4 py-2 text-xs sm:text-sm font-bold text-white shadow-xs transition hover:bg-green-800 disabled:opacity-50"
                >
                  {isSubmitting ? (
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
                disabled={isSubmitting}
                autoFocus={lastUsedMealPlan === null}
                onChange={event => setNewMealPlanName(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    void handleCreate();
                  }
                }}
                placeholder="e.g. Oct 24, 2026"
                className="min-w-0 flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-900 outline-none focus:border-[#1E7538] focus:ring-2 focus:ring-green-100"
              />
              <button
                type="button"
                disabled={isSubmitting || !newMealPlanName.trim()}
                onClick={() => { void handleCreate(); }}
                className={`inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                  selectedPlan
                    ? 'border border-[#1E7538] bg-white text-[#1E7538] hover:bg-green-50'
                    : 'bg-[#1E7538] text-white shadow-xs hover:bg-green-800'
                }`}
              >
                {isSubmitting && !selectedPlan && (
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
                          disabled={isSubmitting}
                          onClick={event => {
                            event.stopPropagation();
                            void handleAssociate(plan);
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
            disabled={isSubmitting}
            onClick={handleClose}
            className="rounded-lg px-4 py-2 text-sm font-semibold text-stone-600 transition hover:bg-stone-100 hover:text-stone-900 disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};
