/** Framework-independent client for React or React Native.
 * Keep database credentials on the backend. Store mobile tokens using your
 * platform's secure storage. This example retains the token in memory only.
 */
export class CampusAPI {
  private token: string | null = null;
  constructor(private readonly baseURL: string) {}
  setToken(token: string | null) { this.token = token; }
  async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const response = await fetch(`${this.baseURL}/v1${path}`, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 204) return undefined as T;
    const result = await response.json();
    if (!response.ok) {
      if (response.status === 401) this.token = null;
      throw new Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
    }
    return result as T;
  }
  async login(email: string, password: string) {
    const result = await this.request<{access_token: string}>('/auth/login', 'POST', {email,password});
    this.setToken(result.access_token);
    return result;
  }
  async logout() {
    try { await this.request('/auth/logout','POST'); }
    finally { this.setToken(null); }
  }
}

// Usage after account approval:
// const api = new CampusAPI('http://localhost:8000');
// await api.login(emailFromForm, passwordFromForm);
// const clubs = await api.request('/clubs');
// await api.request(`/recruitments/${recruitmentId}/applications`, 'POST',
//   {message: 'I build Python projects and want to join the technical team.'});
// const updates = await api.request('/notifications');
// Your client never sends an admin/coordinator role; the server checks the DB.
