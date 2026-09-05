"""Reconstruye próximo NCF desde MAX histórico real. No inventa rangos DGII."""

from __future__ import annotations

from .normalize import ncf_prefix, ncf_seq, norm_ncf

QA_SEQ_MIN = 99100000
QA_SEQ_MAX = 99119999


def is_qa_ncf(ncf: str) -> bool:
    seq = ncf_seq(ncf)
    return seq is not None and QA_SEQ_MIN <= seq <= QA_SEQ_MAX


def format_ncf(prefix: str, seq: int) -> str:
    return f"{prefix}{int(seq):08d}"


def max_historical_for_type(ncfs: list[str], declared_type: str) -> str | None:
    best_seq = None
    best = None
    for raw in ncfs:
        ncf = norm_ncf(raw)
        if not ncf or is_qa_ncf(ncf):
            continue
        if ncf_prefix(ncf) != declared_type:
            continue
        seq = ncf_seq(ncf)
        if seq is None:
            continue
        if best_seq is None or seq > best_seq:
            best_seq = seq
            best = ncf
    return best


def reconstruct_row(seq: dict, historical_ncfs: list[str]) -> dict:
    """Clasifica una fila de secuencia. No usa último/próximo de planilla a ciegas."""
    declared = seq["declared_type"]
    rng_from = norm_ncf(seq.get("range_from") or "")
    rng_to = norm_ncf(seq.get("range_to") or "")
    from_seq = ncf_seq(rng_from)
    to_seq = ncf_seq(rng_to)
    max_real = max_historical_for_type(historical_ncfs, declared)
    max_seq = ncf_seq(max_real) if max_real else None
    notes = list(seq.get("conflicts") or [])
    calculated_next = None
    status = "NO_HISTORICAL_NCF"
    activate = False
    range_confirmation = False

    prefix_ok = True
    if rng_from and ncf_prefix(rng_from) != declared:
        prefix_ok = False
        notes.append("RANGE_FROM_PREFIX_NE_TYPE")
    if rng_to and ncf_prefix(rng_to) != declared:
        prefix_ok = False
        notes.append("RANGE_TO_PREFIX_NE_TYPE")
    if seq.get("last_used") and ncf_prefix(seq["last_used"]) != declared:
        notes.append("PLANILLA_LAST_PREFIX_IGNORED")
    if seq.get("next") and ncf_prefix(seq["next"]) != declared:
        notes.append("PLANILLA_NEXT_PREFIX_IGNORED")

    if max_seq is not None:
        nxt = max_seq + 1
        calculated_next = format_ncf(declared, nxt)
        if not prefix_ok:
            status = "RANGE_PREFIX_CONFLICT"
            activate = False
        elif to_seq is not None and max_seq > to_seq:
            status = "MAX_OUTSIDE_DECLARED_RANGE"
            activate = False
            range_confirmation = True
            notes.append(
                f"MAX {max_real} > RANGE_TO {rng_to}; no activar NEXT {calculated_next}"
            )
        elif from_seq is not None and nxt < from_seq:
            status = "CALCULATED_NEXT_BELOW_RANGE"
            activate = False
        elif to_seq is not None and nxt > to_seq:
            status = "RANGE_EXHAUSTED_OR_INCORRECT"
            activate = False
        else:
            status = "SAFE_TO_ACTIVATE"
            activate = True
            if from_seq is not None and max_seq < from_seq:
                notes.append(
                    f"HISTORICAL_NCF_BELOW_AUTHORIZED_RANGE max={max_real} from={rng_from}"
                )
    else:
        notes.append("NO_USE_PLANILLA_NEXT_WITHOUT_HISTORICAL_EVIDENCE")
        if not prefix_ok:
            status = "RANGE_PREFIX_CONFLICT"

    return {
        "company": seq["company"],
        "ncf_type": declared,
        "declared_range_start": rng_from,
        "declared_range_end": rng_to,
        "declared_last_used": seq.get("last_used") or "",
        "declared_next": seq.get("next") or "",
        "authorization": seq.get("authorization") or "",
        "expiration": seq.get("expiration"),
        "max_historical_ncf_found": max_real,
        "calculated_next": calculated_next,
        "status": status,
        "activate": activate,
        "needs_fiscal_range_confirmation": range_confirmation,
        "notes": notes,
    }
