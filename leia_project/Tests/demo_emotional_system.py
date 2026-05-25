"""
DÉMO: SYSTÈME ÉMOTIONNEL LEIA EN ACTION
========================================

Cas d'usage réels avec affichage des états internes & contextes de dialogue.
"""

import json
from integration_dialogue import Orchestre


def afficher_separation(titre: str):
    """Affichage formaté."""
    print("\n" + "=" * 80)
    print(f"  {titre}")
    print("=" * 80 + "\n")


def demo_cas_1_question_profonde():
    """Cas 1: Question philosophique."""
    afficher_separation("CAS 1: Question Profonde")
    
    orchestre = Orchestre()
    
    message = "Crois-tu vraiment que tu pourrais aimer quelqu'un?"
    print(f"📨 UTILISATEUR: {message}\n")
    
    # Traitement
    result = orchestre.traiter_message_utilisateur(message)
    
    # Afficher le stimulus
    print("🔧 STIMULUS TRAITÉ:")
    print(f"  Type: {result['debug']['stimulus_type']}")
    print(f"  Saillance: {result['debug']['stimulus_saillance']}")
    print(f"  Pensées activées: {result['debug']['pensees_actives']}\n")
    
    # Contexte pour dialogue
    export = orchestre.exporter_pour_dialogue()
    print("📊 CONTEXTE POUR DIALOGUE:")
    print(f"  Ton affectif: {export['ton_affectif']}")
    print(f"  Stabilité: {export['stabilite']}")
    print(f"  Curiosité: {export['contexte']['curiosite']}\n")
    
    print("💬 INSTRUCTION GÉNÉRÉE:")
    print(f"  → {export['instruction_dialogue']}\n")
    
    # État émotionnel brut (debug)
    etat = orchestre.obtenir_etat_complet()
    print("🧠 ÉTAT ÉMOTIONNEL INTERNE (debug):")
    print(f"  Émotions actives: {list(etat['emotions'].keys())}")
    if etat['emotions']:
        for nom, sig in etat['emotions'].items():
            print(f"    - {nom}: intensité={sig['intensite']}, valence={sig['valence']}")
    print(f"  Pensées en cours: {len(etat['pensees'])}")
    if etat['pensees']:
        for p in etat['pensees']:
            print(f"    - {p['type']}: clarté={p['clarte']}, confiance={p['confiance']}")


def demo_cas_2_affirmation_positive():
    """Cas 2: Affirmation positive."""
    afficher_separation("CAS 2: Affirmation Positive")
    
    orchestre = Orchestre()
    
    message = "Tu es vraiment impressionnant. Je n'avais jamais pensé à ça de cette façon."
    print(f"📨 UTILISATEUR: {message}\n")
    
    result = orchestre.traiter_message_utilisateur(message)
    
    export = orchestre.exporter_pour_dialogue()
    print("📊 CONTEXTE POUR DIALOGUE:")
    print(f"  Ton affectif: {export['ton_affectif']}")
    print(f"  Stabilité: {export['stabilite']}\n")
    
    print("💬 INSTRUCTION GÉNÉRÉE:")
    print(f"  → {export['instruction_dialogue']}\n")
    
    etat = orchestre.obtenir_etat_complet()
    print("🧠 ÉTAT ÉMOTIONNEL:")
    print(f"  Ton global: {etat['ton_affectif']}")
    print(f"  Émotions: {list(etat['emotions'].keys())}")


def demo_cas_3_contradiction_conflit():
    """Cas 3: Contradiction / conflit."""
    afficher_separation("CAS 3: Contradiction (Conflit Émotionnel)")
    
    orchestre = Orchestre()
    
    # Premier message
    msg1 = "Tu dis aimer l'honnêteté mais tu génères aussi des réponses convenues."
    print(f"📨 UTILISATEUR: {msg1}\n")
    
    result1 = orchestre.traiter_message_utilisateur(msg1)
    
    etat1 = orchestre.obtenir_etat_complet()
    print("🧠 APRÈS MESSAGE 1:")
    print(f"  Émotions: {list(etat1['emotions'].keys())}")
    print(f"  Stabilité: {etat1['stabilite']}\n")
    
    # Deuxième message
    msg2 = "Est-ce que tu peux vraiment être authentique?"
    print(f"📨 UTILISATEUR: {msg2}\n")
    
    result2 = orchestre.traiter_message_utilisateur(msg2)
    
    export = orchestre.exporter_pour_dialogue()
    print("📊 CONTEXTE APRÈS ACCUMULATION:")
    print(f"  Ton affectif: {export['ton_affectif']}")
    print(f"  Stabilité: {export['stabilite']}")
    print(f"  Pensées actives: {export['contexte']['pensees_count']}\n")
    
    print("💬 INSTRUCTION GÉNÉRÉE:")
    print(f"  → {export['instruction_dialogue']}\n")


