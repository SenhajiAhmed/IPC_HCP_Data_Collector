import os
import re
import subprocess
import tempfile
import threading

import pandas as pd
import pdfplumber
from docx import Document


class TableParser:
    """
    Étape 4 : Extraction des tableaux depuis les documents téléchargés.
    Supporte PDF, DOCX, DOC et RTF.

    Idempotence : Pour chaque fichier dans downloads/, vérifie si au moins
    un CSV correspondant existe dans extracted_tables/<année>/. Si oui, skip.
    """

    LIBREOFFICE_TIMEOUT = 90   # Secondes max pour la conversion LibreOffice
    EXTRACT_TIMEOUT = 60       # Secondes max pour l'extraction des tableaux d'un fichier

    def __init__(
        self,
        download_dir: str = "downloads",
        output_root: str = "extracted_tables",
    ):
        self.download_dir = download_dir
        self.output_root = output_root
        os.makedirs(output_root, exist_ok=True)

    def _parse_year(self, filename: str) -> str:
        m = re.match(r"^(\d{4})_", filename)
        return m.group(1) if m else "Inconnu"

    def _parse_month(self, filename: str) -> str:
        m = re.search(r"^\d{4}_(.*?)(?:_|$)", filename)
        return m.group(1) if m else "MoisInconnu"

    def _output_prefix(self, filename: str, idx: int) -> str:
        year = self._parse_year(filename)
        month = self._parse_month(filename)
        safe_name = re.sub(r'[\\/*?:"<>|]', "", filename)
        return os.path.join(self.output_root, year, f"{month}_{idx}_{safe_name}.csv")

    def _is_file_done(self, filename: str) -> bool:
        """Vérifie si au moins un CSV pour ce fichier existe dans le dossier année."""
        year = self._parse_year(filename)
        month = self._parse_month(filename)
        year_dir = os.path.join(self.output_root, year)
        if not os.path.isdir(year_dir):
            return False
        safe_name = re.sub(r'[\\/*?:"<>|]', "", filename)
        for f in os.listdir(year_dir):
            if f.startswith(month) and safe_name in f:
                return True
        return False

    def is_done(self) -> bool:
        """Vérifie que tous les fichiers de downloads/ ont leurs tableaux extraits."""
        if not os.path.isdir(self.download_dir):
            return False
        files = [f for f in os.listdir(self.download_dir) if os.path.isfile(os.path.join(self.download_dir, f))]
        missing = [f for f in files if not self._is_file_done(f)]
        if missing:
            print(f"  [Parser] {len(missing)} fichier(s) sans tableaux extraits.")
            return False
        return True

    def _clean_df(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.fillna("")
        df = df.astype(str).map(lambda x: x.split("\n"))
        for idx, row in df.iterrows():
            max_len = max(len(x) for x in row)
            for col in df.columns:
                if len(df.at[idx, col]) < max_len:
                    df.at[idx, col].extend([""] * (max_len - len(df.at[idx, col])))
        df = df.explode(list(df.columns)).reset_index(drop=True)

        if not df.empty:
            cols = [str(c) for c in df.iloc[0]]
            counts: dict = {}
            new_cols = []
            for c in cols:
                counts[c] = counts.get(c, -1) + 1
                new_cols.append(f"{c}_{counts[c]}" if counts[c] > 0 else c)
            df.columns = new_cols
            df = df[1:].reset_index(drop=True)
        return df

    def _is_valid(self, df: pd.DataFrame) -> bool:
        return not df.empty and len(df.columns) >= 2

    def _extract_pdf(self, filepath: str) -> list[pd.DataFrame]:
        tables = []
        try:
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    for tab in page.extract_tables():
                        df = self._clean_df(pd.DataFrame(tab))
                        if self._is_valid(df):
                            tables.append(df)
        except Exception as e:
            print(f"    [!] Erreur PDF: {e}")
        return tables

    def _extract_docx(self, filepath: str) -> list[pd.DataFrame]:
        """Extrait les tableaux d'un fichier .docx avec un timeout de sécurité."""
        result = []
        error = []

        def _worker():
            try:
                doc = Document(filepath)
                for table in doc.tables:
                    try:
                        data = [[cell.text for cell in row.cells] for row in table.rows]
                        df = self._clean_df(pd.DataFrame(data))
                        if self._is_valid(df):
                            result.append(df)
                    except Exception as e:
                        error.append(f"Table skipped: {e}")
            except Exception as e:
                error.append(str(e))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=self.EXTRACT_TIMEOUT)

        if t.is_alive():
            print(f"    ⚠️  Extraction DOCX timeout ({self.EXTRACT_TIMEOUT}s) — fichier ignoré.")
            return []
        if error:
            print(f"    [!] Erreur DOCX: {error[0]}")
        return result

    def _convert_and_extract(self, filepath: str) -> list[pd.DataFrame]:
        """Convertit .doc/.rtf en .docx via LibreOffice (avec timeout) puis extrait."""
        tables = []
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "docx", "--outdir", tmpdir, filepath],
                    check=True,
                    capture_output=True,
                    timeout=self.LIBREOFFICE_TIMEOUT,
                )
                base = os.path.splitext(os.path.basename(filepath))[0]
                converted = os.path.join(tmpdir, base + ".docx")
                if os.path.exists(converted):
                    tables = self._extract_docx(converted)
            except subprocess.TimeoutExpired:
                print(f"    ⚠️  Timeout LibreOffice ({self.LIBREOFFICE_TIMEOUT}s) — {os.path.basename(filepath)} ignoré.")
            except subprocess.CalledProcessError as e:
                print(f"    [!] LibreOffice a échoué: {e.stderr.decode(errors='replace')[:200]}")
            except Exception as e:
                print(f"    [!] Erreur conversion: {e}")
        return tables

    def _parse_file(self, filename: str) -> list[pd.DataFrame]:
        filepath = os.path.join(self.download_dir, filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            return self._extract_pdf(filepath)
        elif ext == ".docx":
            return self._extract_docx(filepath)
        elif ext in (".doc", ".rtf"):
            return self._convert_and_extract(filepath)
        return []

    def run(self):
        """Parse uniquement les fichiers sans tableaux extraits."""
        print("\n📊 [Étape 4] Extraction des tableaux...")
        if not os.path.isdir(self.download_dir):
            print("  ❌ Dossier downloads/ introuvable. Lancez d'abord l'étape 3.")
            return

        files = [f for f in os.listdir(self.download_dir) if os.path.isfile(os.path.join(self.download_dir, f))]
        missing = [f for f in files if not self._is_file_done(f)]

        if not missing:
            print("  ✅ Tous les tableaux déjà extraits. Étape sautée.")
            return

        print(f"  🔄 {len(missing)} fichier(s) à traiter...")
        total_tables = 0
        for filename in missing:
            tables = self._parse_file(filename)
            if tables:
                year = self._parse_year(filename)
                year_dir = os.path.join(self.output_root, year)
                os.makedirs(year_dir, exist_ok=True)
                for i, df in enumerate(tables, start=1):
                    path = self._output_prefix(filename, i)
                    df.to_csv(path, index=False, encoding="utf-8")
                total_tables += len(tables)
                print(f"  ✅ {filename} → {len(tables)} tableau(x)")
            else:
                print(f"  ⚠️  {filename} : Aucun tableau trouvé.")

        print(f"  💾 {total_tables} tableau(x) exporté(s) dans {self.output_root}/")
