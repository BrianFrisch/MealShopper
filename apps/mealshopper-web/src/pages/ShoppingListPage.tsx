import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { Header } from '../components/Header';
import { mealPlanApi } from '../services/mealPlanApi';
import type { MealPlanSynthesisResponse } from '../types/mealPlan';

interface ShoppingListItem {
  name: string;
  amount: string;
  store: string;
}

export const ShoppingListPage = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const [mealPlan, setMealPlan] = useState<MealPlanSynthesisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) {
      return;
    }

    let cancelled = false;
    const loadMealPlan = async () => {
      try {
        const status = await mealPlanApi.getMealPlan(taskId);
        if (status.status !== 'Completed' || !status.result) {
          throw new Error(status.errorMessage || 'The saved meal plan could not be loaded.');
        }
        if (!cancelled) {
          setMealPlan(status.result);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : 'Unable to load the shopping list.');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadMealPlan();
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const keptRecipes = mealPlan?.recipes.filter(recipe => recipe.isKept) ?? [];
  const displayedError = taskId ? errorMessage : 'A meal plan ID is required to load this shopping list.';
  const shoppingItems = new Map<string, { name: string; amount: string; store: string }>();
  const addShoppingItem = (key: string, item: ShoppingListItem) => {
    const existing = shoppingItems.get(key);
    if (existing) {
      if (!existing.amount.split('; ').includes(item.amount)) {
        existing.amount = `${existing.amount}; ${item.amount}`;
      }
      return;
    }
    shoppingItems.set(key, item);
  };

  keptRecipes.forEach(recipe => {
    recipe.ingredientsWithDeals.forEach(ingredient => {
      const store = ingredient.storeName || 'Store not specified';
      const key = `${store.toLowerCase()}:${ingredient.name.toLowerCase()}`;
      addShoppingItem(key, {
        name: ingredient.name,
        amount: ingredient.amountDescription,
        store
      });
    });
    recipe.pantryIngredients.forEach(ingredient => {
      const key = `pantry:${ingredient.name.toLowerCase()}`;
      addShoppingItem(key, {
        name: ingredient.name,
        amount: ingredient.amountDescription,
        store: 'Pantry'
      });
    });
  });

  const itemsByStore = [...shoppingItems.values()].reduce<Record<string, ShoppingListItem[]>>(
    (groups, item) => {
      groups[item.store] = [...(groups[item.store] ?? []), item];
      return groups;
    },
    {}
  );

  return (
    <div className="min-h-screen bg-[#FDFDF9] pb-12 text-stone-900">
      <Header />
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-[#1E7538]">Meal plan complete</p>
            <h1 className="mt-1 text-3xl font-extrabold">Your Shopping List</h1>
          </div>
          {mealPlan && (
            <p className="text-lg font-bold text-stone-800">
              Estimated cost: {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(mealPlan.estimatedTotalTripCost)}
            </p>
          )}
        </div>

        {isLoading ? (
          <div role="status" className="flex items-center justify-center gap-3 rounded-2xl border border-stone-200 bg-white p-12 text-stone-600">
            <Loader2 aria-hidden="true" className="h-6 w-6 animate-spin text-[#1E7538]" />
            Loading your saved shopping list...
          </div>
        ) : displayedError ? (
          <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-rose-800">
            {displayedError}
          </p>
        ) : (
          <>
            <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
              <h2 className="text-xl font-bold">Meals in your plan</h2>
              <ul className="mt-3 divide-y divide-stone-100">
                {keptRecipes.map(recipe => (
                  <li key={recipe.recipeId} className="py-3">
                    <p className="font-semibold text-stone-800">{recipe.recipeTitle}</p>
                    <p className="mt-1 text-sm text-stone-500">{recipe.description}</p>
                  </li>
                ))}
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-xl font-bold">Ingredients to buy</h2>
              {Object.entries(itemsByStore).map(([store, items]) => (
                <div key={store} className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
                  <h3 className="font-bold text-stone-900">{store}</h3>
                  <ul className="mt-3 divide-y divide-stone-100">
                    {items.map(item => (
                      <li key={`${item.name}-${item.amount}`} className="flex items-center justify-between gap-4 py-3">
                        <span className="text-stone-800">{item.name}</span>
                        <span className="text-sm text-stone-500">{item.amount}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>
            <Link
              to="/discover"
              className="inline-flex rounded-full bg-[#1E7538] px-5 py-3 font-bold text-white hover:bg-green-800"
            >
              ← Back to Discover
            </Link>
          </>
        )}
      </main>
    </div>
  );
};
