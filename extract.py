import pdfplumber
import pandas as pd
import glob
import os

def est_le_bon_tableau(df):
    """
    Détermine si le tableau correspond à la forme recherchée.
    À adapter selon la structure réelle de vos tableaux (ex: nombre de colonnes).
    """
    # Exemple 1 : Le tableau doit avoir un certain nombre de colonnes
    # if len(df.columns) != 5:
    #     return False
    
    # Exemple 2 : Le tableau doit contenir un certain mot dans la première ligne
    try:
        premiere_ligne = " ".join(str(val).lower() for val in df.iloc[0].values)
        # if "indice" not in premiere_ligne:
        #     return False
    except IndexError:
        return False
        
    # Par défaut, on accepte tous les tableaux pour tester
    # (Décommentez et ajustez les lignes ci-dessus pour filtrer par forme)
    return True

def extraire_tableaux_par_forme(dossier_pdf, fichier_sortie="resultats_extraits.csv"):
    chemin_recherche = os.path.join(dossier_pdf, "*.pdf")
    fichiers_pdf = glob.glob(chemin_recherche)
    tous_les_tableaux = []
    
    if not fichiers_pdf:
        print(f"Aucun fichier PDF trouvé dans {dossier_pdf}")
        return

    for chemin_pdf in fichiers_pdf:
        nom_fichier = os.path.basename(chemin_pdf)
        print(f"Analyse de {nom_fichier}...")
        
        try:
            with pdfplumber.open(chemin_pdf) as pdf:
                for page in pdf.pages:
                    # extract_tables cherche visuellement les grilles (les lignes) sur la page
                    tableaux = page.extract_tables()
                    
                    for tab in tableaux:
                        # Convertir en DataFrame Pandas
                        df = pd.DataFrame(tab)
                        df = df.fillna("")
                        
                        # Séparer les cellules contenant des retours à la ligne (\n) en plusieurs lignes
                        df = df.astype(str).map(lambda x: x.split('\n'))
                        for idx, row in df.iterrows():
                            max_len = max(len(x) for x in row)
                            for col in df.columns:
                                if len(df.at[idx, col]) < max_len:
                                    df.at[idx, col].extend([''] * (max_len - len(df.at[idx, col])))
                        df = df.explode(list(df.columns)).reset_index(drop=True)
                        
                        # Vérifier la "ressemblance de forme"
                        if est_le_bon_tableau(df):
                            print(f" -> ✅ Bon tableau trouvé sur la page {page.page_number} !")
                            
                            # Définir la première ligne comme en-tête et dédupliquer les noms de colonnes
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
                            
                            # Ajouter une colonne d'identification
                            df['Fichier_Source'] = nom_fichier
                            df['Page_Source'] = page.page_number
                            tous_les_tableaux.append(df)
        except Exception as e:
            print(f"Erreur lors de la lecture de {nom_fichier}: {e}")

    if tous_les_tableaux:
        print(f"\nSauvegarde de {len(tous_les_tableaux)} tableaux individuellement...")
        try:
            for i, df in enumerate(tous_les_tableaux):
                nom_fichier_sans_ext = os.path.splitext(df['Fichier_Source'].iloc[0])[0]
                page_num = df['Page_Source'].iloc[0]
                nom_sortie = f"{os.path.splitext(fichier_sortie)[0]}_{i+1}_{nom_fichier_sans_ext}_page{page_num}.csv"
                df.to_csv(nom_sortie, index=False, encoding='utf-8')
            print(f"Extraction terminée. {len(tous_les_tableaux)} fichiers ont été créés.")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde: {e}")
    else:
        print("\nAucun tableau correspondant à la forme n'a été trouvé.")

if __name__ == "__main__":
    # Dossier où se trouvent les PDF (le répertoire courant)
    DOSSIER_PDF = "."
    FICHIER_SORTIE = "resultats_extraits.csv"
    
    extraire_tableaux_par_forme(DOSSIER_PDF, FICHIER_SORTIE)
