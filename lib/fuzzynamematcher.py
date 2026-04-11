from typing import List, Tuple
from rapidfuzz.distance import DamerauLevenshtein
import jellyfish
import phonetics
import unicodedata
import re

# Visuelle Homoglyphen: kyrillische und griechische Zeichen, die lateinischen ähneln.
# Werden VOR der NFKD-Normalisierung ersetzt, weil NFKD sie sonst kommentarlos löscht.
_HOMOGLYPH_MAP: dict = {
    # Kyrillisch → Lateinisch (visuell)
    'а': 'a', 'А': 'a',   # кyr. a → lat. a
    'е': 'e', 'Е': 'e',   # кyr. e → lat. e
    'о': 'o', 'О': 'o',   # кyr. o → lat. o
    'с': 'c', 'С': 'c',   # кyr. s (sieht aus wie c) → lat. c
    'х': 'x', 'Х': 'x',   # кyr. kh → lat. x
    'у': 'y', 'У': 'y',   # кyr. u (sieht aus wie y) → lat. y
    'р': 'p', 'Р': 'p',   # кyr. r (sieht aus wie p) → lat. p
    'В': 'b',              # кyr. V (sieht aus wie B) → lat. b
    'Н': 'h',              # кyr. N (sieht aus wie H) → lat. h
    'К': 'k', 'к': 'k',   # кyr. K → lat. k
    'М': 'm', 'м': 'm',   # кyr. M → lat. m
    'Т': 't', 'т': 't',   # кyr. T → lat. t
    'і': 'i', 'І': 'i',   # ukr. i → lat. i
    'ї': 'i', 'Ї': 'i',   # ukr. yi → lat. i
    'ё': 'e', 'Ё': 'e',   # кyr. yo → lat. e
    'н': 'h', 'н': 'h',   # кyr. н (in CIS-Gaming als H-Ersatz genutzt) → lat. h
    # Griechisch → Lateinisch (visuell)
    'α': 'a', 'Α': 'a',
    'ε': 'e', 'Ε': 'e',
    'ο': 'o', 'Ο': 'o',
    'ι': 'i', 'Ι': 'i',
    'υ': 'u', 'Υ': 'y',
    'ρ': 'r', 'Ρ': 'r',
    'ν': 'v',
    'η': 'n',
    'ω': 'w', 'Ω': 'w',
    # Sonstige visuell ähnliche Zeichen
    'ı': 'i',              # türkisches dotless-i
    'ℓ': 'l',              # Skript-l
    'Ꞵ': 'b',
    # Unsichtbare / Null-Breite Zeichen → leer (werden danach durch [^a-z0-9] entfernt)
    '\u200b': '',          # zero-width space
    '\u200c': '',          # zero-width non-joiner
    '\u200d': '',          # zero-width joiner
    '\u00ad': '',          # soft hyphen
    '\ufeff': '',          # BOM
}

# Übersetzungstabelle für str.translate (schneller als replace-Schleife)
_HOMOGLYPH_TABLE = str.maketrans(_HOMOGLYPH_MAP)


