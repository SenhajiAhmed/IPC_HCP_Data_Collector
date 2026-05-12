import csv
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor


class PDFLinkExtractor:
    """
    Étape 2 : Extraction des liens directs vers les documents (PDF/DOCX)
    à partir des pages des rapports HCP.

    Idempotence : Ne re-traite que les URLs du CSV source qui n'ont pas
    encore de liens dans le CSV de sortie.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    def __init__(
        self,
        input_csv: str = "hcp_ipc_reports_2010_2025.csv",
        output_csv: str = "hcp_ipc_pdfs.csv",
        workers: int = 10,
    ):
        self.input_csv = input_csv
        self.output_csv = output_csv
        self.workers = workers

    def _load_source_rows(self) -> list:
        rows = []
        with open(self.input_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("URL", "nan").lower() != "nan":
                    rows.append(row)
        return rows

    def _load_existing_sources(self) -> set:
        """Retourne l'ensemble des Source_URL déjà présentes dans le CSV de sortie."""
        done = set()
        try:
            with open(self.output_csv, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    done.add(row.get("Source_URL", ""))
        except FileNotFoundError:
            pass
        return done

    def is_done(self) -> bool:
        """Vérifie que chaque URL valide de l'entrée a ses liens dans la sortie."""
        rows = self._load_source_rows()
        done = self._load_existing_sources()
        missing = [r for r in rows if r["URL"] not in done]
        if missing:
            print(f"  [Extractor] {len(missing)} page(s) sans liens extraits.")
            return False
        return True

    def _fetch_links(self, row: dict) -> list:
        url = row["URL"]
        annee = row["Année"]
        mois = row["Mois"]
        results = []
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a", class_="pj")
            if not links:
                div = soup.find("div", class_="pj")
                if div:
                    links = div.find_all("a")
            for link in links:
                href = link.get("href", "")
                if href.startswith("/"):
                    href = "https://www.hcp.ma" + href
                if href:
                    results.append({
                        "Année": annee,
                        "Mois": mois,
                        "Source_URL": url,
                        "PDF_Title": link.get_text(strip=True),
                        "PDF_URL": href,
                    })
        except Exception as e:
            print(f"    [!] Erreur fetch {url}: {e}")
        return results

    def run(self):
        """Extrait les liens pour les pages non encore traitées."""
        print("\n🔗 [Étape 2] Extraction des liens de documents...")
        all_rows = self._load_source_rows()
        done_sources = self._load_existing_sources()

        to_process = [r for r in all_rows if r["URL"] not in done_sources]
        if not to_process:
            print("  ✅ Tous les liens déjà extraits. Étape sautée.")
            return

        print(f"  🔄 {len(to_process)} page(s) à traiter...")
        new_results = []
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            for links in executor.map(self._fetch_links, to_process):
                new_results.extend(links)

        # Append au fichier existant (ou création si absent)
        file_exists = os.path.exists(self.output_csv)
        with open(self.output_csv, "a", newline="", encoding="utf-8") as f:
            fieldnames = ["Année", "Mois", "Source_URL", "PDF_Title", "PDF_URL"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_results)

        print(f"  💾 {len(new_results)} lien(s) ajouté(s) dans {self.output_csv}")
