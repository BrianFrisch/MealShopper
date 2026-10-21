import axios from 'axios';

const GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL
  || (import.meta.env.DEV ? 'http://localhost:5247' : '');

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface CreateUserResponse {
  id: string;
  email: string;
}

const ACCESS_TOKEN_KEY = 'access_token';
const LEGACY_REFRESH_TOKEN_KEY = 'refresh_token';
const ACCESS_TOKEN_EXPIRY_KEY = 'access_token_expiry';
const REFRESH_BEFORE_EXPIRY_MS = 60_000;
const REFRESH_RETRY_DELAY_MS = 30_000;

let refreshTimer: ReturnType<typeof setTimeout> | undefined;
let refreshInFlight: Promise<string> | undefined;
let autoRefreshStarted = false;

function saveTokens(tokens: TokenResponse): string {
  if (
    !tokens.access_token ||
    !Number.isFinite(tokens.expires_in) ||
    tokens.expires_in <= 0
  ) {
    throw new Error('The authentication service returned an invalid token response.');
  }

  const expiresAt = Date.now() + tokens.expires_in * 1000;
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  localStorage.setItem(ACCESS_TOKEN_EXPIRY_KEY, String(expiresAt));
  scheduleRefresh();
  return tokens.access_token;
}

function scheduleRefresh(delay?: number): void {
  if (refreshTimer !== undefined) {
    clearTimeout(refreshTimer);
  }

  if (!localStorage.getItem(ACCESS_TOKEN_KEY)) {
    return;
  }

  const expiresAt = Number(localStorage.getItem(ACCESS_TOKEN_EXPIRY_KEY));
  const delayMs = delay ?? Math.max(0, expiresAt - Date.now() - REFRESH_BEFORE_EXPIRY_MS);
  refreshTimer = setTimeout(() => {
    void refreshAccessToken().catch((error: unknown) => {
      console.error('Unable to refresh the access token.', error);
      if (localStorage.getItem(ACCESS_TOKEN_KEY)) {
        scheduleRefresh(REFRESH_RETRY_DELAY_MS);
      }
    });
  }, delayMs);
}

async function refreshAccessToken(): Promise<string> {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  const requestRefresh = async (): Promise<string> => {
    const expiresAt = Number(localStorage.getItem(ACCESS_TOKEN_EXPIRY_KEY));
    if (expiresAt - Date.now() > REFRESH_BEFORE_EXPIRY_MS) {
      const currentToken = authApi.getToken();
      if (currentToken) {
        return currentToken;
      }
    }

    const params = new URLSearchParams();
    params.append('grant_type', 'refresh_token');

    const response = await axios.post<TokenResponse>(
      `${GATEWAY_URL}/v1/auth/token`,
      params,
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        withCredentials: true,
      }
    );
    return saveTokens(response.data);
  };

  const refreshRequest = 'locks' in navigator
    ? navigator.locks.request('mealshopper-token-refresh', requestRefresh)
    : requestRefresh();

  refreshInFlight = refreshRequest.catch(error => {
    if (axios.isAxiosError(error) && (error.response?.status === 400 || error.response?.status === 401)) {
      authApi.logout();
    }
    throw error;
  }).finally(() => {
    refreshInFlight = undefined;
  });

  return refreshInFlight;
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
        withCredentials: true,
      }
    );

    return saveTokens(response.data);
  },

  async register(email: string, password: string): Promise<CreateUserResponse> {
    const response = await axios.post<CreateUserResponse>(
      `${GATEWAY_URL}/v1/auth/register`,
      { email, password }
    );
    return response.data;
  },

  startAutoRefresh(): void {
    localStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY);

    if (!autoRefreshStarted) {
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
          const expiresAt = Number(localStorage.getItem(ACCESS_TOKEN_EXPIRY_KEY));
          if (localStorage.getItem(ACCESS_TOKEN_KEY) && expiresAt - Date.now() <= REFRESH_BEFORE_EXPIRY_MS) {
            scheduleRefresh(0);
          }
        }
      });
      window.addEventListener('storage', event => {
        if (event.key === ACCESS_TOKEN_EXPIRY_KEY) {
          if (event.newValue && localStorage.getItem(ACCESS_TOKEN_KEY)) {
            scheduleRefresh();
          } else if (refreshTimer !== undefined) {
            clearTimeout(refreshTimer);
            refreshTimer = undefined;
          }
        }
      });
      autoRefreshStarted = true;
    }

    if (localStorage.getItem(ACCESS_TOKEN_KEY)) {
      scheduleRefresh();
    }
  },

  getToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },

  logout(): void {
    if (refreshTimer !== undefined) {
      clearTimeout(refreshTimer);
      refreshTimer = undefined;
    }
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(ACCESS_TOKEN_EXPIRY_KEY);
    void axios.post(
      `${GATEWAY_URL}/v1/auth/logout`,
      null,
      { withCredentials: true }
    ).catch((error: unknown) => {
      console.error('Unable to revoke the refresh-token session.', error);
    });
  },
};
