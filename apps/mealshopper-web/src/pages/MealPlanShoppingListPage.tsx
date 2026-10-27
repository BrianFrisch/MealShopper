import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Check, Loader2, ShoppingCart, Trash2 } from 'lucide-react';
import { Header } from '../components/Header';
import { LoginModal } from '../components/LoginModal';
import { authApi } from '../services/authApi';
import {
  mealPlanApi,
  type MealPlanIngredientDto,
  type MealPlanRecordDto,
} from '../services/mealPlanApi';
import type { StoreDto } from '../types/discovery';

interface ShoppingListDisplayIngredient {
  ingredient_name: string;
  ingredient_quantity: string;
  ingredients: MealPlanIngredientDto[];
}

const parseQuantity = (quantity: string): { amount: number; unit: string } | null => {
  const match = quantity.trim().match(
    /^(\d+\s+\d+\/\d+|\d+\/\d+|\d+(?:\.\d+)?)\s*(.*?)$/
  );
  if (!match) {
    return null;
  }

  const amountText = match[1];
  let amount: number;
  if (amountText.includes(' ')) {
    const [whole, fraction] = amountText.split(/\s+/);
    const [numerator, denominator] = fraction.split('/');
    amount = Number(whole) + Number(numerator) / Number(denominator);
  } else if (amountText.includes('/')) {
    const [numerator, denominator] = amountText.split('/');
    amount = Number(numerator) / Number(denominator);
  } else {
    amount = Number(amountText);
  }

  if (!Number.isFinite(amount)) {
    return null;
  }

  return { amount, unit: match[2].trim() };
};

const formatQuantity = (amount: number): string => (
  Number(amount.toFixed(4)).toString()
);

const combineQuantities = (quantities: string[]): string => {
  const parsed = quantities.map(parseQuantity);
  if (parsed.every(quantity => quantity !== null)) {
    const units = new Set(parsed.map(quantity => quantity!.unit.toLocaleLowerCase()));
    if (units.size === 1) {
      const total = parsed.reduce((sum, quantity) => sum + quantity!.amount, 0);
      const unit = parsed[0]!.unit;
      return `${formatQuantity(total)}${unit ? ` ${unit}` : ''}`;
    }
  }

  const distinctQuantities = [...new Map(
    quantities.map(quantity => [quantity.trim().toLocaleLowerCase(), quantity.trim()])
  ).values()];
  return distinctQuantities.join(' + ');
};

const groupIngredientsByName = (
  ingredients: MealPlanIngredientDto[]
): ShoppingListDisplayIngredient[] => {
  const grouped = new Map<string, MealPlanIngredientDto[]>();
  ingredients.forEach(ingredient => {
    const key = ingredient.ingredient_name.trim().toLocaleLowerCase();
    const items = grouped.get(key) ?? [];
    items.push(ingredient);
    grouped.set(key, items);
  });

  return [...grouped.values()].map(items => ({
    ingredient_name: items[0].ingredient_name,
    ingredient_quantity: combineQuantities(items.map(item => item.ingredient_quantity)),
    ingredients: items,
  }));
};

