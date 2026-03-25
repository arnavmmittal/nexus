/**
 * Nexus Service Worker
 * Handles offline caching, push notifications, and background sync
 */

const CACHE_NAME = 'nexus-v1';
const RUNTIME_CACHE = 'nexus-runtime-v1';
const API_CACHE = 'nexus-api-v1';

// Static assets to cache on install
const STATIC_ASSETS = [
  '/',
  '/jarvis',
  '/goals',
  '/skills',
  '/settings',
  '/ultron',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

// API routes that can be cached for offline
const CACHEABLE_API_ROUTES = [
  '/api/widgets/today',
  '/api/widgets/skills',
  '/api/widgets/goals',
  '/api/skills',
  '/api/goals',
];

// ============ Installation ============

self.addEventListener('install', (event) => {
  console.log('[SW] Installing Service Worker...');

  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Caching static assets');
        // Don't fail install if some assets fail to cache
        return Promise.allSettled(
          STATIC_ASSETS.map(url =>
            cache.add(url).catch(err => {
              console.warn(`[SW] Failed to cache ${url}:`, err);
            })
          )
        );
      })
      .then(() => {
        console.log('[SW] Installation complete');
        return self.skipWaiting();
      })
  );
});

// ============ Activation ============

self.addEventListener('activate', (event) => {
  console.log('[SW] Activating Service Worker...');

  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter(name => name.startsWith('nexus-') && name !== CACHE_NAME && name !== RUNTIME_CACHE && name !== API_CACHE)
            .map(name => {
              console.log('[SW] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => {
        console.log('[SW] Activation complete');
        return self.clients.claim();
      })
  );
});

// ============ Fetch Handling ============

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests and chrome-extension requests
  if (request.method !== 'GET' || url.protocol === 'chrome-extension:') {
    return;
  }

  // Handle API requests
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request));
    return;
  }

  // Handle navigation requests (HTML pages)
  if (request.mode === 'navigate') {
    event.respondWith(handleNavigationRequest(request));
    return;
  }

  // Handle static assets
  event.respondWith(handleStaticRequest(request));
});

async function handleApiRequest(request) {
  const url = new URL(request.url);
  const isCacheable = CACHEABLE_API_ROUTES.some(route => url.pathname.startsWith(route));

  try {
    // Network first for API
    const response = await fetch(request);

    // Cache successful responses for cacheable routes
    if (response.ok && isCacheable) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }

    return response;
  } catch (error) {
    console.log('[SW] Network failed for API, checking cache:', url.pathname);

    // Try cache for cacheable routes
    if (isCacheable) {
      const cachedResponse = await caches.match(request);
      if (cachedResponse) {
        console.log('[SW] Serving cached API response:', url.pathname);
        return cachedResponse;
      }
    }

    // Return offline JSON response
    return new Response(
      JSON.stringify({
        error: 'offline',
        message: 'You are offline. This data will sync when connection is restored.'
      }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

async function handleNavigationRequest(request) {
  try {
    // Try network first
    const response = await fetch(request);

    // Cache the response
    const cache = await caches.open(RUNTIME_CACHE);
    cache.put(request, response.clone());

    return response;
  } catch (error) {
    console.log('[SW] Network failed for navigation, checking cache');

    // Try cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    // Fallback to cached home page
    const fallback = await caches.match('/');
    if (fallback) {
      return fallback;
    }

    // Final fallback: offline page
    return new Response(
      `<!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Nexus - Offline</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            background: #0a0a0a;
            color: #fff;
            font-family: system-ui, -apple-system, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
            text-align: center;
          }
          .container { max-width: 400px; }
          h1 { font-size: 48px; margin-bottom: 16px; }
          p { color: #a1a1a1; margin-bottom: 24px; line-height: 1.6; }
          button {
            background: #10b981;
            color: #000;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
          }
          button:hover { background: #0d9668; }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Offline</h1>
          <p>You're currently offline. Jarvis will be back as soon as your connection is restored.</p>
          <button onclick="location.reload()">Try Again</button>
        </div>
      </body>
      </html>`,
      { headers: { 'Content-Type': 'text/html' } }
    );
  }
}

async function handleStaticRequest(request) {
  // Try cache first for static assets
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }

  try {
    // Fetch from network
    const response = await fetch(request);

    // Cache static assets
    if (response.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, response.clone());
    }

    return response;
  } catch (error) {
    console.log('[SW] Network failed for static asset:', request.url);

    // Return empty response for missing static assets
    return new Response('', { status: 404 });
  }
}

// ============ Push Notifications ============

self.addEventListener('push', (event) => {
  console.log('[SW] Push notification received');

  let data = {
    title: 'Nexus',
    body: 'You have a new notification',
    icon: '/icons/icon-192.png',
    badge: '/icons/badge-72.png',
    tag: 'nexus-notification',
    data: {}
  };

  try {
    if (event.data) {
      const payload = event.data.json();
      data = { ...data, ...payload };
    }
  } catch (e) {
    console.error('[SW] Error parsing push data:', e);
    if (event.data) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || '/icons/icon-192.png',
    badge: data.badge || '/icons/badge-72.png',
    tag: data.tag || 'nexus-notification',
    data: data.data || {},
    vibrate: data.priority === 'critical' ? [200, 100, 200, 100, 200] : [100, 50, 100],
    requireInteraction: data.priority === 'critical' || data.priority === 'high',
    actions: data.actions || [],
    timestamp: Date.now(),
    renotify: true,
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked:', event.notification.tag);

  event.notification.close();

  const data = event.notification.data || {};
  const actionUrl = data.action_url || '/';

  // Handle action button clicks
  if (event.action) {
    console.log('[SW] Action clicked:', event.action);
    // Find the action and its URL
    const action = (event.notification.actions || []).find(a => a.action === event.action);
    if (action && action.url) {
      event.waitUntil(clients.openWindow(action.url));
      return;
    }
  }

  // Focus existing window or open new one
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Check if there's already a window open
        for (const client of clientList) {
          if (client.url.includes(self.location.origin)) {
            client.focus();
            if (actionUrl !== '/') {
              client.navigate(actionUrl);
            }
            // Send message to client about notification click
            client.postMessage({
              type: 'notification-click',
              data: data
            });
            return;
          }
        }
        // No window open, open new one
        return clients.openWindow(actionUrl);
      })
  );
});

