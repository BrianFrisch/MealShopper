import { useState } from 'react';
import { Plus, X } from 'lucide-react';

interface IncludeIngredientsFieldProps {
  ingredients: string[];
  onChange: (ingredients: string[]) => void;
}

export const IncludeIngredientsField = ({ ingredients, onChange }: IncludeIngredientsFieldProps) => {
  const [input, setInput] = useState('');

  const addIngredients = () => {
    const existing = new Set(ingredients.map(ingredient => ingredient.toLowerCase()));
    const additions = input.split(/[,\n]/).map(ingredient => ingredient.trim()).filter(ingredient => {
      const key = ingredient.toLowerCase();
      if (!key || existing.has(key)) return false;
      existing.add(key);
      return true;
    });
    onChange([...ingredients, ...additions]);
    setInput('');
  };

  return (
    <div>
      <label htmlFor="include-ingredients" className="mb-2 block text-sm font-bold text-stone-800">
        Ingredients to Include
      </label>
      <p className="mb-2 text-sm text-stone-600">
        Each ingredient will be used in one recipe if it fits; otherwise it may be omitted. These choices are not saved.
      </p>
      <div className="flex gap-2">
        <input
          id="include-ingredients"
          value={input}
          onChange={event => setInput(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' || event.key === ',') {
              event.preventDefault();
              addIngredients();
            }
          }}
          placeholder="Type an ingredient and press Enter"
          className="min-w-0 flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-[#1E7538] focus:ring-2 focus:ring-green-100"
        />
        <button
          type="button"
          aria-label="Add ingredient to include"
          onClick={addIngredients}
          className="rounded-lg bg-stone-100 px-3 text-stone-700 hover:bg-stone-200"
        >
          <Plus aria-hidden="true" className="h-5 w-5" />
        </button>
      </div>
      {ingredients.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {ingredients.map(ingredient => (
            <li key={ingredient}>
              <button
                type="button"
                aria-label={`Remove ${ingredient} from ingredients to include`}
                onClick={() => onChange(ingredients.filter(item => item !== ingredient))}
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
  );
};
