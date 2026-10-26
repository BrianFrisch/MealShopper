import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/Header';
import { LoginModal } from '../components/LoginModal';
import { DealImageTooltip } from '../components/DealImageTooltip';
import type { Address, MealPlanDiscoveryRequest, Store, Deal, ProteinSubtype } from '../types/discovery';
import { mealPlanApi } from '../services/mealPlanApi';
import { authApi } from '../services/authApi';
import { MapPin, Store as StoreIcon, Loader2, RotateCcw } from 'lucide-react';

type SelectedDealsViewMode = 'collapsed' | 'limited' | 'full';

const SUBTYPE_FILTERS: Array<'All' | ProteinSubtype> = [
  'All', 'Beef', 'Chicken', 'Pork', 'Turkey', 'Seafood', 'Lamb'
];
const SUBTYPE_ICONS: Record<ProteinSubtype, string> = {
  Beef: '🐄',
  Chicken: '🐔',
  Pork: '🐷',
  Turkey: '🦃',
  Seafood: '🦐',
  Lamb: '🐑',
  Other: '🍖',
};
const SELECTED_DEALS_STORAGE_KEY = 'mealshopper_selected_deals';
const USER_ADDRESS_STORAGE_KEY = 'mealshopper_user_address';

const DEFAULT_ADDRESS: Address = {
  street: '123 Main St',
  city: 'Los Angeles',
  state: 'CA',
  zipCode: '90007'
};

const normalizeAddress = (addr: Address): Address => ({
  street: addr.street.trim(),
  city: addr.city.trim(),
  state: addr.state.trim(),
  zipCode: addr.zipCode.trim(),
});

const readStoredAddress = (): Address => {
  try {
    const storedAddress = localStorage.getItem(USER_ADDRESS_STORAGE_KEY);
    if (storedAddress === null) {
      return DEFAULT_ADDRESS;
    }
    const parsedAddress = JSON.parse(storedAddress) as Partial<Address>;
    return normalizeAddress({
      street: typeof parsedAddress.street === 'string' ? parsedAddress.street : DEFAULT_ADDRESS.street,
      city: typeof parsedAddress.city === 'string' ? parsedAddress.city : DEFAULT_ADDRESS.city,
      state: typeof parsedAddress.state === 'string' ? parsedAddress.state : DEFAULT_ADDRESS.state,
      zipCode: typeof parsedAddress.zipCode === 'string' ? parsedAddress.zipCode : DEFAULT_ADDRESS.zipCode,
    });
  } catch {
    return DEFAULT_ADDRESS;
  }
};

interface DealDiscoveryPageProps {
  onProceedToPlan?: (selectedDeals: Deal[]) => void;
}

