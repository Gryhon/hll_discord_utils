from typing import List, Tuple
from rapidfuzz.distance import DamerauLevenshtein
import jellyfish
import phonetics
import re


class FuzzyNameMatcher:
    def __init__(self, threshold: float = 0.75):
        self.blacklist: List[str] = []
        self.phonetic_blacklist_dm: List[str] = []
        self.phonetic_blacklist_sx: List[str] = []
        self.threshold = threshold
        # Leetspeak map, can be easily extended
        self.leet_map = {
            '0': 'o', '1': 'i', '3': 'e', '4': 'a',
            '@': 'a', '$': 's', '5': 's', '7': 't'
        }

    def set_namelist(self, blacklist: List[str]):
        """Blacklist übernehmen und phonetische Codes vorbereiten"""
        self.blacklist = [self._normalize(name) for name in blacklist]
        self.phonetic_blacklist_dm = [self._phonetic_dm(name) for name in self.blacklist]
        self.phonetic_blacklist_sx = [self._phonetic_sx(name) for name in self.blacklist]

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
    def _normalize(self, name: str) -> str:
        name = name.lower()
        # replace leetspeak
        for k, v in self.leet_map.items():
            name = name.replace(k, v)
        # remove special characters and whitespace
        name = re.sub(r'[^a-z0-9]', '', name)
        return name

    def _phonetic_dm(self, name: str) -> str:
        """Double Metaphone Code"""
        # phonetics.dmetaphone returns a tuple
        codes = phonetics.dmetaphone(name)
        return codes[0] if codes and codes[0] else ""

    def _phonetic_sx(self, name: str) -> str:
        """Soundex Code"""
        return jellyfish.soundex(name)

    def _compute_probability(self, name: str) -> Tuple[float, str]:
        name_norm = self._normalize(name)
        name_dm = self._phonetic_dm(name_norm)
        name_sx = self._phonetic_sx(name_norm)
        max_prob = 0.0
        matched_name = ""

        for blk, blk_dm, blk_sx in zip(
            self.blacklist, self.phonetic_blacklist_dm, self.phonetic_blacklist_sx
        ):
            # 1. exact match
            if name_norm == blk:
                return 1.0, blk

            # 2. split multi-part terms
            blk_parts = re.findall(r'[a-z0-9]+', blk)
            part_scores = []
            for part in blk_parts:
                lev_score = DamerauLevenshtein.normalized_similarity(name_norm, part)
                part_scores.append(lev_score)
            lev_score_combined = max(part_scores) if part_scores else 0.0

            # 3. phonetic match
            phon_score_dm = 0.9 if name_dm == blk_dm else 0.0
            phon_score_sx = 0.8 if name_sx == blk_sx else 0.0
            phon_score = max(phon_score_dm, phon_score_sx)

            # 4. combined scoring
            combined = max(lev_score_combined, phon_score)

            if combined > max_prob:
                max_prob = combined
                matched_name = blk

        return round (max_prob,2), matched_name
