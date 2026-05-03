/* LedgerHaul — App Access Guard
   Checks for a valid JWT token and redirects to login if missing.
   Include this script on all /app/* pages that require authentication. */

(function () {
  'use strict';

  var token = localStorage.getItem('lh_token');
  var publicPaths = ['/login.html', '/signup.html', '/forgot-password.html', '/reset-password.html', '/check-email.html', '/verify-success.html', '/access-denied.html'];
  var currentPath = window.location.pathname;

  var isPublic = publicPaths.some(function (p) { return currentPath.endsWith(p); });

  if (!isPublic && !token) {
    window.location.replace('login.html');
    return;
  }

  // Optionally validate token expiry client-side
  if (token) {
    try {
      var payload = JSON.parse(atob(token.split('.')[1]));
      if (payload.exp && Date.now() / 1000 > payload.exp) {
        localStorage.removeItem('lh_token');
        if (!isPublic) { window.location.replace('login.html'); }
      }
    } catch (e) {
      // Token parsing failed — let server validate
    }
  }
})();
