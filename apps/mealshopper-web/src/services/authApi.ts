import axios from 'axios';

const GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:5247';

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export const authApi = {
  async login(email: string, password: string): Promise<string> {
    const params = new URLSearchParams();
    params.append('grant_type', 'password');
    params.append('email', email);
    params.append('password', password);

    const response = await axios.post<TokenResponse>(
      `${GATEWAY_URL}/v1/auth/token`,
      params,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    const token = response.data.access_token;
    localStorage.setItem('access_token', token);
    return token;
  },

  getToken(): string | null {
    return localStorage.getItem('access_token');
  },

  logout(): void {
    localStorage.removeItem('access_token');
  },
};