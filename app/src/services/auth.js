import Cookies from 'js-cookie';

export const authService = {
  isAuthenticated: () => !!Cookies.get('access_token'),

  login: (accessToken, refreshToken, rememberMe = false) => {
    const accessExpires = rememberMe ? 30 : 1;
    const refreshExpires = rememberMe ? 60 : 7;
    Cookies.set('access_token', accessToken, { expires: accessExpires });
    Cookies.set('refresh_token', refreshToken, { expires: refreshExpires });
  },

  logout: () => {
    Cookies.remove('access_token');
    Cookies.remove('refresh_token');
  },

  getAccessToken: () => Cookies.get('access_token'),
  getRefreshToken: () => Cookies.get('refresh_token'),

  getCurrentUser: () => {
    const token = Cookies.get('access_token');
    if (!token) return null;
    try {
      const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      return JSON.parse(decodeURIComponent(atob(base64).split('').map((c) =>
        '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
      ).join('')));
    } catch {
      return null;
    }
  },
};
