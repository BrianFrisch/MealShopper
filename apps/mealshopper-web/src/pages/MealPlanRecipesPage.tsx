import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ChefHat, Loader2, Printer } from 'lucide-react';
import { Header } from '../components/Header';
import { LoginModal } from '../components/LoginModal';
import { authApi } from '../services/authApi';
import { mealPlanApi, type MealPlanRecipeDto } from '../services/mealPlanApi';

export const MealPlanRecipesPage = () => {
  const { recipeId } = useParams<{ recipeId: string }>();
  const hasToken = Boolean(authApi.getToken());
  const [recipe, setRecipe] = useState<MealPlanRecipeDto | null>(null);
  const [isLoading, setIsLoading] = useState(() => Boolean(recipeId && hasToken));
  const [errorMessage, setErrorMessage] = useState<string | null>(() => (
    !recipeId
      ? 'A recipe ID is required to load this recipe.'
      : hasToken
        ? null
        : 'Please sign in to view this recipe.'
  ));
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    const token = authApi.getToken();
    if (!recipeId || !token) {
      return;
    }

    let cancelled = false;
    const loadRecipe = async () => {
      try {
        const result = await mealPlanApi.getRecipe(recipeId, token);
        if (!cancelled) {
          setRecipe(result);
          setErrorMessage(null);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error ? error.message : 'Unable to load this recipe.'
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadRecipe();
    return () => {
      cancelled = true;
    };
  }, [recipeId, reloadCount]);

  return (
    <div className="recipe-page min-h-screen bg-[#FDFDF9] pb-12 text-stone-900">
      <div className="print:hidden">
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
      </div>

      <main className="recipe-page__content mx-auto max-w-6xl space-y-6 px-4 py-8 sm:py-10">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold uppercase tracking-wide text-[#1E7538]">
              Recipe
            </p>
            <h1 className="mt-1 break-words text-2xl font-extrabold sm:text-3xl">
              {recipe?.title ?? 'Recipe'}
            </h1>
          </div>
          <div className="flex items-center gap-4 print:hidden">
            {recipe && (
              <button
                type="button"
                onClick={() => window.print()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#1E7538] px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-green-800"
              >
                <Printer aria-hidden="true" className="h-4 w-4" />
                Print Recipe
              </button>
            )}
            <Link
              to="/meal-plans"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#1E7538] underline hover:text-green-800"
            >
              <ArrowLeft aria-hidden="true" className="h-4 w-4" />
              Back to Meal Plans
            </Link>
          </div>
        </div>

        {isLoading ? (
          <div
            role="status"
            className="flex items-center justify-center gap-3 rounded-2xl border border-stone-200 bg-white p-12 text-stone-600"
          >
            <Loader2 aria-hidden="true" className="h-6 w-6 animate-spin text-[#1E7538]" />
            Loading recipe...
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
        ) : recipe ? (
          <article className="recipe-page__card overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
                {recipe.image_url && (
                  <img
                    src={recipe.image_url}
                    alt=""
                    className="recipe-page__image h-48 w-full object-cover sm:h-56"
                  />
                )}
                <div className="p-4 sm:p-6">
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-green-50 text-[#1E7538]">
                      <ChefHat aria-hidden="true" className="h-5 w-5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <h2 className="mt-0.5 break-words text-xl font-bold text-stone-900">
                        {recipe.title}
                      </h2>
                      {(recipe.cuisine || recipe.protein_subtype) && (
                        <p className="mt-1 text-sm text-stone-500">
                          {[recipe.cuisine, recipe.protein_subtype].filter(Boolean).join(' · ')}
                        </p>
                      )}
                    </div>
                  </div>
                  {recipe.description && (
                    <p className="mt-4 text-sm leading-relaxed text-stone-600">
                      {recipe.description}
                    </p>
                  )}

                  <div className="recipe-page__sections mt-5 grid gap-6 md:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                    <section className="recipe-page__section">
                      <h3 className="mb-3 font-bold text-stone-900">Ingredients</h3>
                      {recipe.ingredients.length > 0 ? (
                        <ul className="space-y-2">
                          {recipe.ingredients.map((ingredient, ingredientIndex) => (
                            <li
                              key={`${ingredient.name}-${ingredientIndex}`}
                              className="flex items-start justify-between gap-3 rounded-lg bg-stone-50 px-3 py-2.5 text-sm"
                            >
                              <span className="font-medium text-stone-800">{ingredient.name}</span>
                              <span className="shrink-0 text-right text-stone-500">
                                {ingredient.quantity}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-stone-500">No ingredients listed.</p>
                      )}
                    </section>

                    <section className="recipe-page__section">
                      <h3 className="mb-3 font-bold text-stone-900">Instructions</h3>
                      {recipe.directions.length > 0 ? (
                        <ol className="space-y-3">
                          {recipe.directions.map((direction, directionIndex) => (
                            <li
                              key={`${directionIndex}-${direction}`}
                              className="flex items-start gap-3 text-sm leading-relaxed text-stone-700"
                            >
                              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-green-50 text-xs font-bold text-[#1E7538]">
                                {directionIndex + 1}
                              </span>
                              <span className="pt-0.5">{direction}</span>
                            </li>
                          ))}
                        </ol>
                      ) : (
                        <p className="text-sm text-stone-500">No instructions listed.</p>
                      )}
                    </section>
                  </div>
                </div>
          </article>
        ) : (
          <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            The recipe could not be loaded.
          </div>
        )}
      </main>
    </div>
  );
};
