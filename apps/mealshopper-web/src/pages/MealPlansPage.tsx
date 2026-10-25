import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Archive, BookOpen, Calendar, Loader2, ShoppingCart } from 'lucide-react';
import { Header } from '../components/Header';
import { LoginModal } from '../components/LoginModal';
import { authApi } from '../services/authApi';
import { mealPlanApi, type MealPlanRecordDto } from '../services/mealPlanApi';

const getMealPlanTimestamp = (plan: MealPlanRecordDto): number => {
  const dateString = plan.updated_at || plan.created_at;
  if (!dateString) {
    return 0;
  }
  const parsed = Date.parse(dateString);
  return Number.isNaN(parsed) ? 0 : parsed;
};

const sortMealPlansMostRecentFirst = (plans: MealPlanRecordDto[]): MealPlanRecordDto[] =>
  [...plans].sort((a, b) => getMealPlanTimestamp(b) - getMealPlanTimestamp(a));

export const MealPlansPage = () => {
  const [mealPlans, setMealPlans] = useState<MealPlanRecordDto[]>([]);
  const [isLoading, setIsLoading] = useState(() => Boolean(authApi.getToken()));
  const [errorMessage, setErrorMessage] = useState<string | null>(() =>
    authApi.getToken() ? null : 'Please sign in to view your meal plans.'
  );
  const [includeArchived, setIncludeArchived] = useState(false);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [reloadCount, setReloadCount] = useState(0);
  const [updatingMealPlanId, setUpdatingMealPlanId] = useState<string | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const visibleMealPlans = includeArchived
    ? mealPlans
    : mealPlans.filter(plan => !plan.is_archived);

  useEffect(() => {
    const token = authApi.getToken();
    if (!token) {
      return;
    }

    let cancelled = false;
    const fetchPlans = async () => {
      try {
        const plans = await mealPlanApi.getMealPlans(token);
        const enrichedPlans = await Promise.all(
          plans.map(async plan => {
            if (typeof plan.recipe_count === 'number') {
              return plan;
            }
            try {
              const recipes = await mealPlanApi.getMealPlanRecipes(plan.meal_plan_id, token);
              return { ...plan, recipe_count: Array.isArray(recipes) ? recipes.length : 0 };
            } catch {
              return { ...plan, recipe_count: 0 };
            }
          })
        );
        if (!cancelled) {
          setMealPlans(sortMealPlansMostRecentFirst(enrichedPlans));
          setErrorMessage(null);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error ? error.message : 'Unable to load your meal plans.'
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void fetchPlans();
    return () => {
      cancelled = true;
    };
  }, [reloadCount]);

  const handleToggleArchive = async (plan: MealPlanRecordDto) => {
    const token = authApi.getToken();
    if (!token) {
      setArchiveError('Please sign in to update this meal plan.');
      setIsLoginOpen(true);
      return;
    }

    setUpdatingMealPlanId(plan.meal_plan_id);
    setArchiveError(null);
    try {
      const updatedPlan = await mealPlanApi.updateMealPlanArchive(
        plan.meal_plan_id,
        plan.meal_plan_name,
        !plan.is_archived,
        token
      );
      setMealPlans(current => sortMealPlansMostRecentFirst(current.map(currentPlan => (
        currentPlan.meal_plan_id === updatedPlan.meal_plan_id
          ? { ...currentPlan, ...updatedPlan }
          : currentPlan
      ))));
    } catch (error) {
      setArchiveError(
        error instanceof Error ? error.message : 'Unable to update the meal plan archive status.'
      );
    } finally {
      setUpdatingMealPlanId(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFDF9] pb-12 text-stone-900">
      <Header onUserClick={() => setIsLoginOpen(true)} />

      <LoginModal
        isOpen={isLoginOpen}
        onClose={() => setIsLoginOpen(false)}
        onSuccess={() => {
          setIsLoginOpen(false);
          setIsLoading(true);
          setErrorMessage(null);
          setReloadCount(count => count + 1);
        }}
      />

      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-[#1E7538]">
              Saved Plans
            </p>
            <h1 className="mt-1 text-2xl font-extrabold sm:text-3xl">Your Meal Plans</h1>
          </div>
          <Link
            to="/discover"
            className="text-sm font-semibold text-[#1E7538] underline hover:text-green-800"
          >
            ← Back to Discover
          </Link>
        </div>

        <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 pb-4">
            <span className="text-sm font-semibold text-stone-700">
              {isLoading
                ? 'Loading meal plans...'
                : `${visibleMealPlans.length} ${visibleMealPlans.length === 1 ? 'meal plan' : 'meal plans'}`}
            </span>

            <label className="inline-flex cursor-pointer items-center gap-2.5 select-none text-sm font-medium text-stone-700">
              <input
                type="checkbox"
                checked={includeArchived}
                onChange={event => setIncludeArchived(event.target.checked)}
                className="peer sr-only"
              />
              <span
                aria-hidden="true"
                className="relative h-5 w-9 rounded-full bg-stone-300 transition peer-checked:bg-[#1E7538] peer-focus-visible:ring-2 peer-focus-visible:ring-[#1E7538] peer-focus-visible:ring-offset-2 after:absolute after:top-0.5 after:left-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:shadow-xs after:transition-transform peer-checked:after:translate-x-4"
              />
              <span>Include archived meal plans</span>
            </label>
          </div>

          <div className="mt-4">
            {archiveError && (
              <p role="alert" className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                {archiveError}
              </p>
            )}
            {isLoading ? (
              <div
                role="status"
                className="flex items-center justify-center gap-3 rounded-xl border border-stone-100 bg-stone-50/50 p-10 text-stone-600"
              >
                <Loader2 aria-hidden="true" className="h-6 w-6 animate-spin text-[#1E7538]" />
                <span>Loading your meal plans...</span>
              </div>
            ) : errorMessage ? (
              <div
                role="alert"
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
              >
                <span>{errorMessage}</span>
                {!authApi.getToken() && (
                  <button
                    type="button"
                    onClick={() => setIsLoginOpen(true)}
                    className="rounded-lg bg-[#1E7538] px-3.5 py-1.5 text-xs font-bold text-white transition hover:bg-green-800"
                  >
                    Sign In
                  </button>
                )}
              </div>
            ) : visibleMealPlans.length > 0 ? (
              <ul className="divide-y divide-stone-200">
                {visibleMealPlans.map(plan => {
                  const recipeCount = plan.recipe_count ?? 0;
                  return (
                    <li
                      key={plan.meal_plan_id}
                      className="flex flex-col justify-between gap-4 py-4 first:pt-1 last:pb-1 sm:flex-row sm:items-center"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2.5">
                          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-green-50 text-[#1E7538]">
                            <Calendar aria-hidden="true" className="h-4 w-4" />
                          </span>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <h2 className="truncate text-base font-bold text-stone-900 sm:text-lg">
                                {plan.meal_plan_name}
                              </h2>
                              {plan.is_archived && (
                                <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-600">
                                  Archived
                                </span>
                              )}
                            </div>
                            <p className="mt-0.5 text-xs font-medium text-stone-500 sm:text-sm">
                              {recipeCount} {recipeCount === 1 ? 'recipe' : 'recipes'} included
                            </p>
                          </div>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
                        <button
                          type="button"
                          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#1E7538] px-3.5 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-green-800 sm:text-sm"
                        >
                          <BookOpen aria-hidden="true" className="h-4 w-4 shrink-0" />
                          <span>Recipes</span>
                        </button>

                        <button
                          type="button"
                          className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-stone-200 bg-white px-3.5 py-2 text-xs font-semibold text-stone-700 transition hover:bg-stone-50 hover:text-stone-900 sm:text-sm"
                        >
                          <ShoppingCart aria-hidden="true" className="h-4 w-4 shrink-0" />
                          <span>Shopping List</span>
                        </button>

                        <button
                          type="button"
                          disabled={updatingMealPlanId === plan.meal_plan_id}
                          onClick={() => { void handleToggleArchive(plan); }}
                          className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-stone-200 bg-stone-50 px-3.5 py-2 text-xs font-semibold text-stone-600 transition hover:bg-stone-100 hover:text-stone-900 disabled:cursor-wait disabled:opacity-60 sm:text-sm"
                        >
                          {updatingMealPlanId === plan.meal_plan_id ? (
                            <Loader2 aria-hidden="true" className="h-4 w-4 shrink-0 animate-spin" />
                          ) : (
                            <Archive aria-hidden="true" className="h-4 w-4 shrink-0" />
                          )}
                          <span>{plan.is_archived ? 'Unarchive' : 'Archive'}</span>
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="rounded-xl border border-dashed border-stone-300 bg-stone-50/40 p-10 text-center">
                <h2 className="font-semibold text-stone-800">
                  {mealPlans.length > 0 ? 'No active meal plans' : 'No meal plans yet'}
                </h2>
                <p className="mx-auto mt-1 max-w-md text-sm text-stone-500">
                  {mealPlans.length > 0
                    ? 'Turn on “Include archived meal plans” to view archived plans.'
                    : 'Discover local grocery deals and add recipes to a meal plan to see them listed here.'}
                </p>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
};
