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

export const mealPlanApi = {
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
