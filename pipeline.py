#!/usr/bin/env python3
"""
Pipeline IPC/HCP — Point d'entrée unique.

Usage:
  python3 pipeline.py                 # Exécute toutes les étapes (saute celles déjà complètes)
  python3 pipeline.py --force         # Force la réexécution de toutes les étapes
  python3 pipeline.py --step 2 3      # Exécute uniquement les étapes 2 et 3

Étapes :
  1 - Scraping       : Récupère les URLs des rapports HCP → hcp_ipc_reports_2010_2025.csv
  2 - Extraction     : Extrait les liens PDF/DOCX depuis chaque page → hcp_ipc_pdfs.csv
  3 - Téléchargement : Télécharge les documents (FR en priorité) → downloads/
  4 - Parsing        : Extrait les tableaux des documents → extracted_tables/<année>/
"""

import argparse
import sys
import time

from src.scraper import HCPScraper
from src.extractor import PDFLinkExtractor
from src.downloader import Downloader
from src.parser import TableParser


class Pipeline:
    """
    Orchestrateur du pipeline IPC/HCP.
    Chaque étape est idempotente : elle vérifie si elle est déjà complète
    et ne retraite que les éléments manquants.
    """

    STEP_NAMES = {
        1: "Scraping des URLs HCP",
        2: "Extraction des liens documents",
        3: "Téléchargement des fichiers",
        4: "Parsing des tableaux",
    }

    def __init__(self):
        self.scraper = HCPScraper(
            output_csv="hcp_ipc_reports_2010_2025.csv"
        )
        self.extractor = PDFLinkExtractor(
            input_csv="hcp_ipc_reports_2010_2025.csv",
            output_csv="hcp_ipc_pdfs.csv",
        )
        self.downloader = Downloader(
            input_csv="hcp_ipc_pdfs.csv",
            download_dir="downloads",
        )
        self.parser = TableParser(
            download_dir="downloads",
            output_root="extracted_tables",
        )

    def _print_header(self, steps: list[int]):
        print("\n" + "=" * 60)
        print("  🚀 PIPELINE IPC/HCP — HautCommissariat au Plan Maroc")
        print("=" * 60)
        print(f"  Étapes sélectionnées : {steps}")
        print("=" * 60)

    def _print_footer(self, start: float, results: dict):
        elapsed = time.time() - start
        print("\n" + "=" * 60)
        print("  📋 RÉSUMÉ DU PIPELINE")
        print("=" * 60)
        for step_num, status in results.items():
            icon = "✅" if status == "ok" else "⚠️ " if status == "warn" else "❌"
            name = self.STEP_NAMES.get(step_num, f"Étape {step_num}")
            print(f"  {icon}  Étape {step_num} — {name}")
        print(f"\n  ⏱️  Durée totale : {elapsed:.1f}s")
        print("=" * 60 + "\n")

    def run_step(self, step_num: int, force: bool = False) -> str:
        """Exécute une étape et retourne son statut ('ok', 'warn', 'error')."""
        steps = {
            1: (self.scraper, "Scraper"),
            2: (self.extractor, "Extractor"),
            3: (self.downloader, "Downloader"),
            4: (self.parser, "Parser"),
        }

        obj, name = steps[step_num]

        try:
            if not force and obj.is_done():
                print(f"\n✅ [Étape {step_num}] {self.STEP_NAMES[step_num]} — déjà complète, ignorée.")
                return "ok"

            obj.run()

            # Vérification post-exécution
            if obj.is_done():
                return "ok"
            else:
                print(f"  ⚠️  Étape {step_num} terminée mais certains éléments sont encore manquants.")
                return "warn"

        except Exception as e:
            print(f"  ❌ Étape {step_num} a échoué : {e}")
            return "error"

    def run(self, steps: list[int] = None, force: bool = False):
        """Lance le pipeline pour les étapes spécifiées (toutes par défaut)."""
        if steps is None:
            steps = [1, 2, 3, 4]

        start = time.time()
        self._print_header(steps)

        results = {}
        for step in steps:
            if step not in self.STEP_NAMES:
                print(f"  ⚠️  Étape inconnue : {step}, ignorée.")
                continue
            status = self.run_step(step, force=force)
            results[step] = status

            # Si une étape critique échoue, on arrête le pipeline
            if status == "error":
                print(f"\n  ❌ Pipeline interrompu à l'étape {step}.")
                break

        self._print_footer(start, results)


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline IPC/HCP — Exécution automatisée et idempotente."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force la réexécution de toutes les étapes sélectionnées.",
    )
    parser.add_argument(
        "--step",
        nargs="+",
        type=int,
        metavar="N",
        help="Exécute uniquement les étapes spécifiées (ex: --step 2 3).",
    )

    args = parser.parse_args()
    steps = args.step if args.step else None

    pipeline = Pipeline()
    pipeline.run(steps=steps, force=args.force)


if __name__ == "__main__":
    main()
