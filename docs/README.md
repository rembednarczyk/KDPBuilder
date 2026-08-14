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

Narzędzie: `python -m kdpbuilder.cli keywords <pliki> --contains niche` wyciąga
kandydackie frazy z częstością z zapisanych aukcji konkurencji.

## Jak dodawać wiedzę

- Nowy research albo decyzja: osobny plik `docs/nazwa.md`, po polsku.
- Dopisz go do listy powyżej i, jeśli to reguła lub stały fakt, do `CLAUDE.md`.
- Trzymaj jedno źródło prawdy. Specyfikacje KDP są w
  `.claude/skills/kdp-compliance/references/kdp_specs.json`, nie powielaj ich.
