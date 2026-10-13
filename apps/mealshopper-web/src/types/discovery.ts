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

export interface StoreDto {
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

export type Store = StoreDto;

export type ProteinSubtype =
  | 'Beef'
  | 'Chicken'
  | 'Pork'
  | 'Turkey'
  | 'Seafood'
  | 'Lamb'
  | 'Other';

export interface DealItemDto {
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
  protein_subtype?: ProteinSubtype;
  image_url?: string | null;
}

export type Deal = DealItemDto;

export interface DiscoveryResultDto {
  stores: StoreDto[];
  deals: DealItemDto[];
}

export type DiscoveryJobResult = DiscoveryResultDto;

export interface TaskStatusResponse<T> {
  jobId: string;
  status: 'Pending' | 'DiscoveringStores' | 'FetchingDeals' | 'Completed' | 'Failed';
  stageDescription?: string;
  errorMessage?: string;
  result?: T;
}