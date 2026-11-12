import { Star } from 'lucide-react';

interface RecipeRatingProps {
  rating?: number;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export const RecipeRating = ({
  rating = 0,
  className = '',
  size = 'sm',
  showLabel = false,
}: RecipeRatingProps) => {
  const normalizedRating = Math.max(0, Math.min(5, Math.round(rating)));
  const starSizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-5 w-5',
    lg: 'h-6 w-6',
  }[size];

  const label = normalizedRating > 0 ? `${normalizedRating} of 5 stars` : 'Not rated';

  return (
    <div
      role="img"
      aria-label={label}
      title={label}
      className={`inline-flex items-center gap-1.5 ${className}`}
    >
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map(starIndex => (
          <Star
            key={starIndex}
            aria-hidden="true"
            className={`${starSizeClasses} ${
              starIndex <= normalizedRating
                ? 'fill-amber-400 text-amber-400'
                : 'fill-stone-200 text-stone-300'
            }`}
          />
        ))}
      </div>
      {showLabel && (
        <span className="text-xs font-medium text-stone-500">
          {normalizedRating > 0 ? `${normalizedRating}/5` : 'Not rated'}
        </span>
      )}
    </div>
  );
};
