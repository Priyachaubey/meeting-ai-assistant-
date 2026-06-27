import { create } from "zustand";

const STORAGE_KEY = "convopilot.token";

type AuthState = {
  token: string | null;
  hydrated: boolean;
  setToken: (token: string) => void;
  logout: () => void;
  hydrate: () => void;
};

// Plain localStorage instead of zustand's persist middleware: this repo's node_modules
// turned out to be hollow placeholder directories (see AUDIT.md), so we can't be sure
// persist's dependency chain is actually resolvable. This has zero extra dependencies.
export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  hydrated: false,
  setToken: (token: string) => {
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, token);
    set({ token });
  },
  logout: () => {
    if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
    set({ token: null });
  },
  hydrate: () => {
    if (typeof window === "undefined") return;
    set({ token: window.localStorage.getItem(STORAGE_KEY), hydrated: true });
  },
}));
