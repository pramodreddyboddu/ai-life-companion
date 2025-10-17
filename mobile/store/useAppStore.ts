import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";
import { create } from "zustand";
import { persist } from "zustand/middleware";

const DEFAULT_API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  (Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined)?.apiBaseUrl ??
  "http://localhost:8000";

type AppState = {
  apiBaseUrl: string;
  apiKey: string | null;
  pushToken: string | null;
  setApiBaseUrl: (url: string) => void;
  setApiKey: (key: string | null) => void;
  setPushToken: (token: string | null) => void;
};

export { DEFAULT_API_BASE_URL };

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      apiBaseUrl: DEFAULT_API_BASE_URL,
      apiKey: null,
      pushToken: null,
      setApiBaseUrl: (url) => set({ apiBaseUrl: url.trim() || DEFAULT_API_BASE_URL }),
      setApiKey: (key) => set({ apiKey: key }),
      setPushToken: (token) => set({ pushToken: token })
    }),
    {
      name: "app-store",
      storage: {
        getItem: (name) => AsyncStorage.getItem(name),
        setItem: (name, value) => AsyncStorage.setItem(name, value),
        removeItem: (name) => AsyncStorage.removeItem(name)
      },
      partialize: (state) => ({
        apiBaseUrl: state.apiBaseUrl,
        apiKey: state.apiKey,
        pushToken: state.pushToken
      })
    }
  )
);
