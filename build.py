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

HIER = os.path.dirname(os.path.abspath(__file__))
FOTOMAP = os.path.join(HIER, "assets", "works")
DIRECT_LADEN = 4          # eerste vier foto's meteen, de rest bij naderen


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
        '          <span class="tl__cap">\n'
        '            <span class="tl__title">%s</span>\n'
        '            %s\n'
        '          </span>\n'
        '        </li>\n'
    ) % (
        attr("|".join(fotos)), attr(detail), breedte / hoogte,
        attr("%s, %s, %s bekijken" % (werk["titel"], werk["jaar"], aantal)),
        fotos[0], lui, breedte, hoogte, attr(alt),
        html.escape(werk["titel"]), regel,
    )


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

    with open(os.path.join(HIER, "index.html"), "w", encoding="utf-8") as f:
        f.write(pagina)

    print("index.html gebouwd: %d werken, %d foto's"
          % (len(werken), sum(len(w["fotos"]) for w in werken)))


if __name__ == "__main__":
    try:
        main()
    except Exception as fout:
        print("Bouwen mislukt: %s" % fout, file=sys.stderr)
        sys.exit(1)
