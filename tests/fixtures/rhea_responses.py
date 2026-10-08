"""Trimmed real Rhea responses (search TSV/JSON and SPARQL, fetched 2026-10-08) for unit tests."""

import json

RH = "http://rdf.rhea-db.org/"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"


def tsv(header: list[str], *rows: list[str]) -> str:
    return "\n".join("\t".join(r) for r in (header, *rows)) + "\n"


# rhea?query=lactate&columns=rhea-id,equation,ec,chebi-id&format=tsv
SEARCH_LACTATE = tsv(
    ["Reaction identifier", "Equation", "EC number", "ChEBI identifier"],
    [
        "RHEA:19909",
        "(S)-lactate + 2 Fe(III)-[cytochrome c] = 2 Fe(II)-[cytochrome c] + pyruvate + 2 H(+)",
        "EC:1.1.2.3",
        "CHEBI:16651;CHEBI:29034;CHEBI:29033;CHEBI:15361;CHEBI:15378",
    ],
    [
        "RHEA:23444",
        "(S)-lactate + NAD(+) = pyruvate + NADH + H(+)",
        "EC:1.1.1.27",
        "CHEBI:16651;CHEBI:57540;CHEBI:15361;CHEBI:57945;CHEBI:15378",
    ],
    # the wildcard search sometimes lists a reaction twice
    [
        "RHEA:23444",
        "(S)-lactate + NAD(+) = pyruvate + NADH + H(+)",
        "EC:1.1.1.27",
        "CHEBI:16651;CHEBI:57540;CHEBI:15361;CHEBI:57945;CHEBI:15378",
    ],
    ["RHEA:99999", "", "", ""],  # no equation: skipped
    ["not-an-id", "x = y", "", ""],  # bad id: skipped
)

EMPTY_TSV = tsv(["Reaction identifier", "Equation"])

# rhea?query=RHEA:23444&columns=<detail columns>&format=tsv
DETAIL_HEADER = [
    "Reaction identifier",
    "Equation",
    "ChEBI name",
    "ChEBI identifier",
    "EC number",
    "Enzymes",
    "PubMed",
    "Gene Ontology",
    "Cross-reference (KEGG)",
    "Cross-reference (MetaCyc)",
    "Cross-reference (Reactome)",
    "Cross-reference (EcoCyc)",
    "Cross-reference (M-CSA)",
]
DETAIL_LACTATE = tsv(
    DETAIL_HEADER,
    [
        "RHEA:23444",
        "(S)-lactate + NAD(+) = pyruvate + NADH + H(+)",
        "(S)-lactate;NAD(1-);pyruvate;NADH(2-);hydron",
        "CHEBI:16651;CHEBI:57540;CHEBI:15361;CHEBI:57945;CHEBI:15378",
        "EC:1.1.1.27",
        "14021",
        "11821921;12867459;7887607;12967707",
        "GO:0004459 L-lactate dehydrogenase (NAD+) activity",
        "KEGG:R00703",
        "MetaCyc:L-LACTATE-DEHYDROGENASE-RXN",
        "Reactome:R-HSA-70510.8,Reactome:R-HSA-6807826.6,Reactome:R-HSA-71849.9",
        "",
        "",
    ],
)
# a reaction with several ECs and no UniProt enzymes
DETAIL_MULTI_EC = tsv(
    DETAIL_HEADER,
    [
        "RHEA:10028",
        "D-glutamate + O2 + H2O = 2-oxoglutarate + H2O2 + NH4(+)",
        "D-glutamate;dioxygen",
        "CHEBI:29988;CHEBI:15379",
        "EC:1.4.3.7;EC:1.4.3.15",
        "0",
        "31420577",
        "GO:0047821 D-glutamate oxidase activity;GO:0008445 D-aspartate oxidase activity",
        "KEGG:R00279",
        "MetaCyc:D-GLUTAMATE-OXIDASE-RXN",
        "",
        "EcoCyc:D-GLUTAMATE-OXIDASE-RXN",
        "M-CSA:12",
    ],
)

# rhea?query=RHEA:23444&format=json&limit=1
STATUS_JSON = json.dumps(
    {
        "count": 1,
        "results": [
            {
                "id": "23444",
                "equation": "(S)-lactate + NAD(+) = pyruvate + NADH + H(+)",
                "status": "approved",
                "htmlequation": "<span>...</span>",
                "comment": "Reaction  of the  lactate cycle.",
                "balanced": True,
                "transport": False,
            }
        ],
    }
)
STATUS_TRANSPORT_JSON = json.dumps(
    {"count": 1, "results": [{"id": "1", "status": "approved", "transport": True}]}
)
EMPTY_JSON = json.dumps({"count": 0, "results": []})

HTML_ERROR = (
    "<!DOCTYPE html><html><head><title>Rhea - reaction knowledgebase</title></head></html>"
)


