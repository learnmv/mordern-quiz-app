'use client';

import { Check, Flag } from 'lucide-react';
import { Button } from '../ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';

interface QuestionNavigatorProps {
  totalQuestions: number;
  currentQ: number;
  answered: Record<number, boolean>;
  onNavigate: (index: number) => void;
  flagged?: Record<number, boolean>;
  onToggleFlag?: (index: number) => void;
}

export function QuestionNavigator({
  totalQuestions,
  currentQ,
  answered,
  onNavigate,
  flagged = {},
}: QuestionNavigatorProps) {
  const answeredCount = Object.keys(answered).filter(k => answered[Number(k)]).length;

  return (
    <TooltipProvider>
      <div className="p-4 border-b">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-sm">Question Navigator</h3>
          <span className="text-xs text-muted-foreground">
            {answeredCount}/{totalQuestions} answered
          </span>
        </div>
        <div className="grid grid-cols-5 gap-2">
          {Array.from({ length: totalQuestions }, (_, i) => {
            const isAnswered = answered[i];
            const isCurrent = i === currentQ;
            const isFlagged = flagged[i];

            return (
              <Tooltip key={i}>
                <TooltipTrigger asChild>
                  <Button
                    variant={isCurrent ? 'default' : isAnswered ? 'secondary' : 'outline'}
                    size="sm"
                    className={`h-10 w-full relative ${
                      isFlagged ? 'border-amber-500 border-2' : ''
                    }`}
                    onClick={() => onNavigate(i)}
                  >
                    {isAnswered ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <span className="text-xs">{i + 1}</span>
                    )}
                    {isFlagged && (
                      <span className="absolute -top-1 -right-1">
                        <Flag className="h-3 w-3 text-amber-500 fill-amber-500" />
                      </span>
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Question {i + 1}</p>
                  {isAnswered && <p className="text-xs text-green-500">Answered</p>}
                  {isFlagged && <p className="text-xs text-amber-500">Flagged</p>}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>

        {/* Legend */}
        <div className="flex gap-4 mt-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-primary" />
            <span>Current</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-secondary" />
            <span>Answered</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded border border-amber-500" />
            <span>Flagged</span>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
