import React from 'react';
import { Menu, User } from 'lucide-react';

interface HeaderProps {
  onUserClick?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onUserClick }) => {
  return (
    <header className="border-b border-stone-200 bg-white/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-20 flex items-center justify-between">
        <button aria-label="Menu" className="p-2 text-stone-600 hover:text-stone-900 rounded-lg hover:bg-stone-100 transition">
          <Menu className="w-6 h-6" />
        </button>

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