import { useState } from "react";
import { Button, StyleSheet, Switch, Text, View } from "react-native";
import * as Notifications from "expo-notifications";

import { usePreferencesStore } from "../../lib/preferencesStore";

export default function SettingsScreen() {
  const { notificationsEnabled, voiceResponses, toggleNotifications, toggleVoiceResponses } =
    usePreferencesStore();
  const [permissionStatus, setPermissionStatus] = useState<string>("Unknown");

  const requestNotificationPermission = async () => {
    const { status } = await Notifications.requestPermissionsAsync();
    setPermissionStatus(status);
  };

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <View>
          <Text style={styles.title}>Notifications</Text>
          <Text style={styles.subtitle}>Enable AI companion reminders and alerts.</Text>
        </View>
        <Switch value={notificationsEnabled} onValueChange={toggleNotifications} />
      </View>

      <View style={styles.row}>
        <View>
          <Text style={styles.title}>Voice Responses</Text>
          <Text style={styles.subtitle}>Receive spoken summaries via the companion.</Text>
        </View>
        <Switch value={voiceResponses} onValueChange={toggleVoiceResponses} />
      </View>

      <View style={styles.row}>
        <View>
          <Text style={styles.title}>Notification Permissions</Text>
          <Text style={styles.subtitle}>Status: {permissionStatus}</Text>
        </View>
        <Button title="Request Access" onPress={requestNotificationPermission} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#ffffff",
    padding: 16,
    gap: 16
  },
  row: {
    padding: 16,
    borderRadius: 12,
    backgroundColor: "#f1f1f1"
  },
  title: {
    fontSize: 16,
    fontWeight: "600"
  },
  subtitle: {
    fontSize: 13,
    color: "#555",
    marginTop: 4
  }
});
