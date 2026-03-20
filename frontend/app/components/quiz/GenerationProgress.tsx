import { Loader2, Sparkles } from 'lucide-react';
import { Progress } from '../ui/progress';

interface GenerationProgressProps {
  stage: 'pregenerated' | 'generating' | 'retrying';
  retryCount?: number;
  maxRetries?: number;
}

export function GenerationProgress({
  stage,
  retryCount = 0,
  maxRetries = 3,
}: GenerationProgressProps) {
  const messages = {
    pregenerated: 'Loading from question bank...',
    generating: 'Crafting new questions just for you...',
    retrying: `Retrying generation... (attempt ${retryCount}/${maxRetries})`,
  };

  const progressValue = stage === 'generating' ? 60 : stage === 'pregenerated' ? 30 : 45;

  return (
    <div className="flex flex-col items-center justify-center h-full space-y-4">
      <div className="relative">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
        <Sparkles className="h-4 w-4 absolute -top-1 -right-1 text-amber-500" />
      </div>
      <p className="text-muted-foreground text-center">{messages[stage]}</p>
      <Progress value={progressValue} className="w-48" />
    </div>
  );
}
