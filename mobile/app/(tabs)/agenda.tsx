import { FlatList, SafeAreaView, StyleSheet, Text, View } from "react-native";

const agendaItems = [
  { id: "1", title: "Team stand-up", time: "09:00" },
  { id: "2", title: "Product sync", time: "11:00" },
  { id: "3", title: "Design review", time: "15:00" }
];

export default function AgendaScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <FlatList
        data={agendaItems}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.time}>{item.time}</Text>
            <Text style={styles.title}>{item.title}</Text>
          </View>
        )}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: "#ffffff"
  },
  card: {
    padding: 16,
    backgroundColor: "#f5f5f5",
    borderRadius: 12
  },
  separator: {
    height: 12
  },
  time: {
    fontSize: 12,
    color: "#666",
    marginBottom: 4
  },
  title: {
    fontSize: 16,
    fontWeight: "600"
  }
});