export const DealDiscoveryPage: React.FC<DealDiscoveryPageProps> = ({ onProceedToPlan }) => {
  const navigate = useNavigate();
  const [address, setAddress] = useState<Address>(readStoredAddress);
  const [searchRadiusMiles, setSearchRadiusMiles] = useState(5);

  const [loading, setLoading] = useState(false);
  const [stageDescription, setStageDescription] = useState<string | null>(null);
  const [discoveredStores, setDiscoveredStores] = useState<Store[]>([]);
  const [discoveredDeals, setDiscoveredDeals] = useState<Deal[]>([]);
  const [selectedDeals, setSelectedDeals] = useState<Deal[]>(() => {
    const storedSelectedDeals = localStorage.getItem(SELECTED_DEALS_STORAGE_KEY);
    return storedSelectedDeals === null ? [] : JSON.parse(storedSelectedDeals) as Deal[];
  });
  const [selectedSubtype, setSelectedSubtype] = useState<'All' | ProteinSubtype>('All');
  const [expandedStoreId, setExpandedStoreId] = useState<string | null>(null);
  const [isSearchHidden, setIsSearchHidden] = useState(false);
  const [selectedDealsViewMode, setSelectedDealsViewMode] = useState<SelectedDealsViewMode>('collapsed');
  const pollIntervalRef = useRef<number | null>(null);
  
  // Auth state
  const [isLoginOpen, setIsLoginOpen] = useState(false);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current !== null) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

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

  const getSubtypeIcon = (subtype?: ProteinSubtype) => (
    SUBTYPE_ICONS[subtype && subtype in SUBTYPE_ICONS ? subtype : 'Other']
  );

  const getStoreAddress = (store: Store) => (
    store.street || store.address ||
    [store.city, store.state, store.postal_code || store.zip_code].filter(Boolean).join(', ')
  );

  const handleToggleDeal = (deal: Deal) => {
    const dealKey = getDealKey(deal);
    const nextSelectedDeals = selectedDeals.some(selected => getDealKey(selected) === dealKey)
      ? selectedDeals.filter(selected => getDealKey(selected) !== dealKey)
      : [...selectedDeals, deal];
    setSelectedDeals(nextSelectedDeals);
    localStorage.setItem(SELECTED_DEALS_STORAGE_KEY, JSON.stringify(nextSelectedDeals));
  };

  const handleRemoveDeal = (deal: Deal) => {
    const dealKey = getDealKey(deal);
    const nextSelectedDeals = selectedDeals.filter(selected => getDealKey(selected) !== dealKey);
    setSelectedDeals(nextSelectedDeals);
    localStorage.setItem(SELECTED_DEALS_STORAGE_KEY, JSON.stringify(nextSelectedDeals));
  };

  const handleClearAll = () => {
    setSelectedDeals([]);
    localStorage.setItem(SELECTED_DEALS_STORAGE_KEY, JSON.stringify([]));
  };

  const handleContinueToPlan = () => {
    localStorage.setItem(SELECTED_DEALS_STORAGE_KEY, JSON.stringify(selectedDeals));
    navigate('/plan');
    onProceedToPlan?.(selectedDeals);
  };

  const handleRestartSearch = () => {
    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setLoading(false);
    setStageDescription(null);
    setIsSearchHidden(false);
  };

  const handleStartDiscovery = async () => {
    const normalizedAddress = normalizeAddress(address);
    setAddress(normalizedAddress);
    localStorage.setItem(USER_ADDRESS_STORAGE_KEY, JSON.stringify(normalizedAddress));

    const token = authApi.getToken();
    if (!token) {
      setIsLoginOpen(true);
      return;
    }

    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    setIsSearchHidden(true);
    setLoading(true);
    setStageDescription('Submitting discovery request...');
    setDiscoveredStores([]);
    setDiscoveredDeals([]);
    setSelectedDeals([]);
    localStorage.setItem(SELECTED_DEALS_STORAGE_KEY, JSON.stringify([]));
    setExpandedStoreId(null);

    try {
      const payload: MealPlanDiscoveryRequest = {
        address: normalizedAddress,
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
            pollIntervalRef.current = null;
            setDiscoveredStores(statusRes.result.stores || []);
            setDiscoveredDeals(statusRes.result.deals || []);
            setLoading(false);
            setStageDescription(
              statusRes.stageDescription?.includes('Partial deal results:')
                ? statusRes.stageDescription
                : null
            );
          } else if (statusRes.status === 'Failed') {
            clearInterval(pollInterval);
            pollIntervalRef.current = null;
            alert(`Discovery failed: ${statusRes.errorMessage || 'Unknown error'}`);
            setLoading(false);
            setStageDescription(null);
          }
        } catch (err: any) {
          clearInterval(pollInterval);
          pollIntervalRef.current = null;
          setLoading(false);
          if (err?.response?.status === 401) {
            authApi.logout();
            setIsLoginOpen(true);
          } else {
            alert('Unable to check discovery status. Please try again.');
          }
        }
      }, 2500);
      pollIntervalRef.current = pollInterval;
    } catch (err: any) {
      setLoading(false);
      setStageDescription(null);
      if (err?.response?.status === 401) {
        authApi.logout();
        setIsLoginOpen(true);
      } else {
        setIsSearchHidden(false);
        const validationErrors = err?.response?.data?.errors;
        const firstValidationMessage = validationErrors
          ? Object.values(validationErrors).flat()[0]
          : null;
        alert(
          typeof firstValidationMessage === 'string'
            ? `Failed to initiate discovery: ${firstValidationMessage}`
            : 'Failed to initiate discovery. Check Gateway status.'
        );
      }
    }
  };

  const selectedStoreCount = new Set(selectedDeals.map(getDealStoreKey).filter(Boolean)).size;
  const selectedDealsSummary = `Selected ${selectedDeals.length} ${selectedDeals.length === 1 ? 'deal' : 'deals'} across ${selectedStoreCount} ${selectedStoreCount === 1 ? 'store' : 'stores'}`;

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

      <main className="max-w-6xl mx-auto px-2.5 py-3 sm:px-4 sm:py-6">
        <div className="text-center max-w-2xl mx-auto mb-4 sm:mb-6">
          <h1 className="text-xl font-extrabold tracking-tight sm:text-3xl text-stone-900">
            Find Local Deals, <span className="text-[#1E7538]">Plan Healthy Meals</span>
          </h1>
          <p className="mt-1 sm:mt-2 text-xs sm:text-sm text-stone-600">
            Discover active grocery circular promotions nearby and synthesize budget-optimized recipes.
          </p>
        </div>

        {!isSearchHidden ? (
          <>
            <div className="mb-4 sm:mb-6 max-w-2xl mx-auto">
              <div className="bg-white rounded-xl sm:rounded-2xl p-3.5 sm:p-5 shadow-sm border border-stone-200">
                <div className="flex items-center gap-2 mb-2.5 sm:mb-3.5 pb-2 border-b border-stone-100">
                  <MapPin className="w-4 h-4 sm:w-5 sm:h-5 text-[#1E7538]" />
                  <h2 className="text-sm sm:text-base font-bold text-stone-800">Home Address</h2>
                </div>

                <div className="space-y-2.5 sm:space-y-3.5">
                  <div>
                    <label className="block text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-1">Street Address</label>
                    <input 
                      type="text" 
                      value={address.street}
                      onChange={e => setAddress({ ...address, street: e.target.value })}
                      className="w-full px-2.5 py-1.5 sm:px-3 sm:py-2 text-sm border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none"
                    />
                  </div>

                  <div className="grid grid-cols-3 gap-2 sm:gap-3">
                    <div>
                      <label className="block text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-1">City</label>
                      <input 
                        type="text" 
                        value={address.city}
                        onChange={e => setAddress({ ...address, city: e.target.value })}
                        className="w-full px-2.5 py-1.5 sm:px-3 sm:py-2 text-sm border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-1">State</label>
                      <input 
                        type="text" 
                        value={address.state}
                        onChange={e => setAddress({ ...address, state: e.target.value })}
                        className="w-full px-2.5 py-1.5 sm:px-3 sm:py-2 text-sm border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-1">Zip Code</label>
                      <input 
                        type="text"
                        inputMode="numeric"
                        autoComplete="postal-code"
                        value={address.zipCode}
                        onChange={e => setAddress({ ...address, zipCode: e.target.value })}
                        className="w-full px-2.5 py-1.5 sm:px-3 sm:py-2 text-sm border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] outline-none"
                      />
                    </div>
                  </div>

                  <div className="pt-1">
                    <label className="block text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-1">Search Radius</label>
                    <select
                      value={searchRadiusMiles}
                      onChange={e => setSearchRadiusMiles(Number(e.target.value))}
                      className="w-full px-2.5 py-1.5 sm:px-3 sm:py-2 text-sm border border-stone-200 rounded-lg focus:ring-2 focus:ring-[#1E7538] bg-white outline-none"
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
                className="flex items-center gap-2 bg-[#E66E1D] hover:bg-[#d25f12] text-white font-bold px-6 py-2.5 sm:px-8 sm:py-3 rounded-full shadow-md hover:shadow-lg transition disabled:opacity-50 text-sm sm:text-base"
              >
                <span>Discover Local Deals</span>
              </button>
            </div>
          </>
        ) : (
          <div className="mb-3 sm:mb-4 flex flex-wrap items-center justify-between gap-2 sm:gap-3 rounded-xl border border-stone-200 bg-white px-3 py-2 sm:px-4 sm:py-3 shadow-sm">
            <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm text-stone-700">
              <MapPin className="h-3.5 w-3.5 sm:h-4 sm:w-4 shrink-0 text-[#1E7538]" />
              <span>
                Within <strong className="font-semibold text-stone-900">{searchRadiusMiles} mi</strong> of{' '}
                <strong className="font-semibold text-stone-900">
                  {address.street}, {address.city}, {address.state} {address.zipCode}
                </strong>
              </span>
              {loading && (
                <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2.5 py-0.5 text-[11px] font-semibold text-[#E66E1D]">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Searching Circulars...
                </span>
              )}
              {stageDescription && (
                <span className={`text-[11px] sm:text-xs text-stone-500 ${loading ? 'animate-pulse' : ''}`}>
                  {stageDescription}
                </span>
              )}
            </div>

            <button
              type="button"
              onClick={handleRestartSearch}
              className="inline-flex items-center gap-1.5 rounded-full border border-stone-300 bg-white px-3 py-1 text-xs font-semibold text-stone-700 shadow-xs transition hover:border-stone-400 hover:bg-stone-50 hover:text-stone-900"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Restart</span>
            </button>
          </div>
        )}

        <section className="sticky top-20 z-40 mt-3 sm:mt-4 rounded-xl border border-stone-200 bg-white/95 px-3 py-2 sm:px-4 sm:py-2.5 shadow-md backdrop-blur">
          <div className={`flex flex-wrap items-center justify-between gap-2 ${selectedDealsViewMode !== 'collapsed' ? 'mb-2' : ''}`}>
            <div className="flex flex-wrap items-baseline gap-2">
              <h2 className="text-xs sm:text-sm font-bold tracking-wide text-stone-900">SELECTED DEALS</h2>
              <p className="text-[11px] sm:text-xs font-medium text-stone-600">
                {selectedDealsSummary}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div
                className="inline-flex items-center rounded-full border border-stone-200 bg-stone-100 p-0.5 text-[11px] sm:text-xs font-semibold"
                role="group"
                aria-label="Selected deals view mode"
              >
                <button
                  type="button"
                  aria-pressed={selectedDealsViewMode === 'collapsed'}
                  onClick={() => setSelectedDealsViewMode('collapsed')}
                  className={`rounded-full px-2 py-0.5 sm:px-2.5 transition ${
                    selectedDealsViewMode === 'collapsed'
                      ? 'bg-white text-stone-900 shadow-xs'
                      : 'text-stone-600 hover:text-stone-900'
                  }`}
                >
                  Collapsed
                </button>
                <button
                  type="button"
                  aria-pressed={selectedDealsViewMode === 'limited'}
                  onClick={() => setSelectedDealsViewMode('limited')}
                  className={`rounded-full px-2 py-0.5 sm:px-2.5 transition ${
                    selectedDealsViewMode === 'limited'
                      ? 'bg-white text-stone-900 shadow-xs'
                      : 'text-stone-600 hover:text-stone-900'
                  }`}
                >
                  Limited
                </button>
                <button
                  type="button"
                  aria-pressed={selectedDealsViewMode === 'full'}
                  onClick={() => setSelectedDealsViewMode('full')}
                  className={`rounded-full px-2 py-0.5 sm:px-2.5 transition ${
                    selectedDealsViewMode === 'full'
                      ? 'bg-white text-stone-900 shadow-xs'
                      : 'text-stone-600 hover:text-stone-900'
                  }`}
                >
                  Full
                </button>
              </div>

              <button
                type="button"
                onClick={handleClearAll}
                disabled={selectedDeals.length === 0}
                className="text-xs font-semibold text-stone-500 underline hover:text-stone-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Clear All
              </button>

              {selectedDealsViewMode === 'collapsed' && (
                <button
                  type="button"
                  disabled={selectedDeals.length === 0}
                  onClick={handleContinueToPlan}
                  className="rounded-full bg-[#1E7538] px-3 py-1 text-[11px] sm:text-xs font-bold text-white shadow-sm transition hover:bg-green-800 disabled:cursor-not-allowed disabled:bg-stone-300 disabled:text-stone-500 disabled:shadow-none"
                >
                  Continue to Meal Planning →
                </button>
              )}
            </div>
          </div>

          {selectedDealsViewMode !== 'collapsed' && (
            <>
              {selectedDeals.length > 0 ? (
                <div
                  className={`overflow-x-auto ${
                    selectedDealsViewMode === 'limited' ? 'max-h-40 sm:max-h-52 overflow-y-auto' : ''
                  }`}
                >
                  <table className="w-full text-left text-xs sm:text-sm">
                    <thead className="sticky top-0 z-10 border-b border-stone-200 bg-white text-[11px] uppercase tracking-wide text-stone-500">
                      <tr>
                        <th className="w-6 px-1 py-1.5 sm:px-2" aria-label="Remove" />
                        <th className="w-8 px-1 py-1.5 text-center sm:px-2">Type</th>
                        <th className="whitespace-nowrap px-1.5 py-1.5 sm:px-2.5">Price</th>
                        <th className="px-1.5 py-1.5 sm:px-2.5">Item</th>
                        <th className="hidden sm:table-cell px-2.5 py-1.5">Store</th>
                        <th className="px-1.5 py-1.5 text-right sm:px-2.5 sm:text-left">Image</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {selectedDeals.map(deal => {
                        const store = discoveredStores.find(candidate => (
                          dealBelongsToStore(deal, candidate)
                        ));
                        const title = getDealTitle(deal);
                        const price = getDealPrice(deal);
                        const subtype = deal.protein_subtype || 'Other';
                        const storeName = deal.store_name || deal.storeName || store?.name || 'Unknown store';

                        return (
                          <tr key={getDealKey(deal)} className="align-middle">
                            <td className="px-1 py-1.5 sm:px-2 sm:py-2">
                              <button
                                type="button"
                                aria-label={`Remove ${title}`}
                                onClick={() => handleRemoveDeal(deal)}
                                className="rounded px-1.5 text-base font-bold leading-none text-rose-600 hover:bg-rose-50"
                              >
                                ×
                              </button>
                            </td>
                            <td className="px-1 py-1.5 text-center sm:px-2 sm:py-2">
                              <span
                                role="img"
                                aria-label={subtype}
                                title={subtype}
                                className="text-base leading-none"
                              >
                                {getSubtypeIcon(deal.protein_subtype)}
                              </span>
                            </td>
                            <td className="whitespace-nowrap px-1.5 py-1.5 font-semibold text-stone-800 sm:px-2.5 sm:py-2">
                              ${price.toFixed(2)}
                              <span className="text-[11px] font-normal text-stone-500">/{deal.unit || 'ea'}</span>
                            </td>
                            <td className="px-1.5 py-1.5 font-medium text-stone-800 sm:px-2.5 sm:py-2">
                              <div className="leading-snug">{title}</div>
                              <div className="text-[11px] font-normal text-stone-500 sm:hidden">{storeName}</div>
                            </td>
                            <td className="hidden sm:table-cell px-2.5 py-2">
                              <div className="font-medium text-stone-800">{storeName}</div>
                              {store && <div className="text-[11px] text-stone-500">{getStoreAddress(store)}</div>}
                            </td>
                            <td className="whitespace-nowrap px-1.5 py-1.5 text-right sm:px-2.5 sm:py-2 sm:text-left">
                              <DealImageTooltip imageUrl={deal.image_url} itemName={title} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="py-3 text-center text-xs text-stone-500">
                  No deals selected. Select deals below to add them to your plan.
                </p>
              )}

              <div className="mt-2.5 flex justify-end">
                <button
                  type="button"
                  disabled={selectedDeals.length === 0}
                  onClick={handleContinueToPlan}
                  className="rounded-full bg-[#1E7538] px-4 py-1.5 text-xs font-bold text-white shadow-sm transition hover:bg-green-800 disabled:cursor-not-allowed disabled:bg-stone-300 disabled:text-stone-500 disabled:shadow-none"
                >
                  Continue to Meal Planning →
                </button>
              </div>
            </>
          )}
        </section>

        {/* Results */}
        {discoveredStores.length > 0 && (
          <section className="mt-4 sm:mt-6 space-y-3 sm:space-y-4">
            <h2 className="text-lg sm:text-xl font-bold text-stone-900">Discovered Stores & Deals</h2>

            <div className="flex flex-wrap gap-1.5 sm:gap-2" aria-label="Filter deals by protein subtype">
              {SUBTYPE_FILTERS.map(subtype => (
                <button
                  type="button"
                  key={subtype}
                  aria-pressed={selectedSubtype === subtype}
                  onClick={() => setSelectedSubtype(subtype)}
                  className={`inline-flex items-center gap-1 rounded-full px-3 py-1 sm:px-3.5 sm:py-1.5 text-xs sm:text-sm font-semibold transition ${
                    selectedSubtype === subtype
                      ? 'bg-[#1E7538] text-white shadow-sm'
                      : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                  }`}
                >
                  {subtype !== 'All' && (
                    <span aria-hidden="true">{getSubtypeIcon(subtype)}</span>
                  )}
                  <span>{subtype}</span>
                </button>
              ))}
            </div>

            <div className="space-y-2.5 sm:space-y-3.5">
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
                  <section key={storeKey} className="rounded-xl sm:rounded-2xl border border-stone-200 bg-white shadow-sm">
                    <button
                      type="button"
                      aria-expanded={isExpanded}
                      onClick={() => setExpandedStoreId(isExpanded ? null : storeKey)}
                      className="flex w-full flex-wrap items-center justify-between gap-2 sm:gap-4 rounded-xl sm:rounded-2xl bg-stone-50 px-3 py-2.5 sm:p-4 text-left transition hover:bg-stone-100"
                    >
                      <span className="flex items-center gap-2.5 sm:gap-3 min-w-0">
                        <span className="shrink-0 rounded-lg sm:rounded-xl bg-[#1E7538]/10 p-2 text-[#1E7538]">
                          <StoreIcon className="h-4 w-4 sm:h-5 sm:w-5" />
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-sm sm:text-base font-bold text-stone-900">{store.name}</span>
                          <span className="block truncate text-[11px] sm:text-xs text-stone-500">
                            {storeAddress} &bull; {distance ?? 0} miles away
                          </span>
                        </span>
                      </span>
                      <span className="shrink-0 text-xs font-semibold text-[#E66E1D]">
                        {storeDeals.length} Deals Found
                      </span>
                    </button>

                    {isExpanded && (
                      <div className="p-2 sm:p-4">
                        {visibleDeals.length > 0 ? (
                          <div className="overflow-x-auto">
                            <table className="w-full text-left text-xs sm:text-sm">
                              <thead className="border-b border-stone-200 text-[11px] uppercase tracking-wide text-stone-500">
                                <tr>
                                  <th className="w-7 px-1.5 py-1.5 sm:w-9 sm:px-2.5 sm:py-2" aria-label="Select" />
                                  <th className="w-8 px-1 py-1.5 text-center sm:w-12 sm:px-2.5 sm:py-2">Type</th>
                                  <th className="whitespace-nowrap px-1.5 py-1.5 sm:px-3 sm:py-2">Price</th>
                                  <th className="px-1.5 py-1.5 sm:px-3 sm:py-2">Item / Cut</th>
                                  <th className="px-1.5 py-1.5 text-right sm:px-3 sm:py-2 sm:text-left">Image</th>
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
                                  const subtype = deal.protein_subtype || 'Other';

                                  return (
                                    <tr
                                      key={dealKey}
                                      onClick={() => handleToggleDeal(deal)}
                                      className={`cursor-pointer transition ${
                                        isSelected ? 'bg-green-50' : 'hover:bg-stone-50'
                                      }`}
                                    >
                                      <td className="px-1.5 py-2 sm:px-2.5 sm:py-2.5">
                                        <input
                                          type="checkbox"
                                          checked={isSelected}
                                          aria-label={`Select ${title}`}
                                          onClick={event => event.stopPropagation()}
                                          onChange={() => handleToggleDeal(deal)}
                                          className="h-4 w-4 accent-[#1E7538]"
                                        />
                                      </td>
                                      <td className="px-1 py-2 text-center sm:px-2.5 sm:py-2.5">
                                        <span
                                          role="img"
                                          aria-label={subtype}
                                          title={subtype}
                                          className="text-base sm:text-lg leading-none"
                                        >
                                          {getSubtypeIcon(deal.protein_subtype)}
                                        </span>
                                      </td>
                                      <td className="whitespace-nowrap px-1.5 py-2 font-semibold text-stone-800 sm:px-3 sm:py-2.5">
                                        ${price.toFixed(2)}
                                        <span className="text-[11px] font-normal text-stone-500">/{deal.unit || 'ea'}</span>
                                      </td>
                                      <td className="px-1.5 py-2 font-medium leading-snug text-stone-800 sm:px-3 sm:py-2.5">
                                        {title}
                                      </td>
                                      <td className="whitespace-nowrap px-1.5 py-2 text-right sm:px-3 sm:py-2.5 sm:text-left">
                                        <DealImageTooltip imageUrl={deal.image_url} itemName={title} />
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <p className="py-3 text-xs sm:text-sm italic text-stone-400">
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