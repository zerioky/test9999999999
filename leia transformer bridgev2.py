# -*- coding: utf-8 -*-
"""
leia_transformer_bridge.py — Pont Transformer ↔ GlobalWorkspace pour Leia V20+
════════════════════════════════════════════════════════════════════════════════

Rôle dans l'organisme :
    Ce module connecte le mini-transformer (leia_mini_transformer.py) au
    GlobalWorkspace de Leia. Il apporte un signal que ni le SemanticCortex
    ni le NLP symbolique ne peuvent produire : la RÉSONANCE SÉMANTIQUE.

    Cortex    → comprend la STRUCTURE de ce message (qui fait quoi, causes,
                tensions) — basé sur le message courant
    Bridge    → retrouve des FRAGMENTS APPRIS similaires dans la mémoire
                vectorielle — basé sur l'apprentissage passé

    Ce sont deux signaux complémentaires. Ensemble, ils donnent à Leia :
        "ce que tu dis maintenant" + "ce que j'ai déjà appris là-dessus"

Philosophie :
    - Zéro dépendance externe (numpy uniquement, déjà requis par le transformer)
    - Dégradation silencieuse : si le modèle n'est pas encore entraîné,
      le bridge ne fait rien et Leia continue normalement
    - L'index sémantique est construit une seule fois au démarrage,
      puis caché sur disque

Pipeline d'intégration (perception) :
    user_message
        → encode_sentence()          [vecteur dim=128]
        → cosine search pondéré      [top-K fragments × poids de consolidation]
        → extraction de concepts     [mots porteurs de sens]
        → workspace.inject_memoire() [signal "résonance" dans le champ]

Pipeline d'apprentissage (après expression) :
    last_leia_response
        → encode_sentence()          [vecteur dim=128]
        → index.ajouter()            [dédupliqué + stocké]
        → sauvegarde périodique      [tous les 10 appris]

Pipeline de consolidation (périodique) :
    fragments les plus activés (hits ≥ 3)
        → index.renforcer()          [poids × 1.08]
        → workspace.inject_memoire() [souvenir qui "remonte"]

Interactions :
    - Reçoit : user_message depuis respond(), last_response depuis après_expression()
    - Utilise : leia_mini_transformer.py (même répertoire ou chemin Python)
    - Influence : GlobalWorkspace via inject_memoire()
    - Persiste : semantic_index.npz + semantic_index_textes.pkl

Statut : V20.1 — apprentissage et consolidation actifs
"""

from __future__ import annotations

import json
import math
import os
import pickle
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# 0. CHEMINS PAR DÉFAUT
# ─────────────────────────────────────────────────────────────────────────────

_HERE = Path(os.path.dirname(os.path.abspath(__file__)))

# Le modèle est cherché dans cet ordre :
_MODEL_CANDIDATES = [
    _HERE / "leia_model" / "leia_model_final",
    _HERE.parent / "leia_model" / "leia_model_final",
    _HERE.parent.parent / "leia_model" / "leia_model_final",
    Path("./leia_model/leia_model_final"),
]

# Les données de Leia (même logique que load_leia_corpus())
_DATA_CANDIDATES = [
    _HERE.parent / "data",
    _HERE.parent.parent / "data",
    _HERE / "data",
    Path("./data"),
]

# Taille maximale de l'index sémantique (fragments encodés)
_INDEX_MAX = 2000

# Seuil de similarité cosinus en-dessous duquel on ignore un fragment
_COSINE_THRESHOLD = 0.32

# Nombre de fragments les plus proches à injecter dans le workspace
_TOP_K = 6

# Stopwords français — mots à exclure de l'extraction de concepts
_STOPWORDS = frozenset({
    "le","la","les","de","du","des","un","une","et","en","que","qui","est","il",
    "elle","ils","elles","nous","vous","je","tu","se","sa","son","ses","ce","ces",
    "au","aux","par","sur","sous","dans","avec","pour","pas","ne","plus","ou","si",
    "mais","donc","or","ni","car","être","avoir","faire","dire","aller","voir",
    "vouloir","pouvoir","falloir","même","tout","très","aussi","comme","dont",
    "car","quand","alors","bien","mais","non","oui","là","ici","leur","leurs",
    "mon","ton","notre","votre","me","te","lui","leur","ont","avait","était",
    "sont","cette","cet","ça","on","y","en","ai","as","ont","eu","été","fait",
})