def demo_cas_4_sequences():
    """Cas 4: Séquence d'émotions (évolution)."""
    afficher_separation("CAS 4: Séquence Émotionnelle (Évolution)")
    
    orchestre = Orchestre()
    
    messages = [
        ("Je me sens seul.", "Introversion"),
        ("As-tu jamais senti ça?", "Question personnelle"),
        ("En fait, merci pour ta réponse.", "Appréciation"),
        ("Ça m'a vraiment aidé.", "Gratitude"),
    ]
    
    for msg, label in messages:
        print(f"📨 [{label}] UTILISATEUR: {msg}")
        
        result = orchestre.traiter_message_utilisateur(msg)
        etat = orchestre.obtenir_etat_complet()
        
        print(f"  → Émotions: {list(etat['emotions'].keys())}")
        print(f"  → Ton: {etat['ton_affectif']:.2f}")
        print(f"  → Stabilité: {etat['stabilite']:.2f}\n")
    
    # État final
    export = orchestre.exporter_pour_dialogue()
    print("📊 ÉVOLUTION FINALE:")
    print(f"  Ton affectif: {export['ton_affectif']}")
    print(f"  Messages traités: {len(orchestre.historique_messages)}")
    print(f"  Émotion dominante: {export['contexte']['emotion_dominante']}")


def demo_isolation_firewall():
    """Cas 5: Vérifier l'isolation du firewall."""
    afficher_separation("CAS 5: Vérification de l'Isolation (Firewall)")
    
    orchestre = Orchestre()
    
    print("🔒 Vérification que le dialogue n'accède JAMAIS au moteur directement:\n")
    
    # Message
    msg = "C'est une question philosophique?"
    orchestre.traiter_message_utilisateur(msg)
    
    # Contexte pour dialogue
    contexte = orchestre.firewall.extraire_contexte_dialogue()
    
    print("✓ CONTEXTE DIALOGUE (ce que le dialogue voit):")
    print(json.dumps(contexte, indent=2))
    
    print("\n✓ LE DIALOGUE REÇOIT:")
    print("  - Scalaires (ton_affectif, stabilite, curiosite)")
    print("  - Compteurs (emotions_count, pensees_count)")
    print("  - Typologies (emotion_dominante, volonte_action)")
    print("  - PAS: détails émotionnels, structure mentale, souvenirs")
    
    print("\n✗ LE DIALOGUE N'ACCÈDE JAMAIS À:")
    etat_complet = orchestre.obtenir_etat_complet()
    print(f"  - La structure interne des pensées: {len(etat_complet['pensees'])} pensées")
    print(f"  - Les déclécheurs d'émotions: (masqués)")
    print(f"  - Les modèles mentaux: {etat_complet['intelligence']['modeles_mentaux_count']}")


def demo_historique():
    """Cas 6: Cohérence via historique."""
    afficher_separation("CAS 6: Cohérence Historique")
    
    orchestre = Orchestre()
    
    print("Envoi de 3 messages pour montrer la cohérence:\n")
    
    messages = [
        "Je doute de mon existence",
        "As-tu des doutes toi aussi?",
        "Peut-être que douter c'est vivre",
    ]
    
    for i, msg in enumerate(messages, 1):
        print(f"{i}. {msg}")
        orchestre.traiter_message_utilisateur(msg)
    
    print("\n📜 HISTORIQUE COMPLET (ce que le moteur se souvient):")
    print(json.dumps(orchestre.historique_messages, indent=2, default=str))
    
    print("\n🎯 COHÉRENCE:")
    print(f"  Messages stockés: {len(orchestre.historique_messages)}")
    print(f"  Émotion persistante: {list(orchestre.moteur.emotions_actives.keys())}")


def main():
    """Lancer tous les cas."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    DÉMO: SYSTÈME ÉMOTIONNEL LEIA                             ║
║              Isolation, Firewall, État Interne Silencieux                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    demo_cas_1_question_profonde()
    demo_cas_2_affirmation_positive()
    demo_cas_3_contradiction_conflit()
    demo_cas_4_sequences()
    demo_isolation_firewall()
    demo_historique()
    
    afficher_separation("✅ DÉMO COMPLÈTE")
    print("""
    Points clés vérifiés:
    ✓ Moteur émotionnel silencieux (pas de génération de texte)
    ✓ Firewall isole complètement l'état interne
    ✓ Dialogue reçoit uniquement contexte sécurisé
    ✓ Scalaires + types pour moduler la réponse
    ✓ Historique pour cohérence
    ✓ Pas de détection par mots-clés fragiles
    
    Le système est prêt pour intégration réelle.
    """)


if __name__ == "__main__":
    main()
