#!/usr/bin/env python3
"""
Bouwt index.html uit de bestanden in werken/ en templates/index.html.

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
DIRECT_LADEN = 4          # eerste vier foto's meteen, de rest bij naderen
BASIS = "https://hilde-windels.com/"


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


def beschrijving(werk):
    delen = [werk.get("techniek", ""), werk.get("afmetingen", ""), werk.get("collectie", "")]
    return ". ".join(d.strip() for d in delen if d and d.strip())


def attr(tekst):
    """Escapen voor een attribuut tussen dubbele aanhalingstekens.
    De apostrof blijft staan, die kan daar geen kwaad en leest prettiger."""
    return (str(tekst).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def bouw_werk(werk, volgnummer):
    fotos = [f for f in werk["fotos"] if f]
    if not fotos:
        raise ValueError("werk zonder foto: %s" % werk["titel"])

    for f in fotos:
        if not os.path.exists(os.path.join(FOTOMAP, f)):
            raise ValueError("foto ontbreekt: assets/works/%s (bij %s)" % (f, werk["titel"]))

    breedte, hoogte = jpeg_formaat(os.path.join(FOTOMAP, fotos[0]))
    detail = beschrijving(werk)
    alt = "%s, %s" % (werk["titel"], werk["jaar"])
    aantal = "%d foto's" % len(fotos) if len(fotos) > 1 else "foto"
    lui = "" if volgnummer < DIRECT_LADEN else ' loading="lazy"'

    if len(fotos) > 1:
        regel = ('<span class="tl__regel"><span class="tl__year">%s</span>'
                 '<span class="tl__meer">%d foto\'s</span></span>' % (werk["jaar"], len(fotos)))
    else:
        regel = '<span class="tl__year">%s</span>' % werk["jaar"]

    return (
        '        <li class="tl__item" data-fotos="%s" data-detail="%s" style="--ar:%.4f">\n'
        '          <button class="tl__frame" type="button" aria-label="%s">'
        '<img src="assets/works/%s"%s width="%d" height="%d" alt="%s" /></button>\n'
        '          <div class="tl__cap">\n'
        '            <h3 class="tl__title">%s</h3>\n'
        '            %s\n'
        '          </div>\n'
        '        </li>\n'
    ) % (
        attr("|".join(fotos)), attr(detail), breedte / hoogte,
        attr("%s, %s, %s bekijken" % (werk["titel"], werk["jaar"], aantal)),
        fotos[0], lui, breedte, hoogte, attr(alt),
        html.escape(werk["titel"]), regel,
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
                    regels.append("      <image:loc>%sassets/works/%s</image:loc>" % (BASIS, foto))
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


def gestructureerde_data(werken):
    """JSON-LD: wie de kunstenaar is en welke werken op de pagina staan."""
    kunstenaar = {
        "@type": "Person",
        "@id": BASIS + "#hilde-windels",
        "name": "Hilde Windels",
        "jobTitle": "Beeldend kunstenaar",
        "url": BASIS,
        "image": BASIS + "assets/preview.jpg",
        "birthPlace": {"@type": "Place", "name": "Tielt, Belgi\u00eb"},
        "address": {"@type": "PostalAddress", "addressLocality": "Gent",
                    "addressCountry": "BE"},
        "knowsAbout": ["Vlas", "Textielkunst", "Beeldende kunst"],
    }

    items = []
    for n, werk in enumerate(werken, start=1):
        items.append({
            "@type": "ListItem",
            "position": n,
            "item": {
                "@type": "VisualArtwork",
                "name": werk["titel"],
                "dateCreated": str(werk["jaar"]),
                "artform": "Textielkunst",
                "artMedium": werk.get("techniek", ""),
                "creator": {"@id": BASIS + "#hilde-windels"},
                "image": BASIS + "assets/works/" + werk["fotos"][0],
            },
        })

    data = {
        "@context": "https://schema.org",
        "@graph": [
            kunstenaar,
            {"@type": "WebSite", "url": BASIS, "name": "Hilde Windels",
             "inLanguage": "nl-BE", "about": {"@id": BASIS + "#hilde-windels"}},
            {"@type": "ItemList", "name": "Werk van Hilde Windels, 1990 tot heden",
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

    lijst = "".join(bouw_werk(w, i) for i, w in enumerate(werken))

    with open(os.path.join(HIER, "templates", "index.html"), encoding="utf-8") as f:
        sjabloon = f.read()

    jaren = [int(w["jaar"]) for w in werken]
    pagina = (sjabloon
              .replace("{{WERKEN}}", lijst.rstrip("\n"))
              .replace("{{EERSTE_DETAIL}}", html.escape(beschrijving(werken[0])))
              .replace("{{PERIODE}}", "%d tot %d" % (max(jaren), min(jaren))))

    pagina = pagina.replace("{{GESTRUCTUREERDE_DATA}}", gestructureerde_data(werken))

    with open(os.path.join(HIER, "index.html"), "w", encoding="utf-8") as f:
        f.write(pagina)

    with open(os.path.join(HIER, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap(werken, [("", "1.0"), ("over-mij.html", "0.8"),
                                 ("contact.html", "0.5")]))

    print("index.html gebouwd: %d werken, %d foto's"
          % (len(werken), sum(len(w["fotos"]) for w in werken)))


if __name__ == "__main__":
    try:
        main()
    except Exception as fout:
        print("Bouwen mislukt: %s" % fout, file=sys.stderr)
        sys.exit(1)
