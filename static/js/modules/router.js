/**
 * Client-Side Router for Immich Quiz
 * Manages deep links, History API (pushState/popstate), and navigation guards.
 */

let currentRouteHandler = null;
let navigationGuardFn = null;
let currentPath = window.location.pathname;

export const RouteType = {
  LOBBY: "LOBBY",
  GAME_ACTIVE: "GAME_ACTIVE",
  GAME_SUMMARY: "GAME_SUMMARY",
  CHALLENGE: "CHALLENGE",
  UNKNOWN: "UNKNOWN",
};

const ROUTE_DEFINITIONS = [
  {
    type: RouteType.LOBBY,
    pattern: /^\/(stats)?$/,
    canonicalPath: () => "/",
  },
  {
    type: RouteType.GAME_SUMMARY,
    pattern: /^\/game\/([^/]+)\/summary$/,
    paramKeys: ["matchId"],
  },
  {
    type: RouteType.GAME_ACTIVE,
    pattern: /^\/game\/([^/]+)$/,
    paramKeys: ["matchId"],
  },
  {
    type: RouteType.CHALLENGE,
    pattern: /^\/play\/([^/]+)$/,
    paramKeys: ["token"],
  },
];

/**
 * Normalize pathname by stripping trailing slashes and defaulting to root.
 * @param {string} pathname
 * @returns {string}
 */
export function normalizePath(pathname) {
  return (pathname || "/").replace(/\/+$/, "") || "/";
}

/**
 * Match a pathname against registered route patterns.
 * @param {string} pathname
 * @returns {{ type: string, params: Record<string, string>, path: string }}
 */
export function parseRoute(pathname) {
  const path = normalizePath(pathname);

  for (const def of ROUTE_DEFINITIONS) {
    const match = path.match(def.pattern);
    if (match) {
      const params = {};
      if (def.paramKeys) {
        def.paramKeys.forEach((key, index) => {
          params[key] = decodeURIComponent(match[index + 1]);
        });
      }
      return {
        type: def.type,
        params,
        path: def.canonicalPath ? def.canonicalPath(params) : path,
      };
    }
  }

  return { type: RouteType.UNKNOWN, params: {}, path };
}

/**
 * Register a global navigation guard before navigating away from a route.
 * @param {(toRoute: ReturnType<typeof parseRoute>, fromRoute: ReturnType<typeof parseRoute>) => boolean} guard
 */
export function setNavigationGuard(guard) {
  navigationGuardFn = guard;
}

/**
 * Navigate to a given path using History API.
 * @param {string} path
 * @param {{ replace?: boolean, state?: any, force?: boolean }} [options]
 */
export function navigate(path, { replace = false, state = null, force = false } = {}) {
  const targetPath = normalizePath(path);
  const fromRoute = parseRoute(currentPath);
  const toRoute = parseRoute(targetPath);

  if (!force && navigationGuardFn && currentPath !== targetPath) {
    const allowed = navigationGuardFn(toRoute, fromRoute);
    if (!allowed) {
      return false;
    }
  }

  if (replace) {
    history.replaceState(state, "", targetPath);
  } else if (window.location.pathname !== targetPath) {
    history.pushState(state, "", targetPath);
  }

  currentPath = targetPath;
  dispatchRoute(toRoute);
  return true;
}

/**
 * Dispatch matched route to the registered handler.
 * @param {ReturnType<typeof parseRoute>} route
 */
function dispatchRoute(route) {
  if (typeof currentRouteHandler === "function") {
    currentRouteHandler(route);
  }
}

/**
 * Initialize the router, attach popstate listener, and dispatch initial route.
 * @param {(route: ReturnType<typeof parseRoute>) => void} handler
 */
export function initRouter(handler) {
  currentRouteHandler = handler;
  currentPath = normalizePath(window.location.pathname);

  window.addEventListener("popstate", (event) => {
    const newPath = normalizePath(window.location.pathname);
    const fromRoute = parseRoute(currentPath);
    const toRoute = parseRoute(newPath);

    if (navigationGuardFn && currentPath !== newPath) {
      const allowed = navigationGuardFn(toRoute, fromRoute);
      if (!allowed) {
        // Restore current URL in browser history
        history.pushState(event.state, "", currentPath);
        return;
      }
    }

    currentPath = newPath;
    dispatchRoute(toRoute);
  });

  const initialRoute = parseRoute(currentPath);
  dispatchRoute(initialRoute);
}
