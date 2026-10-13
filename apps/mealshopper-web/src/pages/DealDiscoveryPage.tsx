import React, { useState } from 'react';
import { Header } from '../components/Header';
import { LoginModal } from '../components/LoginModal';
import { DealImageTooltip } from '../components/DealImageTooltip';
import type { MealPlanDiscoveryRequest, Store, Deal, ProteinSubtype } from '../types/discovery';
import { mealPlanApi } from '../services/mealPlanApi';
import { authApi } from '../services/authApi';
import { MapPin, Store as StoreIcon, Loader2 } from 'lucide-react';

const SUBTYPE_FILTERS: Array<'All' | ProteinSubtype> = [
  'All', 'Beef', 'Chicken', 'Pork', 'Turkey', 'Seafood', 'Lamb'
];

interface DealDiscoveryPageProps {
  onProceedToPlan?: (selectedDeals: Deal[]) => void;
}

export const DealDiscoveryPage: React.FC<DealDiscoveryPageProps> = ({ onProceedToPlan }) => {
  const [address, setAddress] = useState({
    street: '123 Hawthorne Blvd',
    city: 'Lawndale',
    state: 'CA',
    zipCode: '90260'
  });
  const [searchRadiusMiles, setSearchRadiusMiles] = useState(5);

  const [loading, setLoading] = useState(false);
  const [stageDescription, setStageDescription] = useState<string | null>(null);
  const [discoveredStores, setDiscoveredStores] = useState<Store[]>([]);
  const [discoveredDeals, setDiscoveredDeals] = useState<Deal[]>([]);
  const [selectedDeals, setSelectedDeals] = useState<Deal[]>([]);
  const [selectedSubtype, setSelectedSubtype] = useState<'All' | ProteinSubtype>('All');
  const [expandedStoreId, setExpandedStoreId] = useState<string | null>(null);
  
  // Auth state
  const [isLoginOpen, setIsLoginOpen] = useState(false);

  const getDealKey = (deal: Deal) => (
    deal.deal_id || deal.dealId ||
    `${deal.store_id || deal.storeId || ''}:${deal.item_name || deal.itemName || deal.clean_name || ''}:${deal.deal_price ?? deal.dealPrice ?? ''}:${deal.unit || ''}`
  );

  const getStoreKey = (store: Store) => store.id || store.store_id || store.name;

  const dealBelongsToStore = (deal: Deal, store: Store) => {
    const dealStoreId = deal.store_id || deal.storeId;
    const storeIds = [store.id, store.store_id].filter(Boolean);

    if (dealStoreId) {
      return storeIds.includes(dealStoreId);
    }

    return (deal.store_name || deal.storeName) === store.name;
  };

  const getDealStoreKey = (deal: Deal) => (
    deal.store_id || deal.storeId || deal.store_name || deal.storeName || ''
  );

  const getDealTitle = (deal: Deal) => (
    deal.item_name || deal.itemName || deal.clean_name || deal.cleanName || 'Unnamed item'
  );

  const getDealPrice = (deal: Deal) => Number(deal.deal_price ?? deal.dealPrice ?? 0);

  const getStoreAddress = (store: Store) => (
    store.street || store.address ||
    [store.city, store.state, store.postal_code || store.zip_code].filter(Boolean).join(', ')
  );

  const toggleDealSelection = (deal: Deal) => {
    const dealKey = getDealKey(deal);
    setSelectedDeals(current => (
      current.some(selected => getDealKey(selected) === dealKey)
        ? current.filter(selected => getDealKey(selected) !== dealKey)
        : [...current, deal]
    ));
  };

  const handleStartDiscovery = async () => {
    const token = authApi.getToken();
    if (!token) {
      setIsLoginOpen(true);
      return;
    }

    setLoading(true);
    setStageDescription('Submitting discovery request...');
    setDiscoveredStores([]);
    setDiscoveredDeals([]);
    setSelectedDeals([]);
    setExpandedStoreId(null);

    try {
      const payload: MealPlanDiscoveryRequest = {
        address,
        searchRadiusMiles,
        maxStores: 2,
        cuisines: [],
        avoidIngredients: []
      };

      const { jobId } = await mealPlanApi.startDiscovery(payload, token);

      const pollInterval = window.setInterval(async () => {
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
        } catch (err: any) {
          clearInterval(pollInterval);
          setLoading(false);
          if (err?.response?.status === 401) {
            authApi.logout();
            setIsLoginOpen(true);
          }
        }
      }, 2500);
    } catch (err: any) {
      setLoading(false);
      setStageDescription(null);
      if (err?.response?.status === 401) {
        authApi.logout();
        setIsLoginOpen(true);
      } else {
        alert('Failed to initiate discovery. Check Gateway status.');
      }
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFDF9] text-stone-900">
      <Header onUserClick={() => setIsLoginOpen(true)} />

      <LoginModal 
        isOpen={isLoginOpen} 
        onClose={() => setIsLoginOpen(false)} 
        onSuccess={() => {
          setIsLoginOpen(false);
          handleStartDiscovery();
        }} 
      />

      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="text-center max-w-2xl mx-auto mb-10">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl text-stone-900">
            Find Local Deals, <span className="text-[#1E7538]">Plan Healthy Meals</span>
          </h1>
          <p className="mt-3 text-stone-600">
            Discover active grocery circular promotions nearby and synthesize budget-optimized recipes.
          </p>
        </div>

        <div className="mb-8 max-w-2xl mx-auto">
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
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none"
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

              <div className="pt-2">
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

        <section className="mt-12 rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold tracking-wide text-stone-900">SELECTED DEALS</h2>
              <p className="text-sm text-stone-500">
                ({selectedDeals.length} Selected across {new Set(selectedDeals.map(getDealStoreKey).filter(Boolean)).size} Stores)
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedDeals([])}
              disabled={selectedDeals.length === 0}
              className="text-sm font-semibold text-stone-500 underline hover:text-stone-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Clear All
            </button>
          </div>

          {selectedDeals.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-stone-200 text-xs uppercase tracking-wide text-stone-500">
                  <tr>
                    <th className="px-3 py-2">Del</th>
                    <th className="px-3 py-2">Store</th>
                    <th className="px-3 py-2">Subtype</th>
                    <th className="px-3 py-2">Item Name</th>
                    <th className="px-3 py-2">Price/Unit</th>
                    <th className="px-3 py-2">Image</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {selectedDeals.map(deal => {
                    const store = discoveredStores.find(candidate => (
                      dealBelongsToStore(deal, candidate)
                    ));
                    const title = getDealTitle(deal);
                    const price = getDealPrice(deal);

                    return (
                      <tr key={getDealKey(deal)} className="align-middle">
                        <td className="px-3 py-3">
                          <button
                            type="button"
                            aria-label={`Remove ${title}`}
                            onClick={() => toggleDealSelection(deal)}
                            className="rounded px-2 text-lg font-bold leading-none text-rose-600 hover:bg-rose-50"
                          >
                            ×
                          </button>
                        </td>
                        <td className="px-3 py-3">
                          <div className="font-medium text-stone-800">
                            {deal.store_name || deal.storeName || store?.name || 'Unknown store'}
                          </div>
                          {store && <div className="text-xs text-stone-500">{getStoreAddress(store)}</div>}
                        </td>
                        <td className="px-3 py-3">
                          <span className="rounded-full bg-green-50 px-2 py-1 text-xs font-semibold text-[#1E7538]">
                            {deal.protein_subtype || 'Other'}
                          </span>
                        </td>
                        <td className="px-3 py-3 font-medium text-stone-800">{title}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-stone-700">
                          ${price.toFixed(2)} / {deal.unit || 'each'}
                        </td>
                        <td className="px-3 py-3">
                          <DealImageTooltip imageUrl={deal.image_url} itemName={title} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-stone-500">
              No deals selected. Select deals below to add them to your plan.
            </p>
          )}

          <div className="mt-5 flex justify-end">
            <button
              type="button"
              disabled={selectedDeals.length === 0}
              onClick={() => onProceedToPlan?.(selectedDeals)}
              className="rounded-full bg-[#1E7538] px-6 py-3 font-bold text-white shadow-sm transition hover:bg-green-800 disabled:cursor-not-allowed disabled:bg-stone-300 disabled:text-stone-500 disabled:shadow-none"
            >
              Continue to Meal Planning →
            </button>
          </div>
        </section>

        {/* Results */}
        {discoveredStores.length > 0 && (
          <section className="mt-12 space-y-5">
            <h2 className="text-2xl font-bold text-stone-900">Discovered Stores & Deals</h2>

            <div className="flex flex-wrap gap-2" aria-label="Filter deals by protein subtype">
              {SUBTYPE_FILTERS.map(subtype => (
                <button
                  type="button"
                  key={subtype}
                  aria-pressed={selectedSubtype === subtype}
                  onClick={() => setSelectedSubtype(subtype)}
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    selectedSubtype === subtype
                      ? 'bg-[#1E7538] text-white shadow-sm'
                      : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                  }`}
                >
                  {subtype}
                </button>
              ))}
            </div>

            <div className="space-y-4">
              {discoveredStores.map(store => {
                const storeKey = getStoreKey(store);
                const storeDeals = discoveredDeals.filter(deal => dealBelongsToStore(deal, store));
                const visibleDeals = selectedSubtype === 'All'
                  ? storeDeals
                  : storeDeals.filter(deal => deal.protein_subtype === selectedSubtype);
                const isExpanded = expandedStoreId === storeKey;
                const storeAddress = getStoreAddress(store);
                const distance = store.distance_miles ?? store.distanceMiles;

                return (
                  <section key={storeKey} className="rounded-2xl border border-stone-200 bg-white shadow-sm">
                    <button
                      type="button"
                      aria-expanded={isExpanded}
                      onClick={() => setExpandedStoreId(isExpanded ? null : storeKey)}
                      className="flex w-full flex-wrap items-center justify-between gap-4 rounded-2xl bg-stone-50 p-5 text-left transition hover:bg-stone-100"
                    >
                      <span className="flex items-center gap-3">
                        <span className="rounded-xl bg-[#1E7538]/10 p-2.5 text-[#1E7538]">
                          <StoreIcon className="h-6 w-6" />
                        </span>
                        <span>
                          <span className="block text-lg font-bold text-stone-900">{store.name}</span>
                          <span className="block text-xs text-stone-500">
                            {storeAddress} &bull; {distance ?? 0} miles away
                          </span>
                        </span>
                      </span>
                      <span className="text-xs font-semibold text-[#E66E1D]">
                        {storeDeals.length} Deals Found
                      </span>
                    </button>

                    {isExpanded && (
                      <div className="p-4">
                        {visibleDeals.length > 0 ? (
                          <div className="overflow-x-auto">
                            <table className="w-full min-w-[680px] text-left text-sm">
                              <thead className="border-b border-stone-200 text-xs uppercase tracking-wide text-stone-500">
                                <tr>
                                  <th className="px-3 py-2">Select</th>
                                  <th className="px-3 py-2">Subtype</th>
                                  <th className="px-3 py-2">Item / Cut</th>
                                  <th className="px-3 py-2">Price / Unit</th>
                                  <th className="px-3 py-2">Image</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-stone-100">
                                {visibleDeals.map(deal => {
                                  const dealKey = getDealKey(deal);
                                  const isSelected = selectedDeals.some(
                                    selected => getDealKey(selected) === dealKey
                                  );
                                  const title = getDealTitle(deal);
                                  const price = getDealPrice(deal);

                                  return (
                                    <tr
                                      key={dealKey}
                                      onClick={() => toggleDealSelection(deal)}
                                      className={`cursor-pointer transition ${
                                        isSelected ? 'bg-green-50' : 'hover:bg-stone-50'
                                      }`}
                                    >
                                      <td className="px-3 py-3">
                                        <input
                                          type="checkbox"
                                          checked={isSelected}
                                          aria-label={`Select ${title}`}
                                          onClick={event => event.stopPropagation()}
                                          onChange={() => toggleDealSelection(deal)}
                                          className="h-4 w-4 accent-[#1E7538]"
                                        />
                                      </td>
                                      <td className="px-3 py-3">
                                        <span className="rounded-full bg-green-50 px-2 py-1 text-xs font-semibold text-[#1E7538]">
                                          {deal.protein_subtype || 'Other'}
                                        </span>
                                      </td>
                                      <td className="px-3 py-3 font-medium text-stone-800">{title}</td>
                                      <td className="whitespace-nowrap px-3 py-3 text-stone-700">
                                        ${price.toFixed(2)} / {deal.unit || 'each'}
                                      </td>
                                      <td className="px-3 py-3">
                                        <DealImageTooltip imageUrl={deal.image_url} itemName={title} />
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <p className="py-3 text-sm italic text-stone-400">
                            {storeDeals.length === 0
                              ? 'No promotional circular items retrieved for this location.'
                              : `No ${selectedSubtype} deals found at this store.`}
                          </p>
                        )}
                      </div>
                    )}
                  </section>
                );
              })}
            </div>
          </section>
        )}
      </main>
    </div>
  );
};