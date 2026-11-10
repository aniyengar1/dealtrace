-- date_precision mirrors schemas.DatePrecision exactly.
CREATE TYPE date_precision AS ENUM ('day', 'month', 'range', 'unknown');

-- Human-review workflow state for extracted facts. Not part of the
-- extraction pipeline itself -- every row starts 'unreviewed' and a
-- reviewer (via whatever UI eventually sits on top of this) flips it.
CREATE TYPE review_status AS ENUM ('unreviewed', 'confirmed', 'rejected');
