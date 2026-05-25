#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests/test_nlp_integration.py — Test complet : NLP + Mémoire + Apprentissage

Simule une session où :
  1. Leia analyse un message utilisateur
  2. Leia lit un passage de philosophie
  3. Leia répond à une question qui réactive les concepts lus

Usage :
    cd test56847569
    python Tests/test_nlp_integration.py
"""

import sys
import os

# --- Ajouter la racine du projet ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ["", "Cerveau", "Connaissance", "Memory", "Tests"]:
    p = os.path.join(ROOT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

print("=" * 70)
print("TEST INTEGRATION NLP → MEMOIRE → CONNAISSANCE")
print("=" * 70)

# ── 1. Test NLP Bridge ───────────────────────────────────────────────────
print("\n[1] Initialisation NLP Bridge...")
try:
    from nlp_integration import LeiaNLPBridge
    nlp = LeiaNLPBridge()
    print("  ✓ NLP Bridge chargé")
    print(f"  Stats moteur : {nlp.stats()}")
except Exception as e:
    print(f"  ✗ ERREUR : {e}")
    sys.exit(1)

# ── 2. Analyse dialogue ──────────────────────────────────────────────────
print("\n[2] Analyse d'un message utilisateur...")
msg = "Je ne suis pas d'accord — la mémoire n'est pas un tiroir selon Bergson."
sig = nlp.signal(msg)
print(f"  Intent       : {sig['intent']}")
print(f"  Stance       : {sig['stance']}")
print(f"  Focus        : {sig['focus_concepts']}")
print(f"  Propositions : {sig['propositions_count']}")
print(f"  Entities     : {[e['text'] for e in sig['entities']]}")

# ── 3. Lecture livre ─────────────────────────────────────────────────────
print("\n[3] Lecture d'un texte philosophique...")
try:
    from learning_bridge import ReadingBridge
    bridge = ReadingBridge(data_dir="data/test_learn")

    passage = """
La mémoire, selon Bergson, n'est pas un tiroir où l'on range des souvenirs.
Elle est une durée vécue, une continuité vivante qui déborde la perception.
Mais certains philosophes, comme Locke, considèrent au contraire que la mémoire
est fondée sur des impressions passées, des traces fixes.
Cette opposition révèle deux conceptions du temps : le temps mesuré et le temps vécu.
On peut donc affirmer que la question de la mémoire engage nécessairement
une philosophie du temps et de la conscience.
"""
    report = bridge.read_text(passage, source="Bergson - Matière et Mémoire")
    print(f"  Status           : {report['status']}")
    print(f"  Chunks analysés  : {report['chunks_analyzed']}")
    print(f"  Concepts uniques  : {report['unique_concepts']}")
    print(f"  Propositions      : {report['propositions_found']}")
    print(f"  Concepts retenus  : {report['concepts']}")
except Exception as e:
    print(f"  ⚠ learning_bridge non disponible ou erreur : {e}")
    print("  (C'est normal si semantic_plasticity / memory_hierarchy ne sont pas encore copiés)")
    report = None

# ── 4. Réactivation conceptuelle ─────────────────────────────────────────
if report:
    print("\n[4] Réactivation par une question ultérieure...")
    question = "Qu'est-ce que la durée ?"
    q_sig = nlp.signal(question)
    print(f"  Question analysée : intent={q_sig['intent']}, focus={q_sig['focus_concepts']}")

    related = bridge.react_to_concepts(q_sig['focus_concepts'])
    if related:
        print(f"  Concepts réactivés depuis la mémoire de lecture : {related}")
    else:
        print("  (Aucun concept lié encore enregistré — les modules mémoire du dépôt n'ont pas été initialisés)")

    state = bridge.get_knowledge_state()
    print(f"\n[5] État de la connaissance :")
    print(f"  Livres lus        : {state['books_read']}")
    print(f"  Noeuds plasticité : {state['plasticity_nodes']}")
    print(f"  Mémoire fondatrice: {state['memory_foundational']}")
    print(f"  Mémoire pivot     : {state['memory_pivot']}")

print("\n" + "=" * 70)
print("TEST TERMINÉ")
print("=" * 70)
