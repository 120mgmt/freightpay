/* LedgerHaul — Client Configuration
   HOW TO USE:
   - In production: inject API_BASE_URL at build time or via meta tag
   - In development: set window.LH_CONFIG before this file loads
   - Never leave apiBase empty in production — this will throw an error

   Meta tag injection example (in HTML <head>):
   <meta name="lh-api-base" content="https://api.ledgerhaul.com">
*/

(function () {
  // 1. Check for injected meta tag (preferred for server-rendered envs)
  var metaTag = document.querySelector('meta[name="lh-api-base"]');
  var apiBaseFromMeta = metaTag ? metaTag.getAttribute("content") : null;

  // 2. Check for pre-set window config
  var presetConfig = window.LH_CONFIG || {};

  // 3. Resolve final apiBase
  var resolvedApiBase = apiBaseFromMeta || presetConfig.apiBase || "";

  // 4. Fail loudly in non-production if not set — prevents silent prod API calls
  if (!resolvedApiBase) {
    console.error(
      "[LedgerHaul] apiBase is not set. " +
      "Set a <meta name=\"lh-api-base\" content=\"...\"> tag or window.LH_CONFIG.apiBase before loading config.js. " +
      "API calls will fail."
    );
  }

  window.LH_CONFIG = {
    apiBase: resolvedApiBase,
    stripePublishableKey: presetConfig.stripePublishableKey || "",
    env: presetConfig.env || "production",
  };
})();