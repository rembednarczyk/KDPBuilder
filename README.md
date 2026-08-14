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
# generacja obrazów przez Gemini API (opcjonalnie):
pip install -e ".[gen]"
export GEMINI_API_KEY=twoj_klucz
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

### 2. Generacja obrazów (Gemini API)

Integracja z Gemini (Nano Banana) generuje surowe grafiki z promptów. Wymaga
`pip install -e ".[gen]"` i klucza `GEMINI_API_KEY`.

Z pliku promptów (z `book-prompts`):

```bash
python -m kdpbuilder.cli generate --out raw/ --prompts prompts.csv --trim 8.5x11 --image-size 4K
```

Albo budując prompty od razu:

```bash
python -m kdpbuilder.cli generate --out raw/ --theme axolotl --age 3-4 --style kawaii \
  --count 40 --trim 8.5x11 --image-size 4K
```

`--trim` ustawia aspect ratio pod format (8.5x11 to 3:4, 8.5x8.5 to 1:1). Bieg
wznawia się po przerwaniu (istniejące pliki pomija). `--sleep` reguluje tempo,
`--limit` generuje tylko pierwsze N, `--model` zmienia model.

Rozdzielczość pod druk: dla pełnostronicowej grafiki użyj `--image-size 4K`.
Test pokazał, że 4K na 8.5x11 to ~420 DPI, a 2K tylko ~210 DPI (za mało). 2K
wystarcza, gdy wzór jest mniejszy niż strona i składany w obrębie marginesów.

Domyślny model to Nano Banana Pro (`gemini-3-pro-image-preview`). Nazwy i ceny
modeli się zmieniają, potwierdź w dokumentacji Google. Klucz trzymaj w zmiennej
środowiskowej, nie w repo.

Po generacji przejrzyj każdą stronę (krok 6): brak artefaktów, zamknięte
kontury, pola nadające się do kolorowania. Dopiero potem składaj. Wynik AI to
półprodukt, nie plik gotowy do publikacji.

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

### Skan pikselowy (głębsza kontrola)

Komenda `scan` analizuje rzeczywiste piksele osadzonych obrazów w gotowym PDF,
głębiej niż walidator zgodności:

```bash
python -m kdpbuilder.cli scan interior.pdf --trim 8.5x11
```

Sprawdza: czystość (szarość z dala od krawędzi, czyli realne cieniowanie, a nie
antyaliasing), grubość linii w punktach (transformata odległości, kontrola min
0,75 pkt), drobne artefakty (małe spójne komponenty), tusz w marginesie oraz
liczbę zamkniętych obszarów (proxy konturów, eksperymentalne). `--json` daje
wynik maszynowy, `--page-data` dokłada dane per strona. To uzupełnienie walidatora,
nie zamiennik; ręczny przegląd stron dalej obowiązuje.

### Okładka (pełny wrap)

Moduł `cover` składa okładkę paperback KDP do jednego PDF: tył, grzbiet i przód
ze spadem. Szerokość grzbietu liczona z liczby stron i grubości papieru
(`specs`). Grafika przodu jest kolorowa i bez tekstu; tytuł składany jest przez
moduł, nie wypalany w grafice AI.

```bash
# z gotową grafiką przodu
python -m kdpbuilder.cli cover --out cover.pdf --trim 8.5x11 --pages 80 --paper bw_white \
  --front front.png --title "Aksolotki" --subtitle "Wielka kolorowanka dla dzieci 3-6 lat" \
  --author "Twoja Marka" --blurb "Tekst na tył okładki." --bg "#9BE0E6"

# albo z generacją grafiki przodu przez Gemini
python -m kdpbuilder.cli cover --out cover.pdf --trim 8.5x11 --pages 80 \
  --theme axolotl --generate-front --image-size 4K --title "Aksolotki" --author "Twoja Marka"
```

Tekst na grzbiecie pojawia się tylko od 79 stron (wymóg KDP). Kolory `--bg`,
`--text`, `--title-color` podajesz jako hex. Zawsze potwierdź finalny grzbiet w
kalkulatorze okładki KDP przed wgraniem, bo grubość papieru bywa aktualizowana.

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
