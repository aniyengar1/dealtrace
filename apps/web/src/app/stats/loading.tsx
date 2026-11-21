import { Container } from "@/components/ui/Container";
import { Skeleton, TableSkeleton } from "@/components/ui/Skeleton";

export default function StatsLoading() {
  return (
    <Container wide className="py-10">
      <Skeleton className="h-9 w-64" />
      <Skeleton className="mt-2 h-4 w-96" />
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-28 w-full" />
        ))}
      </div>
      <div className="mt-8">
        <TableSkeleton rows={10} cols={11} />
      </div>
    </Container>
  );
}
