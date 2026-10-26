// apps/mealshopper-web/src/pages/HomePage.tsx
import React, { useState } from 'react';
import { Header } from '../components/Header';
import { authApi } from '../services/authApi';

interface HomePageProps {
  onLoginSuccess?: (token: string) => void;
}

export const HomePage: React.FC<HomePageProps> = ({ onLoginSuccess }) => {
  const navigate = (path: string) => window.location.assign(path);
  const [authMode, setAuthMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (authMode === 'signup' && password !== confirmPassword) {
      setErrorMessage('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      if (authMode === 'login') {
        const token = await authApi.login(email, password);
        onLoginSuccess?.(token);
        navigate('/discover');
        return;
      }

      await authApi.register(email, password);
      navigate('/discover');
    } catch (err: any) {
      setErrorMessage(err.message || 'Authentication failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFDF9] text-stone-900 flex flex-col justify-between">
      {/* 1. SITE HEADER */}
      <Header />

      {/* 2. HERO & VALUE PROPOSITION */}
      <main className="max-w-6xl mx-auto px-4 py-12 flex-1 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Column: Mission & Concept */}
          <div className="lg:col-span-7 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-50 border border-green-200 text-xs font-semibold text-[#1E7538]">
              <span>Real Circular Deals</span>
              <span>•</span>
              <span>Custom Tailored Recipes</span>
            </div>

            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-stone-900 leading-tight">
              Smarter Grocery Deals, <br />
              <span className="text-[#1E7538]">Grounded in Reality.</span>
            </h1>

            <p className="text-base sm:text-lg text-stone-600 leading-relaxed">
              Meal planning usually begins in a vacuum—dreaming up recipes first, then facing sticker
              shock in the checkout aisle. <strong>MealShopper</strong> flips the equation. We ingest
              active weekly circular promotions from verified grocers in your immediate neighborhood,
              filtering down to real centerpiece proteins on sale right now.
            </p>

            <p className="text-base sm:text-lg text-stone-600 leading-relaxed">
              You choose the meats, seafood, and stores you actually want to visit. Our AI chef then
              builds practical, high-protein dinners specifically anchored around your discounted
              cart—complete with exact grocery lists and pantry staples.
            </p>

            {/* Feature Highlights Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-stone-200/80">
              <div className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
                <div className="text-sm font-bold text-stone-900">Zero Hallucinations</div>
                <div className="text-xs text-stone-500 mt-1">
                  Recipes generated only from verified, active flyer items from local banners.
                </div>
              </div>
              <div className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
                <div className="text-sm font-bold text-stone-900">Store-Aware Routing</div>
                <div className="text-xs text-stone-500 mt-1">
                  Optimize your trip across 1 or 2 nearby stores to prevent wasted travel time.
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Authentication Card */}
          <div className="lg:col-span-5">
            <div className="bg-white rounded-2xl p-8 shadow-md border border-stone-200 max-w-md mx-auto">
              {/* Tab Selector */}
              <div className="flex rounded-xl bg-stone-100 p-1 mb-6">
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode('login');
                    setErrorMessage(null);
                  }}
                  className={`flex-1 py-2 text-xs font-bold rounded-lg transition ${
                    authMode === 'login'
                      ? 'bg-white text-stone-900 shadow-sm'
                      : 'text-stone-500 hover:text-stone-900'
                  }`}
                >
                  Log In
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode('signup');
                    setErrorMessage(null);
                  }}
                  className={`flex-1 py-2 text-xs font-bold rounded-lg transition ${
                    authMode === 'signup'
                      ? 'bg-white text-stone-900 shadow-sm'
                      : 'text-stone-500 hover:text-stone-900'
                  }`}
                >
                  Create Account
                </button>
              </div>

              {errorMessage && (
                <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-xs text-red-700 font-medium">
                  {errorMessage}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full px-3 py-2.5 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">
                    Password
                  </label>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full px-3 py-2.5 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none text-sm"
                  />
                </div>

                {authMode === 'signup' && (
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">
                      Confirm Password
                    </label>
                    <input
                      type="password"
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full px-3 py-2.5 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none text-sm"
                    />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full mt-2 bg-[#E66E1D] hover:bg-[#d25f12] text-white font-bold py-3 rounded-full shadow transition disabled:opacity-50 text-sm cursor-pointer"
                >
                  {isLoading
                    ? 'Processing...'
                    : authMode === 'login'
                    ? 'Sign In to MealShopper'
                    : 'Start Meal Planning'}
                </button>
              </form>

              <div className="mt-6 pt-4 border-t border-stone-100 text-center">
                <button
                  type="button"
                  onClick={() => navigate('/discover')}
                  className="text-xs font-semibold text-[#1E7538] hover:underline"
                >
                  Continue as Guest to Deal Finder &rarr;
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* 3. FOOTER */}
      <footer className="border-t border-stone-200 bg-white/60 py-6 text-center text-xs text-stone-400">
        MealShopper &copy; 2026. Weekly circular ingestion and meal synthesis engine.
      </footer>
    </div>
  );
};