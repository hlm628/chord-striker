#!/usr/bin/env python3
"""
Script to fetch chord constants from Hook Theory API and generate:
- constants/hooktheory/chord_change_probs.yaml (via --build-aggregated)
- constants/hooktheory/famous_chord_progressions.yaml (via --build-progressions)

Based on: https://www.hooktheory.com/api/trends/docs
"""

import requests
import yaml
import time
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional
from html import unescape

# Add chord-striker directory to path to import load_constants
SCRIPT_DIR = Path(__file__).parent
CHORD_STRIKER_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(CHORD_STRIKER_DIR))

from chord_striker.load_constants import ALLOWED_SYMBOLS  # noqa: E402

API_BASE = "https://api.hooktheory.com/v1/"
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 10  # seconds
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 2  # seconds


class HookTheoryAPI:
    """Wrapper for Hook Theory API with rate limiting."""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        self.authenticate(username, password)
        self.last_request_time = 0
        self.request_count = 0
    
    def authenticate(self, username: str, password: str):
        """Authenticate and get bearer token."""
        response = self.session.post(
            f"{API_BASE}users/auth",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["activkey"]
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}"
        })
        print(f"Authenticated as {data['username']} (ID: {data['id']})", flush=True)
    
    def _rate_limit(self):
        """Implement rate limiting: 10 requests per 10 seconds."""
        current_time = time.time()
        
        # Reset counter if window has passed
        if current_time - self.last_request_time >= RATE_LIMIT_WINDOW:
            self.request_count = 0
        
        # Wait if we've hit the limit
        if self.request_count >= RATE_LIMIT_REQUESTS:
            sleep_time = RATE_LIMIT_WINDOW - (current_time - self.last_request_time)
            if sleep_time > 0:
                msg = f"Rate limit reached. Waiting {sleep_time:.1f} seconds..."
                print(msg, flush=True)
                time.sleep(sleep_time)
            self.last_request_time = time.time()
            self.request_count = 0
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def _handle_rate_limit_response(self, response: requests.Response) -> int:
        """
        Extract rate limit info from response headers.
        Returns the number of seconds to wait if rate limited, or 0.
        """
        if response.status_code == 429:
            # Check for Retry-After header
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return int(retry_after)
                except ValueError:
                    pass
            
            # Check X-Rate-Limit-Reset header
            reset_time = response.headers.get("X-Rate-Limit-Reset")
            if reset_time:
                try:
                    reset_timestamp = int(reset_time)
                    current_time = int(time.time())
                    wait_time = max(0, reset_timestamp - current_time)
                    return wait_time
                except (ValueError, TypeError):
                    pass
            
            # Default: wait for the full rate limit window
            return RATE_LIMIT_WINDOW
        
        # Update our tracking based on response headers
        remaining = response.headers.get("X-Rate-Limit-Remaining")
        if remaining:
            try:
                remaining_count = int(remaining)
                if remaining_count == 0:
                    # We're at the limit, wait for the window
                    reset_time = response.headers.get("X-Rate-Limit-Reset")
                    if reset_time:
                        try:
                            reset_timestamp = int(reset_time)
                            current_time = int(time.time())
                            wait_time = max(0, reset_timestamp - current_time)
                            if wait_time > 0:
                                return wait_time
                        except (ValueError, TypeError):
                            pass
                    return RATE_LIMIT_WINDOW
            except (ValueError, TypeError):
                pass
        
        return 0
    
    def get_nodes(
        self, child_path: Optional[str] = None, retry_count: int = 0
    ) -> List[Dict]:
        """
        Get chord nodes (next chord probabilities) with retry logic.
        
        Args:
            child_path: Optional child path to fetch
            retry_count: Current retry attempt (internal use)
        
        Returns:
            List of chord node dictionaries
        """
        self._rate_limit()
        
        url = f"{API_BASE}trends/nodes"
        params = {}
        if child_path:
            params["cp"] = child_path
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            
            # Handle rate limiting
            if response.status_code == 429:
                wait_time = self._handle_rate_limit_response(response)
                if wait_time > 0 and retry_count < MAX_RETRIES:
                    msg = (
                        f"  Rate limited (429). Waiting {wait_time:.1f} seconds "
                        f"before retry {retry_count + 1}/{MAX_RETRIES}..."
                    )
                    print(msg, flush=True)
                    time.sleep(wait_time)
                    # Reset our rate limit counter
                    self.last_request_time = time.time()
                    self.request_count = 0
                    return self.get_nodes(child_path, retry_count + 1)
                else:
                    response.raise_for_status()
            
            response.raise_for_status()
            
            # Check rate limit headers
            remaining = response.headers.get("X-Rate-Limit-Remaining", "unknown")
            cp_str = child_path or "root"
            print(f"  Fetched nodes (cp={cp_str}), remaining: {remaining}", flush=True)
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            if retry_count < MAX_RETRIES:
                # Exponential backoff
                wait_time = INITIAL_RETRY_DELAY * (2 ** retry_count)
                msg = (
                    f"  Request failed: {e}. Retrying in {wait_time:.1f} seconds "
                    f"({retry_count + 1}/{MAX_RETRIES})..."
                )
                print(msg, flush=True)
                time.sleep(wait_time)
                return self.get_nodes(child_path, retry_count + 1)
            else:
                print(f"  Max retries reached. Error: {e}", flush=True)
                raise
    
    

