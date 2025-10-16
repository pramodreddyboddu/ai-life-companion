import { useState } from "react";
import { StyleSheet, Switch, Text, View } from "react-native";

const remindersSeed = [
  { id: "1", label: "Daily summary", defaultEnabled: true },
  { id: "2", label: "Agenda updates", defaultEnabled: false },
  { id: "3", label: "Task follow-ups", defaultEnabled: true }
];

export default function RemindersScreen() {
  const [reminders, setReminders] = useState(
    remindersSeed.map((item) => ({ ...item, enabled: item.defaultEnabled }))
  );

  return (
    <View style={styles.container}>
      {reminders.map((reminder) => (
        <View key={reminder.id} style={styles.row}>
          <Text style={styles.label}>{reminder.label}</Text>
          <Switch
            value={reminder.enabled}
            onValueChange={(value) =>
              setReminders((current) =>
                current.map((item) => (item.id === reminder.id ? { ...item, enabled: value } : item))
              )
            }
          />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: "#ffffff",
    gap: 12
  },
  row: {
    padding: 16,
    backgroundColor: "#f8f8f8",
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  label: {
    fontSize: 16
  }
});
