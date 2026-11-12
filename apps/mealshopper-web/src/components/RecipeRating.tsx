import { useState, type MouseEvent } from 'react';
import { Loader2, Star } from 'lucide-react';
import { authApi } from '../services/authApi';
import { mealPlanApi } from '../services/mealPlanApi';

const RATING_TOOLTIPS: Record<number, string> = {
  1: '1 - awful, would not make again',
  2: '2 - not good, unlikely to make again',
  3: '3 - acceptable, may make again',
  4: '4 - good, would make again',
  5: '5 - excellent, would absolutely make again',
};

interface RecipeRatingProps {
  rating?: number;
  recipeId?: string;
  onRatingChange?: (newRating: number) => void | Promise<void>;
  interactive?: boolean;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export const RecipeRating = ({
  rating = 0,
  recipeId,
  onRatingChange,
  interactive = true,
  className = '',
  size = 'sm',
  showLabel = false,
}: RecipeRatingProps) => {
  const [optimisticRating, setOptimisticRating] = useState<number | null>(null);
  const [hoverRating, setHoverRating] = useState<number | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);

  const currentRating = optimisticRating !== null ? optimisticRating : rating;
  const normalizedRating = Math.max(0, Math.min(5, Math.round(currentRating)));
  const displayRating = hoverRating !== null ? hoverRating : normalizedRating;

  const starSizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-5 w-5',
    lg: 'h-6 w-6',
  }[size];

  const canInteract = interactive && (Boolean(onRatingChange) || Boolean(recipeId));

  const handleStarClick = async (e: MouseEvent<HTMLButtonElement>, starIndex: number) => {
    e.preventDefault();
    e.stopPropagation();

    if (!canInteract || isUpdating) {
      return;
    }

    setOptimisticRating(starIndex);

    try {
      setIsUpdating(true);
      if (onRatingChange) {
        await onRatingChange(starIndex);
      } else if (recipeId) {
        const token = authApi.getToken();
        if (token) {
          await mealPlanApi.updateRecipeRating(recipeId, starIndex, token);
        }
      }
    } catch {
      setOptimisticRating(null);
    } finally {
      setIsUpdating(false);
    }
  };

  const currentLabel = displayRating > 0 ? `${displayRating} of 5 stars` : 'Not rated';

  return (
    <div
      className={`relative inline-flex items-center gap-1.5 ${className}`}
      onMouseLeave={() => setHoverRating(null)}
    >
      {/* Floating tooltip on hover */}
      {hoverRating !== null && RATING_TOOLTIPS[hoverRating] && (
        <div
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-stone-900 px-2.5 py-1 text-xs font-semibold text-white shadow-lg"
        >
          {RATING_TOOLTIPS[hoverRating]}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-stone-900" />
        </div>
      )}

      <div
        role="group"
        aria-label={currentLabel}
        className="flex items-center gap-0.5"
      >
        {[1, 2, 3, 4, 5].map(starIndex => {
          const isFilled = starIndex <= displayRating;
          const tooltip = RATING_TOOLTIPS[starIndex];

          if (canInteract) {
            return (
              <button
                key={starIndex}
                type="button"
                disabled={isUpdating}
                title={tooltip}
                aria-label={tooltip}
                onMouseEnter={() => setHoverRating(starIndex)}
                onFocus={() => setHoverRating(starIndex)}
                onBlur={() => setHoverRating(null)}
                onClick={e => { void handleStarClick(e, starIndex); }}
                className="group -m-0.5 rounded p-0.5 transition-transform hover:scale-110 focus:outline-none focus:ring-1 focus:ring-amber-400 disabled:cursor-wait"
              >
                <Star
                  aria-hidden="true"
                  className={`${starSizeClasses} transition-colors ${
                    isFilled
                      ? 'fill-amber-400 text-amber-400'
                      : 'fill-stone-200 text-stone-300'
                  }`}
                />
              </button>
            );
          }

          return (
            <span
              key={starIndex}
              title={tooltip}
              aria-label={tooltip}
              className="-m-0.5 p-0.5"
            >
              <Star
                aria-hidden="true"
                className={`${starSizeClasses} ${
                  isFilled
                    ? 'fill-amber-400 text-amber-400'
                    : 'fill-stone-200 text-stone-300'
                }`}
              />
            </span>
          );
        })}
      </div>

      {isUpdating && (
        <Loader2
          aria-label="Updating rating..."
          className="h-3.5 w-3.5 animate-spin text-stone-400"
        />
      )}

      {showLabel && !isUpdating && (
        <span className="text-xs font-medium text-stone-500">
          {normalizedRating > 0 ? `${normalizedRating}/5` : 'Not rated'}
        </span>
      )}
    </div>
  );
};
