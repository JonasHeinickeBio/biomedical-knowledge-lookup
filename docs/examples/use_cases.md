# Use Case Examples

This document provides real-world use cases for the Biomedical Knowledge Lookup library.

## Drug Discovery Pipeline

### Target Identification

Finding potential drug targets for a specific disease:

```python
import asyncio
from knowledge_lookup import CentralKnowledgeLookup, MultiSourceAnnotator, LookupConfig

async def find_targets_for_disease(disease_name: str):
    """Find drug targets for a disease using multiple knowledge sources."""
    config = LookupConfig()
    lookup = CentralKnowledgeLookup(config)

    # Search for the disease
    disease_results = await lookup.search_concepts(
        disease_name,
        sources=["MONDO", "DOID", "DOID"],
        limit=5
    )

    print(f"Found {len(disease_results.concepts)} disease concepts")

    targets = []
    for disease in disease_results.concepts:
        # Find gene-disease associations
        associations = await lookup.search_concepts(
            f"{disease.primary_label} AND gene",
            sources=["DisGeNET", "OpenTargets"],
            limit=20
        )
        targets.extend(associations.concepts)

    await lookup.close()
    return targets

# Usage
targets = asyncio.run(find_targets_for_disease("Alzheimer's disease"))
for target in targets[:10]:
    print(f"- {target.primary_label}: {target.primary_id}")
```

### Drug Repurposing

Finding existing drugs that might be effective for new indications:

```python
async def find_drug_repurposing_candidates(disease: str):
    """Find drugs that could be repurposed for a disease."""
    config = LookupConfig()
    lookup = CentralKnowledgeLookup(config)

    # Get disease concept
    disease_search = await lookup.search_concepts(disease, sources=["MONDO"], limit=1)
    if not disease_search.concepts:
        print("Disease not found")
        return

    disease_id = disease_search.concepts[0].primary_id

    # Search for drug-disease associations
    drug_results = await lookup.search_concepts(
        f"drug AND {disease}",
        sources=["ChEMBL", "OpenTargets"],
        limit=50
    )

    print(f"Found {len(drug_results.concepts)} potential drug candidates")

    for drug in drug_results.concepts[:20]:
        print(f"- {drug.primary_label}")
        print(f"  ID: {drug.primary_id}")
        print(f"  Type: {drug.concept_type}")

    await lookup.close()

asyncio.run(find_drug_repurposing_candidates("diabetes"))
```

## Disease Gene Discovery

Finding genes associated with a disease:

```python
async def find_disease_genes(disease_name: str):
    """Find genes associated with a disease across multiple sources."""
    config = LookupConfig()
    lookup = CentralKnowledgeLookup(config)

    # Search for disease
    disease_search = await lookup.search_concepts(
        disease_name,
        sources=["MONDO", "HPO"],
        limit=3
    )

    all_genes = []
    for disease in disease_search.concepts:
        # Search for gene associations
        gene_results = await lookup.search_concepts(
            f"{disease.primary_label} AND gene",
            sources=["DisGeNET", "OpenTargets", "OMIM"],
            limit=50
        )
        all_genes.extend(gene_results.concepts)

    # Deduplicate genes
    unique_genes = list({g.primary_id: g for g in all_genes}.values())

    print(f"Found {len(unique_genes)} unique genes")
    for gene in unique_genes[:20]:
        print(f"- {gene.primary_label} ({gene.primary_id})")

    await lookup.close()

asyncio.run(find_disease_genes("cystic fibrosis"))
```

## Biomedical Text Mining

Annotating text with biomedical entities:

```python
import re
from knowledge_lookup import MultiSourceAnnotator, LookupConfig

async def annotate_text(text: str):
    """Annotate biomedical entities in text."""
    config = LookupConfig()
    annotator = MultiSourceAnnotator(config)

    # Simple sentence tokenization
    sentences = re.split(r'(?<=[.!?])\s+', text)

    all_annotations = []

    for sentence in sentences:
        annotations = await annotator.annotate_text(sentence)
        all_annotations.extend(annotations.entities)

    await annotator.close()
    return all_annotations

# Usage
text = """
Diabetes mellitus is a group of metabolic disorders characterized by
high blood sugar levels. Insulin resistance and beta cell dysfunction
are key factors in type 2 diabetes.
"""

annotations = asyncio.run(annotate_text(text))
for entity in annotations[:10]:
    print(f"- {entity.text}: {entity.concept_id} ({entity.source})")
```

## Clinical Decision Support

Building a clinical decision support system:

```python
async def clinical_lookup(patient_condition: str, patient_genes: list):
    """Look up clinical information for a patient's condition and genes."""
    config = LookupConfig()
    lookup = CentralKnowledgeLookup(config)

    results = {
        "condition": None,
        "gene_associations": [],
        "drug_interactions": []
    }

    # Look up condition
    condition_results = await lookup.search_concepts(
        patient_condition,
        sources=["MONDO", "HPO"],
        limit=5
    )
    results["condition"] = condition_results

    # Look up gene-disease associations
    for gene in patient_genes:
        gene_results = await lookup.search_concepts(
            f"{gene} AND {patient_condition}",
            sources=["DisGeNET", "ClinVar", "OMIM"],
            limit=10
        )
        results["gene_associations"].extend(gene_results.concepts)

    # Look up drug-gene interactions
    drug_results = await lookup.search_concepts(
        f"drug AND ({' OR '.join(patient_genes)})",
        sources=["ChEMBL", "DrugBank"],
        limit=20
    )
    results["drug_interactions"] = drug_results.concepts

    await lookup.close()
    return results

# Usage
patient_data = {
    "condition": "breast cancer",
    "genes": ["BRCA1", "BRCA2", "TP53"]
}

clinical_results = asyncio.run(clinical_lookup(**patient_data))
```

## Knowledge Graph Construction

Building a knowledge graph from search results:

```python
from rdflib import Graph, Namespace, Literal, URIRef
from knowledge_lookup import CentralKnowledgeLookup, LookupConfig

async def build_knowledge_graph(queries: list):
    """Build a knowledge graph from multiple concept searches."""
    config = LookupConfig()
    lookup = CentralKnowledgeLookup(config)

    # Define namespaces
    EX = Namespace("http://example.org/")
    BIO = Namespace("http://biologicalontology.org/")

    g = Graph()
    g.bind("ex", EX)
    g.bind("bio", BIO)

    all_concepts = []

    # Search for each query
    for query in queries:
        results = await lookup.search_concepts(
            query,
            sources=["MONDO", "ChEMBL", "Gene Ontology"],
            limit=20
        )
        all_concepts.extend(results.concepts)

    # Add concepts to graph
    for concept in all_concepts:
        concept_uri = EX[concept.primary_id.replace(":", "_")]

        g.add((concept_uri, BIO.label, Literal(concept.primary_label)))
        g.add((concept_uri, BIO.type, Literal(concept.concept_type or "unknown")))

        # Add synonyms
        for synonym in concept.synonyms or []:
            g.add((concept_uri, BIO.synonym, Literal(synonym)))

        # Add identifiers
        for identifier in concept.identifiers or []:
            g.add((
                concept_uri,
                BIO.has_identifier,
                Literal(f"{identifier.source}:{identifier.identifier}")
            ))

    await lookup.close()
    return g

# Usage
g = asyncio.run(build_knowledge_graph(["diabetes", "cancer", "Alzheimer"]))

# Export to different formats
print(g.serialize(format="turtle"))
