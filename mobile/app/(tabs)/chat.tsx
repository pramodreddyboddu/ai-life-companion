import { useCallback, useEffect, useState } from "react";
import { GiftedChat, IMessage } from "react-native-gifted-chat";

export default function ChatScreen() {
  const [messages, setMessages] = useState<IMessage[]>([]);

  useEffect(() => {
    setMessages([
      {
        _id: 1,
        text: "Hello! Ask me anything about your day.",
        createdAt: new Date(),
        user: {
          _id: 2,
          name: "AI Companion"
        }
      }
    ]);
  }, []);

  const handleSend = useCallback((newMessages: IMessage[] = []) => {
    setMessages((previousMessages) => GiftedChat.append(previousMessages, newMessages));
  }, []);

  return (
    <GiftedChat
      messages={messages}
      onSend={(newMessages) => handleSend(newMessages)}
      user={{
        _id: 1
      }}
    />
  );
}