self.addEventListener('notificationclose', (event) => {
  console.log('[SW] Notification closed:', event.notification.tag);

  // Track notification dismissals
  const data = event.notification.data || {};
  if (data.id) {
    // Could send analytics here
  }
});

// ============ Background Sync ============

self.addEventListener('sync', (event) => {
  console.log('[SW] Background sync:', event.tag);

  if (event.tag === 'sync-pending-actions') {
    event.waitUntil(syncPendingActions());
  }

  if (event.tag === 'sync-conversations') {
    event.waitUntil(syncConversations());
  }
});

async function syncPendingActions() {
  console.log('[SW] Syncing pending actions...');

  try {
    // Get pending actions from IndexedDB
    const db = await openDatabase();
    const actions = await getAllPendingActions(db);

    for (const action of actions) {
      try {
        const response = await fetch(action.url, {
          method: action.method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(action.data)
        });

        if (response.ok) {
          // Remove from pending
          await removePendingAction(db, action.id);
          console.log('[SW] Synced action:', action.id);
        }
      } catch (error) {
        console.error('[SW] Failed to sync action:', action.id, error);
      }
    }

    // Notify clients
    const allClients = await clients.matchAll({ includeUncontrolled: true });
    allClients.forEach(client => {
      client.postMessage({ type: 'sync-complete', count: actions.length });
    });

  } catch (error) {
    console.error('[SW] Sync failed:', error);
  }
}

async function syncConversations() {
  console.log('[SW] Syncing conversations...');
  // This could sync conversation history with the server
}

// ============ Periodic Sync ============

self.addEventListener('periodicsync', (event) => {
  console.log('[SW] Periodic sync:', event.tag);

  if (event.tag === 'update-widgets') {
    event.waitUntil(updateWidgetCache());
  }

  if (event.tag === 'check-notifications') {
    event.waitUntil(checkForNotifications());
  }
});

async function updateWidgetCache() {
  console.log('[SW] Updating widget cache...');

  const cache = await caches.open(API_CACHE);

  for (const route of CACHEABLE_API_ROUTES) {
    try {
      const response = await fetch(route);
      if (response.ok) {
        await cache.put(route, response);
        console.log('[SW] Updated cache for:', route);
      }
    } catch (error) {
      console.log('[SW] Failed to update cache for:', route);
    }
  }
}

async function checkForNotifications() {
  console.log('[SW] Checking for notifications...');
  // Could poll a notifications endpoint here
}

// ============ IndexedDB Helpers ============

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('nexus-sw', 1);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;

      if (!db.objectStoreNames.contains('pending-actions')) {
        db.createObjectStore('pending-actions', { keyPath: 'id' });
      }

      if (!db.objectStoreNames.contains('cached-conversations')) {
        db.createObjectStore('cached-conversations', { keyPath: 'id' });
      }
    };
  });
}

function getAllPendingActions(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('pending-actions', 'readonly');
    const store = transaction.objectStore('pending-actions');
    const request = store.getAll();

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result || []);
  });
}

function removePendingAction(db, id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('pending-actions', 'readwrite');
    const store = transaction.objectStore('pending-actions');
    const request = store.delete(id);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// ============ Message Handling ============

self.addEventListener('message', (event) => {
  console.log('[SW] Message received:', event.data);

  if (event.data.type === 'skip-waiting') {
    self.skipWaiting();
  }

  if (event.data.type === 'cache-page') {
    cacheSpecificPage(event.data.url);
  }

  if (event.data.type === 'queue-action') {
    queuePendingAction(event.data.action);
  }

  if (event.data.type === 'clear-cache') {
    clearAllCaches();
  }
});

async function cacheSpecificPage(url) {
  const cache = await caches.open(RUNTIME_CACHE);
  try {
    const response = await fetch(url);
    await cache.put(url, response);
    console.log('[SW] Cached page:', url);
  } catch (error) {
    console.error('[SW] Failed to cache page:', url, error);
  }
}

async function queuePendingAction(action) {
  const db = await openDatabase();
  const transaction = db.transaction('pending-actions', 'readwrite');
  const store = transaction.objectStore('pending-actions');

  const actionWithId = {
    ...action,
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    timestamp: Date.now()
  };

  store.add(actionWithId);
  console.log('[SW] Queued action:', actionWithId.id);

  // Register for background sync
  if ('sync' in self.registration) {
    await self.registration.sync.register('sync-pending-actions');
  }
}

async function clearAllCaches() {
  const cacheNames = await caches.keys();
  await Promise.all(
    cacheNames
      .filter(name => name.startsWith('nexus-'))
      .map(name => caches.delete(name))
  );
  console.log('[SW] All caches cleared');
}

console.log('[SW] Service Worker loaded');
