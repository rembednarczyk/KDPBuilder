# KDPBuilder: pamięć projektu

Ten plik jest trwałą pamięcią projektu. Czyta się go na starcie każdej sesji.
Aktualizuj go, gdy zmienia się stan, decyzje albo konwencje.

## Cel

Powtarzalny pipeline do generowania i składania kolorowanek dla dzieci pod
Amazon KDP, równolegle na rynek polski (Amazon.pl) i anglojęzyczny (Amazon.com).
Grafiki z generatywnego AI, doprowadzane do jakości druku, składane w gotowe
wnętrze i okładkę, walidowane pod KDP.

## Marka i stan

- Marka wydawnicza (pen name): **Kolorowe Skarby**. Używaj jej na wszystkich
  okładkach i w metadanych.
- Pierwszy tytuł w produkcji: **aksolotki, grupa wieku 5-6 lat**, styl kawaii,
  format 8.5x11, 40 wzorów (80 stron, druk jednostronny).
- Domyślny model obrazowy: **Nano Banana 2** (`gemini-3.1-flash-image`). Pro
  (`gemini-3-pro-image`) tylko gdy potrzebna najwyższa jakość, np. złożona
  okładka.

## Architektura

- `kdpbuilder/` pakiet pipeline: `prompts` (krok 1), `generate` (Gemini),
  `imageprep` (kroki 3-4), `assemble` (kroki 5-6), `cover`, `specs`, `cli`.
- `.claude/skills/kdp-compliance/` skill z walidatorem i specyfikacjami.
- `references/kdp_specs.json` w skillu to **jedyne źródło prawdy** dla liczb
  (wymiary, spad, DPI, marginesy, limity stron, dane okładki). Nie powielaj
  specyfikacji w kodzie; czytaj je przez `kdpbuilder.specs`.
- Biblioteka promptów: `kdpbuilder/data/prompts.json`.

## Komendy

```bash
python -m kdpbuilder.cli catalog
python -m kdpbuilder.cli book-prompts --theme axolotl --age 5-6 --style kawaii --count 40 --format csv --out prompts.csv
python -m kdpbuilder.cli generate --out raw/ --prompts prompts.csv --trim 8.5x11 --image-size 4K
python -m kdpbuilder.cli build raw/ --out interior.pdf --trim 8.5x11 --thicken 1 --strict
python -m kdpbuilder.cli cover --out cover.pdf --trim 8.5x11 --pages 80 --theme axolotl --generate-front --title "..." --author "Kolorowe Skarby"
python -m pytest
```

## Zgodność KDP, zawsze pilnuj

- Bez znaków towarowych, marek, nazw gier (w tym nie używaj słowa oznaczającego
  popularną grę kojarzoną z aksolotkami), celebrytów.
- Przy publikacji zaznacz "Yes, AI-Generated" dla obrazów.
- Nie wrzucaj masowo niemal identycznych tytułów w jedną niszę. Każdy tytuł
  odrębny, z własną grafiką, tytułem i opisem.
- 4K pod pełnostronicową grafikę (ok. 420 DPI na 8.5x11). 2K to za mało (~210).
- Zawsze potwierdź finalny grzbiet okładki w kalkulatorze KDP.
- Kontrole ręczne przed publikacją: grubość linii, strefa bezpieczna, zamknięte
  kontury, brak artefaktów, egzemplarz próbny.

## Bezpieczeństwo

- Klucz Gemini tylko w zmiennej środowiskowej `GEMINI_API_KEY`. Nigdy w repo,
  czacie ani commit message. `.gitignore` blokuje `.env` i `*.key`.

## Styl tekstu (dla każdego tekstu, PL)

- Bez myślników (em dash).
- Bez konstrukcji "to nie X, to Y".
- Wprost i twierdząco, bez sztucznego napięcia i frazesów marketingowych.
- Opisy pod Amazon.com po angielsku, prosto i naturalnie.

## SEO i słowa kluczowe (ważne)

Rynek polski wymaga osobnego badania słów kluczowych. Rodzice w Polsce
wyszukują inaczej niż klienci w USA, więc nie tłumacz fraz z angielskiego.
Tytuł, podtytuł, opis sprzedażowy i siedem tagów w panelu KDP opracowuj po
polsku na podstawie lokalnego wolumenu wyszukiwań. Szczegóły w `docs/TODO.md`.

## Podatki

Przychody z KDP wymagają ustalenia źródła (prawa majątkowe albo działalność) i
mogą nie mieścić się w ryczałcie. Przy kwestiach podatkowych przypominaj o
potwierdzeniu z doradcą, nie udawaj pewności.