def chord_html_to_symbol(chord_html: str) -> str:
    """
    Convert Hook Theory chord_HTML to chord-striker symbol format.
    
    Hook Theory uses formats like "I", "IV", "vi", "I6", etc.
    We need to map these to chord-striker's format.
    """
    # Remove common extensions that might be in the HTML
    # Hook Theory uses these in chord_HTML but we'll handle them separately
    chord = chord_html.strip()
    
    # Handle inversions like "I6" -> just "I" for now
    # (chord-striker handles inversions separately)
    if len(chord) > 1 and chord[1].isdigit():
        chord = chord[0]
    
    return chord


def chord_symbol_to_path(chord_symbol: str) -> Optional[str]:
    """
    Convert a chord symbol to Hook Theory API path format.
    
    Based on Hook Theory encoding:
    - Roman numerals: 1-7
    - Flat prefix: "b" 
    - Format: [mode], numeral, [inversion]
    
    Args:
        chord_symbol: Chord symbol like "I", "ii", "bVII", "IV", etc.
    
    Returns:
        API path string like "1", "2", "b7", "4", etc. or None if can't be mapped
    """
    if not chord_symbol:
        return None
    
    # Remove any whitespace
    chord = chord_symbol.strip()
    
    # Handle flat chords (bII, bIII, etc.)
    if chord.startswith('b'):
        base = chord[1:]  # Remove 'b' prefix
        # Map to numeral
        roman_to_num = {
            'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5', 'VI': '6', 'VII': '7',
            'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7'
        }
        if base in roman_to_num:
            return f"b{roman_to_num[base]}"
    
    # Handle regular chords (uppercase = major, lowercase = minor)
    # Both map to the same numeral in Hook Theory
    roman_to_num = {
        'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5', 'VI': '6', 'VII': '7',
        'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7'
    }
    
    if chord in roman_to_num:
        return roman_to_num[chord]
    
    return None


