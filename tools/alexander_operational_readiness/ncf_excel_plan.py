"""Plan de rangos NCF tal como la planilla Pendientes.

Carga las 34 filas. No deja rangos inactivos por vencimiento Excel
(2024-12-31 / 2025-12-31 / N/A): Odoo exige date_to futuro para state=active,
así que esos casos usan 2099-12-31. No reemite NCF ya posteados.
"""

from datetime import date


def ncf_prefix(ncf):
    n = str(ncf or "")
    return n[:3] if len(n) >= 3 else ""


def ncf_seq(ncf):
    n = str(ncf or "")
    if len(n) == 11 and n[3:].isdigit():
        return int(n[3:])
    return None


TODAY = date(2026, 9, 7)
OPERATIVE_DATE_TO = "2099-12-31"
QA_MIN = 99100000

COMPANY_VAT = {
    "INVERSIONES DORALEX,S.RL.": "132220112",
    "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.": "132271068",
    "DOMINION BUSINESS,S.R.L.": "132721502",
    "INVERSIONES EL MAYUMA, S.R.L.": "132710152",
    "REMPART GROUP S.R.L.": "132769155",
    "BLUE ELITE, S.R.L.": "133371261",
}

EXCEL_NCF_ROWS = [
    {
        "company": "INVERSIONES DORALEX,S.RL.",
        "declared_type": "B01",
        "range_from": "B0100000052",
        "range_to": "B0100000087",
        "last_used": "B1500000156",
        "next": "B1500000157",
        "expiration": "2027-12-31",
        "authorization": "6005372487",
    },
    {
        "company": "INVERSIONES DORALEX,S.RL.",
        "declared_type": "B02",
        "range_from": "B0200000001",
        "range_to": "B0200000010",
        "last_used": "",
        "next": "B0200000001",
        "expiration": "N/A",
        "authorization": "1002741918",
    },
    {
        "company": "INVERSIONES DORALEX,S.RL.",
        "declared_type": "B04",
        "range_from": "B0400000502",
        "range_to": "B0400000502",
        "last_used": "B0400000501",
        "next": "B0400000502",
        "expiration": "N/A",
        "authorization": "6005472045",
    },
    {
        "company": "INVERSIONES DORALEX,S.RL.",
        "declared_type": "B11",
        "range_from": "B1100000001",
        "range_to": "B1100000005",
        "last_used": "",
        "next": "B1100000001",
        "expiration": "2024-12-31",
        "authorization": "3003703072",
    },
    {
        "company": "INVERSIONES DORALEX,S.RL.",
        "declared_type": "B13",
        "range_from": "B1300000011",
        "range_to": "B1300000015",
        "last_used": "B1300000015",
        "next": "",
        "expiration": "2027-12-31",
        "authorization": "6005031086",
    },
    {
        "company": "INVERSIONES DORALEX,S.RL.",
        "declared_type": "B15",
        "range_from": "B1500000141",
        "range_to": "B1500000160",
        "last_used": "B1500000150",
        "next": "B1500000151",
        "expiration": "2027-12-31",
        "authorization": "6005109381",
    },
    {
        "company": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "declared_type": "B01",
        "range_from": "B0100000006",
        "range_to": "B0100000010",
        "last_used": "B0100000008",
        "next": "",
        "expiration": "2025-12-31",
        "authorization": "4004196168",
    },
    {
        "company": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "declared_type": "B04",
        "range_from": "B0400000001",
        "range_to": "B0400000010",
        "last_used": "",
        "next": "B0400000001",
        "expiration": "N/A",
        "authorization": "3003875941",
    },
    {
        "company": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "declared_type": "B11",
        "range_from": "B1100000001",
        "range_to": "B1100000005",
        "last_used": "",
        "next": "B1100000001",
        "expiration": "2025-12-31",
        "authorization": "4004017760",
    },
    {
        "company": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "declared_type": "B13",
        "range_from": "B1300000018",
        "range_to": "B1300000027",
        "last_used": "",
        "next": "B1300000018",
        "expiration": "2026-12-31",
        "authorization": "5004579811",
    },
    {
        "company": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "declared_type": "B15",
        "range_from": "B1500000093",
        "range_to": "B1500000103",
        "last_used": "B1500000092",
        "next": "B1500000093",
        "expiration": "2028-01-01",
        "authorization": "6005464536",
    },
    {
        "company": "DOMINION BUSINESS,S.R.L.",
        "declared_type": "B01",
        "range_from": "B0100000091",
        "range_to": "B0100000100",
        "last_used": "B0100000093",
        "next": "",
        "expiration": "2025-12-31",
        "authorization": "4004196172",
    },
    {
        "company": "DOMINION BUSINESS,S.R.L.",
        "declared_type": "B02",
        "range_from": "B0200000001",
        "range_to": "B0200000500",
        "last_used": "",
        "next": "",
        "expiration": "N/A",
        "authorization": "2003411708",
    },
    {
        "company": "DOMINION BUSINESS,S.R.L.",
        "declared_type": "B04",
        "range_from": "B0400000001",
        "range_to": "B0400000050",
        "last_used": "",
        "next": "B0400000001",
        "expiration": "N/A",
        "authorization": "2003411709",
    },
    {
        "company": "DOMINION BUSINESS,S.R.L.",
        "declared_type": "B11",
        "range_from": "B1100000001",
        "range_to": "B1100000010",
        "last_used": "",
        "next": "B1100000001",
        "expiration": "2025-12-31",
        "authorization": "4003974422",
    },
    {
        "company": "DOMINION BUSINESS,S.R.L.",
        "declared_type": "B13",
        "range_from": "B1300000057",
        "range_to": "B1300000096",
        "last_used": "",
        "next": "B1300000057",
        "expiration": "2026-12-31",
        "authorization": "5004440728",
    },
    {
        "company": "DOMINION BUSINESS,S.R.L.",
        "declared_type": "B15",
        "range_from": "B1500000140",
        "range_to": "B1500000163",
        "last_used": "B1500000144",
        "next": "B1500000145",
        "expiration": "2026-12-31",
        "authorization": "5004909756",
    },
    {
        "company": "INVERSIONES EL MAYUMA, S.R.L.",
        "declared_type": "B01",
        "range_from": "B0100000006",
        "range_to": "B0100000010",
        "last_used": "",
        "next": "",
        "expiration": "2026-12-31",
        "authorization": "5004743980",
    },
    {
        "company": "INVERSIONES EL MAYUMA, S.R.L.",
        "declared_type": "B02",
        "range_from": "B0200000001",
        "range_to": "B0200000100",
        "last_used": "",
        "next": "",
        "expiration": "N/A",
        "authorization": "3003508919",
    },
    {
        "company": "INVERSIONES EL MAYUMA, S.R.L.",
        "declared_type": "B04",
        "range_from": "B0400000001",
        "range_to": "B0400000005",
        "last_used": "",
        "next": "B0400000001",
        "expiration": "N/A",
        "authorization": "6005472703",
    },
    {
        "company": "INVERSIONES EL MAYUMA, S.R.L.",
        "declared_type": "B11",
        "range_from": "B1100000001",
        "range_to": "B1100000005",
        "last_used": "",
        "next": "",
        "expiration": "2025-12-31",
        "authorization": "4003974363",
    },
    {
        "company": "INVERSIONES EL MAYUMA, S.R.L.",
        "declared_type": "B13",
        "range_from": "B1300000001",
        "range_to": "B1300000005",
        "last_used": "",
        "next": "",
        "expiration": "2025-12-31",
        "authorization": "4003974364",
    },
    {
        "company": "INVERSIONES EL MAYUMA, S.R.L.",
        "declared_type": "B15",
        "range_from": "B1500000109",
        "range_to": "B1500000118",
        "last_used": "B1500000110",
        "next": "B1500000111",
        "expiration": "2026-12-31",
        "authorization": "5004942280",
    },
    {
        "company": "REMPART GROUP S.R.L.",
        "declared_type": "B01",
        "range_from": "B0100000016",
        "range_to": "B0100000030",
        "last_used": "",
        "next": "",
        "expiration": "2026-12-31",
        "authorization": "5004684660",
    },
    {
        "company": "REMPART GROUP S.R.L.",
        "declared_type": "B04",
        "range_from": "B0400000001",
        "range_to": "B0400000005",
        "last_used": "",
        "next": "B0400000001",
        "expiration": "N/A",
        "authorization": "6005474633",
    },
    {
        "company": "REMPART GROUP S.R.L.",
        "declared_type": "B11",
        "range_from": "B1100000001",
        "range_to": "B1100000005",
        "last_used": "",
        "next": "",
        "expiration": "2025-12-31",
        "authorization": "4004004172",
    },
    {
        "company": "REMPART GROUP S.R.L.",
        "declared_type": "B13",
        "range_from": "B1300000006",
        "range_to": "B1300000012",
        "last_used": "",
        "next": "",
        "expiration": "2025-12-31",
        "authorization": "4004004197",
    },
    {
        "company": "REMPART GROUP S.R.L.",
        "declared_type": "B15",
        "range_from": "B1500000106",
        "range_to": "B1500000113",
        "last_used": "B1500000110",
        "next": "B1500000111",
        "expiration": "2027-01-03",
        "authorization": "5004942351",
    },
    {
        "company": "BLUE ELITE, S.R.L.",
        "declared_type": "B01",
        "range_from": "B0100000001",
        "range_to": "B0100000015",
        "last_used": "",
        "next": "B0100000001",
        "expiration": "2027-12-31",
        "authorization": "6005109961",
    },
    {
        "company": "BLUE ELITE, S.R.L.",
        "declared_type": "B02",
        "range_from": "B0200000001",
        "range_to": "B0200000500",
        "last_used": "",
        "next": "B0200000001",
        "expiration": "N/A",
        "authorization": "6005109965",
    },
    {
        "company": "BLUE ELITE, S.R.L.",
        "declared_type": "B04",
        "range_from": "B0400000001",
        "range_to": "B0400000015",
        "last_used": "",
        "next": "B0400000001",
        "expiration": "N/A",
        "authorization": "6005109966",
    },
    {
        "company": "BLUE ELITE, S.R.L.",
        "declared_type": "B11",
        "range_from": "B1100000001",
        "range_to": "B1100000005",
        "last_used": "",
        "next": "B1100000001",
        "expiration": "2027-12-31",
        "authorization": "6005109962",
    },
    {
        "company": "BLUE ELITE, S.R.L.",
        "declared_type": "B13",
        "range_from": "B1300000001",
        "range_to": "B1300000005",
        "last_used": "",
        "next": "B1300000001",
        "expiration": "2027-12-31",
        "authorization": "6005109963",
    },
    {
        "company": "BLUE ELITE, S.R.L.",
        "declared_type": "B15",
        "range_from": "B1500000001",
        "range_to": "B1500000020",
        "last_used": "B1500000101",
        "next": "B1500000102",
        "expiration": "2027-12-31",
        "authorization": "6005109964",
    },
]