class FuzzyNameMatcher:
    def __init__(self, threshold: float = 0.75):
        self.blacklist: List[str] = []
        self.whitelist: List[str] = []
        self.phonetic_blacklist_dm: List[str] = []
        self.phonetic_blacklist_sx: List[str] = []
        self.threshold = threshold
        self.leet_map = {
            '0': 'o', '1': 'i', '3': 'e', '4': 'a',
            '@': 'a', '$': 's', '5': 's', '7': 't',
            '6': 'g', '8': 'b', '2': 'z', '|': 'i',
            '(': 'c', '+': 't', '!': 'i', '9': 'g',
        }

    def set_namelist(self, blacklist: List[str]):
        """Blacklist übernehmen und phonetische Codes vorbereiten"""
        self.blacklist_orig = list(blacklist)
        self.blacklist = [self._normalize(name) for name in blacklist]
        # Kurze Einträge (≤ 2 Buchstaben im Original, z.B. "Z", "SA", "SS") oder rein numerische
        # Einträge (z.B. "88", "14", "420") sollen nur als eigenständiges Wort/Token matchen,
        # nicht als Substring in einem längeren Namen.
        self.blacklist_is_short = [
            len(re.sub(r'[^a-zA-Z]', '', name)) <= 2 for name in blacklist
        ]
        self.phonetic_blacklist_dm = [self._phonetic_dm(name) for name in self.blacklist]
        self.phonetic_blacklist_sx = [self._phonetic_sx(name) for name in self.blacklist]

    def set_whitelist(self, whitelist: List[str]):
        """Whitelist für bekannte harmlose Namen setzen"""
        self.whitelist = [self._normalize(w) for w in whitelist]

    def get_match(self, name: str) -> Tuple[float, str]:
        """Gibt Wahrscheinlichkeit und den Blacklist-Treffer zurück"""
        return self._compute_probability(name)

    def check_name(self, name: str) -> bool:
        """Prüft, ob der Name auf der Blacklist ist"""
        prob, _ = self._compute_probability(name)
        return prob >= self.threshold

    def get_probability(self, name: str) -> float:
        """Gibt Wahrscheinlichkeit zurück (0..1)"""
        prob, _ = self._compute_probability(name)
        return prob

    # --- internal methods ---

    def _normalize_no_leet(self, name: str) -> str:
        """Normalisierung ohne Leet-Substitution (Ziffern bleiben als Ziffern).
        Dient als Referenz: Trifft ein Blacklist-Term hier, ist es ein nativer Buchstaben-Match
        und kein Artefakt der Leet-Konvertierung von Ziffern."""
        name = name.translate(_HOMOGLYPH_TABLE)
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
        name = name.lower()
        name = re.sub(r'(.)\1{2,}', r'\1', name)
        name = re.sub(r'[^a-z0-9]', '', name)
        return name

    def _normalize(self, name: str) -> str:
        # Schritt 1: Visuelle Homoglyphen ersetzen (kyrillisch/griechisch → lateinisch)
        name = name.translate(_HOMOGLYPH_TABLE)
        # Schritt 2: Unicode-Normalisierung (Akzente, verbleibende Komposita)
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
        name = name.lower()
        # Schritt 3: Leetspeak ersetzen
        for k, v in self.leet_map.items():
            name = name.replace(k, v)
        # Schritt 4: Dreifach+ wiederholte Zeichen kollabieren (hiiitler → hitlr, aaaa → a)
        name = re.sub(r'(.)\1{2,}', r'\1', name)
        # Schritt 5: Sonderzeichen und Leerzeichen entfernen
        name = re.sub(r'[^a-z0-9]', '', name)
        return name

    def _tokenize(self, raw_name: str) -> List[str]:
        """Eingabename in Tokens aufteilen (Leerzeichen, Underscore, camelCase).
        Nur Tokens mit mind. 3 Zeichen, um Einzel-/Zwei-Zeichen-Fragmente aus
        CamelCase-Splits zu ignorieren (z.B. 'z' aus 'zEEEEtKa')."""
        split = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw_name)
        tokens = re.findall(r'[a-zA-Z0-9]+', split)
        normalized = list({self._normalize(t) for t in tokens if len(t) >= 3})
        return normalized

    def _natural_tokens(self, raw_name: str) -> List[str]:
        """Tokens nur an natürlichen Grenzen (Leerzeichen, Underscore, Ziffernblöcke) —
        kein CamelCase-Split. Für kurze Blacklist-Terme, die als ganzes Wort stehen müssen.
        Buchstaben- UND Zifferngruppen werden separat extrahiert, damit z.B. '88' als
        eigenständiger Token erkannt wird ('88' → leet → 'bb' matcht Blacklist-Eintrag '88')."""
        tokens = re.findall(r'[a-zA-Z]+|[0-9]+', raw_name)
        return list({self._normalize(t) for t in tokens if t})

    def _phonetic_dm(self, name: str) -> str:
        """Double Metaphone Code"""
        codes = phonetics.dmetaphone(name)
        return codes[0] if codes and codes[0] else ""

    def _phonetic_sx(self, name: str) -> str:
        """Soundex Code"""
        return jellyfish.soundex(name) if name else ""

    def _is_whitelisted(self, name_norm: str) -> bool:
        """True wenn der normalisierte Name einem Whitelist-Eintrag entspricht oder damit beginnt"""
        return any(name_norm == w or name_norm.startswith(w) for w in self.whitelist)

    def _sliding_window_score(self, name_norm: str, blk: str, min_ratio: float = 0.24) -> float:
        """
        Prüft alle Teilstrings des normalisierten Namens der Länge len(blk) ± 1
        auf DL-Ähnlichkeit. Fängt Fälle wie "xxhitlerxx" oder eingebettete
        leicht veränderte Terme (Padding-Bypass).
        Nur für Blacklist-Terme mit mindestens 3 Zeichen, um False Positives zu vermeiden.

        min_ratio: Mindest-Längenratio len(blk)/len(name_norm). Für native Buchstaben-Matches
        (Term im Pre-Leet-Namen vorhanden) wird ein niedrigerer Wert (0.24) verwendet,
        für reine Leet-Digit-Matches ein höherer (0.35), um z.B. "gas" aus "9457" zu vermeiden.
        """
        if len(blk) < 3 or len(name_norm) <= len(blk):
            return 0.0

        if len(blk) / len(name_norm) < min_ratio:
            return 0.0

        best = 0.0
        for win_size in (len(blk) - 1, len(blk), len(blk) + 1):
            if win_size < 3 or win_size > len(name_norm):
                continue
            for start in range(len(name_norm) - win_size + 1):
                window = name_norm[start:start + win_size]
                sim = DamerauLevenshtein.normalized_similarity(window, blk)
                if sim > best:
                    best = sim
        return best

    def _compute_probability(self, name: str) -> Tuple[float, str]:
        name_norm = self._normalize(name)

        # Whitelist: bekannte harmlose Namen direkt ausschließen
        if self._is_whitelisted(name_norm):
            return 0.0, ""

        # Pre-Leet-Referenz: Name ohne Leet-Substitution.
        # Dient zur Unterscheidung zwischen nativen Buchstaben-Matches ("jew" in "jewkiller")
        # und reinen Leet-Digit-Artefakten ("gas" aus "9457" in "carlos9457").
        name_preleet = self._normalize_no_leet(name)

        # Eingabe-Tokens für Token-basiertes Matching
        name_tokens = self._tokenize(name)

        name_dm = self._phonetic_dm(name_norm)
        name_sx = self._phonetic_sx(name_norm)
        max_prob = 0.0
        matched_orig = ""

        for blk, blk_orig, blk_dm, blk_sx, is_short in zip(
            self.blacklist, self.blacklist_orig, self.phonetic_blacklist_dm,
            self.phonetic_blacklist_sx, self.blacklist_is_short
        ):
            score = 0.0

            # 1. Exakter Match auf den vollständig normalisierten Namen
            if name_norm == blk:
                return 1.0, blk_orig

            # Kurze Terme (≤ 2 Buchstaben im Original, z.B. "Z", "SA", "SS") oder rein numerische
            # Einträge: nur Wort-Grenz-Matching — der Term muss als eigenständiges Wort stehen.
            if is_short:
                natural = self._natural_tokens(name)
                if blk in natural:
                    return 1.0, blk_orig
                continue

            # Ist der Blacklist-Term bereits im Pre-Leet-Namen vorhanden?
            # Wenn ja, ist der Match ein nativer Buchstaben-Treffer (kein Leet-Digit-Artefakt).
            native_match = blk in name_preleet

            # 2. Substring-Match: Blacklist-Term steckt im Namen (z.B. "bearjew" enthält "jew")
            #    Für native Matches: Ratio-Schwelle 0.3.
            #    Für Leet-Digit-Matches (nur nach Ziffern-Konvertierung): strengere Schwelle 0.35,
            #    um Artefakte wie "gas" aus "9457" in "carlos9457" zu unterdrücken.
            if len(blk) >= 2 and blk in name_norm:
                length_ratio = len(blk) / len(name_norm)
                min_sub_ratio = 0.3 if native_match else 0.35
                if length_ratio >= min_sub_ratio:
                    score = max(score, 0.95)

            # 3. Token-basiertes Matching: jeden Token des Eingabenamens einzeln prüfen
            #    Deckt "Adolf Hitler" → Token "hitler" == blacklist "hitler"
            for token in name_tokens:
                if token == blk:
                    return 1.0, blk_orig
                token_score = DamerauLevenshtein.normalized_similarity(token, blk)
                score = max(score, token_score)

            # 4. Sliding-Window-DL: findet eingebettete/gepolsterte Terme
            #    Native Matches: min_ratio 0.24 (z.B. "jew" in "jewhaunterge" = 3/12 = 0.25).
            #    Leet-Digit-Matches: min_ratio 0.35 (verhindert "gas" aus "9457" in kurzen Namen).
            win_min_ratio = 0.24 if native_match else 0.35
            win_score = self._sliding_window_score(name_norm, blk, min_ratio=win_min_ratio)
            score = max(score, win_score)

            # 5. Phonetisches Matching
            #    Guard: DL-Ähnlichkeit zwischen Name und Blacklist-Term muss mind. 0.5 betragen,
            #    damit kurze/unähnliche Namen (z.B. "K9" → "kg" vs "kike") nicht matchen.
            # DL-Ähnlichkeit zwischen Name und Blacklist-Term als Plausibilitäts-Guard.
            # Verhindert phonetische Treffer bei zu unähnlichen Strings:
            # "beara" (Bearrr444) vs "beria" → DL=0.60 < 0.65 → kein phonetischer Treffer.
            # "kg" (K9) vs "kike" → DL=0.25 < 0.65 → kein phonetischer Treffer.
            dl_sim = DamerauLevenshtein.normalized_similarity(name_norm, blk)
            if blk_dm and name_dm and name_dm == blk_dm and dl_sim >= 0.65:
                score = max(score, 0.9)
            if blk_sx and name_sx and name_sx == blk_sx and dl_sim >= 0.65:
                score = max(score, 0.8)

            if score > max_prob:
                max_prob = score
                matched_orig = blk_orig

        return round(max_prob, 2), matched_orig
