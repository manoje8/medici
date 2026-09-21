import { FileText, MessageCircle, Search } from 'lucide-react';

export function WelcomeMessage() {
  return (
    <div className="flex items-center justify-center min-h-[60vh] px-4">
      <div className="max-w-lg text-center animate-[bounce-in_0.4s_cubic-bezier(0.34,1.56,0.64,1)]">
        <div className="h-20 w-20 mx-auto rounded-2xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-glow-strong mb-6">
          <span className="text-4xl">🤖</span>
        </div>

        <h2 className="text-2xl font-bold text-text-primary mb-2">
          Welcome to <span className="bg-gradient-to-r from-primary-light to-accent bg-clip-text text-transparent">Medici</span>
        </h2>
        <p className="text-sm text-text-muted mb-8">
          Your Intelligent Document Analysis Assistant
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <FeatureCard
            icon={<FileText className="h-5 w-5" />}
            title="Document Analysis"
            description="Upload documents and ask questions"
          />
          <FeatureCard
            icon={<MessageCircle className="h-5 w-5" />}
            title="Intelligent Queries"
            description="Get detailed answers with sources"
          />
          <FeatureCard
            icon={<Search className="h-5 w-5" />}
            title="Context-Aware"
            description="I remember our conversation"
          />
        </div>

        <p className="text-xs text-text-muted/50 mt-8">
          Start by uploading a document or asking me a question!
        </p>
      </div>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="glass rounded-xl p-4 text-left hover:border-primary/30 transition-all duration-200 group">
      <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center text-primary-light mb-3 group-hover:bg-primary/20 transition-colors">
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-text-primary mb-1">{title}</h3>
      <p className="text-xs text-text-muted leading-relaxed">{description}</p>
    </div>
  );
}