def extract_base_chord(chord_html: str) -> str:
    """
    Extract base chord from HTML, ignoring extensions, inversions, and slash chords.
    
    Examples:
        "ii<sup>7</sup>" -> "ii"
        "I<sup>6</sup><sub>4</sub>" -> "I"
        "V/vi" -> "V"
        "&#9837;VII" -> "bVII"
        "vii&deg;" -> "vii"
    """
    # Unescape HTML entities
    chord = unescape(chord_html.strip())
    
    # Remove HTML tags (<sup>...</sup>, <sub>...</sub>)
    chord = re.sub(r'<[^>]+>', '', chord)
    
    # Handle slash chords (secondary dominants) - take the part before the slash
    if '/' in chord:
        chord = chord.split('/')[0]
    
    # Handle special cases
    # Flat symbols: &#9837; or flat characters
    if '♭' in chord or '&#9837;' in chord:
        chord = chord.replace('&#9837;', 'b').replace('♭', 'b')
    
    # Diminished symbol: &deg; or °
    if '°' in chord or '&deg;' in chord or 'deg' in chord.lower():
        chord = re.sub(r'[°&deg;]', '', chord, flags=re.IGNORECASE)
    
    # Remove any remaining numbers (inversions, extensions)
    # Keep only Roman numerals and optional 'b' prefix
    chord = re.sub(r'[0-9]', '', chord)
    
    # Extract base: optional 'b' or 'B' followed by Roman numerals (i, v, x, etc.)
    match = re.match(r'^([bB]?)([ivxlcdmIVXLCDM]+)', chord)
    if match:
        prefix = match.group(1).lower()
        roman = match.group(2)
        return prefix + roman if prefix else roman
    
    # Fallback: return first part if it looks like a chord
    # Remove any non-alphanumeric except 'b' at start
    base = re.sub(r'[^bBivxlcdmIVXLCDM]', '', chord)
    return base if base else chord_html.strip()


