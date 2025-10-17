import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { GiftedChat, IMessage } from "react-native-gifted-chat";

import { postJson } from "../../lib/api";
import { useAppStore } from "../../store/useAppStore";

type ChatAction = {
  tool: string;
  params?: Record<string, unknown>;
  result?: Record<string, unknown>;
};

type ChatResponse = {
  assistant_message: string;
  actions: ChatAction[];
};

const ASSISTANT_USER = { _id: 2, name: "AI Companion" };
const PERSONA_KEY = "accountability";

export default function ChatScreen() {
  const [messages, setMessages] = useState<IMessage[]>([]);
  const [actions, setActions] = useState<ChatAction[]>([]);
  const [isSending, setIsSending] = useState(false);
  const { apiKey } = useAppStore();

  useEffect(() => {
    setMessages([
      {
        _id: "assistant-greeting",
        text: "Hello! Ask me anything about your day.",
        createdAt: new Date(),
        user: ASSISTANT_USER
      }
    ]);
  }, []);

  const formatAction = useCallback((action: ChatAction) => {
    if (action.tool === "schedule_reminder") {
      const text = (action.result?.text || action.params?.text) as string | undefined;
      const runTs = (action.result?.run_ts || action.params?.run_ts) as string | undefined;
      if (text && runTs) {
        return `${text} → ${runTs}`;
      }
    }
    if (action.result && Object.keys(action.result).length > 0) {
      return JSON.stringify(action.result);
    }
    if (action.params && Object.keys(action.params).length > 0) {
      return JSON.stringify(action.params);
    }
    return "Action completed";
  }, []);

  const handleSend = useCallback(
    async (newMessages: IMessage[] = []) => {
      if (newMessages.length === 0) {
        return;
      }

      if (!apiKey) {
        Alert.alert("API Key Required", "Add an API key in Settings before chatting.");
        return;
      }

      setMessages((previous) => GiftedChat.append(previous, newMessages));
      const latest = newMessages[0];

      try {
        setIsSending(true);
        const response = await postJson<ChatResponse>("/chat", {
          message: latest.text,
          persona_key: PERSONA_KEY
        });

        const assistantMessage: IMessage = {
          _id: `assistant-${Date.now()}`,
          text: response.assistant_message,
          createdAt: new Date(),
          user: ASSISTANT_USER
        };

        setMessages((previous) => GiftedChat.append(previous, [assistantMessage]));
        setActions(response.actions ?? []);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to send message.";
        Alert.alert("Chat Error", message);
      } finally {
        setIsSending(false);
      }
    },
    [apiKey]
  );

  const actionsFooter = useMemo(() => {
    if (!actions.length) {
      return null;
    }

    return (
      <View style={styles.actionsContainer}>
        {actions.map((action, index) => (
          <View key={`${action.tool}-${index}`} style={styles.actionChip}>
            <Text style={styles.actionChipLabel}>{action.tool}</Text>
            <Text style={styles.actionChipText}>{formatAction(action)}</Text>
          </View>
        ))}
      </View>
    );
  }, [actions, formatAction]);

  return (
    <GiftedChat
      messages={messages}
      onSend={handleSend}
      user={{ _id: 1 }}
      isTyping={isSending}
      renderChatFooter={() => actionsFooter}
    />
  );
}

const styles = StyleSheet.create({
  actionsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 4,
    gap: 8
  },
  actionChip: {
    backgroundColor: "#eef2ff",
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#c7d2fe",
    maxWidth: "100%"
  },
  actionChipLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#4338ca",
    textTransform: "uppercase"
  },
  actionChipText: {
    marginTop: 2,
    fontSize: 13,
    color: "#312e81"
  }
});
