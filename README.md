# KDPBuilder

Powtarzalny pipeline do generowania i składania kolorowanek dla dzieci pod
Amazon KDP. Bierze surową grafikę liniową z generatywnego AI, czyści ją do
druku, składa jednostronne wnętrze PDF i sprawdza je walidatorem KDP.

Styl produktu: bold and easy dla wieku 3-6 lat. Grube kontury, proste kształty,
jeden wzór na stronę, pusta strona z tyłu (druk jednostronny), czarne linie na
czystej bieli.

## Struktura

```
kdpbuilder/                 pakiet pipeline
  prompts.py                krok 1: prompty pod line art
  imageprep.py              kroki 3-4: czyszczenie do B&W, pogrubianie linii
  assemble.py               kroki 5-6: skalowanie do DPI, składanie wnętrza PDF
  specs.py                  odczyt specyfikacji KDP z jednego źródła prawdy
  cli.py                    interfejs wiersza poleceń
.claude/skills/kdp-compliance/   skill z walidatorem i specyfikacjami KDP
  references/kdp_specs.json  jedyne źródło prawdy dla liczb (wymiary, spad, DPI)
  scripts/validate_kdp_pdf.py  walidator gotowego wnętrza
tests/                      testy pipeline i walidacji
```

Specyfikacje KDP mają jedno źródło prawdy: `kdp_specs.json` w skillu.
`kdpbuilder.specs` czyta ten plik, więc generator i walidator się nie rozjadą.
Nie powielaj liczb w kodzie.

## Instalacja

```bash
pip install -r requirements.txt
# lub jako pakiet z komendą `kdpbuilder`:
pip install -e .
```

## Workflow (kroki 1-6 z instrukcji projektu)

### 1. Prompt pod grafikę liniową

Prompty składane są z biblioteki `kdpbuilder/data/prompts.json` (jedno źródło
prawdy dla treści promptów): temat, grupa wieku i stylistyka. Zobacz co jest
dostępne:

```bash
python -m kdpbuilder.cli catalog
```

Grupy wieku: `3-4`, `5-6`, `6-7` (rosnąca złożoność i cieńsza kreska z wiekiem).
Stylistyki: `kawaii`, `cozy`, `fantasy_costume`, `seasonal`, `habitat_scene`,
`realistic_simple`, `patterned`. Sezony dla `seasonal`: christmas, halloween,
easter, birthday, valentine.

Pojedynczy prompt (temat + scena + wiek + styl):

```bash
python -m kdpbuilder.cli prompt --theme axolotl --scene "sitting inside a teacup" \
  --age 3-4 --style kawaii
```

Prompty na całą książkę, jeden na stronę (styl stały, scena zmienna, co trzyma
spójność kreski z kroku 2):

```bash
python -m kdpbuilder.cli book-prompts --theme axolotl --age 5-6 --style kawaii \
  --count 40 --format csv --out prompts.csv
```

Zwraca prompt pozytywny i negatywny w stylu bold and easy. Grafikę generujesz
swoim narzędziem AI. Dla spójności użyj tego samego seeda lub referencji stylu na
wszystkich stronach: wygeneruj kilka, potwierdź jeden wygląd, dopiero potem resztę.

### 3-4. Czyszczenie do czystego B&W

```bash
python -m kdpbuilder.cli prep raw/ clean/ --thicken 1
```

Progowanie usuwa szarości, cienie i gradienty (domyślnie Otsu, albo
`--threshold 0-255`). `--thicken N` pogrubia linie o N pikseli. Autokadrowanie
wyrównuje ramkę wokół wzoru (`--no-crop` wyłącza).

### 5-6. Składanie wnętrza PDF

```bash
python -m kdpbuilder.cli assemble clean/ --out interior.pdf --trim 8.5x11
```

Każdy wzór trafia na stronę w dokładnym formacie KDP, przy 300 DPI, z pustą
stroną z tyłu (druk jednostronny). Dla grafiki sięgającej krawędzi dodaj
`--bleed` (strona = format + spad, wzór wypełnia do brzegu).

### Bramka: walidacja

```bash
python -m kdpbuilder.cli validate interior.pdf --trim 8.5x11 --strict
```

Kod wyjścia 0 gdy brak błędów krytycznych, 1 przy FAIL (a z `--strict` również
przy ostrzeżeniach). Nadaje się jako krok build przed publikacją.

### Wszystko naraz

```bash
python -m kdpbuilder.cli build raw/ --out interior.pdf --trim 8.5x11 \
  --thicken 1 --strict
```

Czyści, składa i waliduje w jednym przebiegu.

## Co jest automatyczne, a co ręczne

Automatycznie: konwersja do B&W, usuwanie szarości i gradientów, pogrubianie
linii, skalowanie do 300 DPI, składanie jednostronne ze spadem lub bez, kontrola
rozmiaru stron, limitów, DPI, koloru, cieniowania, pustych stron, fontów i
szyfrowania.

Ręcznie (krok 6 i publikacja): grubość linii w punktach, strefa bezpieczna,
zamknięte kontury i pola do kolorowania, artefakty z generacji AI, realny
wygląd druku. Zamów egzemplarz próbny przed skalowaniem tytułu. Pełna checklista
jest w `.claude/skills/kdp-compliance/SKILL.md`.

## Testy

```bash
python -m pytest
```

Sprawdzają odczyt specyfikacji, czyszczenie obrazów, geometrię składania (format,
spad, 300 DPI, puste strony) oraz przejście gotowego PDF przez walidator.

## Zgodność i ryzyka

Przy publikacji zaznacz w KDP "Yes, AI-Generated" dla obrazów. Nie wrzucaj masowo
niemal identycznych tytułów w jedną niszę. Bez postaci chronionych, celebrytów i
znaków towarowych. Czysto AI-owa grafika ma ograniczoną ochronę prawnoautorską.
Kwestie podatkowe (źródło przychodu, ryczałt) potwierdź z doradcą podatkowym.
