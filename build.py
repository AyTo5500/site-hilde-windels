#!/usr/bin/env python3
"""
Bouwt de startpagina in twee talen uit de bestanden in werken/:
index.html (Engels, uit templates/index.html) en nl/index.html
(Nederlands, uit templates/index.nl.html).

Draait op kale Python 3, zonder installatie van pakketten, zodat dit over
jaren nog werkt. Netlify voert dit uit bij elke wijziging via het CMS.

    python3 build.py
"""

import html
import json
import os
import re
import struct
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
FOTOMAP = os.path.join(HIER, "assets", "works")


def lokaal(pad):
    """Van /assets/works/x.jpg naar het bestand op schijf."""
    return os.path.join(HIER, pad.lstrip("/"))
DIRECT_LADEN = 4          # eerste vier foto's meteen, de rest bij naderen
BASIS = "https://hilde-windels.com/"

# Vaste woorden op de startpagina, per taal
TEKST = {
    "en": {"foto": "Photo %s", "fotos": "%d photos", "een": "photo",
           "bekijk": "View %s, %s, %s", "per_stuk": "(each)"},
    "nl": {"foto": "Foto %s", "fotos": "%d foto's", "een": "foto",
           "bekijk": "%s, %s, %s bekijken", "per_stuk": "(per stuk)"},
}


def maten_nl(tekst):
    """Afmetingen en collectie worden in het Engels ingevuld; de
    Nederlandse versie volgt daar vanzelf uit."""
    for en, nl in [("Room ", "Kamer "), ("H variable", "H variabel"),
                   ("variable width/depth", "variabele breedte/diepte"),
                   ("Ø circle", "Ø cirkel"), ("(each)", "(per stuk)"),
                   ("Collection ", "Collectie "), ("Ghent", "Gent"),
                   ("Bruges", "Brugge"), ("Brussels", "Brussel")]:
        tekst = tekst.replace(en, nl)
    tekst = re.sub(r"\bW (?=\d)", "B ", tekst)          # width wordt breedte
    return re.sub(r"(\d)\.(\d)", r"\1,\2", tekst)      # 4.5 wordt 4,5


def in_taal(werk, taal):
    """Titel, materiaal, maten en collectie van een werk in de gevraagde taal."""
    if taal == "en":
        return {k: werk.get(k, "") for k in ("titel", "materiaal", "afmetingen", "collectie")}
    return {
        "titel": werk.get("titel_nl") or werk["titel"],
        "materiaal": werk.get("materiaal_nl") or werk.get("materiaal", ""),
        "afmetingen": maten_nl(str(werk.get("afmetingen", ""))),
        "collectie": maten_nl(str(werk.get("collectie", ""))),
    }


