import { Container } from "@/components/ui/Container";
import { Skeleton, TableSkeleton } from "@/components/ui/Skeleton";

export default function DealsLoading() {
  return (
    <Container wide className="py-10">
      <Skeleton className="h-9 w-56" />
      <Skeleton className="mt-2 h-4 w-80" />
      <div className="mt-6 flex gap-2.5">
        <Skeleton className="h-9 flex-1" />
        <Skeleton className="h-9 w-36" />
        <Skeleton className="h-9 w-36" />
        <Skeleton className="h-9 w-36" />
      </div>
      <div className="mt-6">
        <TableSkeleton rows={10} cols={8} />
      </div>
    </Container>
  );
}
