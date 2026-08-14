# Baza wiedzy KDPBuilder

Zbieramy wiedzę. Każde badanie, decyzja i wniosek trafia tu jako plik markdown,
żeby przechodził między sesjami i się nie gubił. Dopisuj nowe dokumenty do tego
indeksu. Pamięć projektu i reguły są w `../CLAUDE.md`.

## Dokumenty

- [TODO.md](TODO.md) plan i backlog zadań.
- [seo_axolotl_pl.md](seo_axolotl_pl.md) badanie SEO pod Amazon.pl dla tytułu z
  aksolotkami: tytuł, podtytuł, 7 tagów, opis, kategorie, ryzyka.
- [seo_axolotl_en.md](seo_axolotl_en.md) pakiet SEO pod Amazon.com (EN):
  tytuł, podtytuł, 7 tagów, opis, kategorie.
- [cover_slots.svg](cover_slots.svg) mapa okładki: które obszary składa skrypt,
  które są slotami pod dekoracje z AI, gdzie idzie logo i strefa kodu kreskowego.

Narzędzie: `python -m kdpbuilder.cli keywords <pliki> --contains niche` wyciąga
kandydackie frazy z częstością z zapisanych aukcji konkurencji. Przydatne flagi:
`--segment` (tnie n-gramy na markupie, zalecane dla dumpów HTML), `--normalize`
(skleja polską odmianę), `--csv plik.csv` (eksport z flagą 50 znaków KDP),
`--pack phrases|dense` (pakuje w 7 pól słów kluczowych KDP). Uwaga: auto-pack
potrafi wyciągnąć fragment tytułu konkurenta, więc przejrzyj wynik i wyrzuć
cudze tytuły i marki. Funkcja `autocomplete()` (podpowiedzi Amazona) działa tylko
lokalnie z `pip install ".[keywords]"`, nie z tego środowiska (proxy), i podlega
ToS Amazona, więc używaj oszczędnie.

## Jak dodawać wiedzę

- Nowy research albo decyzja: osobny plik `docs/nazwa.md`, po polsku.
- Dopisz go do listy powyżej i, jeśli to reguła lub stały fakt, do `CLAUDE.md`.
- Trzymaj jedno źródło prawdy. Specyfikacje KDP są w
  `.claude/skills/kdp-compliance/references/kdp_specs.json`, nie powielaj ich.
