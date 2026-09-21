import { AuthGate } from '@/features/auth/AuthGate';
import { ChatPage } from '@/features/chat/ChatPage';

function App() {
  return (
    <AuthGate>
      <ChatPage />
    </AuthGate>
  );
}

export default App;
