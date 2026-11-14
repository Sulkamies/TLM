"""Fixed explanation templates in English, German and Finnish (A0 decision: no LLM in A4).

``render(msg, lang)`` turns a language-independent ``Msg`` into one sentence. The
language is chosen from the primary subtag of ``ParsedQuestion.language``
(``pick_language``); any language other than en/de/fi falls back to English.

Numbers in the text are formatted for reading only. ``Answer.value`` is never rounded.
"""

from __future__ import annotations

from collections.abc import Mapping

from blueprint_qa.contracts import EntityRef
from blueprint_qa.reasoning.outcome import Msg

SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "de", "fi")
FALLBACK_LANGUAGE = "en"


def pick_language(tag: str) -> str:
    """Primary subtag of a BCP-47 tag if supported (``de-AT`` → ``de``), else English."""
    primary = tag.replace("_", "-").split("-", 1)[0].strip().lower()
    return primary if primary in SUPPORTED_LANGUAGES else FALLBACK_LANGUAGE


# ------------------------------------------------------------------- names per language
# Keyed by language, then by the contract value.

_CATEGORY: Mapping[str, Mapping[str, str]] = {
    "en": {
        "ROOM": "room",
        "DOOR": "door",
        "WINDOW": "window",
        "WALL": "wall",
        "STAIR": "stair",
        "STOREY": "storey",
        "WHOLE_PLAN": "whole plan",
        "FIXTURE": "sanitary fixture",
    },
    "de": {
        "ROOM": "Raum",
        "DOOR": "Tür",
        "WINDOW": "Fenster",
        "WALL": "Wand",
        "STAIR": "Treppe",
        "STOREY": "Geschoss",
        "WHOLE_PLAN": "gesamter Grundriss",
        "FIXTURE": "Sanitärobjekt",
    },
    "fi": {
        "ROOM": "huone",
        "DOOR": "ovi",
        "WINDOW": "ikkuna",
        "WALL": "seinä",
        "STAIR": "portaat",
        "STOREY": "kerros",
        "WHOLE_PLAN": "koko pohjapiirros",
        "FIXTURE": "saniteettikaluste",
    },
}

_ROOM_TYPE: Mapping[str, Mapping[str, str]] = {
    "en": {
        "BEDROOM": "bedroom",
        "BATHROOM": "bathroom",
        "TOILET": "WC room",
        "KITCHEN": "kitchen",
        "LIVING_ROOM": "living room",
        "DINING_ROOM": "dining room",
        "HALLWAY": "hallway",
        "GARAGE": "garage",
        "STORAGE": "storage room",
        "CLOSET": "closet",
        "LAUNDRY": "laundry room",
        "SAUNA": "sauna",
        "BALCONY": "balcony",
        "OFFICE": "office",
        "TECHNICAL": "technical room",
        "OTHER": "other room",
        "UNKNOWN": "room of unknown type",
    },
    "de": {
        "BEDROOM": "Schlafzimmer",
        "BATHROOM": "Badezimmer",
        "TOILET": "WC",
        "KITCHEN": "Küche",
        "LIVING_ROOM": "Wohnzimmer",
        "DINING_ROOM": "Esszimmer",
        "HALLWAY": "Flur",
        "GARAGE": "Garage",
        "STORAGE": "Abstellraum",
        "CLOSET": "Schrankraum",
        "LAUNDRY": "Waschküche",
        "SAUNA": "Sauna",
        "BALCONY": "Balkon",
        "OFFICE": "Arbeitszimmer",
        "TECHNICAL": "Technikraum",
        "OTHER": "sonstiger Raum",
        "UNKNOWN": "Raum unbekannter Art",
    },
    "fi": {
        "BEDROOM": "makuuhuone",
        "BATHROOM": "kylpyhuone",
        "TOILET": "WC",
        "KITCHEN": "keittiö",
        "LIVING_ROOM": "olohuone",
        "DINING_ROOM": "ruokailuhuone",
        "HALLWAY": "eteinen",
        "GARAGE": "autotalli",
        "STORAGE": "varasto",
        "CLOSET": "vaatehuone",
        "LAUNDRY": "kodinhoitohuone",
        "SAUNA": "sauna",
        "BALCONY": "parveke",
        "OFFICE": "työhuone",
        "TECHNICAL": "tekninen tila",
        "OTHER": "muu huone",
        "UNKNOWN": "tuntematon huone",
    },
}

