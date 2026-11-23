// A tiny external store that lets the always-loaded parts of the app (the Profiles tab, App) see the account state without importing the account feature
// (which is a lazy chunk, only present when the Firebase config is set).  The account chunk PUBLISHES here; with the feature off nothing ever publishes and
// the readers see `null`.  Keep this file free of heavy imports: it is part of the main bundle.
import { useSyncExternalStore } from "react";
import type { ProfileSyncStatus } from "./merge";

export interface CloudBridgeState {
  signedIn: boolean;
  busy: boolean; // loading or saving
  dirtyCount: number;
  statuses: Record<string, ProfileSyncStatus>;
  errors: Record<string, string>; // per profile: why it could not be saved
  save: () => void;
  refresh: () => void;
}

let current: CloudBridgeState | null = null;
const listeners = new Set<() => void>();

export function publishCloud(next: CloudBridgeState | null): void {
  current = next;
  listeners.forEach((fn) => fn());
}
export const getCloudBridge = (): CloudBridgeState | null => current;
export function subscribeCloudBridge(fn: () => void): () => void {
  listeners.add(fn);
  return () => void listeners.delete(fn);
}
/** null while the account feature is off (or not mounted yet). */
export function useCloudBridge(): CloudBridgeState | null {
  return useSyncExternalStore(subscribeCloudBridge, getCloudBridge, getCloudBridge);
}

// the profile the user loaded last (stored with the account settings as `lastProfileId`)
let lastProfileId: string | undefined;
export const noteLastProfile = (id: string): void => void (lastProfileId = id);
export const getLastProfile = (): string | undefined => lastProfileId;
