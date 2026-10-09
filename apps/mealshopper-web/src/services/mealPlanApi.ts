import axios from 'axios';
import type { MealPlanDiscoveryRequest, DiscoveryJobResult, TaskStatusResponse } from '../types/discovery';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:5247',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const mealPlanApi = {
  async startDiscovery(request: MealPlanDiscoveryRequest, token: string): Promise<{ jobId: string }> {
    const response = await apiClient.post<{ jobId: string }>(
      '/v1/meal-plans/discovery',
      request,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async pollTaskStatus(jobId: string, token: string): Promise<TaskStatusResponse<DiscoveryJobResult>> {
    const response = await apiClient.get<TaskStatusResponse<DiscoveryJobResult>>(
      `/v1/tasks/${jobId}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },
};