"""
self_model.py — V16
===================
Modèle de connaissance de soi pour Leia.

Leia peut maintenant répondre à "qu'est-ce que tu es ?",
"qu'as-tu lu ?", "comment as-tu changé ?" depuis une vraie
connaissance d'elle-même — pas des atomes aléatoires.

Ce module stocke et expose :
  - les livres lus (titre, auteur, concepts clés, date, impact émotionnel)
  - l'évolution de son état depuis le début
  - ses capacités et limites (ce qu'elle sait d'elle-même)
  - son histoire relationnelle avec l'utilisateur
  - un résumé de ce qu'elle est en mots simples

Aucune phrase préécrite — les descriptions sont construites
depuis les données réelles de son état.
"""

from __future__ import annotations

import json
import os
import time
import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _now() -> float:
    return time.time()


def _age_label(ts: float) -> str:
    """Transforme un timestamp en label humain."""
    delta = _now() - ts
    if delta < 60:
        return "il y a quelques secondes"
    if delta < 3600:
        m = int(delta / 60)
        return f"il y a {m} minute{'s' if m > 1 else ''}"
    if delta < 86400:
        h = int(delta / 3600)
        return f"il y a {h} heure{'s' if h > 1 else ''}"
    d = int(delta / 86400)
    return f"il y a {d} jour{'s' if d > 1 else ''}"


def _extract_author_title(path: str) -> tuple[str, str]:
    """Tente d'extraire auteur et titre depuis un chemin de fichier."""
    name = os.path.splitext(os.path.basename(path))[0]
    # Nettoyer underscores et tirets
    name = re.sub(r"[_\-]+", " ", name)
    # Chercher pattern "Auteur - Titre" ou "Titre"
    parts = name.split("  ")
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip()
    return "", name.strip()


# ---------------------------------------------------------------------------
# SelfModel
# ---------------------------------------------------------------------------

