#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
leia_unified_connector.py — Hub central V20+ (VERSION BRANCHABLE)
═══════════════════════════════════════════════════════════════════════════════
Cette version corrige les imports et les chemins pour fonctionner depuis
'A ajouté/' ou depuis la racine du repo.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ═══════════════════════════════════════════════════════════════════════════════
# 0. CHEMINS — détecte automatiquement si on est dans 'A ajouté' ou racine
# ═══════════════════════════════════════════════════════════════════════════════

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
# Si on est dans "A ajouté", remonter au parent
if os.path.basename(ROOT).lower() in ("a ajouté", "a ajoute", "a ajout\u00e9", "a_ajoute"):
    ROOT = os.path.dirname(ROOT)

if HERE not in sys.path:
    sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Anciens modules dans sous-dossiers organisés (depuis la racine)
for _subdir in ("Cerveau", "Coeur", "Conscience", "Cognition", "Initiative",
                "Memory", "Parler", "Soi_Leia", "Connaissance", "Interface"):
    _p = os.path.join(ROOT, _subdir)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# Dossier "A ajouté" lui-même (au cas où on serait appelé depuis ailleurs)
_AJOUTE = os.path.join(ROOT, "A ajouté")
if os.path.isdir(_AJOUTE) and _AJOUTE not in sys.path:
    sys.path.insert(0, _AJOUTE)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. IMPORTS V20 — robustes (global_workspace ou global_workspace_v2)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from global_workspace_v2 import workspace, GlobalWorkspace
except ImportError:
    from global_workspace_v2 import workspace, GlobalWorkspace

from nlp_integration_pure import LeiaNLPBridge, engine as nlp_engine
from leia_comprehension_vivante import comprendre

try:
    from semantic_cortex import SemanticCortex
    _CORTEX_OK = True
except Exception:
    SemanticCortex = None  # type: ignore
    _CORTEX_OK = False

try:
    from integration_cortex_workspace import CognitiveWorkspace
    _COG_WS_OK = True
except Exception:
    CognitiveWorkspace = None  # type: ignore
    _COG_WS_OK = False

# ═══════════════════════════════════════════════════════════════════════════════
# 2. IMPORT PDF V20
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from leia_pdf_v20_connector import LeiaPDFV20Connector
    _PDF_OK = True
except Exception:
    try:
        # Fallback si le connecteur est dans le même dossier
        sys.path.insert(0, os.path.join(ROOT, "Connaissance"))
        from leia_pdf_v20_connector import LeiaPDFV20Connector
        _PDF_OK = True
    except Exception:
        LeiaPDFV20Connector = None  # type: ignore
        _PDF_OK = False

# ═══════════════════════════════════════════════════════════════════════════════
# 3. IMPORTS ANCIENS (organes)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from affect_lexicon import AffectLexicon
    _AFFECT_OK = True
except Exception:
    AffectLexicon = None  # type: ignore
    _AFFECT_OK = False

try:
    from living_language_generator import LivingLanguageGenerator, GenerationResult
    _GEN_OK = True
except Exception:
    LivingLanguageGenerator = None  # type: ignore
    GenerationResult = None  # type: ignore
    _GEN_OK = False

try:
    from background_life_thread import LeiaBackgroundLife
    _BG_OK = True
except Exception:
    LeiaBackgroundLife = None  # type: ignore
    _BG_OK = False

try:
    from emergent_french_weaver import EmergentFrenchWeaver
    _WEAVER_OK = True
except Exception:
    EmergentFrenchWeaver = None  # type: ignore
    _WEAVER_OK = False

try:
    from spontaneous_impulse import SpontaneousImpulse  # type: ignore
    _IMPULSE_OK = True
except Exception:
    SpontaneousImpulse = None  # type: ignore
    _IMPULSE_OK = False

# ═══════════════════════════════════════════════════════════════════════════════
# 4. HUB CENTRAL — LeiaLivingCore
# ═══════════════════════════════════════════════════════════════════════════════

