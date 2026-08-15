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
- Pierwszy tytuł w produkcji: **aksolotki**, styl kawaii, format 8.5x11, 40
  wzorów (80 stron, druk jednostronny). Wiek w metadanych: **4-8 lat** (szerszy
  zasięg, jak konkurencja). Wnętrze dostrojone pod 5-6, ale celuj w nieco
  bogatsze wzory (część wyszła za prosta); używaj profilu wieku `4-8`.
- Domyślny model obrazowy: **Nano Banana 2** (`gemini-3.1-flash-image`). Pro
  (`gemini-3-pro-image`) tylko gdy potrzebna najwyższa jakość, np. złożona
  okładka.
- **Format standardowy: 40 wzorów = 80 stron** (druk jednostronny, każdy wzór z
  pustą stroną z tyłu). Przy 80 stronach KDP pozwala na tekst na grzbiecie
  (min 79). Pamiętaj, że przy druku jednostronnym liczba stron to dwa razy
  liczba wzorów.

## Architektura

- `kdpbuilder/` pakiet pipeline: `prompts` (krok 1), `generate` (Gemini),
  `imageprep` (kroki 3-4), `assemble` (kroki 5-6), `cover`, `specs`, `cli`.
- `.claude/skills/kdp-compliance/` skill z walidatorem i specyfikacjami.
- `references/kdp_specs.json` w skillu to **jedyne źródło prawdy** dla liczb
  (wymiary, spad, DPI, marginesy, limity stron, dane okładki). Nie powielaj
  specyfikacji w kodzie; czytaj je przez `kdpbuilder.specs`.
- Biblioteka promptów: `kdpbuilder/data/prompts.json`.
- Spec książki: `books/<slug>.json`. Jedno źródło prawdy dla danego tytułu
  (tytuł, podtytuł, autor, blurb, kolory, format, liczba stron). Okładkę składa
  się przez `cover --book books/<slug>.json`; jawne flagi wciąż wygrywają ze
  specem. Kanoniczny tytuł/podtytuł/autor mieszkają tutaj, nie w kodzie.

## Warstwa tekstu vs warstwa obrazu (decyzja)

Dwie osobne warstwy, nie mieszaj ich źródeł:

- **Warstwa tekstu** (tytuł, podtytuł, blurb, 7 tagów, opis sprzedażowy):
  zasilana wiedzą SEO i keywords. Kanoniczny tekst tytułu w `books/<slug>.json`,
  research w `docs/seo_*`. Tekst na okładce **zawsze składa skrypt** (poprawna
  polska pisownia, diakrytyki), nigdy nie jest wypalany w obraz przez AI.
- **Warstwa obrazu** (grafika przodu, miniaturki, dekoracje pod sloty):
  zasilana **tematem i stylem**, nie słowami kluczowymi. SEO to tekst
  wyszukiwania, nie wygląd, więc w promptach obrazowych byłby szumem. Sloty
  wizualne (podtytuł, blurb) mają **własne, oddzielne prompty** dekoracji z
  `prompts.json` (`decoration_assets`). To wystarczy, keywords ich nie zasilają.

Sloty pod dekorację z AI na okładce: `--subtitle-asset`, `--blurb-asset` (asset
to tło, tekst dalej składa skrypt) oraz `--title-asset` (asset JEST tytułem, z
wypalonymi literami, skrypt nie rysuje tekstu). `--title-asset` to jedyny
wyjątek od reguły "tekst zawsze składa skrypt": przy nim liternictwo robi AI
albo gotowy PNG. Jeśli używasz, koniecznie sprawdź polską pisownię i diakrytyki
na wyniku, bo model potrafi je przekręcić. Tytuł napędzany specem dalej idzie na
grzbiet składany skryptem, niezależnie od assetu.

## Komendy

Spec książki (`--book books/<slug>.json`) zasila `book-prompts`, `generate` i
`cover`: temat, wiek, styl, liczbę wzorów, trim, teksty i kolory okładki. Jawne
flagi wciąż wygrywają ze specem.

