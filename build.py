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


def lokaal(pad):
    """Van /assets/works/x.jpg naar het bestand op schijf."""
    return os.path.join(HIER, pad.lstrip("/"))
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


def regels(werk):
    """De losse velden van een werk, elk opgeschoond, als (soort, tekst).

    Bestand tegen hoe mensen echt typen: regeleindes, dubbele spaties en een
    punt aan het eind van een veld. Zonder dit wordt "stuks." plus ". " samen
    "stuks..", en dat is precies wat er gebeurde.
    """
    fotograaf = " ".join(str(werk.get("fotograaf", "")).split())
    velden = [("materiaal", werk.get("materiaal", "")),
              ("maten", werk.get("afmetingen", "")),
              ("collectie", werk.get("collectie", "")),
              ("foto", "Photo %s" % fotograaf if fotograaf else "")]
    schoon = []
    for soort, deel in velden:
        tekst = " ".join(str(deel).split())      # regeleindes en dubbele spaties weg
        tekst = tekst.rstrip(". ")               # eindpunt weg, de opmaak scheidt zelf
        # "(each)" nooit los op een nieuwe regel laten vallen
        tekst = tekst.replace(" (each)", "\u00a0(each)")
        if tekst:
            schoon.append((soort, tekst))
    return schoon


def beschrijving(werk):
    """De velden aan elkaar tot een zin, voor zoekmachines."""
    return ". ".join(tekst for _, tekst in regels(werk))


def detail_html(werk):
    """De velden als losse regels, elk met een eigen klasse voor de opmaak."""
    return "".join('<span class="d d--%s">%s</span>' % (soort, html.escape(tekst))
                   for soort, tekst in regels(werk))


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
        if not os.path.exists(lokaal(f)):
            raise ValueError("foto ontbreekt: %s (bij %s)" % (f, werk["titel"]))

    breedte, hoogte = jpeg_formaat(lokaal(fotos[0]))
    detail = detail_html(werk)
    alt = "%s, %s" % (werk["titel"], werk["jaar"])
    aantal = "%d photos" % len(fotos) if len(fotos) > 1 else "photo"
    lui = "" if volgnummer < DIRECT_LADEN else ' loading="lazy"'

    if len(fotos) > 1:
        regel = ('<span class="tl__regel"><span class="tl__year">%s</span>'
                 '<span class="tl__meer">%d photos</span></span>' % (werk["jaar"], len(fotos)))
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
        attr("View %s, %s, %s" % (werk["titel"], werk["jaar"], aantal)),
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


def gestructureerde_data(werken):
    """JSON-LD: wie de kunstenaar is en welke werken op de pagina staan."""
    kunstenaar = {
        "@type": "Person",
        "@id": BASIS + "#hilde-windels",
        "name": "Hilde Windels",
        "jobTitle": "Visual artist",
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
                "name": werk["titel"],
                "dateCreated": str(werk["jaar"]),
                "artform": "Textile art",
                "artMedium": werk.get("materiaal", ""),
                "creator": {"@id": BASIS + "#hilde-windels"},
                "image": BASIS + werk["fotos"][0].lstrip("/"),
            },
        })

    data = {
        "@context": "https://schema.org",
        "@graph": [
            kunstenaar,
            {"@type": "WebSite", "url": BASIS, "name": "Hilde Windels",
             "inLanguage": "en", "about": {"@id": BASIS + "#hilde-windels"}},
            {"@type": "ItemList", "name": "Work by Hilde Windels, 1990 to present",
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
              .replace("{{EERSTE_DETAIL}}", detail_html(werken[0]))
              .replace("{{OUDSTE}}", str(min(jaren))))

    pagina = pagina.replace("{{GESTRUCTUREERDE_DATA}}", gestructureerde_data(werken))

    with open(os.path.join(HIER, "index.html"), "w", encoding="utf-8") as f:
        f.write(pagina)

    with open(os.path.join(HIER, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap(werken, [("", "1.0"), ("about.html", "0.8"),
                                 ("contact.html", "0.5")]))

    print("index.html gebouwd: %d werken, %d foto's"
          % (len(werken), sum(len(w["fotos"]) for w in werken)))


if __name__ == "__main__":
    try:
        main()
    except Exception as fout:
        print("Bouwen mislukt: %s" % fout, file=sys.stderr)
        sys.exit(1)