def build_aggregated_transitions(api: HookTheoryAPI) -> Dict:
    """
    Build aggregated chord transition probabilities by base chord.
    
    Aggregates all variations (extensions, inversions) into base chords
    and sums their probabilities. Uses ALLOWED_SYMBOLS from load_constants.
    
    Returns:
        Dictionary with "start" key for root chords, and base chord keys
        for transitions (e.g., {"start": {"I": 1450, "IV": 1420, ...},
        "I": {"V": 3620, ...}})
    """
    print("Building aggregated transition matrix...", flush=True)
    transitions = {}
    SCALE_FACTOR = 10000
    
    # Get root chords and aggregate for "start"
    print("  Fetching root chords...", flush=True)
    try:
        root_nodes = api.get_nodes(None)
    except Exception as e:
        print(f"  Error fetching root nodes: {e}", flush=True)
        return {}
    
    # Aggregate root chords by base
    print("  Aggregating root chords...", flush=True)
    start_chords = {}
    for node in root_nodes:
        chord_html = node.get("chord_HTML", "")
        probability = node.get("probability", 0)
        base = extract_base_chord(chord_html)
        weight = int(probability * SCALE_FACTOR)
        
        if weight > 0:
            if base not in start_chords:
                start_chords[base] = 0
            start_chords[base] += weight
    
    transitions["start"] = start_chords
    print(f"  Root chords aggregated into {len(start_chords)} base chords", flush=True)
    
    # Build mapping of all chords to their paths from root nodes
    print("  Building chord path mapping...", flush=True)
    base_to_path = {}
    base_to_prob = {}
    for node in root_nodes:
        chord_html = node.get("chord_HTML", "")
        base = extract_base_chord(chord_html)
        child_path = node.get("child_path")
        probability = node.get("probability", 0)
        
        if child_path:
            if base not in base_to_path or probability > base_to_prob.get(base, 0):
                base_to_path[base] = child_path
                base_to_prob[base] = probability
    
    # Fetch transitions for all chords in ALLOWED_SYMBOLS
    num_chords = len(ALLOWED_SYMBOLS)
    msg = f"  Fetching transitions for {num_chords} chords from ALLOWED_SYMBOLS..."
    print(msg, flush=True)
    
    for i, chord in enumerate(sorted(ALLOWED_SYMBOLS), 1):
        # Find path for this chord
        if chord not in base_to_path:
            # Try to find it in root nodes first
            for node in root_nodes:
                chord_html = node.get("chord_HTML", "")
                base = extract_base_chord(chord_html)
                if base == chord:
                    child_path = node.get("child_path")
                    if child_path:
                        base_to_path[chord] = child_path
                        break
            
            # If still not found, construct path from chord symbol
            if chord not in base_to_path:
                constructed_path = chord_symbol_to_path(chord)
                if constructed_path:
                    base_to_path[chord] = constructed_path
                    msg = (
                        f"    [{i}/{len(ALLOWED_SYMBOLS)}] Constructed path "
                        f"for {chord}: {constructed_path}"
                    )
                    print(msg, flush=True)
                else:
                    msg = (
                        f"    [{i}/{len(ALLOWED_SYMBOLS)}] No path found "
                        f"for {chord}, skipping..."
                    )
                    print(msg, flush=True)
                    transitions[chord] = {}
                    continue
        
        chord_path = base_to_path[chord]
        msg = f"    [{i}/{len(ALLOWED_SYMBOLS)}] Fetching transitions from {chord}..."
        print(msg, flush=True)
        
        try:
            next_nodes = api.get_nodes(chord_path)
        except Exception as e:
            print(f"      Error fetching nodes for {chord}: {e}", flush=True)
            transitions[chord] = {}
            continue
        
        if not next_nodes:
            transitions[chord] = {}
            continue
        
        # Aggregate next chords by base
        next_chords = {}
        for node in next_nodes:
            chord_html = node.get("chord_HTML", "")
            probability = node.get("probability", 0)
            next_base = extract_base_chord(chord_html)
            
            # Skip self-transitions (same chord)
            if next_base == chord:
                continue
            
            weight = int(probability * SCALE_FACTOR)
            
            if weight > 0:
                if next_base not in next_chords:
                    next_chords[next_base] = 0
                next_chords[next_base] += weight
        
        transitions[chord] = next_chords
        print(f"      Found {len(next_chords)} unique next base chords", flush=True)
    
    # Normalize weights so each chord's transitions sum to 100
    print("\n  Normalizing weights to sum to 100 (with 1 decimal place)...", flush=True)
    for chord_key, next_chords in transitions.items():
        if not next_chords:
            continue
        
        total_weight = sum(next_chords.values())
        if total_weight == 0:
            continue
        
        # Normalize to sum to 100, using floats with 1 decimal place
        normalized = {}
        for next_chord, weight in next_chords.items():
            # Calculate normalized value (0-100)
            normalized_value = (weight / total_weight) * 100
            # Round to 1 decimal place
            normalized[next_chord] = round(normalized_value, 1)
        
        # Adjust to ensure sum is exactly 100 (handle rounding errors)
        current_sum = sum(normalized.values())
        if abs(current_sum - 100) > 0.05:  # Allow small floating point errors
            diff = 100 - current_sum
            # Find the chord with largest weight to adjust
            if normalized:
                largest_chord = max(normalized.items(), key=lambda x: x[1])[0]
                normalized[largest_chord] = round(normalized[largest_chord] + diff, 1)
        
        transitions[chord_key] = normalized
    
    return transitions


