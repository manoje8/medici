import { FileText, MessageCircle, Search } from 'lucide-react';

export function WelcomeMessage() {
  return (
    <div className="flex items-center justify-center min-h-[60vh] px-4">
      <div className="max-w-2xl text-center animate-[bounce-in_0.4s_cubic-bezier(0.34,1.56,0.64,1)]">

        <h2 className="text-2xl font-bold text-text-primary mb-2">
          Welcome to <span className="bg-gradient-to-r from-primary-light to-accent bg-clip-text text-transparent">Medici</span>
        </h2>
        <p className="text-sm text-text-muted mb-8">
          Your Intelligent Document Analysis Assistant
        </p>

        {/* <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
        </div> */}

        {/* <p className="text-xs text-text-muted mt-8">
          Start by uploading a document or asking me a question!
        </p> */}
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
    <div className="glass rounded-xl p-4 text-left hover:border-primary-light transition-all duration-200 group">
      <div className="h-9 w-9 rounded-lg bg-primary-glow flex items-center justify-center text-primary-light mb-3 group-hover:bg-primary-glow transition-colors">
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-text-primary mb-1">{title}</h3>
      <p className="text-xs text-text-muted leading-relaxed">{description}</p>
    </div>
  );
}