```bash
python -m kdpbuilder.cli catalog
python -m kdpbuilder.cli book-prompts --book books/axolotl_5-6.json --format csv --out prompts.csv
python -m kdpbuilder.cli generate --out raw/ --book books/axolotl_5-6.json
python -m kdpbuilder.cli build raw/ --out interior.pdf --trim 8.5x11 --thicken 1 --strict
python -m kdpbuilder.cli scan interior.pdf --trim 8.5x11
python -m kdpbuilder.cli cover --out cover.pdf --book books/axolotl_5-6.json --generate-front
python -m pytest
```

## Zgodność KDP, zawsze pilnuj

- Bez znaków towarowych, marek, nazw gier (w tym nie używaj słowa oznaczającego
  popularną grę kojarzoną z aksolotkami), celebrytów.
- Przy publikacji zaznacz "Yes, AI-Generated" dla obrazów.
- **Bez tekstu w grafikach.** Kolorowanka to sam line art, negatyw wymusza brak
  napisów. Jeśli model mimo to wstawi jakiś napis (zdarzało się np. "Story"),
  musi być po polsku, nigdy po angielsku. Stronę z angielskim napisem odrzuć
  albo zregeneruj. Tekst na okładce składa moduł po polsku, nie AI.
- Nie wrzucaj masowo niemal identycznych tytułów w jedną niszę. Każdy tytuł
  odrębny, z własną grafiką, tytułem i opisem.
- Wnętrze generuj w **2K**, nie 4K. Pipeline składa wzór na płótnie strony w
  300 DPI, więc finalny PDF ma 300 DPI niezależnie od źródła, a walidator
  przechodzi. Dla bold-and-easy line artu 2K jest wizualnie nie do odróżnienia
  od 4K (sprawdzone), a kosztuje ok. połowę. 4K trzymaj dla kolorowej okładki.
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

## Koszty generacji (pilnuj)

Realny koszt to prawdziwe pieniądze. 40 wzorów w 4K NB2 kosztowało ok. 20 zł.
Dźwignie oszczędności, od najważniejszej:

- **2K zamiast 4K** dla wnętrza. Około połowa kosztu, bez straty jakości (pipeline
  i tak skaluje na stronę 300 DPI). To domyślne ustawienie `generate`.
- **Model flash-lite** (`gemini-3.1-flash-lite-image`) do przetestowania, jeszcze
  taniej, jeśli jakość się utrzyma.
- **Batch API** daje kolejne 50% zniżki, kosztem pracy asynchronicznej (do
  wdrożenia w przyszłości).
- **Najpierw próbka**, potem całość. Zawsze generuj kilka wzorów, potwierdź styl,
  dopiero potem resztę. Resume nie regeneruje gotowych plików.
- **Regeneruj tylko słabe strony**, nie całą książkę. Usuń pliki wybranych
  wzorów i uruchom `generate` z resume; dogeneruje tylko brakujące.

## Baza wiedzy (reguła)

Zbieramy wiedzę. Każde badanie, decyzja i wniosek ląduje jako plik markdown w
`docs/`, a nie tylko w rozmowie. Odwołuj się do tych plików z `CLAUDE.md` i z
`docs/README.md` (indeks). Nowy research dopisuj do indeksu. Dzięki temu wiedza
przechodzi między sesjami i się nie gubi. Aktualne dokumenty:

- `docs/README.md` indeks bazy wiedzy.
- `docs/TODO.md` plan i backlog.
- `docs/seo_axolotl_pl.md` badanie SEO pod Amazon.pl (aksolotki).

## SEO i słowa kluczowe (ważne)

Rynek polski wymaga osobnego badania słów kluczowych. Rodzice w Polsce
wyszukują inaczej niż klienci w USA, więc nie tłumacz fraz z angielskiego.
Tytuł, podtytuł, opis sprzedażowy i siedem tagów w panelu KDP opracowuj po
polsku na podstawie lokalnego wolumenu wyszukiwań. Szczegóły w `docs/TODO.md`.

## Podatki

Przychody z KDP wymagają ustalenia źródła (prawa majątkowe albo działalność) i
mogą nie mieścić się w ryczałcie. Przy kwestiach podatkowych przypominaj o
potwierdzeniu z doradcą, nie udawaj pewności.
