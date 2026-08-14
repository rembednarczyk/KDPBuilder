# KDPBuilder

Narzędzia do przygotowania kolorowanek dla dzieci pod Amazon KDP.

## Skill: kdp-compliance

Skill `kdp-compliance` trzyma specyfikacje druku KDP w jednym miejscu i uruchamia
automatyczną walidację gotowego wnętrza PDF. Znajduje się w
`.claude/skills/kdp-compliance/`.

Zawartość:

- `SKILL.md` — opis, workflow, uruchomienie walidatora i checklista ręczna.
- `references/kdp_specs.json` — jedno źródło prawdy dla specyfikacji KDP
  (wymiary, spad, DPI, marginesy, limity stron). Nie powielaj tych liczb w kodzie.
- `scripts/validate_kdp_pdf.py` — walidator PDF (PyMuPDF, opcjonalnie numpy).
- `requirements.txt` — zależności Pythona.

## Szybki start

```bash
pip install -r .claude/skills/kdp-compliance/requirements.txt

python .claude/skills/kdp-compliance/scripts/validate_kdp_pdf.py interior.pdf \
  --trim 8.5x11 --paper bw_white --check-single-sided
```

Kod wyjścia 0 gdy brak błędów krytycznych, 1 gdy jest FAIL. `--json` daje wynik
maszynowy do testów, `--strict` traktuje ostrzeżenia jak błędy i działa jako
bramka przed publikacją.

## Co walidator sprawdza automatycznie

Rozmiar strony (trim vs spad, spójny w całym pliku), limity liczby stron, efektywne
DPI, kolor w książce B&W, cieniowanie i gradienty, puste strony przy druku
jednostronnym, osadzenie fontów, szyfrowanie.

## Co zostaje do sprawdzenia ręcznie

Grubość linii (min 0,75 pkt), strefa bezpieczna, zamknięte kontury, artefakty z
generacji AI, realny wygląd druku. Zamów egzemplarz próbny przed skalowaniem tytułu.
Pełna checklista jest w `SKILL.md`.
