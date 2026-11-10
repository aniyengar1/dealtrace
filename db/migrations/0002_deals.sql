CREATE TABLE deals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    deal_name TEXT NOT NULL,
    target TEXT NOT NULL,
    acquirer TEXT NOT NULL,
    search_term TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
