import React, { useState } from 'react';
import { Header } from '../components/Header';
import type { MealPlanDiscoveryRequest, Store, Deal } from '../types/discovery';
import { mealPlanApi } from '../services/mealPlanApi';
import { MapPin, Utensils, Store as StoreIcon, Loader2, Tag } from 'lucide-react';

const COMMON_CUISINES = [
  'American', 'Mexican', 'Italian', 'Chinese', 'Thai', 
  'Indian', 'Mediterranean', 'Japanese', 'Korean', 'Greek'
];



export const HomePage: React.FC = () => {
  const [address, setAddress] = useState({
    street: '123 Hawthorne Blvd',
    city: 'Lawndale',
    state: 'CA',
    zipCode: '90260'
  });
  const [searchRadiusMiles, setSearchRadiusMiles] = useState(5);
  const [maxStores, setMaxStores] = useState(2);
  const [selectedCuisines, setSelectedCuisines] = useState<string[]>(['Mediterranean', 'Mexican']);
  const [avoidIngredientInput, setAvoidIngredientInput] = useState('');
  const [avoidIngredients, setAvoidIngredients] = useState<string[]>(['Pork']);

  const [loading, setLoading] = useState(false);
  const [stageDescription, setStageDescription] = useState<string | null>(null);
  const [discoveredStores, setDiscoveredStores] = useState<Store[]>([]);
  const [discoveredDeals, setDiscoveredDeals] = useState<Deal[]>([]);

  const toggleCuisine = (cuisine: string) => {
    setSelectedCuisines(prev => 
      prev.includes(cuisine) ? prev.filter(c => c !== cuisine) : [...prev, cuisine]
    );
  };

  const addAvoidIngredient = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && avoidIngredientInput.trim()) {
      e.preventDefault();
      if (!avoidIngredients.includes(avoidIngredientInput.trim())) {
        setAvoidIngredients(prev => [...prev, avoidIngredientInput.trim()]);
      }
      setAvoidIngredientInput('');
    }
  };

  const removeAvoidIngredient = (ingredient: string) => {
    setAvoidIngredients(prev => prev.filter(i => i !== ingredient));
  };

  const handleStartDiscovery = async () => {
    setLoading(true);
    setStageDescription('Submitting discovery request...');
    setDiscoveredStores([]);
    setDiscoveredDeals([]);

    try {
      const payload: MealPlanDiscoveryRequest = {
        address,
        searchRadiusMiles,
        maxStores,
        cuisines: selectedCuisines,
        avoidIngredients
      };

      // Uses existing bearer token acquisition flow
      const token = localStorage.getItem('access_token') || '';
      const { jobId } = await mealPlanApi.startDiscovery(payload, token);

      // Poll until completed
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await mealPlanApi.pollTaskStatus(jobId, token);
          setStageDescription(statusRes.stageDescription || 'Processing flyer deals...');

          if (statusRes.status === 'Completed' && statusRes.result) {
            clearInterval(pollInterval);
            setDiscoveredStores(statusRes.result.stores || []);
            setDiscoveredDeals(statusRes.result.deals || []);
            setLoading(false);
            setStageDescription(null);
          } else if (statusRes.status === 'Failed') {
            clearInterval(pollInterval);
            alert(`Discovery failed: ${statusRes.errorMessage || 'Unknown error'}`);
            setLoading(false);
            setStageDescription(null);
          }
        } catch (err) {
          clearInterval(pollInterval);
          setLoading(false);
          console.error(err);
        }
      }, 2500);
    } catch (err) {
      setLoading(false);
      setStageDescription(null);
      alert('Failed to initiate discovery. Check Gateway status.');
      console.error(err);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFDF9] text-stone-900">
      <Header />

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Intro */}
        <div className="text-center max-w-2xl mx-auto mb-10">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl text-stone-900">
            Find Local Deals, <span className="text-[#1E7538]">Plan Healthy Meals</span>
          </h1>
          <p className="mt-3 text-stone-600">
            Discover active grocery circular promotions nearby and synthesize budget-optimized recipes.
          </p>
        </div>

        {/* Two-Column Intake Form */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
          
          {/* Left Column: Shopper & Location Preferences */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-stone-200">
            <div className="flex items-center gap-2 mb-4 pb-2 border-b border-stone-100">
              <MapPin className="w-5 h-5 text-[#1E7538]" />
              <h2 className="text-lg font-bold text-stone-800">Store & Location</h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">Street Address</label>
                <input 
                  type="text" 
                  value={address.street}
                  onChange={e => setAddress({ ...address, street: e.target.value })}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] focus:border-transparent outline-none transition"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">City</label>
                  <input 
                    type="text" 
                    value={address.city}
                    onChange={e => setAddress({ ...address, city: e.target.value })}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">State</label>
                  <input 
                    type="text" 
                    value={address.state}
                    onChange={e => setAddress({ ...address, state: e.target.value })}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">Zip Code</label>
                  <input 
                    type="text" 
                    value={address.zipCode}
                    onChange={e => setAddress({ ...address, zipCode: e.target.value })}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">Search Radius</label>
                  <select 
                    value={searchRadiusMiles}
                    onChange={e => setSearchRadiusMiles(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] bg-white outline-none"
                  >
                    {[1, 2, 5, 7, 10].map(mi => (
                      <option key={mi} value={mi}>{mi} Miles</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">Max Stores</label>
                  <select 
                    value={maxStores}
                    onChange={e => setMaxStores(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] bg-white outline-none"
                  >
                    {[1, 2, 3, 4].map(s => (
                      <option key={s} value={s}>{s} Stores</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Meal Preferences */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-stone-200">
            <div className="flex items-center gap-2 mb-4 pb-2 border-b border-stone-100">
              <Utensils className="w-5 h-5 text-[#E66E1D]" />
              <h2 className="text-lg font-bold text-stone-800">Diet & Cuisines</h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Preferred Cuisines</label>
                <div className="flex flex-wrap gap-2">
                  {COMMON_CUISINES.map(c => {
                    const active = selectedCuisines.includes(c);
                    return (
                      <button
                        type="button"
                        key={c}
                        onClick={() => toggleCuisine(c)}
                        className={`text-xs font-medium px-3 py-1.5 rounded-full transition ${
                          active 
                            ? 'bg-[#1E7538] text-white shadow-sm' 
                            : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                        }`}
                      >
                        {c}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">Avoid Ingredients / Allergies</label>
                <input 
                  type="text"
                  placeholder="Type an ingredient and press Enter"
                  value={avoidIngredientInput}
                  onChange={e => setAvoidIngredientInput(e.target.value)}
                  onKeyDown={addAvoidIngredient}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#E66E1D] outline-none"
                />
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {avoidIngredients.map(item => (
                    <span 
                      key={item} 
                      className="inline-flex items-center gap-1 text-xs bg-amber-50 text-[#E66E1D] border border-amber-200 px-2 py-0.5 rounded-full"
                    >
                      {item}
                      <button type="button" onClick={() => removeAvoidIngredient(item)} className="hover:text-stone-900">&times;</button>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="flex flex-col items-center justify-center">
          <button
            type="button"
            disabled={loading}
            onClick={handleStartDiscovery}
            className="flex items-center gap-2 bg-[#E66E1D] hover:bg-[#d25f12] text-white font-bold px-8 py-3.5 rounded-full shadow-md hover:shadow-lg transition disabled:opacity-50 text-base"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Searching Circulars...</span>
              </>
            ) : (
              <span>Discover Local Deals</span>
            )}
          </button>

          {stageDescription && (
            <p className="mt-3 text-sm text-stone-500 animate-pulse">
              {stageDescription}
            </p>
          )}
        </div>

        {/* Results Presentation View */}
        {discoveredStores.length > 0 && (
          <div className="mt-12 space-y-8">
            <h2 className="text-2xl font-bold text-stone-900 border-b border-stone-200 pb-2">
              Discovered Stores & Deals
            </h2>

            {discoveredStores.map(store => {
              const storeDeals = discoveredDeals.filter(d => d.storeId === store.id);
              return (
                <div key={store.id} className="bg-white rounded-2xl border border-stone-200 overflow-hidden shadow-sm">
                  {/* Store Header */}
                  <div className="bg-stone-50 p-5 border-b border-stone-200 flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 bg-[#1E7538]/10 text-[#1E7538] rounded-xl">
                        <StoreIcon className="w-6 h-6" />
                      </div>
                      <div>
                        <h3 className="font-bold text-stone-900 text-lg">{store.name}</h3>
                        <p className="text-xs text-stone-500">{store.address} &bull; {store.distanceMiles} miles away</p>
                      </div>
                    </div>
                    <span className="text-xs font-semibold px-3 py-1 bg-amber-100 text-[#E66E1D] rounded-full">
                      {storeDeals.length} Deals Found
                    </span>
                  </div>

                  {/* Deals Grid */}
                  <div className="p-5">
                    {storeDeals.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {storeDeals.map(deal => (
                          <div 
                            key={deal.dealId} 
                            className="p-4 rounded-xl border border-stone-100 bg-stone-50/50 hover:bg-stone-50 hover:border-stone-200 transition flex flex-col justify-between"
                          >
                            <div>
                              <div className="flex items-center justify-between gap-2 mb-1.5">
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#1E7538] bg-green-50 px-2 py-0.5 rounded">
                                  <Tag className="w-3 h-3" />
                                  {deal.normalizedCategory}
                                </span>
                                <span className="font-black text-stone-900 text-sm">
                                  ${deal.dealPrice.toFixed(2)} <span className="text-xs font-normal text-stone-500">/ {deal.unit}</span>
                                </span>
                              </div>
                              <p className="font-semibold text-stone-800 text-sm line-clamp-2">{deal.itemName}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-stone-400 italic py-2">No promotional circular items retrieved for this location.</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
};