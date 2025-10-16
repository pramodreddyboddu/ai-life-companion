import { Tabs } from "expo-router";

export default function TabLayout() {
  return (
    <Tabs screenOptions={{ headerTitleAlign: "center" }}>
      <Tabs.Screen
        name="index"
        options={{
          href: null
        }}
      />
      <Tabs.Screen
        name="chat"
        options={{
          title: "Chat"
        }}
      />
      <Tabs.Screen
        name="agenda"
        options={{
          title: "Agenda"
        }}
      />
      <Tabs.Screen
        name="reminders"
        options={{
          title: "Reminders"
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Settings"
        }}
      />
    </Tabs>
  );
}
