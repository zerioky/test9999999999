#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pdf_knowledge_engine import LeiaPDFKnowledgeEngine

def log(message: str) -> None:
    print(message, flush=True)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_reading.py '/chemin/livre.pdf' [max_pages]", flush=True)
        raise SystemExit(1)

    pdf_path = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) >= 3 else 3

    engine = LeiaPDFKnowledgeEngine(progress_callback=log)
    result = engine.read_pdf(pdf_path, max_pages=max_pages)
    print("\nRESULTAT:")
    print(result)
