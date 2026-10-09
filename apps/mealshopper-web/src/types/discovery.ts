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
  id: string;
  name: string;
  address: string;
  postalCode: string;
  distanceMiles: number;
}

export interface Deal {
  dealId: string;
  storeId: string;
  storeName: string;
  itemName: string;
  cleanName: string;
  normalizedCategory: string;
  dealPrice: number;
  currency: string;
  unit: string;
  valueScore: number;
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