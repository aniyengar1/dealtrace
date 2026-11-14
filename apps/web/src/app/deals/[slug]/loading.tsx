import { Container } from "@/components/ui/Container";
import { Skeleton } from "@/components/ui/Skeleton";

export default function DealLoading() {
  return (
    <Container wide className="py-10">
      <div className="flex items-start justify-between gap-4">
        <Skeleton className="h-10 w-96" />
        <div className="flex gap-2">
          <Skeleton className="h-9 w-20" />
          <Skeleton className="h-9 w-32" />
        </div>
      </div>
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
      <Skeleton className="mt-6 h-40 w-full" />
      <Skeleton className="mt-10 h-72 w-full" />
    </Container>
  );
}
