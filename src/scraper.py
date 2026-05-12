import json
import re
import csv
import time
import unicodedata
import urllib.parse
import requests
from typing import Optional


class HCPScraper:
    """
    Étape 1 : Scraping des URLs des rapports IPC mensuels (2010-2025)
    via l'API Google Custom Search du HCP.

    Idempotence : Ne re-scrape que les mois dont l'URL est 'nan' ou absents.
    """

    MONTHS = [
        "de Janvier", "de Février", "de Mars", "d'Avril",
        "de Mai", "de Juin", "de Juillet", "d'Août",
        "de Septembre", "d'Octobre", "de Novembre", "de Décembre"
    ]
    YEARS = range(2010, 2026)
    CX = "04ef8a898c9384bec"
    MAX_RETRIES = 4          # Nombre de tentatives max par mois
    BASE_DELAY = 2           # Délai de base entre requêtes (secondes)
    RATE_LIMIT_WAIT = 65     # Attente en cas de 429 (secondes)

    def __init__(self, output_csv: str = "hcp_ipc_reports_2010_2025.csv"):
        self.output_csv = output_csv
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

    def _load_existing(self) -> dict:
        """Charge le CSV existant et retourne un dict {(year, month): url}."""
        existing = {}
        try:
            with open(self.output_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (int(row["Année"]), row["Mois"])
                    existing[key] = row["URL"]
        except FileNotFoundError:
            pass
        return existing

    def _save(self, data: dict):
        """Sauvegarde le dictionnaire {(year, month): url} en CSV."""
        with open(self.output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Année", "Mois", "URL"])
            for year in self.YEARS:
                for month in self.MONTHS:
                    url = data.get((year, month), "nan")
                    writer.writerow([year, month, url])

    def is_done(self) -> bool:
        """Vérifie si toutes les entrées valides sont présentes (pas de nan)."""
        data = self._load_existing()
        missing = [
            (y, m) for y in self.YEARS for m in self.MONTHS
            if data.get((y, m), "nan") == "nan"
        ]
        if missing:
            print(f"  [Scraper] {len(missing)} entrée(s) manquante(s) ou nan.")
            return False
        return True

    def _remove_accents(self, s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

    def _is_valid_url(self, url: str) -> bool:
        if "downloads/" in url or "Actualite-" in url:
            return False
        if url.endswith(".html") and "_r" in url.split("/")[-1]:
            return False
        return True

    def _find_report_url(self, month: str, year: int) -> tuple[Optional[str], bool]:
        """
        Retourne (url, is_blocked).
        - (url, False)  : URL trouvée
        - (None, False) : Pas de résultat (donnée vraiment absente)
        - (None, True)  : Bloqué par rate-limit (403 ou 429)
        """
        mois_propre = month.replace("d'", "d ").split()[-1]
        mois_sans_accent = self._remove_accents(mois_propre).lower()
        query = f"Indice des prix à la consommation {mois_propre} {year}"
        encoded = urllib.parse.quote_plus(query)

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                init = self.session.get(f"https://cse.google.com/cse.js?cx={self.CX}", timeout=15)

                # 403 ou 429 sur init → bloqué
                if init.status_code in (403, 429):
                    print(f"    ⏳ Bloqué HTTP {init.status_code} (init) — attente {self.RATE_LIMIT_WAIT}s (tentative {attempt}/{self.MAX_RETRIES})...")
                    time.sleep(self.RATE_LIMIT_WAIT)
                    continue

                token = re.search(r'"cse_token":\s*"([^"]+)"', init.text)
                version = re.search(r'"cselibVersion":\s*"([^"]+)"', init.text)
                if not token or not version:
                    print(f"    [!] Token CSE introuvable (tentative {attempt}/{self.MAX_RETRIES}).")
                    time.sleep(self.BASE_DELAY * attempt)
                    continue

                rurl = urllib.parse.quote_plus(f"https://www.hcp.ma/plugin/?q={encoded}#gsc.tab=0&gsc.q={encoded}&gsc.page=1")
                api_url = (
                    f"https://cse.google.com/cse/element/v1?rsz=filtered_cse&num=10&hl=fr&source=gcsc"
                    f"&cselibv={version.group(1)}&cx={self.CX}&q={encoded}&safe=off"
                    f"&cse_tok={urllib.parse.quote_plus(token.group(1))}&callback=google.search.cse.api"
                    f"&rurl={rurl}"
                )
                resp = self.session.get(api_url, timeout=15)

                # 403 ou 429 sur l'API → bloqué
                if resp.status_code in (403, 429):
                    print(f"    ⏳ Bloqué HTTP {resp.status_code} (API) — attente {self.RATE_LIMIT_WAIT}s (tentative {attempt}/{self.MAX_RETRIES})...")
                    time.sleep(self.RATE_LIMIT_WAIT)
                    continue

                if resp.status_code != 200:
                    print(f"    [!] HTTP {resp.status_code} (tentative {attempt}/{self.MAX_RETRIES}).")
                    time.sleep(self.BASE_DELAY * attempt)
                    continue

                match = re.search(r"google\.search\.cse\.api\((.*)\);?", resp.text, re.DOTALL)
                if not match:
                    print(f"    [!] Parsing JSONP échoué (tentative {attempt}/{self.MAX_RETRIES}).")
                    time.sleep(self.BASE_DELAY * attempt)
                    continue

                results = json.loads(match.group(1)).get("results", [])
                for r in results:
                    text = (r.get("titleNoFormatting", "").lower() + " "
                            + r.get("unescapedUrl", "").lower() + " "
                            + r.get("contentNoFormatting", "").lower())
                    url = r.get("unescapedUrl", "")
                    if ("prix" in text and "consommation" in text
                            and str(year) in text
                            and (mois_propre.lower() in text or mois_sans_accent in text)):
                        if self._is_valid_url(url):
                            return url, False  # Trouvé, non bloqué

                # Résultats traités sans match valide → donnée absente (pas un blocage)
                return None, False

            except requests.exceptions.Timeout:
                print(f"    ⏱️  Timeout réseau (tentative {attempt}/{self.MAX_RETRIES}).")
                time.sleep(self.BASE_DELAY * attempt)
            except Exception as e:
                print(f"    [!] Exception inattendue: {e} (tentative {attempt}/{self.MAX_RETRIES}).")
                time.sleep(self.BASE_DELAY * attempt)

        # Toutes les tentatives ont échoué avec 403/429 → bloqué
        print(f"    ❌ Échec après {self.MAX_RETRIES} tentatives (blocage API).")
        return None, True

    def run(self):
        """Lance le scraping, uniquement pour les entrées manquantes ou nan."""
        print("\n📡 [Étape 1] Scraping des URLs des rapports HCP...")
        data = self._load_existing()

        missing = [
            (y, m) for y in self.YEARS for m in self.MONTHS
            if data.get((y, m), "nan") == "nan"
        ]

        if not missing:
            print("  ✅ Toutes les URLs sont déjà présentes. Étape sautée.")
            return

        print(f"  🔄 {len(missing)} entrée(s) à (re)scraper...")

        # File d'attente pour les items bloqués à retenter après cooldown
        retry_queue: list[tuple[int, str]] = []
        consecutive_blocked = 0          # Compteur de nans consécutifs dus à un blocage
        pending_blocked: list[tuple[int, str]] = []  # Buffer des items bloqués en cours

        def _scrape_and_record(year, month, is_retry: bool = False):
            """Scrape un item et met à jour data. Retourne (url, is_blocked)."""
            prefix = "  [Retry]" if is_retry else "  [*]"
            print(f"{prefix} Scraping {month} {year}...")
            url, blocked = self._find_report_url(month, year)
            data[(year, month)] = url if url else "nan"
            if url:
                print(f"    ✅ Trouvé : {url}")
            elif blocked:
                print(f"    🔒 Bloqué — nan provisoire.")
            else:
                print(f"    ⚠️  Non trouvé (donnée absente sur le site).")
            self._save(data)
            time.sleep(self.BASE_DELAY)
            return url, blocked

        for year, month in missing:
            url, blocked = _scrape_and_record(year, month)

            if url is None and blocked:
                consecutive_blocked += 1
                pending_blocked.append((year, month))

                if consecutive_blocked >= 2:
                    # ────── COOLDOWN ──────
                    print(f"\n  ⏸️  {consecutive_blocked} nan(s) consécutif(s) causés par un blocage.")
                    print(f"  ⏳ Cooldown de 60s puis retry des {consecutive_blocked} item(s) bloqué(s)...\n")
                    time.sleep(60)

                    # Retry immédiat des items bloqués
                    recovered = []
                    for ry, rm in pending_blocked:
                        r_url, r_blocked = _scrape_and_record(ry, rm, is_retry=True)
                        if r_url:
                            recovered.append((ry, rm))
                        elif r_blocked:
                            # Toujours bloqué → ajouter à la file pour retry final
                            if (ry, rm) not in retry_queue:
                                retry_queue.append((ry, rm))

                    if recovered:
                        print(f"  ✅ {len(recovered)} item(s) récupéré(s) après cooldown.")

                    # Réinitialiser le buffer
                    consecutive_blocked = 0
                    pending_blocked.clear()

            else:
                # URL trouvée OU nan non-bloqué (donnée vraiment absente) → reset compteur
                if pending_blocked:
                    # Le nan isolé précédent n'était pas un blocage → on l'ignore (déjà sauvegardé)
                    if consecutive_blocked == 1:
                        print(f"  ℹ️  Nan isolé pour {pending_blocked[-1][1]} {pending_blocked[-1][0]} — ignoré (donnée absente).")
                consecutive_blocked = 0
                pending_blocked.clear()

        # ── Retry final pour les items toujours bloqués ──
        if retry_queue:
            print(f"\n  🔁 Retry final de {len(retry_queue)} entrée(s) encore bloquées...")
            time.sleep(60)  # Dernier cooldown avant retry final
            for ry, rm in retry_queue:
                if data.get((ry, rm)) != "nan":
                    continue
                _scrape_and_record(ry, rm, is_retry=True)

        found = sum(1 for y in self.YEARS for m in self.MONTHS if data.get((y, m), "nan") != "nan")
        print(f"\n  💾 Sauvegardé dans {self.output_csv} — {found}/192 URLs trouvées.")

