"""
Integration test for RAG V2 Pipeline.
Run: cd backend && python test_rag_upgrade.py
"""
import sys
import os

# Ensure we can import from the backend directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def test_indexer():
    """Test: Enhanced chunking with metadata extraction."""
    separator("TEST 1: RAG Indexer — Metadata Extraction")
    from services.rag_indexer import (
        enhanced_chunk_text, _extract_keywords, _has_definition,
        _has_list, _has_math, _estimate_complexity, _make_stable_chunk_id,
        _make_chunk_hash,
    )
    
    sample_text = """
    Osteoradionecrosis (ORN) is defined as the irradiated bone which becomes 
    devitalized and is exposed through the overlying skin or mucosa and does 
    not heal within a period of three months, without tumor recurrence.
    
    The following factors contribute to ORN:
    1. Radiation dose above 60 Gy
    2. Poor oral hygiene
    3. Tooth extraction post-radiation
    4. Mandibular location
    
    Treatment protocols include:
    - Hyperbaric oxygen therapy (HBO)
    - Conservative debridement
    - Surgical resection with reconstruction
    
    The formula for calculating BED (Biologically Effective Dose) is:
    BED = nd(1 + d/(alpha/beta))
    where n = number of fractions, d = dose per fraction.
    """
    
    # Test chunking
    chunks = enhanced_chunk_text(sample_text, chunk_size=300, overlap=50)
    print(f"  Chunks produced: {len(chunks)}")
    assert len(chunks) > 0, "Should produce at least 1 chunk"
    
    # Test metadata detection
    print(f"  has_definition: {_has_definition(sample_text)}")
    print(f"  has_list: {_has_list(sample_text)}")
    print(f"  has_math: {_has_math(sample_text)}")
    print(f"  complexity: {_estimate_complexity(sample_text)}")
    print(f"  keywords: {_extract_keywords(sample_text, top_n=5)}")
    
    assert _has_definition(sample_text) == True, "Should detect definition"
    assert _has_list(sample_text) == True, "Should detect list"
    assert _has_math(sample_text) == True, "Should detect math"
    
    # Test stable chunk IDs
    id1 = _make_stable_chunk_id(1, "hello world")
    id2 = _make_stable_chunk_id(1, "hello world")
    id3 = _make_stable_chunk_id(2, "hello world")
    print(f"  Stable ID (same input): {id1} == {id2}: {id1 == id2}")
    print(f"  Stable ID (diff material): {id1} != {id3}: {id1 != id3}")
    assert id1 == id2, "Same input should produce same ID"
    assert id1 != id3, "Different material_id should produce different ID"
    
    # Test chunk hash
    h1 = _make_chunk_hash("Hello World")
    h2 = _make_chunk_hash("hello world")  # Normalized
    print(f"  Chunk hash dedup (case-insensitive): {h1 == h2}")
    assert h1 == h2, "Hashes should match after normalization"
    
    print("  [PASS]")


def test_query_builder():
    """Test: Multi-variant query generation."""
    separator("TEST 2: Query Builder — Variant Generation")
    from services.rag_query_builder import build_query_variants
    
    variants = build_query_variants(
        topic_name="Clinical Maxillofacial Prosthetics",
        lo_text="Implement dental protocols to prevent osteoradionecrosis and manage xerostomia",
        co_text="Apply clinical prosthetic rehabilitation techniques",
        bloom_level="Application",
        difficulty="Hard",
        question_type="MCQ",
    )
    
    print(f"  Variants generated: {len(variants)}")
    for v in variants:
        print(f"    [{v.strategy}] (w={v.weight:.2f}) {v.text[:80]}...")
    
    assert 4 <= len(variants) <= 10, f"Expected 4-10 variants, got {len(variants)}"
    
    strategies = [v.strategy for v in variants]
    assert any("semantic" in s for s in strategies), "Should have semantic variant"
    assert any("bloom" in s for s in strategies), "Should have bloom variant"
    assert any("keyword" in s for s in strategies), "Should have keyword variant"
    
    print("  [PASS]")