_FIXTURE_TYPE: Mapping[str, Mapping[str, str]] = {
    "en": {
        "TOILET": "toilet bowl",
        "SINK": "sink",
        "SHOWER": "shower",
        "BATHTUB": "bathtub",
        "SAUNA_BENCH": "sauna bench",
        "OTHER": "other fixture",
    },
    "de": {
        "TOILET": "WC-Becken",
        "SINK": "Waschbecken",
        "SHOWER": "Dusche",
        "BATHTUB": "Badewanne",
        "SAUNA_BENCH": "Saunabank",
        "OTHER": "sonstiges Sanitärobjekt",
    },
    "fi": {
        "TOILET": "WC-istuin",
        "SINK": "pesuallas",
        "SHOWER": "suihku",
        "BATHTUB": "kylpyamme",
        "SAUNA_BENCH": "lauteet",
        "OTHER": "muu kaluste",
    },
}

_STOREY_LEVEL: Mapping[str, Mapping[str, str]] = {
    "en": {
        "BASEMENT": "basement",
        "GROUND": "ground floor",
        "UPPER": "upper floor",
        "UPPER_1": "1st floor above ground",
        "UPPER_2": "2nd floor above ground",
        "UPPER_3": "3rd floor above ground",
        "ATTIC": "attic",
    },
    "de": {
        "BASEMENT": "Keller",
        "GROUND": "Erdgeschoss",
        "UPPER": "Obergeschoss",
        "UPPER_1": "1. Obergeschoss",
        "UPPER_2": "2. Obergeschoss",
        "UPPER_3": "3. Obergeschoss",
        "ATTIC": "Dachgeschoss",
    },
    "fi": {
        "BASEMENT": "kellari",
        "GROUND": "maantasokerros",
        "UPPER": "yläkerta",
        "UPPER_1": "2. kerros",
        "UPPER_2": "3. kerros",
        "UPPER_3": "4. kerros",
        "ATTIC": "ullakko",
    },
}

_MEASURE: Mapping[str, Mapping[str, str]] = {
    "en": {
        "COUNT": "number",
        "AREA": "area",
        "LENGTH": "length",
        "PERIMETER": "perimeter",
        "HEIGHT": "height",
        "VOLUME": "volume",
        "DISTANCE": "distance",
        "RATIO": "ratio",
    },
    "de": {
        "COUNT": "Anzahl",
        "AREA": "Fläche",
        "LENGTH": "Länge",
        "PERIMETER": "Umfang",
        "HEIGHT": "Höhe",
        "VOLUME": "Volumen",
        "DISTANCE": "Abstand",
        "RATIO": "Verhältnis",
    },
    "fi": {
        "COUNT": "lukumäärä",
        "AREA": "pinta-ala",
        "LENGTH": "pituus",
        "PERIMETER": "piiri",
        "HEIGHT": "korkeus",
        "VOLUME": "tilavuus",
        "DISTANCE": "etäisyys",
        "RATIO": "suhde",
    },
}

_AGGREGATION: Mapping[str, Mapping[str, str]] = {
    "en": {"SUM": "sum", "MAX": "maximum", "MIN": "minimum", "MEAN": "mean"},
    "de": {"SUM": "Summe", "MAX": "Maximum", "MIN": "Minimum", "MEAN": "Mittelwert"},
    "fi": {"SUM": "summa", "MAX": "suurin", "MIN": "pienin", "MEAN": "keskiarvo"},
}

_OPERATOR: Mapping[str, Mapping[str, str]] = {
    "en": {
        "GT": "greater than",
        "GE": "at least",
        "LT": "less than",
        "LE": "at most",
        "EQ": "equal to",
    },
    "de": {
        "GT": "größer als",
        "GE": "mindestens",
        "LT": "kleiner als",
        "LE": "höchstens",
        "EQ": "gleich",
    },
    "fi": {
        "GT": "suurempi kuin",
        "GE": "vähintään",
        "LT": "pienempi kuin",
        "LE": "enintään",
        "EQ": "yhtä suuri kuin",
    },
}

_LABEL = {"en": 'label "{}"', "de": "Beschriftung „{}“", "fi": 'merkintä "{}"'}
_ORDINAL = {"en": "no. {}", "de": "Nr. {}", "fi": "nro {}"}