# ─────────────────────────────────────────────────────────────────────────────
# 1. IMPORT DU TRANSFORMER (facultatif)
# ─────────────────────────────────────────────────────────────────────────────

try:
    # Ajoute le chemin du transformer si nécessaire
    _tf_candidates = [
        _HERE,
        _HERE.parent,
        _HERE.parent.parent,
        Path("."),
    ]
    for _p in _tf_candidates:
        _tf_path = str(_p)
        if _tf_path not in sys.path:
            sys.path.insert(0, _tf_path)

    from leia_mini_transformer import (
        Params as _TFParams,
        LeiaTokenizer as _TFTokenizer,
        encode_sentence as _tf_encode,
        tokenize as _tf_tokenize,
        MAX_SEQ as _TF_MAX_SEQ,
    )
    _TF_AVAILABLE = True
except ImportError:
    _TF_AVAILABLE = False
    _TFParams = None
    _TFTokenizer = None

try:
    import numpy as np
    _NP_AVAILABLE = True
except ImportError:
    _NP_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# 2. UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────

def _cosine(a, b) -> float:
    """Similarité cosinus entre deux vecteurs numpy."""
    if not _NP_AVAILABLE:
        return 0.0
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _extraire_concepts(texte: str, n: int = 6) -> List[str]:
    """
    Extrait les N mots porteurs de sens depuis un texte court.
    Filtre les stopwords, garde les mots ≥ 4 lettres.
    """
    mots = re.findall(r"[a-zàâäéèêëïîôùûüç']+", texte.lower())
    concepts = [
        m for m in mots
        if len(m) >= 4 and m not in _STOPWORDS
    ]
    # Dédoublonner en conservant l'ordre
    vus = set()
    result = []
    for c in concepts:
        if c not in vus:
            vus.add(c)
            result.append(c)
        if len(result) >= n:
            break
    return result


def _trouver_model_path() -> Optional[Path]:
    """Trouve le chemin du modèle parmi les candidats."""
    for p in _MODEL_CANDIDATES:
        if (Path(str(p) + ".npz")).exists():
            return p
    return None


def _trouver_data_dir() -> Optional[Path]:
    """Trouve le dossier data parmi les candidats."""
    for p in _DATA_CANDIDATES:
        if p.exists() and p.is_dir():
            return p
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. CHARGEMENT DU CORPUS POUR L'INDEX
# ─────────────────────────────────────────────────────────────────────────────

def _charger_corpus_index(data_dir: Path, max_items: int = _INDEX_MAX) -> List[str]:
    """
    Charge un sous-ensemble du corpus de Leia pour construire l'index.
    Mêmes sources que load_leia_corpus() dans leia_mini_transformer.py.
    Limite à max_items pour la vitesse.
    """
    textes = []

    # causal_memory : fragments de livres
    cm = data_dir / "causal_memory.json"
    if cm.exists():
        try:
            with open(cm, encoding="utf-8") as f:
                data = json.load(f)
            for v in data.values():
                event = v.get("event", "")
                m = re.search(r"fragment \d+:\s*(.+)", event, re.DOTALL)
                if m:
                    textes.append(m.group(1).strip()[:200])
        except Exception:
            pass

    # digested_neurons
    dn = data_dir / "digestion_memory_interface" / "digested_neurons.json"
    if dn.exists():
        try:
            with open(dn, encoding="utf-8") as f:
                neurons = json.load(f)
            items = neurons if isinstance(neurons, list) else list(neurons.values())
            for n in items:
                content = str(n.get("content", "") or n.get("text", "")).strip()
                if len(content) > 15:
                    textes.append(content[:200])
        except Exception:
            pass

    # semantic_plasticity : paires de concepts
    sp = data_dir / "semantic_plasticity_interface.json"
    if sp.exists():
        try:
            with open(sp, encoding="utf-8") as f:
                data = json.load(f)
            graph = data.get("graph", {})
            for word, neighbors in graph.items():
                if isinstance(neighbors, dict):
                    for neighbor in list(neighbors)[:3]:
                        textes.append(f"{word} {neighbor}")
        except Exception:
            pass

    # opinions et raisonnements
    for fname in ["opinions_interface.json", "reasoning_trace_interface.json"]:
        p = data_dir / fname
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                _extraire_strings_recursif(data, textes, profondeur=3)
            except Exception:
                pass

    # Nettoyer + déduplication légère + limiter
    vus = set()
    propres = []
    for t in textes:
        t = str(t).strip()
        cle = t[:40]  # clé de dédup approximative
        if len(t) >= 10 and cle not in vus:
            vus.add(cle)
            propres.append(t)
        if len(propres) >= max_items:
            break

    return propres


