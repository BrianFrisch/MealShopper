import axios from 'axios';
import type { MealPlanDiscoveryRequest, DiscoveryJobResult, TaskStatusResponse } from '../types/discovery';
import type { MealPlanSynthesisRequest, MealPlanSynthesisResponse } from '../types/mealPlan';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_GATEWAY_URL
    || (import.meta.env.DEV ? 'http://localhost:5247' : ''),
  headers: {
    'Content-Type': 'application/json',
  },
});

const authorizationHeaders = (token: string) => ({
  headers: { Authorization: `Bearer ${token}` }
});

export interface MealPlanRecordDto {
  meal_plan_id: string;
  meal_plan_name: string;
  user_id: string;
  is_archived: boolean;
  recipe_count?: number;
  created_at?: string;
  updated_at?: string;
}

export const mealPlanApi = {
  async getMealPlans(token: string): Promise<MealPlanRecordDto[]> {
    const response = await apiClient.get<MealPlanRecordDto[]>(
      '/v1/planner/meal-plans',
      authorizationHeaders(token)
    );
    return response.data;
  },

  async getMealPlanRecipes(mealPlanId: string, token: string): Promise<unknown[]> {
    const response = await apiClient.get<unknown[]>(
      `/v1/planner/meal-plans/${mealPlanId}/recipes`,
      authorizationHeaders(token)
    );
    return response.data;
  },

  async createMealPlan(
    mealPlanName: string,
    token: string,
    mealPlanId?: string
  ): Promise<MealPlanRecordDto> {
    const response = await apiClient.post<MealPlanRecordDto>(
      '/v1/planner/meal-plans',
      {
        mealPlanName,
        ...(mealPlanId ? { mealPlanId } : {}),
      },
      authorizationHeaders(token)
    );
    return response.data;
  },

  async associateRecipeToMealPlan(
    mealPlanId: string,
    recipeId: string,
    token: string
  ): Promise<{ status: string; meal_plan_id: string; recipe_id: string }> {
    const response = await apiClient.post<{ status: string; meal_plan_id: string; recipe_id: string }>(
      `/v1/planner/meal-plans/${mealPlanId}/recipes`,
      { recipeId },
      authorizationHeaders(token)
    );
    return response.data;
  },

  async updateMealPlanName(
    mealPlanId: string,
    mealPlanName: string,
    token: string
  ): Promise<MealPlanRecordDto> {
    const response = await apiClient.put<MealPlanRecordDto>(
      `/v1/planner/meal-plans/${mealPlanId}`,
      { mealPlanName },
      authorizationHeaders(token)
    );
    return response.data;
  },

  async updateMealPlanArchive(
    mealPlanId: string,
    mealPlanName: string,
    isArchived: boolean,
    token: string
  ): Promise<MealPlanRecordDto> {
    const response = await apiClient.put<MealPlanRecordDto>(
      `/v1/planner/meal-plans/${mealPlanId}`,
      { mealPlanName, isArchived },
      authorizationHeaders(token)
    );
    return response.data;
  },

  async startDiscovery(request: MealPlanDiscoveryRequest, token: string): Promise<{ jobId: string }> {
    const response = await apiClient.post<{ jobId: string }>(
      '/v1/meal-plans/discovery',
      request,
      authorizationHeaders(token)
    );
    return response.data;
  },

  async pollTaskStatus(jobId: string, token: string): Promise<TaskStatusResponse<DiscoveryJobResult>> {
    const response = await apiClient.get<TaskStatusResponse<DiscoveryJobResult>>(
      `/v1/tasks/${jobId}`,
      authorizationHeaders(token)
    );
    return response.data;
  },

  async startGeneration(
    request: MealPlanSynthesisRequest,
    token: string
  ): Promise<{ jobId: string }> {
    const response = await apiClient.post<{ jobId: string }>(
      '/v1/meal-plans/generation',
      request,
      authorizationHeaders(token)
    );
    return response.data;
  },

  async pollGeneration(jobId: string, token: string): Promise<TaskStatusResponse<MealPlanSynthesisResponse>> {
    const response = await apiClient.get<TaskStatusResponse<MealPlanSynthesisResponse>>(
      `/v1/tasks/${jobId}`,
      authorizationHeaders(token)
    );
    return response.data;
  },

  async confirmMealPlan(
    jobId: string,
    selectedRecipeIds: string[],
    token: string
  ): Promise<void> {
    await apiClient.post(
      `/v1/meal-plans/${jobId}/confirm`,
      { selectedRecipeIds },
      authorizationHeaders(token)
    );
  },

  async getMealPlan(
    jobId: string
  ): Promise<TaskStatusResponse<MealPlanSynthesisResponse>> {
    const response = await apiClient.get<TaskStatusResponse<MealPlanSynthesisResponse>>(
      `/v1/tasks/${jobId}`
    );
    return response.data;
  },
};
