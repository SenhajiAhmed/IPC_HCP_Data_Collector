import csv
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


class Downloader:
    """
    Étape 3 : Téléchargement des documents (FR en priorité, sinon AR).

    Idempotence : Vérifie l'existence du fichier sur disque avant chaque
    téléchargement. Détecte automatiquement le vrai format du fichier
    (PDF, DOCX, DOC, RTF) via les magic bytes.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    MAGIC = {
        b"%PDF": ".pdf",
        b"PK\x03\x04": ".docx",
        b"\xd0\xcf\x11\xe0": ".doc",
        b"{\\rtf": ".rtf",
    }

    def __init__(
        self,
        input_csv: str = "hcp_ipc_pdfs.csv",
        download_dir: str = "downloads",
        workers: int = 5,
    ):
        self.input_csv = input_csv
        self.download_dir = download_dir
        self.workers = workers
        os.makedirs(download_dir, exist_ok=True)

    def _is_fr(self, title: str) -> bool:
        return bool(re.search(r"(?i)(_fr\b|\bfr\b|français|francais)", title))

    def _is_ar(self, title: str) -> bool:
        return bool(re.search(r"(?i)(_ar\b|\bar\b|arabe)", title))

    def _detect_extension(self, chunk: bytes) -> str | None:
        for magic, ext in self.MAGIC.items():
            if chunk.startswith(magic):
                return ext
        if b"<html" in chunk.lower() or b"<!doct" in chunk.lower():
            return None  # Page d'erreur HTML
        return ".bin"  # Format inconnu

    def _build_base_filename(self, item: dict) -> str:
        title = re.sub(r"[\\/*?:\"<>|]", "", item["PDF_Title"]).strip()
        title = re.sub(r"(?i)\.(pdf|docx?|zip|rtf)$", "", title)
        return f"{item['Année']}_{item['Mois']}_{title}"

    def _find_existing_file(self, base: str) -> str | None:
        """Cherche si un fichier avec ce base name (toute extension) existe déjà."""
        for f in os.listdir(self.download_dir):
            name_no_ext = os.path.splitext(f)[0]
            if name_no_ext == base:
                return os.path.join(self.download_dir, f)
        return None

    def _select_items(self) -> list:
        """Sélectionne un item par (Année, Mois) : FR > AR > autre."""
        groups: dict[tuple, dict] = {}
        with open(self.input_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (row["Année"], row["Mois"])
                title = row["PDF_Title"]
                current = groups.get(key)
                # Priorité : FR > AR > autre
                if self._is_fr(title):
                    groups[key] = row
                elif self._is_ar(title) and (current is None or not self._is_fr(current["PDF_Title"])):
                    groups[key] = row
                elif current is None:
                    groups[key] = row
        return list(groups.values())

    def is_done(self) -> bool:
        """Vérifie qu'un fichier existe pour chaque (Année, Mois) sélectionné."""
        items = self._select_items()
        missing = [i for i in items if self._find_existing_file(self._build_base_filename(i)) is None]
        if missing:
            print(f"  [Downloader] {len(missing)} fichier(s) manquant(s).")
            return False
        return True

    def _download_file(self, item: dict):
        base = self._build_base_filename(item)
        if self._find_existing_file(base) is not None:
            return f"  ⏭️  Déjà présent : {base}"

        try:
            resp = requests.get(item["PDF_URL"], headers=self.HEADERS, stream=True, timeout=20)
            resp.raise_for_status()

            iterator = resp.iter_content(chunk_size=8192)
            first_chunk = next(iterator, b"")
            ext = self._detect_extension(first_chunk)

            if ext is None:
                return f"  ⚠️  Page HTML ignorée : {item['PDF_URL']}"

            filepath = os.path.join(self.download_dir, base + ext)
            with open(filepath, "wb") as f:
                f.write(first_chunk)
                for chunk in iterator:
                    f.write(chunk)
            return f"  ✅ Téléchargé : {base + ext}"

        except Exception as e:
            return f"  ❌ Échec ({item['PDF_URL']}): {e}"

    def run(self):
        """Télécharge uniquement les fichiers manquants."""
        print("\n📥 [Étape 3] Téléchargement des documents...")
        items = self._select_items()
        missing = [i for i in items if self._find_existing_file(self._build_base_filename(i)) is None]

        if not missing:
            print("  ✅ Tous les fichiers déjà téléchargés. Étape sautée.")
            return

        print(f"  🔄 {len(missing)} fichier(s) à télécharger...")
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self._download_file, item): item for item in missing}
            for future in as_completed(futures):
                print(future.result())

        print(f"  💾 Fichiers dans {self.download_dir}/")