_UNIT_DISPLAY: Mapping[str, str] = {
    "m": "m",
    "m2": "m²",
    "m3": "m³",
    "ft": "ft",
    "ft2": "ft²",
    "ft3": "ft³",
}

# ------------------------------------------------------------------------- templates
# Fields: what, rhs_what, n, ordinal, storey, measure, Measure (capitalised), agg
# (", <aggregation>" or ""), value, unit, lhs, rhs, op. Every key exists in every language
# (enforced by a unit test).

TEMPLATES: Mapping[str, Mapping[str, str]] = {
    "en": {
        "unsupported": "This question cannot be answered with a number.",
        "count": "Number of matching elements ({what}): {value}.",
        "count_zero": "No matching elements ({what}) were found. The analysis can detect this "
        "kind of element, so the count is 0.",
        "exists_yes": "Yes: {n} matching element(s) found ({what}).",
        "exists_no": "No: no matching element was found ({what}). The analysis can detect this "
        "kind of element.",
        "measure": "{Measure} ({what}{agg}): {value} {unit}.",
        "distance": "Straight-line distance between the centres ({what}): {value} {unit}.",
        "ratio": "Area ratio ({what} / {rhs_what}): {value}.",
        "comparison_yes": "Yes: {Measure} ({what}) = {lhs}, which is {op} {rhs}.",
        "comparison_no": "No: {Measure} ({what}) = {lhs}, which is not {op} {rhs}.",
        "note_sum_over_rooms": "The value is the sum over {n} room(s).",
        "note_all_storeys": "No storey was named, so all {n} storeys are included.",
        "no_category_data": "The plan analysis contains no data about this kind of element "
        "({what}).",
        "not_detectable": "No matching elements ({what}) were found, but the analysis cannot "
        "reliably detect this kind of element, so 0 cannot be confirmed.",
        "no_metric": "The plan has no known scale, so real-world measurements cannot be computed.",
        "missing_area": "The area of at least one matching room is unknown ({what}).",
        "missing_height": "The ceiling height of at least one matching room is unknown ({what}).",
        "degenerate_geometry": "The geometry of a matching element is insufficient for this "
        "measurement ({what}).",
        "storey_not_found": "The requested storey ({storey}) was not found in the plan.",
        "storey_unknown": "Some matching elements ({what}) could not be assigned to a storey.",
        "no_match": "No matching element was found ({what}).",
        "no_rooms": "No rooms were found to compute this value ({what}).",
        "ordinal_too_few": "Only {n} matching element(s) were found ({what}), so no. {ordinal} "
        "cannot be identified.",
        "measure_not_applicable": "The {measure} cannot be computed for this kind of element "
        "({what}).",
        "bad_question": "The question is incomplete for this kind of calculation.",
        "zero_denominator": "The reference area is zero, so the ratio cannot be computed "
        "({rhs_what}).",
        "different_storeys": "The elements are on different storeys, so a straight-line "
        "distance cannot be given ({what}).",
        "several_matches": "Several elements match ({what}: {n}). Please specify which one you "
        "mean.",
        "upper_ambiguous": "The plan has several upper storeys. Please specify which one you mean.",
    },
    "de": {
        "unsupported": "Diese Frage lässt sich nicht mit einer Zahl beantworten.",
        "count": "Anzahl passender Elemente ({what}): {value}.",
        "count_zero": "Es wurden keine passenden Elemente ({what}) gefunden. Die Analyse kann "
        "diese Art von Element erkennen, daher ist die Anzahl 0.",
        "exists_yes": "Ja: {n} passende(s) Element(e) gefunden ({what}).",
        "exists_no": "Nein: Es wurde kein passendes Element gefunden ({what}). Die Analyse kann "
        "diese Art von Element erkennen.",
        "measure": "{Measure} ({what}{agg}): {value} {unit}.",
        "distance": "Luftlinie zwischen den Mittelpunkten ({what}): {value} {unit}.",
        "ratio": "Flächenverhältnis ({what} / {rhs_what}): {value}.",
        "comparison_yes": "Ja: {Measure} ({what}) = {lhs}, also {op} {rhs}.",
        "comparison_no": "Nein: {Measure} ({what}) = {lhs}, also nicht {op} {rhs}.",
        "note_sum_over_rooms": "Der Wert ist die Summe über {n} Raum/Räume.",
        "note_all_storeys": "Es wurde kein Geschoss genannt, daher sind alle {n} Geschosse "
        "berücksichtigt.",
        "no_category_data": "Die Plananalyse enthält keine Daten zu dieser Art von Element "
        "({what}).",
        "not_detectable": "Es wurden keine passenden Elemente ({what}) gefunden, aber die Analyse "
        "kann diese Art von Element nicht zuverlässig erkennen, daher kann 0 nicht bestätigt "
        "werden.",
        "no_metric": "Der Plan hat keinen bekannten Maßstab, daher können keine realen Maße "
        "berechnet werden.",
        "missing_area": "Die Fläche mindestens eines passenden Raums ist unbekannt ({what}).",
        "missing_height": "Die Raumhöhe mindestens eines passenden Raums ist unbekannt ({what}).",
        "degenerate_geometry": "Die Geometrie eines passenden Elements reicht für diese Messung "
        "nicht aus ({what}).",
        "storey_not_found": "Das angefragte Geschoss ({storey}) wurde im Plan nicht gefunden.",
        "storey_unknown": "Einige passende Elemente ({what}) konnten keinem Geschoss zugeordnet "
        "werden.",
        "no_match": "Es wurde kein passendes Element gefunden ({what}).",
        "no_rooms": "Es wurden keine Räume gefunden, um diesen Wert zu berechnen ({what}).",
        "ordinal_too_few": "Es wurden nur {n} passende Elemente gefunden ({what}), daher lässt "
        "sich Nr. {ordinal} nicht bestimmen.",
        "measure_not_applicable": "{Measure} lässt sich für diese Art von Element nicht "
        "berechnen ({what}).",
        "bad_question": "Die Frage ist für diese Art von Berechnung unvollständig.",
        "zero_denominator": "Die Bezugsfläche ist null, daher lässt sich das Verhältnis nicht "
        "berechnen ({rhs_what}).",
        "different_storeys": "Die Elemente liegen in verschiedenen Geschossen, daher lässt sich "
        "keine Luftlinie angeben ({what}).",
        "several_matches": "Mehrere Elemente passen ({what}: {n}). Bitte geben Sie an, welches "
        "gemeint ist.",
        "upper_ambiguous": "Der Plan hat mehrere Obergeschosse. Bitte geben Sie an, welches "
        "gemeint ist.",
    },
    "fi": {
        "unsupported": "Tähän kysymykseen ei voi vastata luvulla.",
        "count": "Täsmäävien kohteiden määrä ({what}): {value}.",
        "count_zero": "Täsmääviä kohteita ({what}) ei löytynyt. Analyysi pystyy tunnistamaan "
        "tämän kohdetyypin, joten määrä on 0.",
        "exists_yes": "Kyllä: täsmääviä kohteita löytyi {n} ({what}).",
        "exists_no": "Ei: täsmäävää kohdetta ei löytynyt ({what}). Analyysi pystyy "
        "tunnistamaan tämän kohdetyypin.",
        "measure": "{Measure} ({what}{agg}): {value} {unit}.",
        "distance": "Linnuntie-etäisyys keskipisteiden välillä ({what}): {value} {unit}.",
        "ratio": "Pinta-alojen suhde ({what} / {rhs_what}): {value}.",
        "comparison_yes": "Kyllä: {Measure} ({what}) = {lhs}, eli {op} {rhs}.",
        "comparison_no": "Ei: {Measure} ({what}) = {lhs}, eli ei {op} {rhs}.",
        "note_sum_over_rooms": "Arvo on summa {n} huoneen yli.",
        "note_all_storeys": "Kerrosta ei mainittu, joten kaikki {n} kerrosta on otettu mukaan.",
        "no_category_data": "Pohjapiirroksen analyysissä ei ole tietoja tästä kohdetyypistä "
        "({what}).",
        "not_detectable": "Täsmääviä kohteita ({what}) ei löytynyt, mutta analyysi ei pysty "
        "luotettavasti tunnistamaan tätä kohdetyyppiä, joten nollaa ei voi vahvistaa.",
        "no_metric": "Pohjapiirroksen mittakaava ei ole tiedossa, joten todellisia mittoja ei "
        "voi laskea.",
        "missing_area": "Ainakin yhden täsmäävän huoneen pinta-ala on tuntematon ({what}).",
        "missing_height": "Ainakin yhden täsmäävän huoneen huonekorkeus on tuntematon ({what}).",
        "degenerate_geometry": "Täsmäävän kohteen geometria ei riitä tähän mittaukseen ({what}).",
        "storey_not_found": "Pyydettyä kerrosta ({storey}) ei löytynyt pohjapiirroksesta.",
        "storey_unknown": "Joitakin täsmääviä kohteita ({what}) ei voitu liittää mihinkään "
        "kerrokseen.",
        "no_match": "Täsmäävää kohdetta ei löytynyt ({what}).",
        "no_rooms": "Arvon laskemiseen ei löytynyt huoneita ({what}).",
        "ordinal_too_few": "Täsmääviä kohteita löytyi vain {n} ({what}), joten kohdetta nro "
        "{ordinal} ei voi tunnistaa.",
        "measure_not_applicable": "Suuretta {measure} ei voi laskea tälle kohdetyypille ({what}).",
        "bad_question": "Kysymys on puutteellinen tämäntyyppistä laskentaa varten.",
        "zero_denominator": "Vertailupinta-ala on nolla, joten suhdetta ei voi laskea "
        "({rhs_what}).",
        "different_storeys": "Kohteet ovat eri kerroksissa, joten linnuntie-etäisyyttä ei voi "
        "antaa ({what}).",
        "several_matches": "Useampi kohde täsmää ({what}: {n}). Tarkenna, mitä niistä tarkoitat.",
        "upper_ambiguous": "Pohjapiirroksessa on useita yläkerroksia. Tarkenna, mitä niistä "
        "tarkoitat.",
    },
}