def jpeg_formaat(pad):
    """Breedte en hoogte van een jpeg, zonder externe pakketten."""
    with open(pad, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError("geen jpeg: %s" % pad)
        while True:
            b = f.read(1)
            if not b:
                raise ValueError("geen afmetingen gevonden: %s" % pad)
            if b != b"\xff":
                continue
            merk = f.read(1)
            while merk == b"\xff":
                merk = f.read(1)
            code = merk[0]
            # SOF0 tot SOF15, met uitzondering van de niet-formaatmarkeringen
            if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                f.read(3)
                hoogte, breedte = struct.unpack(">HH", f.read(4))
                return breedte, hoogte
            if code in (0xD8, 0xD9) or 0xD0 <= code <= 0xD7:
                continue
            lengte = struct.unpack(">H", f.read(2))[0]
            f.seek(lengte - 2, 1)


def regels(werk, taal="en"):
    """De losse velden van een werk, elk opgeschoond, als (soort, tekst).

    Bestand tegen hoe mensen echt typen: regeleindes, dubbele spaties en een
    punt aan het eind van een veld. Zonder dit wordt "stuks." plus ". " samen
    "stuks..", en dat is precies wat er gebeurde.
    """
    t = TEKST[taal]
    w = in_taal(werk, taal)
    fotograaf = " ".join(str(werk.get("fotograaf", "")).split())
    velden = [("materiaal", w["materiaal"]),
              ("maten", w["afmetingen"]),
              ("collectie", w["collectie"]),
              ("foto", t["foto"] % fotograaf if fotograaf else "")]
    schoon = []
    for soort, deel in velden:
        tekst = " ".join(str(deel).split())      # regeleindes en dubbele spaties weg
        tekst = tekst.rstrip(". ")               # eindpunt weg, de opmaak scheidt zelf
        # "(each)" of "(per stuk)" nooit los op een nieuwe regel laten vallen
        tekst = tekst.replace(" " + t["per_stuk"], "\u00a0" + t["per_stuk"].replace(" ", "\u00a0"))
        if tekst:
            schoon.append((soort, tekst))
    return schoon


def beschrijving(werk):
    """De velden aan elkaar tot een zin, voor zoekmachines."""
    return ". ".join(tekst for _, tekst in regels(werk))


def detail_html(werk, taal="en"):
    """De velden als losse regels, elk met een eigen klasse voor de opmaak."""
    return "".join('<span class="d d--%s">%s</span>' % (soort, html.escape(tekst))
                   for soort, tekst in regels(werk, taal))


def attr(tekst):
    """Escapen voor een attribuut tussen dubbele aanhalingstekens.
    De apostrof blijft staan, die kan daar geen kwaad en leest prettiger."""
    return (str(tekst).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def bouw_werk(werk, volgnummer, taal="en"):
    fotos = [f for f in werk["fotos"] if f]
    if not fotos:
        raise ValueError("werk zonder foto: %s" % werk["titel"])

    for f in fotos:
        if not os.path.exists(lokaal(f)):
            raise ValueError("foto ontbreekt: %s (bij %s)" % (f, werk["titel"]))

    t = TEKST[taal]
    titel = in_taal(werk, taal)["titel"]
    breedte, hoogte = jpeg_formaat(lokaal(fotos[0]))
    detail = detail_html(werk, taal)
    alt = "%s, %s" % (titel, werk["jaar"])
    aantal = t["fotos"] % len(fotos) if len(fotos) > 1 else t["een"]
    lui = "" if volgnummer < DIRECT_LADEN else ' loading="lazy"'

    if len(fotos) > 1:
        regel = ('<span class="tl__regel"><span class="tl__year">%s</span>'
                 '<span class="tl__meer">%s</span></span>' % (werk["jaar"], t["fotos"] % len(fotos)))
    else:
        regel = '<span class="tl__year">%s</span>' % werk["jaar"]

    return (
        '        <li class="tl__item" data-fotos="%s" data-detail="%s" style="--ar:%.4f">\n'
        '          <button class="tl__frame" type="button" aria-label="%s">'
        '<img src="%s"%s width="%d" height="%d" alt="%s" /></button>\n'
        '          <div class="tl__cap">\n'
        '            <h3 class="tl__title">%s</h3>\n'
        '            %s\n'
        '          </div>\n'
        '        </li>\n'
    ) % (
        attr("|".join(fotos)), attr(detail), breedte / hoogte,
        attr(t["bekijk"] % (titel, werk["jaar"], aantal)),
        fotos[0], lui, breedte, hoogte, attr(alt),
        html.escape(titel), regel,
    )


def sitemap(werken, paginas):
    """Een sitemap met de pagina's en de werkfoto's erin, zodat die ook in
    Google Afbeeldingen terechtkomen."""
    vandaag = time.strftime("%Y-%m-%d")
    regels = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
              ' xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']

    for slug, prioriteit in paginas:
        regels.append("  <url>")
        regels.append("    <loc>%s%s</loc>" % (BASIS, slug))
        regels.append("    <lastmod>%s</lastmod>" % vandaag)
        regels.append("    <priority>%s</priority>" % prioriteit)
        if slug == "":
            for werk in werken:
                for foto in werk["fotos"]:
                    regels.append("    <image:image>")
                    regels.append("      <image:loc>%s%s</image:loc>" % (BASIS, foto.lstrip("/")))
                    regels.append("      <image:title>%s, %s</image:title>"
                                  % (escape_xml(werk["titel"]), werk["jaar"]))
                    regels.append("      <image:caption>%s</image:caption>"
                                  % escape_xml(beschrijving(werk)))
                    regels.append("    </image:image>")
        regels.append("  </url>")

    regels.append("</urlset>")
    return "\n".join(regels) + "\n"


def escape_xml(tekst):
    return (str(tekst).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def gestructureerde_data(werken, taal="en"):
    """JSON-LD: wie de kunstenaar is en welke werken op de pagina staan."""
    kunstenaar = {
        "@type": "Person",
        "@id": BASIS + "#hilde-windels",
        "name": "Hilde Windels",
        "jobTitle": "Visual artist" if taal == "en" else "Beeldend kunstenaar",
        "url": BASIS,
        "image": BASIS + "assets/preview.jpg",
        "birthPlace": {"@type": "Place", "name": "Tielt, Belgium"},
        "address": {"@type": "PostalAddress", "addressLocality": "Ghent",
                    "addressCountry": "BE"},
        "knowsAbout": ["Flax", "Textile art", "Visual art"],
    }

    items = []
    for n, werk in enumerate(werken, start=1):
        items.append({
            "@type": "ListItem",
            "position": n,
            "item": {
                "@type": "VisualArtwork",
                "name": in_taal(werk, taal)["titel"],
                "dateCreated": str(werk["jaar"]),
                "artform": "Textile art",
                "artMedium": in_taal(werk, taal)["materiaal"],
                "creator": {"@id": BASIS + "#hilde-windels"},
                "image": BASIS + werk["fotos"][0].lstrip("/"),
            },
        })

    data = {
        "@context": "https://schema.org",
        "@graph": [
            kunstenaar,
            {"@type": "WebSite", "url": BASIS if taal == "en" else BASIS + "nl/",
             "name": "Hilde Windels", "inLanguage": taal,
             "about": {"@id": BASIS + "#hilde-windels"}},
            {"@type": "ItemList", "name": "Work by Hilde Windels, 1990 to present"
             if taal == "en" else "Werk van Hilde Windels, 1990 tot heden",
             "numberOfItems": len(werken), "itemListElement": items},
        ],
    }
    return ('<script type="application/ld+json">\n%s\n  </script>'
            % json.dumps(data, ensure_ascii=False, indent=2))


def main():
    map_werken = os.path.join(HIER, "werken")
    bestanden = sorted(f for f in os.listdir(map_werken) if f.endswith(".json"))
    if not bestanden:
        raise ValueError("geen werken gevonden in werken/")

    werken = []
    for naam in bestanden:
        with open(os.path.join(map_werken, naam), encoding="utf-8") as f:
            try:
                werken.append(json.load(f))
            except json.JSONDecodeError as e:
                raise ValueError("werken/%s is geen geldige json: %s" % (naam, e))

    # nieuwste eerst. Binnen hetzelfde jaar bepaalt "volgorde" de plek,
    # zodat de volgorde niet afhangt van bestandsnamen.
    werken.sort(key=lambda w: (-int(w["jaar"]), int(w.get("volgorde") or 0)))

    jaren = [int(w["jaar"]) for w in werken]
    for taal, sjabloon_naam, uit in [("en", "index.html", "index.html"),
                                     ("nl", "index.nl.html", os.path.join("nl", "index.html"))]:
        lijst = "".join(bouw_werk(w, i, taal) for i, w in enumerate(werken))
        with open(os.path.join(HIER, "templates", sjabloon_naam), encoding="utf-8") as f:
            sjabloon = f.read()
        pagina = (sjabloon
                  .replace("{{WERKEN}}", lijst.rstrip("\n"))
                  .replace("{{EERSTE_DETAIL}}", detail_html(werken[0], taal))
                  .replace("{{OUDSTE}}", str(min(jaren)))
                  .replace("{{GESTRUCTUREERDE_DATA}}", gestructureerde_data(werken, taal)))
        with open(os.path.join(HIER, uit), "w", encoding="utf-8") as f:
            f.write(pagina)

    with open(os.path.join(HIER, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap(werken, [("", "1.0"), ("about.html", "0.8"), ("contact.html", "0.5"),
                                 ("nl/", "0.9"), ("nl/over-mij.html", "0.7"),
                                 ("nl/contact.html", "0.4")]))

    print("index.html en nl/index.html gebouwd: %d werken, %d foto's"
          % (len(werken), sum(len(w["fotos"]) for w in werken)))


if __name__ == "__main__":
    try:
        main()
    except Exception as fout:
        print("Bouwen mislukt: %s" % fout, file=sys.stderr)
        sys.exit(1)
