import { Container } from "@/components/ui/Container";
import { Skeleton } from "@/components/ui/Skeleton";

export default function HomeLoading() {
  return (
    <div>
      <Container wide className="grid grid-cols-1 gap-10 py-16 sm:py-24 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <div>
          <Skeleton className="h-16 w-full max-w-xl" />
          <Skeleton className="mt-4 h-16 w-full max-w-lg" />
          <Skeleton className="mt-6 h-10 w-full max-w-sm" />
        </div>
        <Skeleton className="h-64 w-full" />
      </Container>
      <Container wide className="py-12">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </Container>
    </div>
  );
}
