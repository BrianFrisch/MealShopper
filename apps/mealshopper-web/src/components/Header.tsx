import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Menu, User } from 'lucide-react';

interface HeaderProps {
  onUserClick?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onUserClick }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="border-b border-stone-200 bg-white/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-20 flex items-center justify-between">
        <div className="relative">
          <button
            type="button"
            aria-label="Menu"
            aria-expanded={isMenuOpen}
            aria-controls="main-navigation"
            onClick={() => setIsMenuOpen(open => !open)}
            className="p-2 text-stone-600 hover:text-stone-900 rounded-lg hover:bg-stone-100 transition"
          >
            <Menu aria-hidden="true" className="w-6 h-6" />
          </button>
          {isMenuOpen && (
            <nav
              id="main-navigation"
              aria-label="Main navigation"
              className="absolute left-0 top-full z-50 mt-2 w-64 overflow-hidden rounded-xl border border-stone-200 bg-white py-1 shadow-lg"
            >
              <span className="block px-4 py-2.5 text-sm text-stone-500">
                Account Settings and Preferences
              </span>
              <Link
                to="/discover"
                onClick={() => setIsMenuOpen(false)}
                className="block px-4 py-2.5 text-sm font-medium text-stone-800 transition hover:bg-stone-50"
              >
                Discover Deals
              </Link>
              <Link
                to="/custom-recipe"
                onClick={() => setIsMenuOpen(false)}
                className="block px-4 py-2.5 text-sm font-medium text-stone-800 transition hover:bg-stone-50"
              >
                Custom Recipe
              </Link>
              <Link
                to="/meal-plans"
                onClick={() => setIsMenuOpen(false)}
                className="block px-4 py-2.5 text-sm font-medium text-stone-800 transition hover:bg-stone-50"
              >
                Meal Plans
              </Link>
            </nav>
          )}
        </div>

        <div className="flex items-center justify-center">
          <img 
            src="/logo.png" 
            alt="MealShopper" 
            className="h-12 w-auto object-contain cursor-pointer"
          />
        </div>

        <button 
          aria-label="User Profile" 
          onClick={onUserClick}
          className="p-2 text-stone-600 hover:text-stone-900 rounded-full hover:bg-stone-100 transition border border-stone-200"
        >
          <User className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
};