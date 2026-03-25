/**
 * Offline Support Utilities
 * Handles data persistence and sync when offline
 */

const DB_NAME = 'nexus-offline';
const DB_VERSION = 1;

// Store names
const STORES = {
  PENDING_ACTIONS: 'pending-actions',
  CACHED_DATA: 'cached-data',
  CONVERSATIONS: 'conversations',
} as const;

// Action types for offline queue
export interface PendingAction {
  id: string;
  type: 'chat' | 'goal' | 'skill' | 'other';
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  url: string;
  data: unknown;
  timestamp: number;
  retryCount: number;
}

// Open IndexedDB database
function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB not supported'));
      return;
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      // Create stores if they don't exist
      if (!db.objectStoreNames.contains(STORES.PENDING_ACTIONS)) {
        db.createObjectStore(STORES.PENDING_ACTIONS, { keyPath: 'id' });
      }

      if (!db.objectStoreNames.contains(STORES.CACHED_DATA)) {
        const store = db.createObjectStore(STORES.CACHED_DATA, { keyPath: 'key' });
        store.createIndex('timestamp', 'timestamp');
      }

      if (!db.objectStoreNames.contains(STORES.CONVERSATIONS)) {
        db.createObjectStore(STORES.CONVERSATIONS, { keyPath: 'id' });
      }
    };
  });
}

// Queue an action for later sync
export async function queueAction(action: Omit<PendingAction, 'id' | 'timestamp' | 'retryCount'>): Promise<string> {
  const db = await openDatabase();

  return new Promise((resolve, reject) => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const fullAction: PendingAction = {
      ...action,
      id,
      timestamp: Date.now(),
      retryCount: 0,
    };

    const transaction = db.transaction(STORES.PENDING_ACTIONS, 'readwrite');
    const store = transaction.objectStore(STORES.PENDING_ACTIONS);
    const request = store.add(fullAction);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      // Register for background sync if available
      if ('serviceWorker' in navigator && 'sync' in ServiceWorkerRegistration.prototype) {
        navigator.serviceWorker.ready.then((registration) => {
          (registration as ServiceWorkerRegistration & { sync: { register: (tag: string) => Promise<void> } })
            .sync.register('sync-pending-actions');
        });
      }
      resolve(id);
    };
  });
}

// Get all pending actions
export async function getPendingActions(): Promise<PendingAction[]> {
  const db = await openDatabase();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORES.PENDING_ACTIONS, 'readonly');
    const store = transaction.objectStore(STORES.PENDING_ACTIONS);
    const request = store.getAll();

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result || []);
  });
}

// Remove a pending action
export async function removePendingAction(id: string): Promise<void> {
  const db = await openDatabase();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORES.PENDING_ACTIONS, 'readwrite');
    const store = transaction.objectStore(STORES.PENDING_ACTIONS);
    const request = store.delete(id);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// Cache data for offline use
export async function cacheData(key: string, data: unknown, ttlMs = 3600000): Promise<void> {
  const db = await openDatabase();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORES.CACHED_DATA, 'readwrite');
    const store = transaction.objectStore(STORES.CACHED_DATA);
    const request = store.put({
      key,
      data,
      timestamp: Date.now(),
      expiresAt: Date.now() + ttlMs,
    });

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// Get cached data
export async function getCachedData<T>(key: string): Promise<T | null> {
  const db = await openDatabase();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORES.CACHED_DATA, 'readonly');
    const store = transaction.objectStore(STORES.CACHED_DATA);
    const request = store.get(key);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const result = request.result;
      if (!result) {
        resolve(null);
        return;
      }

      // Check if expired
      if (result.expiresAt < Date.now()) {
        // Clean up expired data
        const deleteTransaction = db.transaction(STORES.CACHED_DATA, 'readwrite');
        deleteTransaction.objectStore(STORES.CACHED_DATA).delete(key);
        resolve(null);
        return;
      }

      resolve(result.data as T);
    };
  });
}

// Save conversation for offline access
export async function saveConversation(id: string, messages: Array<{ role: string; content: string }>): Promise<void> {
  const db = await openDatabase();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORES.CONVERSATIONS, 'readwrite');
    const store = transaction.objectStore(STORES.CONVERSATIONS);
    const request = store.put({
      id,
      messages,
      updatedAt: Date.now(),
    });

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// Get saved conversation
export async function getConversation(id: string): Promise<Array<{ role: string; content: string }> | null> {
  const db = await openDatabase();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORES.CONVERSATIONS, 'readonly');
    const store = transaction.objectStore(STORES.CONVERSATIONS);
    const request = store.get(id);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      resolve(request.result?.messages || null);
    };
  });
}

// Clear all offline data
export async function clearOfflineData(): Promise<void> {
  const db = await openDatabase();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(
      [STORES.PENDING_ACTIONS, STORES.CACHED_DATA, STORES.CONVERSATIONS],
      'readwrite'
    );

    transaction.objectStore(STORES.PENDING_ACTIONS).clear();
    transaction.objectStore(STORES.CACHED_DATA).clear();
    transaction.objectStore(STORES.CONVERSATIONS).clear();

    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
}

// Check if we have pending actions
export async function hasPendingActions(): Promise<boolean> {
  const actions = await getPendingActions();
  return actions.length > 0;
}

// Sync pending actions when online
export async function syncPendingActions(): Promise<{ synced: number; failed: number }> {
  const actions = await getPendingActions();
  let synced = 0;
  let failed = 0;

  for (const action of actions) {
    try {
      const response = await fetch(action.url, {
        method: action.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action.data),
      });

      if (response.ok) {
        await removePendingAction(action.id);
        synced++;
      } else {
        failed++;
      }
    } catch {
      failed++;
    }
  }

  return { synced, failed };
}