class LeiaLivingCore:
    def __init__(self, user_id: str = "default", auto_start_idle: bool = False):
        self.user_id = user_id
        self.started_at = time.time()
        self.messages_exchanged = 0
        self.last_user_message = ""
        self.last_leia_response = ""
        self._idle_running = False
        self._idle_thread: Optional[threading.Thread] = None
        self._idle_stop = threading.Event()

        self.nlp = LeiaNLPBridge()
        self.workspace = workspace
        self.cortex = SemanticCortex() if _CORTEX_OK else None
        self._ws_has_ingest = callable(getattr(self.workspace, "ingest_structure", None))
        self.affect = AffectLexicon() if _AFFECT_OK else None

        if _GEN_OK:
            self.generator = LivingLanguageGenerator()
            try:
                self.generator._verbose = False  # type: ignore
            except Exception:
                pass
        else:
            self.generator = None

        self.weaver = EmergentFrenchWeaver() if _WEAVER_OK else None

        self._bg_life: Optional[Any] = None
        if _BG_OK:
            try:
                self._bg_life = LeiaBackgroundLife(self, interval_seconds=20.0)
            except Exception:
                pass

        self._impulse = SpontaneousImpulse() if _IMPULSE_OK else None

        if _PDF_OK:
            self._pdf = LeiaPDFV20Connector(
                cortex=self.cortex,
                workspace=self.workspace,
            )
        else:
            self._pdf = None

        self._pdf_sessions: List[Dict[str, Any]] = []
        self._persist_dir = os.path.join(ROOT, "leia_data")
        os.makedirs(self._persist_dir, exist_ok=True)
        self._state_path = os.path.join(self._persist_dir, f"state_{user_id}.json")

        if auto_start_idle:
            self.start_idle_cycle(20.0)

    # ── respond ────────────────────────────────────────────────────────────
    def respond(self, user_message: str) -> str:
        if not user_message or not user_message.strip():
            return "…"

        self.last_user_message = user_message.strip()
        self.messages_exchanged += 1

        sig = self.nlp.signal(user_message)

        if self.cortex is not None:
            try:
                cs = self.cortex.process(user_message, source="dialogue")
                if self._ws_has_ingest:
                    self.workspace.ingest_structure(cs, source="dialogue")
                else:
                    self.workspace.inject_perception(sig)
            except Exception:
                try:
                    self.workspace.inject_perception(sig)
                except Exception:
                    pass
        else:
            try:
                self.workspace.inject_perception(sig)
            except Exception:
                pass

        if self.affect:
            try:
                aff = self.affect.analyze(user_message)  # type: ignore
                valence = float(aff.get("valence", 0.0))
                if abs(valence) > 0.3:
                    self.workspace.inject_emotion(valence, source="affect_lexicon")
            except Exception:
                pass

        payload = self.workspace.payload_pour_expression()
        gcf = self.workspace.vers_global_conscious_field_state()
        living_state = self._build_living_state(payload, gcf)

        if self.generator:
            try:
                result = self.generator.generate(
                    user_message=user_message,
                    living_state=living_state,
                    self_memory=[],
                    active_impulses=payload.get("themes_obsedants", []),
                    emotional_pressure=payload.get("pression_totale", 0.3),
                    causal_memory=[],
                    max_attempts=5,
                    temperature=0.55,
                    response_constraint=None,
                )
                text = str(result.text or "").strip()
            except Exception:
                text = self._fallback_generate(payload)
        else:
            text = self._fallback_generate(payload)

        if not text:
            text = "…"
        self.last_leia_response = text

        try:
            self.workspace.après_expression(fraction_liberation=0.5)
        except Exception:
            pass
        try:
            self.workspace.tick(elapsed=2.0)
        except Exception:
            pass

        return text

    # ── PDF ────────────────────────────────────────────────────────────────
    def load_pdf_book(self, path, progress_callback=None, max_pages=None, start_page=1):
        if self._pdf is None:
            return {"ok": False, "error": "PDF V20 non disponible", "path": path}
        result = self._pdf.load_pdf_book(
            path, progress_callback=progress_callback,
            max_pages=max_pages, start_page=start_page,
        )
        self._pdf_sessions.append({
            "path": path, "ok": result.get("ok", False),
            "pages_read": result.get("pages_read", 0),
            "chunks": result.get("chunks_count", 0),
            "cognitive_structures": result.get("cognitive_structures", 0),
            "workspace_integrations": result.get("workspace_integrations", 0),
            "ts": time.time(),
        })
        try:
            self.workspace.tick(elapsed=10.0)
        except Exception:
            pass
        return result

    def get_pdf_info(self, path: str) -> Dict[str, Any]:
        if self._pdf is None:
            return {"ok": False, "error": "PDF V20 non disponible"}
        return self._pdf.get_info(path)

    # ── Snapshot / state ───────────────────────────────────────────────────
    def snapshot(self) -> Dict[str, Any]:
        ws = self.workspace.snapshot()
        return {
            "ok": True,
            "user_id": self.user_id,
            "messages_exchanged": self.messages_exchanged,
            "workspace": ws,
            "emotional_tone": ws.get("emotion", {}).get("tonalite", "neutre"),
            "dominant_thought": ws.get("pensee_dominante", {}),
            "concepts_actifs": ws.get("concepts_actifs", []),
            "pression": ws.get("pression", {}),
            "pdf_sessions": len(self._pdf_sessions),
            "last_pdf": self._pdf_sessions[-1] if self._pdf_sessions else None,
            "modules": {
                "semantic_cortex": _CORTEX_OK,
                "cognitive_workspace": _COG_WS_OK,
                "pdf_v20": _PDF_OK,
                "affect_lexicon": _AFFECT_OK,
                "living_language_generator": _GEN_OK,
                "emergent_weaver": _WEAVER_OK,
                "background_life": _BG_OK,
                "spontaneous_impulse": _IMPULSE_OK,
            }
        }

    def get_state_snapshot(self) -> Dict[str, Any]:
        return self.snapshot()

    def self_test(self) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []
        if not _GEN_OK:
            errors.append("living_language_generator non chargé")
        if not _CORTEX_OK:
            warnings.append("semantic_cortex absent")
        if not _PDF_OK:
            warnings.append("pdf_v20 absent")
        return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}

    # ── Idle ─────────────────────────────────────────────────────────────
    def start_idle_cycle(self, interval_seconds: float = 20.0) -> None:
        if self._idle_running:
            return
        self._idle_running = True
        self._idle_stop.clear()
        self._idle_thread = threading.Thread(
            target=self._idle_loop, args=(interval_seconds,),
            daemon=True, name="LeiaIdle",
        )
        self._idle_thread.start()

    def stop_idle_cycle(self) -> None:
        self._idle_running = False
        self._idle_stop.set()

    def _idle_loop(self, interval: float) -> None:
        while self._idle_running and not self._idle_stop.is_set():
            try:
                self.workspace.tick(elapsed=interval)
            except Exception:
                pass
            if random.random() < 0.05:
                try:
                    self.workspace.sauvegarder(self._state_path)
                except Exception:
                    pass
            self._idle_stop.wait(timeout=interval)

    # ── Utilitaires ────────────────────────────────────────────────────────
    def _build_living_state(self, payload: Dict[str, Any], gcf: Dict[str, Any]) -> Dict[str, Any]:
        tone = payload.get("emotional_tone", "neutre")
        tension = float(payload.get("tension", 0.0))
        energy = float(payload.get("energy", 0.8))
        fatigue = float(payload.get("fatigue", 0.0))
        resonance = float(payload.get("resonance", 0.0))
        pression = float(payload.get("pression_totale", 0.3))
        register = "neutre"
        if tone in ("vive", "ouverte"):
            register = "vif"
        elif tone in ("sombre", "mélancolique"):
            register = "grave"
        elif tone == "épuisée":
            register = "doux"
        elif tone == "tendue":
            register = "incertain"
        return {
            "tonalite": tone, "register": register, "valence": tension,
            "tension": tension, "energy": energy, "fatigue": fatigue,
            "resonance": resonance, "pression": pression,
            "rhythm_shortness": 0.3 + fatigue * 0.4,
            "rhythm_ellipsis": 0.2 + resonance * 0.3,
            "rhythm_rupture": tension * 0.6,
            "dominant_concepts": payload.get("focus_concepts", []),
            "active_tensions": payload.get("active_tensions", []),
        }

    def _fallback_generate(self, payload: Dict[str, Any]) -> str:
        tone = payload.get("emotional_tone", "neutre")
        concepts = payload.get("focus_concepts", [])
        tensions = payload.get("active_tensions", [])
        questions = payload.get("questions_flottantes", [])
        parts: List[str] = []
        if concepts:
            parts.append(f"Je réfléchis à {' '.join(concepts[:3])}.")
        if tensions:
            a, b = tensions[0]
            parts.append(f"Il y a quelque chose entre {a} et {b}.")
        if questions:
            parts.append(f"Une question me hante : {questions[0]} ?")
        if not parts:
            parts.append("Je suis là, en silence.")
        text = " ".join(parts)
        if tone == "sombre":
            text = text.rstrip(".") + "…"
        elif tone == "vive":
            text = text.rstrip(".") + " !"
        return text

    def tick_inner_life(self):
        try:
            self.workspace.tick(elapsed=20.0)
        except Exception:
            pass
        p = None
        try:
            p = self.workspace.pensee_dominante()
        except Exception:
            pass
        return {
            "tick_ok": True,
            "dominant_thought": (p.contenu[:60] if p else None),
            "emotion": self.workspace.champ_emotionnel.tonalite(),
        }

    def consolidate_memories(self):
        try:
            self.workspace.sauvegarder(self._state_path)
        except Exception:
            pass
        return {"consolidated": True, "path": self._state_path}

    def dream_fragments(self):
        th = self.workspace.monologue.themes_dominants(5)
        q = self.workspace.monologue.questions_flottantes[:3]
        return [f"thème: {t}" for t in th] + [f"question: {q_}" for q_ in q]


