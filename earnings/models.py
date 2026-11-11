"""Immutable records. Decimal strings are the JSON interchange format."""
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from uuid import UUID, uuid5

NAMESPACE = UUID('96679524-b146-4ec0-a53e-19a1de969bd6')


def money(value):
    if isinstance(value, (float, bool)):
        raise ValueError('Financial values must be Decimal, integer, or decimal string')
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError('Non-finite financial value')
    return result


def plain(value):
    if is_dataclass(value):
        return plain(asdict(value))
    if isinstance(value, (Decimal, date, UUID)):
        return str(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, float):
        raise ValueError('Floats are not valid record values')
    return value


def dumps(value):
    return json.dumps(plain(value), sort_keys=True, indent=2)


def record_id(kind, value):
    return str(uuid5(NAMESPACE, kind + ':' + dumps(value)))


def digest(value):
    return hashlib.sha256(dumps(value).encode()).hexdigest()


@dataclass(frozen=True)
class DateInterval:
    start: date
    end: date
    precision: str = 'day'

    def __post_init__(self):
        if self.start > self.end or self.precision not in ('day', 'month', 'range'):
            raise ValueError('Invalid date interval')
        if self.precision == 'day' and self.start != self.end:
            raise ValueError('Day precision requires one day')

    def available(self, cutoff):
        return self.end <= cutoff

    @classmethod
    def read(cls, value):
        if isinstance(value, str):
            day = date.fromisoformat(value)
            return cls(day, day)
        return cls(date.fromisoformat(value['start']), date.fromisoformat(value['end']), value['precision'])


@dataclass(frozen=True)
class Actual:
    company: str
    concept: str
    start: date
    end: date
    value: Decimal
    unit: str
    basis: str
    accession: str
    filed: date
    form: str
    fiscal_year: int | None
    fiscal_period: str | None
    source_url: str
    parents: tuple[str, ...] = ()
    derivation: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'value', money(self.value))
        if self.start > self.end:
            raise ValueError('Reversed actual period')

    @property
    def id(self):
        return record_id('actual-v1', self)


@dataclass(frozen=True)
class Guidance:
    company: str
    issued: DateInterval
    filed: date
    start: date
    end: date
    low: Decimal | None
    high: Decimal | None
    unit: str
    basis: str
    status: str
    accession: str
    exhibit: str
    source_url: str
    quote: str
    metric: str = 'consolidated_revenue'
    original_verified: bool = False
    notes: str = ''

    def __post_init__(self):
        if self.status not in ('initial', 'reaffirmed', 'raised', 'lowered', 'withdrawn', 'reinstated'):
            raise ValueError('Invalid guidance status')
        if self.start > self.end or not self.quote.strip():
            raise ValueError('Guidance requires a period and evidence')
        if self.status == 'withdrawn':
            if self.low is not None or self.high is not None:
                raise ValueError('Withdrawal must have null bounds')
        else:
            if self.low is None or self.high is None:
                raise ValueError('Active guidance requires both bounds')
            object.__setattr__(self, 'low', money(self.low))
            object.__setattr__(self, 'high', money(self.high))
            if self.low > self.high:
                raise ValueError('Reversed guidance range')
        if self.original_verified and self.status != 'initial':
            raise ValueError('Only an initial record can establish original guidance')

    @property
    def available_on(self):
        return max(self.issued.end, self.filed)

    @property
    def id(self):
        return record_id('guidance-v1', self)


@dataclass(frozen=True)
class Policy:
    version: str = 'manual-freshness-v1'
    actual_days: int = 135
    guidance_days: int = 150
    assumption: str = 'Manual research policy; not an accounting standard'

    def __post_init__(self):
        if self.actual_days < 0 or self.guidance_days < 0 or not self.version:
            raise ValueError('Invalid freshness policy')


@dataclass(frozen=True)
class Calculation:
    company: str
    as_of: date
    policy: Policy
    inputs: dict
    codes: tuple[str, ...] = ()
    details: tuple[str, ...] = ()
    remaining_low: Decimal | None = None
    remaining_high: Decimal | None = None
    growth_low: Decimal | None = None
    growth_high: Decimal | None = None
    formula_version: str = 'revenue-hurdle-v1-decimal50'
    # Decimal division uses 50-digit precision; no display quantization here.

    @property
    def id(self):
        return record_id('calculation-v1', self)

    @property
    def state(self):
        return 'review' if self.codes == ('NEGATIVE_RESIDUAL',) else 'blocked' if self.codes else 'ok'