def test_retriever():
    """Test: Hybrid retrieval pipeline against existing ChromaDB data."""
    separator("TEST 3: Retriever — Hybrid Pipeline")
    from services.rag_retriever import retrieve_context_for_generation
    
    result = retrieve_context_for_generation(
        subject_id=1,
        topic_id=1,
        topic_name="Clinical Maxillofacial Prosthetics",
        lo_text="Implement dental protocols to prevent osteoradionecrosis",
        co_text="",
        bloom_level="Application",
        difficulty="Medium",
        question_type="MCQ",
        n_results=5,
        use_cross_encoder=False,  # Skip for faster test
    )
    
    chunks = result["chunks"]
    chunk_ids = result["chunk_ids"]
    debug = result["debug_info"]
    
    print(f"  Chunks retrieved: {len(chunks)}")
    print(f"  Chunk IDs: {len(chunk_ids)}")
    print(f"  Total candidates: {debug.get('total_candidates', 0)}")
    print(f"  Pipeline time: {debug.get('pipeline_time_seconds', 0):.3f}s")
    print(f"  Query variants used: {len(debug.get('query_variants', []))}")
    
    if chunks:
        print(f"  First chunk preview: {chunks[0][:120]}...")
    
    assert len(chunks) > 0, "Should retrieve at least 1 chunk"
    assert len(chunks) == len(chunk_ids), "Chunks and IDs should be same length"
    assert debug["total_candidates"] > 0, "Should have candidates"
    
    print("  [PASS]")


def test_novelty():
    """Test: Question novelty detection."""
    separator("TEST 4: Novelty — Similarity Detection")
    from services.novelty import _cosine_similarity
    from services.rag import embedding_fn
    
    q1 = "What is osteoradionecrosis and how is it treated?"
    q2 = "What is osteoradionecrosis and what are the treatment options?"  # Very similar
    q3 = "Describe the components of a removable partial denture."  # Very different
    
    emb1 = embedding_fn([q1])[0]
    emb2 = embedding_fn([q2])[0]
    emb3 = embedding_fn([q3])[0]
    
    sim_12 = _cosine_similarity(emb1, emb2)
    sim_13 = _cosine_similarity(emb1, emb3)
    
    print(f"  Similarity (near-duplicate): {sim_12:.4f}")
    print(f"  Similarity (different topic): {sim_13:.4f}")
    
    assert sim_12 > 0.8, f"Near-duplicate should have sim > 0.8, got {sim_12}"
    assert sim_13 < 0.7, f"Different topics should have sim < 0.7, got {sim_13}"
    
    print("  [PASS]")


def test_grounding():
    """Test: Grounding validation."""
    separator("TEST 5: Grounding — Validation")
    from services.novelty import validate_grounding
    
    # Question that should be grounded (about dentistry/ORN)
    grounded_q = "What presurgical procedure is used to align alveolar segments in infants with cleft lip and palate?"
    
    result = validate_grounding(
        subject_id=1,
        question_text=grounded_q,
        topic_id=1,
    )
    
    print(f"  Is grounded: {result['is_grounded']}")
    print(f"  Grounding score: {result['grounding_score']}")
    if result['best_matching_chunk']:
        print(f"  Best chunk preview: {result['best_matching_chunk'][:120]}...")
    
    # The score should be > 0 if there's relevant material
    assert result['grounding_score'] >= 0, "Score should be non-negative"
    
    print("  [PASS]")


if __name__ == "__main__":
    print("\n🧪 RAG V2 Pipeline Integration Tests")
    print("=" * 60)
    
    tests = [test_indexer, test_query_builder, test_retriever, test_novelty, test_grounding]
    passed = 0
    failed = 0
    
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL]: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    separator(f"RESULTS: {passed}/{len(tests)} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
