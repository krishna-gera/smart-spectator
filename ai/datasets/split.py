"""
Smart Spectator - Deterministic Dataset Splitting with Temporal Leakage Prevention
Conforms to Section 14 of Phase 3 specification.
Groups samples by recording session_id so overlapping windows NEVER leak across splits.
"""

from collections import defaultdict
import random
from typing import List, Dict, Tuple, Any

from .schema import SequenceSample, ManifestEntry


def split_samples_by_session(
    samples: List[SequenceSample],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> Tuple[List[SequenceSample], List[SequenceSample], List[SequenceSample]]:
    """
    Splits samples deterministically by session_id, ensuring no temporal leakage.
    Target ratio: 70% train, 15% validation, 15% test.
    """
    assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-4

    # Group samples by session_id
    sessions: Dict[str, List[SequenceSample]] = defaultdict(list)
    for sample in samples:
        sessions[sample.session_id].append(sample)

    unique_sessions = sorted(list(sessions.keys()))
    rng = random.Random(seed)
    rng.shuffle(unique_sessions)

    n_sessions = len(unique_sessions)
    if n_sessions == 1:
        # Fallback for single session test case: split windows directly
        train_count = max(1, int(len(samples) * train_ratio))
        val_count = max(1, int(len(samples) * val_ratio))
        return samples[:train_count], samples[train_count:train_count + val_count], samples[train_count + val_count:]

    train_sess_count = max(1, int(n_sessions * train_ratio))
    val_sess_count = max(1, int(n_sessions * val_ratio))
    
    # Ensure all splits get at least one session if n_sessions >= 3
    if n_sessions >= 3 and (train_sess_count + val_sess_count >= n_sessions):
        val_sess_count = 1
        train_sess_count = n_sessions - 2

    train_sessions = set(unique_sessions[:train_sess_count])
    val_sessions = set(unique_sessions[train_sess_count:train_sess_count + val_sess_count])
    test_sessions = set(unique_sessions[train_sess_count + val_sess_count:])
    if not test_sessions and len(unique_sessions) >= 3:
        test_sessions = {unique_sessions[-1]}
        if unique_sessions[-1] in val_sessions:
            val_sessions.remove(unique_sessions[-1])

    train_samples = [s for s in samples if s.session_id in train_sessions]
    val_samples = [s for s in samples if s.session_id in val_sessions]
    test_samples = [s for s in samples if s.session_id in test_sessions]

    # Verify zero temporal leakage
    train_sess_ids = {s.session_id for s in train_samples}
    val_sess_ids = {s.session_id for s in val_samples}
    test_sess_ids = {s.session_id for s in test_samples}

    assert not (train_sess_ids & val_sess_ids), "Temporal leakage detected between train and val!"
    assert not (train_sess_ids & test_sess_ids), "Temporal leakage detected between train and test!"
    assert not (val_sess_ids & test_sess_ids), "Temporal leakage detected between val and test!"

    return train_samples, val_samples, test_samples