def sparql(*rows: dict[str, str]) -> str:
    """SPARQL JSON body; each row maps a variable to its (string) value."""
    bindings = [{k: {"type": "literal", "value": v} for k, v in row.items()} for row in rows]
    return json.dumps({"head": {"vars": []}, "results": {"bindings": bindings}})


def _sub(p: str) -> str:
    return f"{RDFS}subClassOf" if p == "subClassOf" else f"{RH}{p}"


def info_rows(*triples: tuple) -> str:
    """SPARQL body for the reaction info query from ``(predicate, object, label?, subs?)``."""
    rows = []
    for t in triples:
        row = {"p": _sub(t[0]), "o": t[1]}
        if len(t) > 2 and t[2]:
            row["olabel"] = t[2]
        if len(t) > 3 and t[3]:
            row["osubs"] = t[3]
        rows.append(row)
    return sparql(*rows)


# SPARQL info for the master reaction 23444 (cut down)
INFO_MASTER = info_rows(
    ("subClassOf", f"{RH}Reaction", "Reaction"),
    (
        "subClassOf",
        f"{RH}34555",
        "a (2S)-2-hydroxycarboxylate + NAD(+) = a 2-oxocarboxylate + NADH + H(+)",
    ),
    ("equation", "(S)-lactate + NAD(+) = pyruvate + NADH + H(+)"),
    (
        "directionalReaction",
        f"{RH}23445",
        "(S)-lactate + NAD(+) => pyruvate + NADH + H(+)",
        f"{RH}23444_L",
    ),
    (
        "directionalReaction",
        f"{RH}23446",
        "pyruvate + NADH + H(+) => (S)-lactate + NAD(+)",
        f"{RH}23444_R",
    ),
    (
        "bidirectionalReaction",
        f"{RH}23447",
        "(S)-lactate + NAD(+) <=> pyruvate + NADH + H(+)",
    ),
    ("status", f"{RH}Approved"),
    ("ec", "http://purl.uniprot.org/enzyme/1.1.1.27"),
)
# SPARQL info for the R->L directional variant 23446
INFO_RL = info_rows(
    ("subClassOf", f"{RH}DirectionalReaction", "Directional reaction"),
    (
        "subClassOf",
        f"{RH}34557",
        "a 2-oxocarboxylate + NADH + H(+) => a (2S)-2-hydroxycarboxylate + NAD(+)",
        f"{RH}34555_R",
    ),
    ("equation", "pyruvate + NADH + H(+) => (S)-lactate + NAD(+)"),
    ("status", f"{RH}Approved"),
    ("substrates", f"{RH}23444_R"),
)
# SPARQL info for the L->R directional variant 23445
INFO_LR = info_rows(
    ("subClassOf", f"{RH}DirectionalReaction", "Directional reaction"),
    ("equation", "(S)-lactate + NAD(+) => pyruvate + NADH + H(+)"),
    ("status", f"{RH}Approved"),
    ("substrates", f"{RH}23444_L"),
    ("ec", "http://purl.uniprot.org/enzyme/1.1.1.27"),
)
# SPARQL info for the bidirectional variant 23447
INFO_BIDI = info_rows(
    ("subClassOf", f"{RH}BidirectionalReaction", "Bidirectional reaction"),
    ("equation", "(S)-lactate + NAD(+) <=> pyruvate + NADH + H(+)"),
    ("status", f"{RH}Approved"),
)

MASTER_23444 = sparql({"m": f"{RH}23444"})


def _participant(side: str, pred: str, acc: str, name: str) -> dict[str, str]:
    return {
        "side": f"{RH}23444_{side}",
        "pred": f"{RH}{pred}",
        "acc": acc,
        "name": name,
    }


# SPARQL participants of master 23444 (unordered, as the endpoint returns them)
PARTICIPANTS = sparql(
    _participant("L", "contains1", "CHEBI:57540", "NAD(+)"),
    _participant("L", "contains1", "CHEBI:16651", "(S)-lactate"),
    _participant("R", "contains1", "CHEBI:15378", "H(+)"),
    _participant("R", "contains1", "CHEBI:57945", "NADH"),
    _participant("R", "contains2", "CHEBI:15361", "pyruvate"),
    _participant("R", "containsN", "POLYMER:9999", "polymer"),
    _participant("X", "contains1", "CHEBI:1", "wrong side"),
    {"side": f"{RH}23444_L", "pred": f"{RH}curatedOrder", "acc": "CHEBI:2", "name": "no count"},
)

# rhea?query=RHEA:23444&columns=rhea-id,go&format=tsv
GO_TSV = tsv(
    ["Reaction identifier", "Gene Ontology"],
    ["RHEA:23444", "GO:0004459 L-lactate dehydrogenase (NAD+) activity;not a go cell"],
)