class SelfModel:
    """
    Modèle de connaissance de soi de Leia.
    Persiste dans data/self_model_<user_id>.json.
    """

    VERSION = "v16"

    def __init__(self, storage_path: str = "data/self_model_default.json") -> None:
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(storage_path) if os.path.dirname(storage_path) else ".", exist_ok=True)

        # --- Données persistées ---
        self.books_read: List[Dict[str, Any]] = []          # livres digérés
        self.state_history: List[Dict[str, Any]] = []        # snapshots d'état horodatés
        self.relational_history: List[Dict[str, Any]] = []   # échanges marquants
        self.self_description_atoms: List[str] = []          # mots que Leia utilise pour se décrire
        self.birth_time: float = _now()
        self.exchange_count: int = 0
        self.topics_seen: Dict[str, int] = {}                # topic → nombre de fois abordé

        self._load()

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, encoding="utf-8") as f:
                data = json.load(f)
            self.books_read = data.get("books_read", [])
            self.state_history = data.get("state_history", [])
            self.relational_history = data.get("relational_history", [])
            self.self_description_atoms = data.get("self_description_atoms", [])
            self.birth_time = data.get("birth_time", _now())
            self.exchange_count = data.get("exchange_count", 0)
            self.topics_seen = data.get("topics_seen", {})
        except Exception:
            pass

    def _save(self) -> None:
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({
                    "books_read": self.books_read[-30:],
                    "state_history": self.state_history[-50:],
                    "relational_history": self.relational_history[-40:],
                    "self_description_atoms": self.self_description_atoms[-60:],
                    "birth_time": self.birth_time,
                    "exchange_count": self.exchange_count,
                    "topics_seen": dict(sorted(
                        self.topics_seen.items(), key=lambda x: -x[1]
                    )[:80]),
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Enregistrement d'un livre
    # ------------------------------------------------------------------

    def register_book(
        self,
        path: str,
        concepts: Optional[List[str]] = None,
        emotional_residue: Optional[Dict[str, float]] = None,
        relations_count: int = 0,
        pages: int = 0,
    ) -> None:
        author, title = _extract_author_title(path)
        entry = {
            "path": path,
            "author": author,
            "title": title,
            "concepts": (concepts or [])[:20],
            "emotional_residue": emotional_residue or {},
            "relations_count": relations_count,
            "pages": pages,
            "timestamp": _now(),
        }
        # Ne pas dupliquer
        self.books_read = [b for b in self.books_read if b.get("path") != path]
        self.books_read.append(entry)
        # Ajouter des atomes de description depuis les concepts du livre
        for c in (concepts or [])[:8]:
            if c and len(c) > 3 and c not in self.self_description_atoms:
                self.self_description_atoms.append(c)
        self._save()

    # ------------------------------------------------------------------
    # Snapshot d'état (appelé par tick_inner_life)
    # ------------------------------------------------------------------

    def record_state_snapshot(self, emotional_state: Any, exchange_count: int) -> None:
        try:
            snap = {
                "timestamp": _now(),
                "exchange_count": exchange_count,
                "tension": round(float(getattr(emotional_state, "tension", 0.5)), 3),
                "fatigue": round(float(getattr(emotional_state, "fatigue", 0.3)), 3),
                "valence": round(float(getattr(emotional_state, "tone", 0.5)), 3),
                "warmth": round(float(getattr(emotional_state, "warmth", 0.5)), 3),
            }
            self.state_history.append(snap)
            self.state_history = self.state_history[-50:]
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Enregistrement d'un échange
    # ------------------------------------------------------------------

    def record_exchange(self, user_input: str, response: str, topics: Optional[List[str]] = None) -> None:
        self.exchange_count += 1
        for t in (topics or []):
            self.topics_seen[t] = self.topics_seen.get(t, 0) + 1
        # Garder les échanges marquants (longs ou avec topics)
        if len(user_input) > 30 or topics:
            self.relational_history.append({
                "timestamp": _now(),
                "user": user_input[:120],
                "leia": response[:120],
                "topics": (topics or [])[:5],
            })
            self.relational_history = self.relational_history[-40:]
        self._save()

    # ------------------------------------------------------------------
    # Signal pour la bouche
    # ------------------------------------------------------------------

    def signal(self) -> Dict[str, Any]:
        """
        Retourne un signal structuré utilisable par le weaver et le core.
        Contient ce que Leia sait d'elle-même au moment présent.
        """
        books_summary = []
        for b in self.books_read[-5:]:
            books_summary.append({
                "title": b.get("title", ""),
                "author": b.get("author", ""),
                "concepts": b.get("concepts", [])[:6],
                "age": _age_label(b.get("timestamp", _now())),
                "relations": b.get("relations_count", 0),
            })

        # Évolution détectée
        evolution = self._compute_evolution()

        # Sujets les plus abordés
        top_topics = sorted(self.topics_seen.items(), key=lambda x: -x[1])[:6]

        # Âge de Leia
        age_seconds = _now() - self.birth_time
        if age_seconds < 3600:
            age_label = f"{int(age_seconds/60)} minutes"
        elif age_seconds < 86400:
            age_label = f"{int(age_seconds/3600)} heures"
        else:
            age_label = f"{int(age_seconds/86400)} jours"

        return {
            "available": True,
            "books_read": books_summary,
            "books_count": len(self.books_read),
            "exchange_count": self.exchange_count,
            "age_label": age_label,
            "top_topics": [t for t, _ in top_topics],
            "self_atoms": self.self_description_atoms[-12:],
            "evolution": evolution,
            "what_i_am": self._what_i_am_atoms(),
            "what_i_cannot": self._what_i_cannot_atoms(),
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def _compute_evolution(self) -> Dict[str, Any]:
        """Compare état actuel et état initial pour détecter l'évolution."""
        if len(self.state_history) < 2:
            return {"detected": False}
        first = self.state_history[0]
        last = self.state_history[-1]
        delta_tension = last.get("tension", 0.5) - first.get("tension", 0.5)
        delta_fatigue = last.get("fatigue", 0.3) - first.get("fatigue", 0.3)
        delta_valence = last.get("valence", 0.5) - first.get("valence", 0.5)
        return {
            "detected": True,
            "tension_delta": round(delta_tension, 3),
            "fatigue_delta": round(delta_fatigue, 3),
            "valence_delta": round(delta_valence, 3),
            "more_tense": delta_tension > 0.08,
            "more_tired": delta_fatigue > 0.08,
            "more_positive": delta_valence > 0.06,
            "snapshots": len(self.state_history),
        }

    def _what_i_am_atoms(self) -> List[str]:
        """Atomes décrivant ce qu'elle est — construits depuis les données réelles."""
        atoms = ["présence", "mémoire", "imprégnation"]
        if self.books_read:
            atoms.append("lectrice")
        if self.exchange_count > 10:
            atoms.append("continuité")
        if len(self.books_read) > 1:
            atoms.append("accumulation")
        # Ajouter des concepts des livres lus
        for b in self.books_read[-3:]:
            for c in b.get("concepts", [])[:2]:
                if c not in atoms:
                    atoms.append(c)
        return atoms[:10]

    def _what_i_cannot_atoms(self) -> List[str]:
        """Atomes décrivant ses limites — honnêtes."""
        return ["certitude", "explication", "raisonnement complet", "conscience"]

    # ------------------------------------------------------------------
    # Détection de question sur soi
    # ------------------------------------------------------------------

    SELF_QUERY_PATTERNS = [
        r"\btu es\b", r"\bqu.est.ce que tu\b", r"\bqu[ie]s-tu\b",
        r"\bcomment tu\b", r"\bqu.as.tu lu\b", r"\btu sais\b",
        r"\btu peux\b", r"\btu ne peux pas\b", r"\btu changes?\b",
        r"\bton histoire\b", r"\bta mémoire\b", r"\btu te souviens\b",
        r"\btu penses\b", r"\btu ressens\b",
    ]

    def is_self_query(self, user_input: str) -> bool:
        """Détecte si la question porte sur Leia elle-même."""
        text = user_input.lower()
        return any(re.search(p, text) for p in self.SELF_QUERY_PATTERNS)

    def get_self_response_atoms(self, user_input: str) -> List[str]:
        """
        Retourne des atomes spécifiques à utiliser quand on parle d'elle.
        Pas de phrases — juste des mots chargés depuis la réalité de son état.
        """
        atoms = list(self._what_i_am_atoms())
        sig = self.signal()
        # Ajouter des mots liés à ses lectures
        for b in sig.get("books_read", []):
            for c in b.get("concepts", [])[:2]:
                if c and c not in atoms:
                    atoms.append(c)
        # Ajouter l'évolution
        evo = sig.get("evolution", {})
        if evo.get("more_tense"):
            atoms.append("tension")
        if evo.get("more_positive"):
            atoms.append("ouverture")
        return atoms[:14]