def _extraire_strings_recursif(obj, out: list, profondeur: int = 3) -> None:
    """Extraction récursive de chaînes depuis JSON."""
    if profondeur <= 0:
        return
    if isinstance(obj, str) and len(obj) > 10:
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _extraire_strings_recursif(v, out, profondeur - 1)
    elif isinstance(obj, list):
        for item in obj[:100]:
            _extraire_strings_recursif(item, out, profondeur - 1)


# ─────────────────────────────────────────────────────────────────────────────
# 4. INDEX SÉMANTIQUE
# ─────────────────────────────────────────────────────────────────────────────

class IndexSemantique:
    """
    Index plat de vecteurs sémantiques.
    Recherche par cosinus (O(n) — suffisant pour ≤ 2000 fragments sur CPU).

    Supporte :
      - construire()   : encodage initial du corpus
      - ajouter()      : ajout dynamique d'un fragment appris
      - renforcer()    : amplification des fragments fréquemment activés
      - hits           : compteur de résonances par fragment (consolidation)
    """

    def __init__(self):
        self.textes: List[str] = []
        self.vecteurs = None       # np.ndarray (N, dim)
        self._poids   = None       # np.ndarray (N,) — poids de consolidation
        self._hits: Dict[int, int] = {}
        self._pret = False
        self._poids = None         # np.ndarray (N,) — poids de consolidation
        self._hits: Dict[int, int] = {}   # indice → nb de fois activé
        self._pret = False

    @property
    def pret(self) -> bool:
        return self._pret and self.vecteurs is not None and len(self.textes) > 0

    def construire(self, textes: List[str], params, tokenizer,
                   max_seq: int = 64) -> None:
        """Encode tous les textes et stocke les vecteurs."""
        if not _NP_AVAILABLE or not textes:
            return

        vecs = []
        skipped = 0
        for texte in textes:
            try:
                tokens = _tf_tokenize(texte)
                if len(tokens) < 2:
                    skipped += 1
                    continue
                ids = tokenizer.encode(" ".join(tokens), max_seq)
                if len(ids) < 2:
                    skipped += 1
                    continue
                vec = _tf_encode(params, ids)
                vecs.append(vec)
                self.textes.append(texte)
            except Exception:
                skipped += 1
                continue

        if vecs:
            self.vecteurs = np.stack(vecs).astype(np.float32)
            self._poids   = np.ones(len(self.textes), dtype=np.float32)
            self._pret    = True


    def ajouter(self, vecteur, texte: str, dedup_seuil: float = 0.92) -> bool:
        """
        Ajoute un nouveau fragment à l'index dynamiquement.
        Déduplique si un fragment très proche existe déjà (cosinus > dedup_seuil).
        Retourne True si l'ajout a eu lieu, False si dédup ou erreur.
        """
        if not _NP_AVAILABLE or not self._pret:
            return False
        if not texte or len(texte.strip()) < 6:
            return False
        try:
            vec = np.array(vecteur, dtype=np.float32)
            norme_v = float(np.linalg.norm(vec))
            if norme_v < 1e-9:
                return False
            normes = np.linalg.norm(self.vecteurs, axis=1)
            normes = np.where(normes < 1e-9, 1e-9, normes)
            scores = self.vecteurs @ vec / (normes * norme_v)
            best_idx = int(np.argmax(scores))
            if float(scores[best_idx]) >= dedup_seuil:
                # Quasi-identique : renforcer l'existant légèrement
                self.renforcer([best_idx], facteur=1.04)
                return False
            # Vrai ajout
            self.vecteurs = np.vstack([self.vecteurs, vec[np.newaxis, :]])
            self.textes.append(texte.strip()[:200])
            self._poids = np.append(self._poids, 1.0)
            return True
        except Exception:
            return False

    def renforcer(self, indices: List[int], facteur: float = 1.08) -> None:
        """
        Amplifie le poids des fragments aux indices donnés.
        La recherche pondère les scores par self._poids,
        donc un fragment renforcé revient plus souvent en surface.
        Facteur typique : 1.05–1.15. Plafonné à 3.0.
        """
        if self._poids is None:
            return
        facteur = max(1.0, min(facteur, 1.3))
        for i in indices:
            if 0 <= i < len(self._poids):
                self._poids[i] = min(self._poids[i] * facteur, 3.0)

    def enregistrer_hit(self, indice: int) -> None:
        """Incrémente le compteur de résonances pour un fragment."""
        self._hits[indice] = self._hits.get(indice, 0) + 1

    def fragments_frequents(self, seuil_hits: int = 3,
                            n: int = 10) -> List[Tuple[int, int]]:
        """
        Retourne les (indice, nb_hits) des fragments les plus activés.
        Utilisé par consolider() pour le renforcement ciblé.
        """
        candidats = [(i, h) for i, h in self._hits.items() if h >= seuil_hits]
        return sorted(candidats, key=lambda x: -x[1])[:n]

    def sauvegarder(self, chemin: Path) -> None:
        """Sauvegarde l'index sur disque (vecteurs + poids + textes + hits)."""
        if not self.pret:
            return
        try:
            chemin.parent.mkdir(parents=True, exist_ok=True)
            save_data = {"vecteurs": self.vecteurs}
            if self._poids is not None:
                save_data["poids"] = self._poids
            np.savez_compressed(str(chemin), **save_data)
            with open(str(chemin) + "_textes.pkl", "wb") as f:
                pickle.dump({"textes": self.textes, "hits": self._hits}, f)
        except Exception:
            pass

    def charger(self, chemin: Path) -> bool:
        """Charge l'index depuis disque. Retourne True si succès."""
        if not _NP_AVAILABLE:
            return False
        npz = Path(str(chemin) + ".npz")
        pkl = Path(str(chemin) + "_textes.pkl")
        if not npz.exists() or not pkl.exists():
            return False
        try:
            data = np.load(str(npz))
            self.vecteurs = data["vecteurs"]
            self._poids = (
                data["poids"].copy()
                if "poids" in data
                else np.ones(len(self.vecteurs), dtype=np.float32)
            )
            with open(str(pkl), "rb") as f:
                saved = pickle.load(f)
            if isinstance(saved, dict):
                self.textes = saved.get("textes", [])
                self._hits  = saved.get("hits", {})
            else:
                # Rétrocompatibilité avec l'ancien format (liste)
                self.textes = saved
                self._hits  = {}
            self._pret = len(self.textes) > 0
            return self._pret
        except Exception:
            return False

    def chercher(self, vecteur_requete, top_k: int = _TOP_K,
                 seuil: float = _COSINE_THRESHOLD) -> List[Tuple[str, float]]:
        """
        Retourne les top_k fragments les plus proches au-dessus du seuil.
        Résultats : [(texte, score_cosinus), ...]
        """
        if not self.pret or not _NP_AVAILABLE:
            return []
        try:
            # Cosinus vectorisé (rapide même pour 2000 vecteurs)
            norme_q = float(np.linalg.norm(vecteur_requete))
            if norme_q < 1e-9:
                return []
            normes = np.linalg.norm(self.vecteurs, axis=1)
            normes = np.where(normes < 1e-9, 1e-9, normes)
            raw_scores = self.vecteurs @ vecteur_requete / (normes * norme_q)
            # Pondération par les poids de consolidation
            if self._poids is not None and len(self._poids) == len(raw_scores):
                scores = raw_scores * self._poids
            else:
                scores = raw_scores

            # Top-K au-dessus du seuil
            indices = np.argsort(scores)[::-1]
            resultats = []
            for i in indices[:top_k * 2]:
                score = float(scores[i])
                if score < seuil:
                    break
                resultats.append((self.textes[i], score))
                self.enregistrer_hit(int(i))
                if len(resultats) >= top_k:
                    break
            return resultats
        except Exception:
            return []