def _same_prefix_seq(declared, ncf):
    if not ncf:
        return None
    if ncf_prefix(ncf) != declared:
        return None
    return ncf_seq(ncf)


def _date_to(expiration):
    notes = []
    exp = (expiration or "").strip()
    if not exp or exp.upper() in {"N/A", "NA", "NO APLICA"}:
        notes.append("EXCEL_EXPIRATION=N/A → operativa 2099-12-31")
        return OPERATIVE_DATE_TO, notes
    try:
        parsed = date.fromisoformat(exp)
    except ValueError:
        notes.append(f"EXCEL_EXPIRATION_UNPARSED={exp} → operativa 2099-12-31")
        return OPERATIVE_DATE_TO, notes
    if parsed < TODAY:
        notes.append(
            f"EXCEL_EXPIRATION={exp} ya pasó; Odoo bloquea vencidos. "
            "Vigencia operativa 2099-12-31 (instrucción: no dejar inactivo)"
        )
        return OPERATIVE_DATE_TO, notes
    return exp, notes


def plan_range(row, max_historical_seq=None):
    declared = row["declared_type"]
    start = ncf_seq(row["range_from"])
    excel_end = ncf_seq(row["range_to"])
    excel_next = _same_prefix_seq(declared, row.get("next"))
    excel_last = _same_prefix_seq(declared, row.get("last_used"))
    notes = []
    if row.get("next") and excel_next is None:
        notes.append(f"EXCEL_NEXT_PREFIX_IGNORED={row['next']}")
    if row.get("last_used") and excel_last is None:
        notes.append(f"EXCEL_LAST_PREFIX_IGNORED={row['last_used']}")
    nxt = excel_next
    if nxt is None and excel_last is not None:
        nxt = excel_last + 1
        notes.append(f"NEXT_FROM_LAST+1={nxt}")
    if nxt is None:
        nxt = start
        notes.append(f"NEXT_FROM_RANGE_START={start}")
    if max_historical_seq is not None and max_historical_seq < QA_MIN:
        bumped = max_historical_seq + 1
        if bumped > nxt:
            notes.append(
                f"NEXT_BUMPED_FOR_EXISTING_NCF hist={max_historical_seq} → {bumped}"
            )
            nxt = bumped
    end = excel_end
    if nxt > end:
        end = nxt
        notes.append(f"END_EXTENDED_TO_NEXT excel_end={excel_end} end={end}")
    if nxt < start:
        nxt = start
        notes.append("NEXT_RAISED_TO_START")
    date_to, date_notes = _date_to(row.get("expiration"))
    notes.extend(date_notes)
    return {
        "company": row["company"],
        "vat": COMPANY_VAT[row["company"]],
        "prefix": declared,
        "start": start,
        "end": end,
        "excel_end": excel_end,
        "next": nxt,
        "auth": row["authorization"],
        "excel_expiration": row.get("expiration") or "",
        "date_from": "2020-01-01",
        "date_to": date_to,
        "notes": notes,
    }