def build_greedy_progressions(
    api: HookTheoryAPI,
    min_len: int = 3,
    max_len: int = 4,
    top_starts: int = 4,
    beam_width: int = 2,
    top_n: int = 150,
    per_level_top: int = 2,
    min_cumulative_prob: float = 0.0005,
) -> List[Dict]:
    """
    Build most popular chord progressions using a greedy/beam search.
    
    - Starts from top `top_starts` root chords
    - At each step, extends sequences using top `beam_width` next chords
    - Sequence weight is product of step probabilities
    
    Returns a list of dicts: { progression: [..], weight: int }
    """
    msg = (
        f"Building greedy progressions min_len={min_len} max_len={max_len} "
        f"starts={top_starts} beam={beam_width}..."
    )
    print(msg, flush=True)

    try:
        root_nodes = api.get_nodes(None)
    except Exception as e:
        print(f"  Error fetching root nodes: {e}", flush=True)
        return []

    # Sort starts by probability desc and take top
    # Use stricter threshold: 0.07 for start, 0.06 for step
    start_prob_threshold = 0.07
    step_prob_threshold = 0.06
    sorted_starts = sorted(
        root_nodes, key=lambda n: n.get("probability", 0), reverse=True
    )
    starts = [
        n
        for n in sorted_starts
        if n.get("probability", 0) >= start_prob_threshold
    ][:top_starts]

    # Helper: extend a path
    def extend(child_path: str) -> List[Dict]:
        try:
            nodes = api.get_nodes(child_path)
            return nodes or []
        except Exception:
            return []

    # Beam entries: (progression_symbols, child_path, cumulative_prob)
    beams = []
    for s in starts:
        sym = chord_html_to_symbol(s.get("chord_HTML", ""))
        beams.append(([sym], s.get("child_path", ""), s.get("probability", 0.0)))

    collected: Dict[tuple, float] = {}

    for target_len in range(2, max_len + 1):
        print(f"  Extending to length {target_len}...", flush=True)
        new_beams = []
        for seq_syms, seq_cp, seq_prob in beams:
            # Stop if sequence already at max length
            if len(seq_syms) >= max_len:
                continue
            
            # Prune by cumulative probability
            if seq_prob < min_cumulative_prob:
                continue

            nodes = extend(seq_cp)
            if not nodes:
                continue
            # Filter by per-step probability threshold, then take top-k
            filtered = [
                n for n in nodes if n.get("probability", 0) >= step_prob_threshold
            ]
            if not filtered:
                continue
            candidates = sorted(
                filtered, key=lambda n: n.get("probability", 0), reverse=True
            )[:per_level_top]
            for n in candidates:
                sym = chord_html_to_symbol(n.get("chord_HTML", ""))
                prob = n.get("probability", 0.0)
                cp = n.get("child_path", "")
                new_syms = seq_syms + [sym]
                
                # Don't create sequences longer than max_len
                if len(new_syms) > max_len:
                    continue

                # Rule out 2-chord cycles like A, B, A, B
                if len(new_syms) >= 4:
                    a, b, c, d = new_syms[-4:]
                    if a == c and b == d:
                        continue

                new_prob = seq_prob * prob
                new_beams.append((new_syms, cp, new_prob))

        # Keep only the top beams by probability to prevent explosion
        if not new_beams:
            # No viable extensions at this length; stop early
            break
        new_beams = sorted(new_beams, key=lambda b: b[2], reverse=True)[
            : max(top_starts, 3) * beam_width
        ]

        # Collect sequences that satisfy min_len..target_len
        for seq_syms, _, p in new_beams:
            if len(seq_syms) >= min_len:
                key = tuple(seq_syms[:target_len])
                # Sum duplicate sequences' weights
                collected[key] = collected.get(key, 0.0) + p

        beams = new_beams

    # Convert to list and weights to integer scale
    SCALE = 10000
    results = [
        {"progression": list(k), "weight": int(v * SCALE)}
        for k, v in collected.items()
        if v > 0
    ]
    results.sort(key=lambda x: x["weight"], reverse=True)
    return results[:top_n]

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Fetch chord constants from Hook Theory API"
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("hooktheory_credentials.yaml"),
        help="Path to credentials YAML file (default: hooktheory_credentials.yaml)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("constants/hooktheory"),
        help="Output directory for generated YAML files"
    )
    parser.add_argument(
        "--progression-min-len",
        type=int,
        default=3,
        help="Minimum progression length (default: 3)",
    )
    parser.add_argument(
        "--progression-max-len",
        type=int,
        default=4,
        help="Maximum progression length (default: 4)",
    )
    parser.add_argument(
        "--progression-top",
        type=int,
        default=200,
        help="How many top progressions to keep (default: 200)",
    )
    parser.add_argument(
        "--progression-beam",
        type=int,
        default=5,
        help="Beam width for greedy search (default: 5)",
    )
    parser.add_argument(
        "--progression-starts",
        type=int,
        default=4,
        help="How many top starting chords to consider (default: 4)",
    )
    parser.add_argument(
        "--progression-per-level",
        type=int,
        default=2,
        help="Max children to keep per level (default: 2)",
    )
    parser.add_argument(
        "--progression-min-cum",
        type=float,
        default=0.0005,
        help="Minimum cumulative probability to keep a path (default: 0.0005)",
    )
    
    args = parser.parse_args()
    
    # Load credentials from file
    creds_path = args.credentials
    if not creds_path.exists():
        msg = (
            f"Credentials file not found: {creds_path}. "
            f"Provide --credentials or create hooktheory_credentials.yaml"
        )
        raise SystemExit(msg)
    
    try:
        with open(creds_path, "r") as f:
            creds = yaml.safe_load(f) or {}
        username = creds.get("username")
        password = creds.get("password")
    except Exception as e:
        raise SystemExit(f"Failed to read credentials file {creds_path}: {e}")
    
    if not username or not password:
        msg = (
            f"Credentials incomplete in {creds_path}. "
            f"Ensure it has username and password fields."
        )
        raise SystemExit(msg)

    # Authenticate
    print("Authenticating with Hook Theory API...", flush=True)
    api = HookTheoryAPI(username, password)
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build aggregated transition matrix
    print("\n" + "="*60, flush=True)
    print("Building aggregated transition matrix...", flush=True)
    print("="*60, flush=True)
    transitions = build_aggregated_transitions(api)
    
    # Save chord change probabilities
    output_file = args.output_dir / "chord_change_probs.yaml"
    
    # Sort keys with "start" first
    sorted_transitions = {}
    if "start" in transitions:
        sorted_transitions["start"] = transitions["start"]
    for key in sorted(k for k in transitions.keys() if k != "start"):
        sorted_transitions[key] = transitions[key]
    
    with open(output_file, "w") as f:
        yaml.dump(sorted_transitions, f, default_flow_style=False, sort_keys=False)
    print(f"\nSaved aggregated transitions to {output_file}", flush=True)
    print(f"  Total chords: {len(transitions)}", flush=True)
    if "start" in transitions:
        print(f"  Starting chords: {len(transitions['start'])}", flush=True)
    
    # Build greedy chord progressions
    print("\n" + "="*60, flush=True)
    print("Building greedy chord progressions (3-4 chords)...", flush=True)
    print("="*60, flush=True)
    progs = build_greedy_progressions(
        api,
        min_len=args.progression_min_len,
        max_len=args.progression_max_len,
        top_starts=args.progression_starts,
        beam_width=args.progression_beam,
        top_n=args.progression_top,
        per_level_top=args.progression_per_level,
        min_cumulative_prob=args.progression_min_cum,
    )

    # Convert to YAML format matching the existing file
    # Format: - progression: [chords] followed by weight: value
    yaml_progs = []
    for prog in progs:
        yaml_progs.append({
            "progression": prog["progression"],
            "weight": prog["weight"]
        })
    
    # Add blues progressions at the bottom
    blues_progressions = [
        {
            "progression": ["I", "IV", "I", "V", "IV", "I"],
            "weight": 2,
            "tag": "twelve-bar blues",
            "blues": True
        },
        {
            "progression": ["I", "IV", "I", "V", "IV", "I", "V"],
            "weight": 2,
            "tag": "twelve-bar blues",
            "blues": True
        }
    ]
    yaml_progs.extend(blues_progressions)

    # Save to famous_chord_progressions.yaml
    output_file = args.output_dir / "famous_chord_progressions.yaml"
    with open(output_file, "w") as f:
        for prog in yaml_progs:
            f.write("- progression:\n")
            for chord in prog["progression"]:
                f.write(f"  - {chord}\n")
            f.write(f"  weight: {prog['weight']}\n")
            if "tag" in prog:
                f.write(f"  tag: {prog['tag']}\n")
            if "blues" in prog:
                f.write(f"  blues: {prog['blues']}\n")
    print(f"\nSaved greedy progressions to {output_file}", flush=True)
    print(f"  Total progressions: {len(yaml_progs)}", flush=True)
    
    print("\n" + "="*60, flush=True)
    print("Done!", flush=True)
    print("="*60, flush=True)

if __name__ == "__main__":
    main()



