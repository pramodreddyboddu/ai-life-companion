import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Slot } from "expo-router";
import { useEffect, useState } from "react";
import { Alert, Platform } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { StatusBar } from "expo-status-bar";

import { postJson } from "../lib/api";
import { useAppStore } from "../store/useAppStore";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false
  })
});

async function registerForPushNotificationsAsync() {
  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;
  if (existingStatus !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== "granted") {
    throw new Error("Push notification permission denied.");
  }

  const projectId =
    (Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined)?.eas?.projectId ??
    Constants.easConfig?.projectId;

  const tokenResponse = await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined);
  return tokenResponse.data;
}

function usePushRegistration() {
  const apiKey = useAppStore((state) => state.apiKey);
  const pushToken = useAppStore((state) => state.pushToken);
  const setPushToken = useAppStore((state) => state.setPushToken);

  useEffect(() => {
    if (!apiKey || pushToken) {
      return;
    }

    let isMounted = true;

    const register = async () => {
      try {
        const token = await registerForPushNotificationsAsync();
        if (!isMounted) {
          return;
        }
        setPushToken(token);
        await postJson("/users/push-token", { push_token: token });
      } catch (error) {
        console.error("Failed to register push notifications", error);
        if (isMounted) {
          Alert.alert("Notifications", "Unable to register device for push notifications.");
        }
      }
    };

    register();

    return () => {
      isMounted = false;
    };
  }, [apiKey, pushToken, setPushToken]);
}

export default function RootLayout() {
  const [queryClient] = useState(() => new QueryClient());
  usePushRegistration();

  useEffect(() => {
    if (Platform.OS === "android") {
      Notifications.setNotificationChannelAsync("default", {
        name: "default",
        importance: Notifications.AndroidImportance.MAX
      });
    }
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <StatusBar style="auto" />
        <Slot />
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