# ─────────────────────────────────────────────────────────────────────────────
# 5. BRIDGE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class LeiaTransformerBridge:
    """
    Pont entre leia_mini_transformer et GlobalWorkspace.

    Usage dans LeiaLivingCore.__init__() :
        from leia_transformer_bridge import LeiaTransformerBridge
        self.transformer_bridge = LeiaTransformerBridge()

    Usage dans LeiaLivingCore.respond() après le cortex :
        self.transformer_bridge.enrichir_workspace(user_message, self.workspace)

    Si le modèle n'est pas encore entraîné, le bridge reste silencieux.
    """

    def __init__(self, model_dir: Optional[Path] = None,
                 data_dir: Optional[Path] = None):
        self._pret = False
        self._params = None
        self._tokenizer = None
        self._index = IndexSemantique()
        self._n_enrichissements = 0
        self._t_init = time.time()

        if not _TF_AVAILABLE or not _NP_AVAILABLE:
            return

        # Trouver le modèle
        model_path = model_dir or _trouver_model_path()
        if model_path is None:
            return  # Modèle pas encore entraîné — silence total

        # Charger le tokenizer
        tok_path = Path(str(model_path).replace("leia_model_final", "tokenizer.pkl"))
        if not tok_path.parent.exists():
            tok_path = model_path.parent / "tokenizer.pkl"
        if not tok_path.exists():
            return

        try:
            self._tokenizer = _TFTokenizer.load(tok_path)
        except Exception:
            return

        # Charger les poids
        try:
            self._params = _TFParams.load(model_path, len(self._tokenizer.word2id))
        except Exception:
            return

        # Charger ou construire l'index
        index_path = model_path.parent / "semantic_index"
        if not self._index.charger(index_path):
            # Construire l'index depuis le corpus
            data_path = data_dir or _trouver_data_dir()
            if data_path is not None:
                corpus = _charger_corpus_index(data_path, _INDEX_MAX)
                if corpus:
                    self._index.construire(
                        corpus, self._params, self._tokenizer, _TF_MAX_SEQ
                    )
                    self._index.sauvegarder(index_path)

        if self._index.pret:
            self._pret = True

        self._index_path: Optional[Path] = (
            (model_path.parent / "semantic_index") if model_path else None
        )
        self._n_appris = 0
        self._save_threshold = 10   # sauvegarder tous les N apprentissages

    @property
    def pret(self) -> bool:
        return self._pret

    def etat(self) -> Dict:
        """Snapshot pour diagnostics / snapshot() du core."""
        freq = self._index.fragments_frequents(seuil_hits=3, n=3) if self._index.pret else []
        return {
            "disponible": self._pret,
            "tf_importé": _TF_AVAILABLE,
            "numpy_disponible": _NP_AVAILABLE,
            "n_fragments_indexés": len(self._index.textes) if self._index.pret else 0,
            "n_enrichissements": self._n_enrichissements,
            "n_appris": self._n_appris,
            "fragments_consolidés": len(freq),
        }

    # ── API PRINCIPALE ────────────────────────────────────────────────────

    def enrichir_workspace(self, texte: str, workspace,
                           top_k: int = _TOP_K,
                           seuil: float = _COSINE_THRESHOLD) -> bool:
        """
        Encode `texte`, trouve les fragments les plus proches dans l'index,
        injecte leurs concepts dans le workspace comme signal de résonance.

        Retourne True si au moins un fragment a été injecté.
        """
        if not self._pret or not texte or not texte.strip():
            return False

        try:
            # ── Encoder le message ────────────────────────────────────────
            tokens = _tf_tokenize(texte)
            if len(tokens) < 2:
                return False
            ids = self._tokenizer.encode(" ".join(tokens), _TF_MAX_SEQ)
            if len(ids) < 2:
                return False
            vecteur = _tf_encode(self._params, ids)

            # ── Chercher les fragments proches ────────────────────────────
            resultats = self._index.chercher(vecteur, top_k=top_k, seuil=seuil)
            if not resultats:
                return False

            # ── Injecter dans le workspace ────────────────────────────────
            injectes = 0
            for fragment, score in resultats:
                concepts = _extraire_concepts(fragment, n=6)
                if not concepts:
                    continue

                # Intensité proportionnelle au score cosinus
                # (score entre seuil et 1.0 → intensité entre 0.2 et 0.7)
                intensite = 0.2 + (score - seuil) / (1.0 - seuil + 1e-6) * 0.5
                intensite = max(0.2, min(0.7, intensite))

                # Valence émotionnelle neutre (le workspace décidera)
                workspace.inject_memoire(
                    concepts=concepts,
                    intensite=intensite,
                    ton_emotionnel=0.0,
                )
                injectes += 1

            if injectes > 0:
                self._n_enrichissements += 1
                return True
            return False

        except Exception:
            return False

    def vecteur(self, texte: str):
        """
        Retourne le vecteur sémantique de `texte` (numpy array dim=128).
        Utile pour la mémoire vectorielle directe.
        Retourne None si le bridge n'est pas prêt.
        """
        if not self._pret:
            return None
        try:
            tokens = _tf_tokenize(texte)
            if len(tokens) < 2:
                return None
            ids = self._tokenizer.encode(" ".join(tokens), _TF_MAX_SEQ)
            if len(ids) < 2:
                return None
            return _tf_encode(self._params, ids)
        except Exception:
            return None

    def apprendre(self, texte: str, source: str = "expression") -> bool:
        """
        Apprend un nouveau fragment depuis l'expérience de Leia.

        Appelé après chaque expression de Leia (post-respond) pour que
        ce qu'elle vient de dire entre dans sa mémoire vectorielle.
        Appelé aussi pour consolider des passages lus ou pensées importantes.

        Déduplique automatiquement si trop proche d'un souvenir existant.
        Sauvegarde l'index périodiquement (tous les _save_threshold appris).

        Args:
            texte   : texte à apprendre (réponse de Leia, passage, pensée)
            source  : origine ("expression", "lecture", "pensée")

        Retourne True si le fragment est réellement ajouté (pas dédupliqué).
        """
        if not self._pret or not texte or len(texte.strip()) < 8:
            return False

        try:
            tokens = _tf_tokenize(texte)
            if len(tokens) < 2:
                return False
            ids = self._tokenizer.encode(" ".join(tokens), _TF_MAX_SEQ)
            if len(ids) < 2:
                return False
            vecteur = _tf_encode(self._params, ids)

            ajoute = self._index.ajouter(vecteur, texte)
            if ajoute:
                self._n_appris += 1
                self._sauvegarder_si_necessaire()
            return ajoute

        except Exception:
            return False

    def consolider(self, workspace=None) -> Dict:
        """
        Consolide les souvenirs les plus fréquemment activés.

        Logique :
          1. Récupère les fragments ayant eu ≥ 3 résonances
          2. Les renforce dans l'index (poids + 8%)
          3. Si workspace fourni : injecte leurs concepts avec forte intensité
             (comme un souvenir qui "remonte" spontanément)

        À appeler periodiquement (par exemple depuis tick_inner_life).

        Retourne un dict de statut pour diagnostics.
        """
        if not self._pret:
            return {"consolidés": 0, "raison": "bridge non prêt"}

        try:
            frequents = self._index.fragments_frequents(seuil_hits=3, n=8)
            if not frequents:
                return {"consolidés": 0, "raison": "pas assez de résonances"}

            indices = [i for i, _ in frequents]
            self._index.renforcer(indices, facteur=1.08)

            # Injection workspace optionnelle (souvenir qui remonte)
            if workspace is not None:
                for indice, hits in frequents[:3]:
                    fragment = self._index.textes[indice]
                    concepts = _extraire_concepts(fragment, n=5)
                    if concepts:
                        intensite = min(0.75, 0.4 + hits * 0.05)
                        workspace.inject_memoire(
                            concepts=concepts,
                            intensite=intensite,
                            ton_emotionnel=0.0,
                        )

            # Réinitialiser les hits après consolidation
            # (on garde seulement un historique partiel)
            for i, _ in frequents:
                self._index._hits[i] = max(0, self._index._hits.get(i, 0) - 2)

            self._sauvegarder_si_necessaire(force=True)
            return {"consolidés": len(indices), "fragments": [self._index.textes[i][:50] for i in indices[:3]]}

        except Exception:
            return {"consolidés": 0, "raison": "erreur"}

    def _sauvegarder_si_necessaire(self, force: bool = False) -> None:
        """Sauvegarde l'index si le seuil d'apprentissages est atteint."""
        if self._index_path is None or not self._index.pret:
            return
        if force or (self._n_appris > 0 and self._n_appris % self._save_threshold == 0):
            try:
                self._index.sauvegarder(self._index_path)
            except Exception:
                pass

    def similaires(self, texte: str, n: int = 5) -> List[Tuple[str, float]]:
        """
        Retourne les n fragments les plus proches de `texte`.
        API publique pour la recherche de mémoire sémantique directe.
        """
        if not self._pret:
            return []
        vec = self.vecteur(texte)
        if vec is None:
            return []
        return self._index.chercher(vec, top_k=n, seuil=_COSINE_THRESHOLD)


# ─────────────────────────────────────────────────────────────────────────────
# 6. SINGLETON (comme workspace dans global_workspace_v2.py)
# ─────────────────────────────────────────────────────────────────────────────

transformer_bridge = LeiaTransformerBridge()
