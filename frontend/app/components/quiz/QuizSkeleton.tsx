import { Skeleton } from '../ui/skeleton';
import { Card } from '../ui/card';

export function QuizSkeleton() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Question header */}
      <div className="flex items-center gap-2">
        <Skeleton className="h-6 w-12" />
        <Skeleton className="h-6 w-24" />
      </div>

      {/* Question text */}
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-3/4" />

      {/* Options */}
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="p-4">
            <div className="flex items-center gap-3">
              <Skeleton className="h-8 w-8 rounded" />
              <Skeleton className="h-4 flex-1" />
            </div>
          </Card>
        ))}
      </div>

      {/* Explanation placeholder */}
      <Skeleton className="h-24 w-full" />
    </div>
  );
}