# --------------------------------------------------------------------------- rendering


def format_number(value: float, lang: str) -> str:
    """Readable number: integers without decimals, else at most 3 decimals (display only)."""
    if value == int(value) and abs(value) < 1e15:
        text = str(int(value))
    else:
        text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if lang in ("de", "fi") else text


def _with_unit(value: float | None, unit: str | None, lang: str) -> str:
    if value is None:
        return ""
    shown = _UNIT_DISPLAY.get(unit or "", "")
    number = format_number(value, lang)
    return f"{number} {shown}" if shown else number


def describe_target(ref: EntityRef, lang: str) -> str:
    """Short localised description of one target, e.g. ``bedroom, ground floor, no. 2``."""
    if ref.category == "ROOM" and ref.room_type is not None:
        base = _ROOM_TYPE[lang][ref.room_type.value]
    elif ref.category == "FIXTURE" and ref.fixture_type is not None:
        base = _FIXTURE_TYPE[lang][ref.fixture_type.value]
    else:
        base = _CATEGORY[lang][ref.category]
    parts = [base]
    if ref.storey is not None:
        parts.append(_STOREY_LEVEL[lang].get(ref.storey, ref.storey))
    if ref.label is not None:
        parts.append(_LABEL[lang].format(ref.label))
    if ref.ordinal is not None:
        parts.append(_ORDINAL[lang].format(ref.ordinal))
    return ", ".join(parts)