export const MealPlanShoppingListPage = () => {
  const { mealPlanId } = useParams<{ mealPlanId: string }>();
  const hasToken = Boolean(authApi.getToken());
  const [mealPlan, setMealPlan] = useState<MealPlanRecordDto | null>(null);
  const [ingredients, setIngredients] = useState<MealPlanIngredientDto[]>([]);
  const [storesById, setStoresById] = useState<Record<string, StoreDto>>({});
  const [storeDetailsError, setStoreDetailsError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(() => Boolean(mealPlanId && hasToken));
  const [errorMessage, setErrorMessage] = useState<string | null>(() => (
    !mealPlanId
      ? 'A meal plan ID is required to load this shopping list.'
      : hasToken
        ? null
        : 'Please sign in to view this shopping list.'
  ));
  const [updatingIngredientId, setUpdatingIngredientId] = useState<string | null>(null);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [reloadCount, setReloadCount] = useState(0);
  const [newItemName, setNewItemName] = useState('');
  const [newItemQuantity, setNewItemQuantity] = useState('');
  const [isAddingItem, setIsAddingItem] = useState(false);
  const [removingIngredientId, setRemovingIngredientId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    const token = authApi.getToken();
    if (!mealPlanId || !token) {
      return;
    }

    let cancelled = false;
    const loadShoppingList = async () => {
      try {
        const [plan, items] = await Promise.all([
          mealPlanApi.getMealPlanRecord(mealPlanId, token),
          mealPlanApi.getMealPlanShoppingList(mealPlanId, token),
        ]);
        if (!cancelled) {
          setMealPlan(plan);
          setIngredients(items);
          setErrorMessage(null);
        }
        const storeIds = [...new Set(
          items.flatMap(item => item.store_id ? [item.store_id] : [])
        )];
        const storeResults = await Promise.allSettled(
          storeIds.map(storeId => mealPlanApi.getStoreDetails(storeId, token))
        );
        if (!cancelled) {
          const nextStoresById: Record<string, StoreDto> = {};
          storeResults.forEach((result, index) => {
            if (result.status === 'fulfilled') {
              nextStoresById[storeIds[index]] = result.value;
            }
          });
          setStoresById(nextStoresById);
          setStoreDetailsError(
            storeResults.some(result => result.status === 'rejected')
              ? 'Some store details could not be loaded.'
              : null
          );
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error ? error.message : 'Unable to load this shopping list.'
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadShoppingList();
    return () => {
      cancelled = true;
    };
  }, [mealPlanId, reloadCount]);

  const ingredientsByStore = useMemo(() => {
    const byStore = new Map<string, MealPlanIngredientDto[]>();
    const withoutStore: MealPlanIngredientDto[] = [];

    ingredients.forEach(ingredient => {
      if (!ingredient.deal_id || !ingredient.store_id) {
        withoutStore.push(ingredient);
        return;
      }
      const storeItems = byStore.get(ingredient.store_id) ?? [];
      storeItems.push(ingredient);
      byStore.set(ingredient.store_id, storeItems);
    });

    return { byStore, withoutStore };
  }, [ingredients]);

  const handlePurchasedChange = async (
    ingredient: ShoppingListDisplayIngredient,
    isPurchased: boolean
  ) => {
    const token = authApi.getToken();
    if (!mealPlanId || !token) {
      setErrorMessage('Please sign in to update this shopping list.');
      setIsLoginOpen(true);
      return;
    }

    const ingredientIds = ingredient.ingredients.map(item => item.meal_plan_ingredient_id);
    setUpdatingIngredientId(ingredientIds.join(','));
    setErrorMessage(null);
    const results = await Promise.allSettled(
      ingredient.ingredients.map(item => mealPlanApi.updateMealPlanIngredientPurchased(
        mealPlanId,
        item.meal_plan_ingredient_id,
        isPurchased,
        token
      ))
    );
    const updatedIngredients = results.flatMap(result => (
      result.status === 'fulfilled' ? [result.value] : []
    ));
    if (updatedIngredients.length > 0) {
      const updatedById = new Map(
        updatedIngredients.map(item => [item.meal_plan_ingredient_id, item])
      );
      setIngredients(current => current.map(item => (
        updatedById.get(item.meal_plan_ingredient_id) ?? item
      )));
    }
    const failedResult = results.find(result => result.status === 'rejected');
    if (failedResult?.status === 'rejected') {
      setErrorMessage(
        failedResult.reason instanceof Error
          ? failedResult.reason.message
          : 'Unable to update ingredient purchase status.'
      );
    }
    setUpdatingIngredientId(null);
  };

  const handleAddItem = async (event: FormEvent) => {
    event.preventDefault();
    const token = authApi.getToken();
    if (!mealPlanId || !token) {
      setErrorMessage('Please sign in to update this shopping list.');
      setIsLoginOpen(true);
      return;
    }

    const ingredientName = newItemName.trim();
    const ingredientQuantity = newItemQuantity.trim();
    if (!ingredientName || !ingredientQuantity) {
      setFormError('Enter both a name and a quantity.');
      return;
    }

    setIsAddingItem(true);
    setFormError(null);
    try {
      const added = await mealPlanApi.addMealPlanShoppingListItem(
        mealPlanId,
        ingredientName,
        ingredientQuantity,
        token
      );
      setIngredients(current => [...current, added]);
      setNewItemName('');
      setNewItemQuantity('');
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Unable to add this item.');
    } finally {
      setIsAddingItem(false);
    }
  };

  const handleRemoveItem = async (ingredient: ShoppingListDisplayIngredient) => {
    const token = authApi.getToken();
    if (!mealPlanId || !token) {
      setErrorMessage('Please sign in to update this shopping list.');
      setIsLoginOpen(true);
      return;
    }

    const ids = ingredient.ingredients.map(item => item.meal_plan_ingredient_id);
    setRemovingIngredientId(ids.join(','));
    setFormError(null);
    const results = await Promise.allSettled(
      ids.map(id => mealPlanApi.removeMealPlanShoppingListItem(mealPlanId, id, token))
    );
    const removedIds = new Set(ids.filter((_, index) => results[index].status === 'fulfilled'));
    setIngredients(current => current.filter(item => !removedIds.has(item.meal_plan_ingredient_id)));
    const failed = results.find(result => result.status === 'rejected');
    if (failed?.status === 'rejected') {
      setFormError(failed.reason instanceof Error ? failed.reason.message : 'Unable to remove this item.');
    }
    setRemovingIngredientId(null);
  };

  const renderIngredient = (ingredient: ShoppingListDisplayIngredient) => {
    const ingredientIds = ingredient.ingredients.map(item => item.meal_plan_ingredient_id);
    const isPurchased = ingredient.ingredients.every(item => item.is_purchased);
    const isUpdating = updatingIngredientId === ingredientIds.join(',');
    const isCustomItem = ingredient.ingredients.every(item => item.recipe_id === null);
    const isRemoving = removingIngredientId === ingredientIds.join(',');
    return (
      <li
        key={ingredientIds.join(',')}
        className="flex items-center gap-3 border-t border-stone-100 px-4 py-3 first:border-t-0 sm:px-5"
      >
        <input
          type="checkbox"
          checked={isPurchased}
          disabled={isUpdating}
          aria-label={`Mark ${ingredient.ingredient_name} as ${isPurchased ? 'not purchased' : 'purchased'}`}
          onChange={event => {
            void handlePurchasedChange(ingredient, event.target.checked);
          }}
          className="h-4 w-4 shrink-0 accent-[#1E7538] disabled:cursor-wait"
        />
        <span className={`min-w-0 flex-1 font-medium ${
          isPurchased ? 'text-stone-400 line-through' : 'text-stone-800'
        }`}>
          {ingredient.ingredient_name}
        </span>
        <span className="shrink-0 text-right text-sm text-stone-500">
          {ingredient.ingredient_quantity}
        </span>
        {isCustomItem && (
          <button
            type="button"
            disabled={isRemoving}
            onClick={() => { void handleRemoveItem(ingredient); }}
            aria-label={`Remove ${ingredient.ingredient_name}`}
            className="shrink-0 rounded-md p-1.5 text-stone-400 transition hover:bg-rose-50 hover:text-rose-700 disabled:cursor-wait disabled:opacity-60"
          >
            {isRemoving
              ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              : <Trash2 aria-hidden="true" className="h-4 w-4" />}
          </button>
        )}
      </li>
    );
  };

  const renderStoreGroup = (storeId: string, items: MealPlanIngredientDto[]) => {
    const store = storesById[storeId];
    const storeAddress = store && (
      store.street || store.address ||
      [store.city, store.state, store.postal_code || store.zip_code].filter(Boolean).join(', ')
    );
    return (
      <section key={storeId} className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
        <h2 className="bg-stone-50 px-4 py-3 sm:px-5">
          <span className="block font-bold text-stone-900">{store?.name ?? storeId}</span>
          {storeAddress && (
            <span className="mt-0.5 block text-xs font-normal text-stone-500">
              {storeAddress}
            </span>
          )}
        </h2>
        <ul>{groupIngredientsByName(items).map(renderIngredient)}</ul>
      </section>
    );
  };

  const addItemForm = (
    <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-bold">Add shopping list item</h2>
      <form onSubmit={event => { void handleAddItem(event); }} className="mt-3 grid gap-3 md:grid-cols-[1fr_220px_auto]">
        <input
          type="text"
          value={newItemName}
          onChange={event => setNewItemName(event.target.value)}
          placeholder="Item name (e.g. Eggo Waffles)"
          aria-label="Item name"
          className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
        <input
          type="text"
          value={newItemQuantity}
          onChange={event => setNewItemQuantity(event.target.value)}
          placeholder="Quantity (e.g. 1 box)"
          aria-label="Item quantity"
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
      {formError && (
        <p role="alert" className="mt-3 text-sm text-rose-700">{formError}</p>
      )}
    </section>
  );

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
              Meal plan shopping
            </p>
            <h1 className="mt-1 text-2xl font-extrabold sm:text-3xl">
              {mealPlan?.meal_plan_name ?? 'Shopping List'}
            </h1>
          </div>
          <Link
            to="/meal-plans"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#1E7538] underline hover:text-green-800"
          >
            <ArrowLeft aria-hidden="true" className="h-4 w-4" />
            Back to Meal Plans
          </Link>
        </div>

        {isLoading ? (
          <div role="status" className="flex items-center justify-center gap-3 rounded-2xl border border-stone-200 bg-white p-12 text-stone-600">
            <Loader2 aria-hidden="true" className="h-6 w-6 animate-spin text-[#1E7538]" />
            Loading your shopping list...
          </div>
        ) : errorMessage ? (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
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
        ) : ingredients.length === 0 ? (
          <>
            {addItemForm}
            <section className="rounded-2xl border border-dashed border-stone-300 bg-white p-10 text-center">
              <ShoppingCart aria-hidden="true" className="mx-auto h-8 w-8 text-stone-400" />
              <h2 className="mt-3 font-semibold text-stone-800">No ingredients in this meal plan yet</h2>
              <p className="mt-1 text-sm text-stone-500">
                Add recipes to this plan or add your own items above.
              </p>
            </section>
          </>
        ) : (
          <>
            {addItemForm}
            {errorMessage && (
              <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                {errorMessage}
              </p>
            )}
            {storeDetailsError && (
              <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                {storeDetailsError} Store IDs are shown where details are unavailable.
              </p>
            )}
            <div className="space-y-4">
              {[...ingredientsByStore.byStore.entries()].map(([storeId, items]) => (
                renderStoreGroup(storeId, items)
              ))}
            </div>

            {ingredientsByStore.withoutStore.length > 0 && (
              <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
                <div className="flex items-center gap-2 bg-stone-50 px-4 py-3 sm:px-5">
                  <Check aria-hidden="true" className="h-4 w-4 text-[#1E7538]" />
                  <h2 className="font-bold text-stone-900">Other ingredients</h2>
                </div>
                <ul>{groupIngredientsByName(ingredientsByStore.withoutStore).map(renderIngredient)}</ul>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
};
