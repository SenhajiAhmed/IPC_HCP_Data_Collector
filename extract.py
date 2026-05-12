import pdfplumber
import pandas as pd
import glob
import os
import re
import subprocess
import shutil
import tempfile
from docx import Document

# Dossiers configuration
DOWNLOADS_DIR = "downloads"
OUTPUT_ROOT = "extracted_tables"

def est_le_bon_tableau(df):
    """
    Détermine si le tableau correspond à la forme recherchée.
    """
    if df.empty or len(df.columns) < 2:
        return False
    return True

def nettoyer_dataframe(df):
    """
    Applique le nettoyage standard (gestion des retours à la ligne dans les cellules).
    """
    df = df.fillna("")
    # Séparer les cellules contenant des retours à la ligne (\n) en plusieurs lignes
    df = df.astype(str).map(lambda x: x.split('\n'))
    for idx, row in df.iterrows():
        max_len = max(len(x) for x in row)
        for col in df.columns:
            if len(df.at[idx, col]) < max_len:
                df.at[idx, col].extend([''] * (max_len - len(df.at[idx, col])))
    df = df.explode(list(df.columns)).reset_index(drop=True)
    
    # Définir la première ligne comme en-tête et dédupliquer les noms de colonnes
    if not df.empty:
        colonnes = [str(c) for c in df.iloc[0]]
        counts = {}
        nouvelles_colonnes = []
        for col in colonnes:
            if col in counts:
                counts[col] += 1
                nouvelles_colonnes.append(f"{col}_{counts[col]}")
            else:
                counts[col] = 0
                nouvelles_colonnes.append(col)
        
        df.columns = nouvelles_colonnes
        df = df[1:].reset_index(drop=True)
    return df

def extraire_pdf(filepath):
    tableaux_extraits = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                tableaux = page.extract_tables()
                for tab in tableaux:
                    df = pd.DataFrame(tab)
                    df = nettoyer_dataframe(df)
                    if est_le_bon_tableau(df):
                        tableaux_extraits.append(df)
    except Exception as e:
        print(f"Erreur PDF ({os.path.basename(filepath)}): {e}")
    return tableaux_extraits

def extraire_docx(filepath):
    tableaux_extraits = []
    try:
        doc = Document(filepath)
        for table in doc.tables:
            data = []
            for row in table.rows:
                data.append([cell.text for cell in row.cells])
            df = pd.DataFrame(data)
            df = nettoyer_dataframe(df)
            if est_le_bon_tableau(df):
                tableaux_extraits.append(df)
    except Exception as e:
        print(f"Erreur DOCX ({os.path.basename(filepath)}): {e}")
    return tableaux_extraits

def convertir_et_extraire(filepath, extension):
    """
    Convertit .doc ou .rtf en .docx temporaire puis extrait les tableaux.
    """
    tableaux = []
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Conversion via LibreOffice
            subprocess.run([
                "libreoffice", "--headless", "--convert-to", "docx",
                "--outdir", tmpdir, filepath
            ], check=True, capture_output=True)
            
            # Trouver le fichier converti
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            converted_path = os.path.join(tmpdir, base_name + ".docx")
            
            if os.path.exists(converted_path):
                tableaux = extraire_docx(converted_path)
        except Exception as e:
            print(f"Erreur conversion {extension} ({os.path.basename(filepath)}): {e}")
    return tableaux

def main():
    if not os.path.exists(DOWNLOADS_DIR):
        print(f"Dossier {DOWNLOADS_DIR} introuvable.")
        return

    fichiers = os.listdir(DOWNLOADS_DIR)
    print(f"Début de l'extraction sur {len(fichiers)} fichiers...")

    for filename in fichiers:
        filepath = os.path.join(DOWNLOADS_DIR, filename)
        if not os.path.isfile(filepath):
            continue

        # Extraire l'année du nom de fichier (format: YYYY_...)
        match_annee = re.match(r'^(\d{4})_', filename)
        annee = match_annee.group(1) if match_annee else "Inconnu"
        
        # Extraire le mois pour le nom de sortie
        match_mois = re.search(r'^\d{4}_(.*?)(?:_|$)', filename)
        mois = match_mois.group(1) if match_mois else "MoisInconnu"

        ext = os.path.splitext(filename)[1].lower()
        tableaux = []

        if ext == ".pdf":
            tableaux = extraire_pdf(filepath)
        elif ext == ".docx":
            tableaux = extraire_docx(filepath)
        elif ext in [".doc", ".rtf"]:
            tableaux = convertir_et_extraire(filepath, ext)
        
        if tableaux:
            # Créer le dossier de l'année
            annee_dir = os.path.join(OUTPUT_ROOT, annee)
            os.makedirs(annee_dir, exist_ok=True)
            
            base_name_clean = re.sub(r'[\\/*?:"<>|]', "", filename)
            
            for i, df in enumerate(tableaux):
                output_name = f"{mois}_{i+1}_{base_name_clean}.csv"
                output_path = os.path.join(annee_dir, output_name)
                df.to_csv(output_path, index=False, encoding='utf-8')
            
            print(f"✅ {filename} : {len(tableaux)} tableaux extraits vers {annee}/")
        else:
            print(f"⚠️ {filename} : Aucun tableau trouvé.")

if __name__ == "__main__":
    main()