def _describe(refs: tuple[EntityRef, ...], lang: str) -> str:
    return " + ".join(describe_target(ref, lang) for ref in refs)


def render(msg: Msg, lang: str) -> str:
    """Render one message in ``lang`` (must be a supported language)."""
    measure = _MEASURE[lang].get(msg.measure or "", msg.measure or "")
    agg = _AGGREGATION[lang].get(msg.aggregation or "", "")
    fields = {
        "what": _describe(msg.what, lang),
        "rhs_what": _describe(msg.rhs_what, lang),
        "n": "" if msg.n is None else str(msg.n),
        "ordinal": "" if msg.ordinal is None else str(msg.ordinal),
        "storey": _STOREY_LEVEL[lang].get(msg.storey or "", msg.storey or ""),
        "measure": measure,
        "Measure": measure[:1].upper() + measure[1:],
        "agg": f", {agg}" if agg else "",
        "value": "" if msg.value is None else format_number(msg.value, lang),
        "unit": _UNIT_DISPLAY.get(msg.unit or "", ""),
        "lhs": _with_unit(msg.lhs, msg.unit, lang),
        "rhs": _with_unit(msg.rhs, msg.unit, lang),
        "op": _OPERATOR[lang].get(msg.operator or "", msg.operator or ""),
    }
    return TEMPLATES[lang][msg.key].format(**fields).replace(" .", ".")


def render_all(msgs: list[Msg], lang: str) -> str:
    return " ".join(render(msg, lang) for msg in msgs)
