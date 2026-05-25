#!/usr/bin/env python3
"""Test rapide des modules V18."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

print("=== Test V18 modules ===")

# 1. UserUtteranceParser
try:
    from user_utterance_parser import UserUtteranceParser
    p = UserUtteranceParser("data/test_utt.json")
    sig = p.signal("Est-ce que la mémoire peut vraiment mentir ?")
    assert sig["available"]
    assert sig["is_question"]
    print(f"✓ UserUtteranceParser  intent={sig['intent']} focus={sig['focus_concept']}")
except Exception as e:
    print(f"✗ UserUtteranceParser  {e}")

# 2. AssociativeMemory
try:
    from associative_memory import AssociativeMemory
    am = AssociativeMemory("data/test_assoc.json")
    am.impregnate(["mémoire","durée","bergson","souvenir","temps","conscience"], "test")
    am.impregnate(["absurde","camus","révolte","sens","mort","liberté"], "test")
    sig = am.signal(["mémoire"], top_k=5)
    assert sig["available"]
    print(f"✓ AssociativeMemory    top={sig['top_concept']} act={sig['top_activation']:.3f}")
except Exception as e:
    print(f"✗ AssociativeMemory    {e}")

# 3. SemanticCoherence
try:
    from semantic_coherence import SemanticCoherence
    sc = SemanticCoherence("data/test_coh.json")
    sig = sc.signal(["mémoire","durée"], "Il reste une tension, quelque chose comme un appui.")
    print(f"✓ SemanticCoherence    coherence={sig.get('coherence',0):.3f} judgment={sig.get('judgment','')}")
except Exception as e:
    print(f"✗ SemanticCoherence    {e}")

# 4. PropositionExtractor
try:
    from proposition_extractor import PropositionExtractor
    pe = PropositionExtractor("data/test_props.json")
    result = pe.extract_from_text(
        "La mémoire n'est pas un tiroir mais une durée vécue. Bergson affirme que la conscience est mouvement.",
        source="test"
    )
    sig = pe.signal("mémoire")
    print(f"✓ PropositionExtractor props={len(result)} total={sig.get('count',0)}")
except Exception as e:
    print(f"✗ PropositionExtractor {e}")

# 5. UserModel
try:
    from user_model import UserModel
    um = UserModel("data/test_um.json")
    um.observe("Est-ce que la conscience peut vraiment se connaître elle-même ?")
    um.observe("Je ressens quelque chose d'étrange quand j'y pense.")
    um.observe("La phénoménologie de Husserl répond à ça non ?")
    sig = um.signal()
    print(f"✓ UserModel            vocab={sig.get('vocab_level',0):.3f} domain={sig.get('dominant_domain','')}")
except Exception as e:
    print(f"✗ UserModel            {e}")

# 6. AffectLexicon
try:
    from affect_lexicon import AffectLexicon
    al = AffectLexicon("data/test_affect.json")
    sig = al.signal("Je ressens une angoisse profonde face au néant et à la mort.")
    assert sig["available"]
    print(f"✓ AffectLexicon        valence={sig['valence']:.3f} emotion={sig['emotion']}")
    sig2 = al.signal("Une joie légère, de la curiosité, de l'espoir.")
    print(f"  AffectLexicon+        valence={sig2['valence']:.3f} emotion={sig2['emotion']}")
except Exception as e:
    print(f"✗ AffectLexicon        {e}")

print()
print("=== Intégration core ===")
try:
    from leia_living_core import LeiaLivingCore
    core = LeiaLivingCore()
    v18_modules = ["utterance_parser","associative_memory","semantic_coherence",
                   "proposition_extractor","user_model","affect_lexicon"]
    for m in v18_modules:
        status = "✓" if getattr(core, m, None) is not None else "✗ (non instancié)"
        print(f"  core.{m}: {status}")
    print()
    resp = core.process_message("La mémoire peut-elle vraiment trahir ?")
    print(f"✓ process_message OK   réponse: {resp[:80]}...")
except Exception as e:
    print(f"✗ Intégration core     {e}")

print()
print("Nettoyage fichiers test...")
import glob
for f in glob.glob("data/test_*.json"):
    try: os.remove(f)
    except: pass
print("Done.")
