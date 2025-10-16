import { create } from "zustand";

type PreferencesState = {
  notificationsEnabled: boolean;
  voiceResponses: boolean;
  toggleNotifications: () => void;
  toggleVoiceResponses: () => void;
};

export const usePreferencesStore = create<PreferencesState>((set) => ({
  notificationsEnabled: true,
  voiceResponses: false,
  toggleNotifications: () => set((state) => ({ notificationsEnabled: !state.notificationsEnabled })),
  toggleVoiceResponses: () => set((state) => ({ voiceResponses: !state.voiceResponses }))
}));
