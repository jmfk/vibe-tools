import { Message } from './components/AgentInteraction';

type ChatContext = 'setup' | 'planner' | 'issues' | 'interface' | 'database';

type Subscriber = (messages: Message[]) => void;

class ChatStore {
  private messages: Record<ChatContext, Message[]> = {
    setup: [{ role: 'Architect', content: "Hello! I am the Setup Agent. I can help you configure your project and environment. What would you like to set up first?" }],
    planner: [{ role: 'Architect', content: "Hello! I am the Planner Architect. How can I help you with your PRDs today?" }],
    issues: [{ role: 'Architect', content: "Hello! I am the Issues Agent. How can I help you with your bug tracking today?" }],
    interface: [{ role: 'Architect', content: "Hello! I am the Interface Designer Agent. How can I help you design your UI today?" }],
    database: [{ role: 'Architect', content: "Hello! I am the Database Designer Agent. How can I help you architect your schema today?" }]
  };

  private subscribers: Record<ChatContext, Set<Subscriber>> = {
    setup: new Set(),
    planner: new Set(),
    issues: new Set(),
    interface: new Set(),
    database: new Set()
  };

  getMessages(context: ChatContext): Message[] {
    return this.messages[context];
  }

  addMessage(context: ChatContext, message: Message) {
    this.messages[context] = [...this.messages[context], message];
    this.notify(context);
  }

  clearChat(context: ChatContext) {
    this.messages[context] = [this.messages[context][0]]; // Keep the first architect message
    this.notify(context);
  }

  subscribe(context: ChatContext, callback: Subscriber) {
    this.subscribers[context].add(callback);
    return () => this.subscribers[context].delete(callback);
  }

  private notify(context: ChatContext) {
    const messages = this.messages[context];
    this.subscribers[context].forEach(callback => callback(messages));
  }
}

export const chatStore = new ChatStore();