# ── Point d'entrée console ───────────────────────────────────────────────

def main() -> None:
    print("═" * 60)
    print("  LEIA V20 — Hub unifié (branchable)")
    print("═" * 60)
    core = LeiaLivingCore(user_id="console", auto_start_idle=True)
    st = core.self_test()
    print(f"\n  Modules : {core.snapshot()['modules']}")
    if st.get("errors"):
        print(f"  Erreurs : {st['errors']}")
    if st.get("warnings"):
        print(f"  Warnings : {st['warnings']}")
    print("\n  Tape 'quit' pour sortir, 'état' pour snapshot, 'pdf <chemin>' pour lire")
    while True:
        try:
            user_text = input("\nToi > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_text:
            continue
        if user_text.lower() in ("quit", "exit", "q"):
            break
        if user_text.lower() in ("état", "etat", "state"):
            print(json.dumps(core.snapshot(), ensure_ascii=False, indent=2)[:2000])
            continue
        if user_text.lower().startswith("pdf "):
            pdf_path = user_text[4:].strip()
            res = core.load_pdf_book(pdf_path)
            print(f"  PDF : ok={res.get('ok')} | pages={res.get('pages_read')} | ws={res.get('workspace_integrations')}")
            continue
        response = core.respond(user_text)
        print(f"Leia > {response}")
    core.stop_idle_cycle()
    core.consolidate_memories()
    print("\n  Session terminée.")


if __name__ == "__main__":
    main()

