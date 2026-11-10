import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChefHat, Loader2 } from 'lucide-react';
import { Header } from '../components/Header';
import { LoginModal } from '../components/LoginModal';
import { authApi } from '../services/authApi';
import { mealPlanApi, type RecipePageDto } from '../services/mealPlanApi';

const PAGE_SIZE = 10;

export const RecipesPage = () => {
  const [page, setPage] = useState(0);
  const [result, setResult] = useState<RecipePageDto | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const loadRecipes = async () => {
      try {
        const token = authApi.getToken();
        if (!token) {
          throw new Error('Please sign in to view your recipes.');
        }
        const data = await mealPlanApi.getUserRecipes(page * PAGE_SIZE, PAGE_SIZE, token);
        if (!cancelled) {
          setResult(data);
          setErrorMessage(null);
        }
      } catch (error) {
        if (!cancelled) {
          setResult(null);
          setErrorMessage(error instanceof Error ? error.message : 'Unable to load your recipes.');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };
    void loadRecipes();
    return () => { cancelled = true; };
  }, [page, reloadCount]);

  const changePage = (nextPage: number) => {
    setIsLoading(true);
    setErrorMessage(null);
    setPage(nextPage);
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
          setPage(0);
          setReloadCount(count => count + 1);
        }}
      />
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:py-10">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-[#1E7538]">Saved Recipes</p>
          <h1 className="mt-1 text-2xl font-extrabold sm:text-3xl">Your Recipe Library</h1>
        </div>
        <section aria-label="Recipe library" className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:p-6">
          {isLoading ? (
            <div role="status" className="flex items-center justify-center gap-3 p-8 text-stone-600">
              <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin text-[#1E7538]" />
              Loading recipes...
            </div>
          ) : errorMessage ? (
            <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
              {errorMessage}
              <button
                type="button"
                onClick={() => { setIsLoading(true); setReloadCount(count => count + 1); }}
                className="ml-3 font-semibold underline"
              >
                Try again
              </button>
            </div>
          ) : result && (
            <>
              <p className="border-b border-stone-200 pb-4 text-sm font-semibold text-stone-700">
                {result.total_count} {result.total_count === 1 ? 'recipe' : 'recipes'}
              </p>
              {result.recipes.length === 0 ? (
                <p className="py-8 text-center text-sm text-stone-600">
                  {result.total_count === 0 ? 'You have no saved recipes yet.' : 'No recipes on this page.'}
                </p>
              ) : (
                <ul className="divide-y divide-stone-200">
                  {result.recipes.map(recipe => (
                    <li key={recipe.recipe_id} className="flex items-center gap-4 py-4">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-green-50 text-[#1E7538]">
                        <ChefHat aria-hidden="true" className="h-5 w-5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <Link to={`/recipes/${recipe.recipe_id}`} state={{ fromRecipeLibrary: true }} className="break-words font-bold text-[#1E7538] hover:underline">
                          {recipe.title}
                        </Link>
                        {recipe.description && <p className="mt-1 text-sm text-stone-600">{recipe.description}</p>}
                      </div>
                      <button
                        type="button"
                        disabled
                        aria-label={`Remove ${recipe.title} (coming soon)`}
                        className="shrink-0 rounded-lg border border-stone-200 px-3 py-2 text-sm text-stone-400"
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {result.total_count > PAGE_SIZE && (
                <nav aria-label="Recipe pages" className="flex items-center justify-between gap-4 border-t border-stone-200 pt-4">
                  <button type="button" disabled={page === 0} onClick={() => changePage(page - 1)} className="rounded-lg border border-stone-300 px-3 py-2 text-sm font-semibold disabled:opacity-40">
                    Previous
                  </button>
                  <span className="text-sm text-stone-600">Page {page + 1} of {Math.max(1, Math.ceil(result.total_count / PAGE_SIZE))}</span>
                  <button type="button" disabled={(page + 1) * PAGE_SIZE >= result.total_count} onClick={() => changePage(page + 1)} className="rounded-lg border border-stone-300 px-3 py-2 text-sm font-semibold disabled:opacity-40">
                    Next
                  </button>
                </nav>
              )}
              {page > 0 && result.total_count <= PAGE_SIZE && (
                <button type="button" onClick={() => changePage(0)} className="mt-4 text-sm font-semibold text-[#1E7538] underline">
                  Back to first page
                </button>
              )}
            </>
          )}
        </section>
      </main>
    </div>
  );
};
