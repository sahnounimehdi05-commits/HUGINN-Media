#!/usr/bin/env python3
"""Ajoute une édition du HUGINN Daily Brief au site (dossier site/).

Usage :
  python3 scripts/publish_edition.py --pdf /chemin/HUGINN_DAILY_BRIEF_2026-11-27.pdf \
      --title "Titre factuel de la une" --refs 35

Ce que fait le script :
  - copie le PDF dans site/editions/ ;
  - crée la couverture site/covers/c<AAAA-MM-JJ>.jpg (page 1, 80 dpi, comme les précédentes) ;
  - met à jour index.html : bloc « dernier numéro », nouvelle carte en tête de la grille,
    chiffres clés (éditions, pages, références) et pied de page.
Relancer le script pour la même date remplace l'entrée existante au lieu de la dupliquer.
"""
import argparse
import datetime as dt
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
INDEX = SITE / "index.html"
FIRST_DAY = dt.date(2026, 11, 23)  # édition n° 001

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def date_fr(d, cap=False):
    s = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"
    return s[0].upper() + s[1:] if cap else s


def date_courte(d):
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def pdf_pages(p):
    out = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", out, re.M).group(1))


def cover_name(d):
    # Les quatre premières couvertures gardent leur ancien nom (c23.jpg ... c26.jpg).
    legacy = SITE / "covers" / f"c{d.day:02d}.jpg"
    if d <= dt.date(2026, 11, 26) and legacy.exists():
        return legacy.name
    return f"c{d.isoformat()}.jpg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--title", required=True, help="titre factuel de la une (texte brut)")
    ap.add_argument("--refs", type=int, required=True, help="nombre de références citées dans ce numéro")
    a = ap.parse_args()

    src = Path(a.pdf)
    m = re.fullmatch(r"HUGINN_DAILY_BRIEF_(\d{4}-\d{2}-\d{2})\.pdf", src.name)
    if not m or not src.exists():
        sys.exit(f"PDF introuvable ou mal nommé : {src}")
    d = dt.date.fromisoformat(m.group(1))
    num = (d - FIRST_DAY).days + 1
    if num < 1:
        sys.exit("Date antérieure à l'édition n° 001")
    n3 = f"{num:03d}"

    pdf_rel = f"editions/{src.name}"
    dst = SITE / pdf_rel
    if src.resolve() != dst.resolve():
        shutil.copyfile(src, dst)
    pages = pdf_pages(dst)

    cov = cover_name(d)
    tmp = Path("/tmp/huginn_cover")
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "80", "-jpeg", "-jpegopt", "quality=85",
                    "-singlefile", str(dst), str(tmp)], check=True)
    shutil.move(str(tmp) + ".jpg", SITE / "covers" / cov)
    cov_rel = f"covers/{cov}"

    s = INDEX.read_text(encoding="utf8")
    title = html.escape(a.title, quote=False)

    # 1. Carte de l'édition (remplace une carte existante pour ce PDF, sinon l'ajoute en tête).
    card = (f'<article class="card"><a class="cv" href="{pdf_rel}" target="_blank" rel="noopener">'
            f'<img src="{cov_rel}" alt="Couverture de l’édition n° {n3}" loading="lazy"></a>\n'
            f'    <p class="meta"><b>Édition n° {n3}</b> · {date_fr(d, cap=True)}</p><h3>{title}</h3>'
            f'<a class="rd" href="{pdf_rel}" target="_blank" rel="noopener">Lire le PDF, {pages} pages</a></article>')
    card_re = re.compile(r'<article class="card"><a class="cv" href="' + re.escape(pdf_rel) + r'".*?</article>', re.S)
    if card_re.search(s):
        s = card_re.sub(lambda _: card, s, count=1)
    else:
        s = s.replace('<div class="grid">\n', '<div class="grid">\n   ' + card + '\n', 1)

    # Liste des éditions présentes (dans la grille) pour les chiffres clés.
    eds = sorted(set(re.findall(r'<a class="cv" href="editions/HUGINN_DAILY_BRIEF_(\d{4}-\d{2}-\d{2})\.pdf"', s)))
    latest = dt.date.fromisoformat(eds[-1])
    first = dt.date.fromisoformat(eds[0])

    # 2. Bloc « dernier numéro » : seulement si cette édition est la plus récente.
    if d == latest:
        s = re.sub(r'(<div class="cta"><a class="btn pri" href=")editions/[^"]+(")', rf'\g<1>{pdf_rel}\2', s, count=1)
        s = re.sub(r'(<a class="hero-fig" href=")editions/[^"]+(")', rf'\g<1>{pdf_rel}\2', s, count=1)
        s = re.sub(r'(<div class="hero">.*?<img src=")[^"]+(" alt=")[^"]*(")',
                   lambda mm: f'{mm.group(1)}{cov_rel}{mm.group(2)}Couverture de l’édition n° {n3} du HUGINN Daily Brief, {date_fr(d)}{mm.group(3)}',
                   s, count=1, flags=re.S)
        s = re.sub(r'<figcaption>.*?</figcaption>',
                   f'<figcaption>Édition n° {n3} · {date_fr(d)} · PDF, {pages} pages</figcaption>', s, count=1)

    # 3. Chiffres clés.
    total_pages = sum(pdf_pages(SITE / f"editions/HUGINN_DAILY_BRIEF_{e}.pdf") for e in eds)
    s = re.sub(r'<div><b>\d+</b><span>éditions publiées[^<]*</span></div>',
               f'<div><b>{len(eds)}</b><span>éditions publiées depuis le {date_courte(first)}</span></div>', s, count=1)
    s = re.sub(r'<div><b>\d+</b><span>pages de rédaction',
               f'<div><b>{total_pages}</b><span>pages de rédaction', s, count=1)
    refs_m = re.search(r'<div><b>(\d+)</b><span>références consultées', s)
    marker = f'<!--refs:{d.isoformat()}:'
    old = re.search(re.escape(marker) + r'(\d+)-->', s)
    prev_for_day = int(old.group(1)) if old else 0
    new_total = int(refs_m.group(1)) - prev_for_day + a.refs
    s = s.replace(refs_m.group(0), f'<div><b>{new_total}</b><span>références consultées', 1)
    if old:
        s = s.replace(old.group(0), f'{marker}{a.refs}-->', 1)
    else:
        s = s.replace('</body>', f'{marker}{a.refs}-->\n</body>', 1)

    # 4. Pied de page.
    s = re.sub(r'éditions n° \d{3} à \d{3}, du [^<]*?(</span>)',
               f'éditions n° 001 à {len(eds):03d}, du {date_courte(first)} au {date_courte(latest)}\\1', s, count=1)

    INDEX.write_text(s, encoding="utf8")
    print(f"OK : édition n° {n3} du {date_fr(d)} — {pages} pages, couverture {cov_rel}, "
          f"{len(eds)} éditions, {total_pages} pages, {new_total} références.")


if __name__ == "__main__":
    main()
