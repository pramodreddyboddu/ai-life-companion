import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";
import { persist } from "zustand/middleware";

type AppState = {
  apiKey: string | null;
  pushToken: string | null;
  setApiKey: (key: string | null) => void;
  setPushToken: (token: string | null) => void;
};

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      apiKey: null,
      pushToken: null,
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
      partialize: (state) => ({ apiKey: state.apiKey, pushToken: state.pushToken })
    }
  )
);
