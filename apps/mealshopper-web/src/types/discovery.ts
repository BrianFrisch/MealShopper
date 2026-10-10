export interface Address {
  street: string;
  city: string;
  state: string;
  zipCode: string;
}

export interface MealPlanDiscoveryRequest {
  address: Address;
  searchRadiusMiles: number;
  maxStores: number;
  cuisines: string[];
  avoidIngredients: string[];
}

export interface Store {
  id?: string;
  store_id?: string;
  name: string;
  address: string;
  street?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  postal_code?: string;
  distance_miles?: number;
  distanceMiles?: number;
}

export interface Deal {
  deal_id?: string;
  dealId?: string;
  store_id?: string;
  storeId?: string;
  store_name?: string;
  storeName?: string;
  item_name?: string;
  itemName?: string;
  clean_name?: string;
  cleanName?: string;
  normalized_category?: string;
  normalizedCategory?: string;
  deal_price?: number;
  dealPrice?: number;
  currency?: string;
  unit?: string;
  value_score?: number;
  valueScore?: number;
}

export interface DiscoveryJobResult {
  stores: Store[];
  deals: Deal[];
}

export interface TaskStatusResponse<T> {
  jobId: string;
  status: 'Pending' | 'DiscoveringStores' | 'FetchingDeals' | 'Completed' | 'Failed';
  stageDescription?: string;
  errorMessage?: string;
  result?: T;
}