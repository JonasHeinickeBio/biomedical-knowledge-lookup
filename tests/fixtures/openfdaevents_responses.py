"""Real openFDA drug/event count responses (fetched 2026-10-07; meta trimmed)."""

ASPIRIN_SERIOUS = {
    "meta": {"last_updated": "2026-07-30"},
    "results": [{"term": 1, "count": 381371}, {"term": 2, "count": 152457}],
}

FATIGUE_SERIOUS = {
    "meta": {"last_updated": "2026-07-30"},
    "results": [{"term": 1, "count": 400892}, {"term": 2, "count": 365257}],
}

ASPIRIN_REACTIONS = {
    "meta": {"last_updated": "2026-07-30"},
    "results": [
        {"term": "FATIGUE", "count": 33155},
        {"term": "DYSPNOEA", "count": 28112},
        {"term": "DIARRHOEA", "count": 27506},
        {"term": "NAUSEA", "count": 27443},
        {"term": "DIZZINESS", "count": 23142},
        {"term": "DRUG INEFFECTIVE", "count": 22481},
    ],
}

FATIGUE_DRUGS = {
    "meta": {"last_updated": "2026-07-30"},
    "results": [
        {"term": "PREDNISONE", "count": 40818},
        {"term": "ADALIMUMAB", "count": 39654},
        {"term": "ERGOCALCIFEROL", "count": 37943},
        {"term": "ACETAMINOPHEN", "count": 36342},
        {"term": "ASPIRIN", "count": 33155},
        {"term": "METHOTREXATE SODIUM", "count": 32749},
    ],
}

ASPIRIN_INDICATIONS = {
    "meta": {"last_updated": "2026-07-30"},
    "results": [
        {"term": "PRODUCT USED FOR UNKNOWN INDICATION", "count": 130100},
        {"term": "Product used for unknown indication", "count": 92142},
        {"term": "HYPERTENSION", "count": 38543},
        {"term": "PLASMA CELL MYELOMA", "count": 36018},
        {"term": "DIABETES MELLITUS", "count": 23825},
        {"term": "ATRIAL FIBRILLATION", "count": 19769},
        {"term": "PAIN", "count": 18024},
        {"term": "BLOOD CHOLESTEROL INCREASED", "count": 17747},
        {"term": "Plasma cell myeloma", "count": 16111},
        {"term": "Hypertension", "count": 14866},
    ],
}

SEARCH_DRUG_ASPIRIN = {
    "meta": {"last_updated": "2026-07-30"},
    "results": [
        {"term": "ASPIRIN", "count": 534081},
        {"term": "ASPIRIN 81 MG", "count": 508850},
        {"term": "ASPIRIN 325 MG", "count": 508604},
        {"term": "ACETAMINOPHEN, ASPIRIN, AND CAFFEINE", "count": 20953},
        {"term": "FUROSEMIDE", "count": 74428},
        {"term": "ERGOCALCIFEROL", "count": 74159},
        {"term": "OMEPRAZOLE MAGNESIUM", "count": 69128},
    ],
}

SEARCH_REACTION_CFS = {
    "meta": {"last_updated": "2026-07-30"},
    "results": [
        {"term": "CHRONIC FATIGUE SYNDROME", "count": 1371},
        {"term": "FATIGUE", "count": 335},
        {"term": "DEPRESSION", "count": 325},
        {"term": "FIBROMYALGIA", "count": 259},
    ],
}

NOT_FOUND_ERROR = {"error": {"code": "NOT_FOUND", "message": "No matches found!"}}
