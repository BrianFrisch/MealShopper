import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Loader2, Trash2 } from 'lucide-react';
import { Header } from '../components/Header';
import { authApi } from '../services/authApi';
import { mealPlanApi, type MealPlanIngredientDto } from '../services/mealPlanApi';

type StoreMap = Record<string, string>;

export const ShoppingListPage = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const [mealPlanId, setMealPlanId] = useState<string | null>(null);
  const [estimatedTotalTripCost, setEstimatedTotalTripCost] = useState<number | null>(null);
  const [ingredients, setIngredients] = useState<MealPlanIngredientDto[]>([]);
  const [storeNames, setStoreNames] = useState<StoreMap>({});
  const [newItemName, setNewItemName] = useState('');
  const [newItemQuantity, setNewItemQuantity] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isAddingItem, setIsAddingItem] = useState(false);
  const [removingIds, setRemovingIds] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadShoppingList = async (planId: string, token: string) => {
    const items = await mealPlanApi.getMealPlanShoppingList(planId, token);
    setIngredients(items);

    const uniqueStoreIds = [...new Set(items.flatMap(item => item.store_id ? [item.store_id] : []))];
    if (uniqueStoreIds.length === 0) {
      setStoreNames({});
      return;
    }

    const stores = await Promise.all(uniqueStoreIds.map(async storeId => {
      try {
        const store = await mealPlanApi.getStoreDetails(storeId, token);
        return [storeId, store.name] as const;
      } catch {
        return [storeId, storeId] as const;
      }
    }));
    setStoreNames(Object.fromEntries(stores));
  };

  useEffect(() => {
    if (!taskId) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    const load = async () => {
      try {
        const status = await mealPlanApi.getMealPlan(taskId);
        if (status.status !== 'Completed' || !status.result) {
          throw new Error(status.errorMessage || 'The saved meal plan could not be loaded.');
        }

        const token = authApi.getToken();
        if (!token) {
          throw new Error('Please sign in to view this shopping list.');
        }

        if (cancelled) {
          return;
        }
        setMealPlanId(status.result.mealPlanId);
        setEstimatedTotalTripCost(status.result.estimatedTotalTripCost);
        await loadShoppingList(status.result.mealPlanId, token);
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

    void load();
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const itemsByStore = useMemo(() => {
    return ingredients.reduce<Record<string, MealPlanIngredientDto[]>>((groups, item) => {
      const storeLabel = item.store_id ? (storeNames[item.store_id] || item.store_id) : 'Other Items';
      groups[storeLabel] = [...(groups[storeLabel] ?? []), item];
      return groups;
    }, {});
  }, [ingredients, storeNames]);

  const handleAddItem = async (event: FormEvent) => {
    event.preventDefault();
    if (!mealPlanId) {
      setErrorMessage('A meal plan ID is required to add shopping list items.');
      return;
    }

    const token = authApi.getToken();
    if (!token) {
      setErrorMessage('Please sign in to modify this shopping list.');
      return;
    }

    const ingredientName = newItemName.trim();
    const ingredientQuantity = newItemQuantity.trim();
    if (!ingredientName || !ingredientQuantity) {
      setErrorMessage('Enter both a name and quantity.');
      return;
    }

    setIsAddingItem(true);
    setErrorMessage(null);
    try {
      const added = await mealPlanApi.addMealPlanShoppingListItem(
        mealPlanId,
        ingredientName,
        ingredientQuantity,
        token
      );
      setIngredients(current => [added, ...current]);
      setNewItemName('');
      setNewItemQuantity('');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to add this shopping list item.');
    } finally {
      setIsAddingItem(false);
    }
  };

  const handleRemoveItem = async (ingredient: MealPlanIngredientDto) => {
    if (!mealPlanId) {
      setErrorMessage('A meal plan ID is required to update this shopping list.');
      return;
    }

    const token = authApi.getToken();
    if (!token) {
      setErrorMessage('Please sign in to modify this shopping list.');
      return;
    }

    setRemovingIds(current => [...current, ingredient.meal_plan_ingredient_id]);
    setErrorMessage(null);
    try {
      const result = await mealPlanApi.removeMealPlanShoppingListItem(
        mealPlanId,
        ingredient.meal_plan_ingredient_id,
        token
      );
      if (result.status === 'removed') {
        setIngredients(current => current.filter(item => item.meal_plan_ingredient_id !== ingredient.meal_plan_ingredient_id));
      } else {
        setIngredients(current => current.map(item => (
          item.meal_plan_ingredient_id === ingredient.meal_plan_ingredient_id
            ? { ...item, is_purchased: true }
            : item
        )));
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to update this shopping list item.');
    } finally {
      setRemovingIds(current => current.filter(id => id !== ingredient.meal_plan_ingredient_id));
    }
  };

  const displayedError = taskId ? errorMessage : 'A meal plan task ID is required to load this shopping list.';

  return (
    <div className="min-h-screen bg-[#FDFDF9] pb-12 text-stone-900">
      <Header />
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-[#1E7538]">Meal plan complete</p>
            <h1 className="mt-1 text-3xl font-extrabold">Your Shopping List</h1>
          </div>
          {estimatedTotalTripCost !== null && (
            <p className="text-lg font-bold text-stone-800">
              Estimated cost: {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(estimatedTotalTripCost)}
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
              <h2 className="text-xl font-bold">Add shopping list item</h2>
              <form onSubmit={handleAddItem} className="mt-3 grid gap-3 md:grid-cols-[1fr_220px_auto]">
                <input
                  type="text"
                  value={newItemName}
                  onChange={event => setNewItemName(event.target.value)}
                  placeholder="Item name (e.g. Eggo Waffles)"
                  className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
                <input
                  type="text"
                  value={newItemQuantity}
                  onChange={event => setNewItemQuantity(event.target.value)}
                  placeholder="Quantity (e.g. 1 box)"
                  className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
                <button
                  type="submit"
                  disabled={isAddingItem}
                  className="rounded-lg bg-[#1E7538] px-4 py-2 text-sm font-semibold text-white hover:bg-green-800 disabled:opacity-60"
                >
                  {isAddingItem ? 'Adding...' : 'Add item'}
                </button>
              </form>
            </section>

            <section className="space-y-4">
              <h2 className="text-xl font-bold">Ingredients to buy</h2>
              {Object.entries(itemsByStore).map(([store, items]) => (
                <div key={store} className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
                  <h3 className="font-bold text-stone-900">{store}</h3>
                  <ul className="mt-3 divide-y divide-stone-100">
                    {items.map(item => {
                      const isRemoving = removingIds.includes(item.meal_plan_ingredient_id);
                      return (
                        <li key={item.meal_plan_ingredient_id} className="flex items-center justify-between gap-4 py-3">
                          <div>
                            <span className={`text-stone-800 ${item.is_purchased ? 'line-through text-stone-400' : ''}`}>
                              {item.ingredient_name}
                            </span>
                            <p className="text-sm text-stone-500">{item.ingredient_quantity}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => { void handleRemoveItem(item); }}
                            disabled={isRemoving}
                            className="inline-flex items-center gap-2 rounded-md border border-stone-300 px-3 py-1.5 text-xs font-semibold text-stone-700 hover:bg-stone-50 disabled:opacity-60"
                          >
                            {isRemoving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                            {item.recipe_id ? 'Mark purchased' : 'Remove'}
                          </button>
                        </li>
                      );
                    })}
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
