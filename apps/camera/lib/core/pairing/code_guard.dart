import 'dart:math';

/// A permanent 6-digit pairing code with brute-force protection.
///
/// The code only changes when the user asks for a new one. Wrong guesses are
/// counted per caller (its network address): after [maxFailures] wrong
/// guesses that caller is refused for [lockout] (even with the right code),
/// so one device guessing cannot lock everyone else out. A shared limit,
/// [maxTotalFailures] wrong guesses from all callers within [totalWindow],
/// pauses every caller for [lockout] and still caps guessing from many
/// addresses: at most ~150 guesses an hour, ≈0.02% chance per hour.
class CodeGuard {
  final int maxFailures;
  final int maxTotalFailures;
  final Duration lockout;
  final Duration totalWindow;
  final DateTime Function() _now;
  final Random _random;

  String _code;
  final Map<String, _Failures> _byCaller = {};
  int _totalFailures = 0;
  DateTime? _totalWindowStart;
  DateTime? _lockedAllUntil;

  CodeGuard({
    String? code,
    this.maxFailures = 10,
    this.maxTotalFailures = 50,
    this.lockout = const Duration(minutes: 5),
    this.totalWindow = const Duration(minutes: 15),
    DateTime Function()? now,
    Random? random,
  })  : _now = now ?? DateTime.now,
        _random = random ?? Random.secure(),
        _code = code ?? '' {
    if (!isValidCode(_code)) _code = _newCode();
  }

  static bool isValidCode(String code) => RegExp(r'^\d{6}$').hasMatch(code);

  String get code => _code;

  /// Remaining pause for every caller (too many wrong codes overall), or null.
  Duration? get lockedFor => _left(_lockedAllUntil);

  /// Remaining pause for [caller] (its own or the shared one), or null.
  Duration? lockedForCaller(String caller) {
    final all = lockedFor;
    final own = _left(_byCaller[caller]?.lockedUntil);
    if (all == null) return own;
    if (own == null) return all;
    return all > own ? all : own;
  }

  /// Replaces the code (user pressed "Change code"). Returns the new code.
  String regenerate() {
    _code = _newCode();
    _byCaller.clear();
    _totalFailures = 0;
    _totalWindowStart = null;
    _lockedAllUntil = null;
    return _code;
  }

  /// Checks [submitted] from [caller] (the caller's network address).
  CodeCheck check(String submitted, {String caller = ''}) {
    final locked = lockedForCaller(caller);
    if (locked != null) {
      return CodeCheck.locked('Too many wrong codes. Try again in ${(locked.inSeconds / 60).ceil()} min.');
    }
    final mine = _byCaller[caller];
    if (_constantTimeEquals(_code, submitted.trim())) {
      _byCaller.remove(caller);
      return const CodeCheck.ok();
    }
    final now = _now();
    final failures = (mine == null || mine.lockedUntil != null) ? _Failures() : mine;
    failures.count++;
    _remember(caller, failures);

    final windowStart = _totalWindowStart;
    if (windowStart == null || now.difference(windowStart) >= totalWindow) {
      _totalWindowStart = now;
      _totalFailures = 0;
    }
    _totalFailures++;
    if (_totalFailures >= maxTotalFailures) {
      _lockedAllUntil = now.add(lockout);
      _totalFailures = 0;
      _totalWindowStart = null;
    }
    if (failures.count >= maxFailures) {
      failures.lockedUntil = now.add(lockout);
    }
    if (failures.lockedUntil != null || _lockedAllUntil != null) {
      return CodeCheck.locked('Too many wrong codes. Pairing is paused for ${lockout.inMinutes} minutes.');
    }
    return const CodeCheck.wrong('That code is not correct. Check the code on the other phone.');
  }

  void _remember(String caller, _Failures failures) {
    // Keep the table small: drop callers whose pause is over.
    if (_byCaller.length >= 500 && !_byCaller.containsKey(caller)) {
      _byCaller.removeWhere((_, f) => f.lockedUntil == null || _left(f.lockedUntil) == null);
      if (_byCaller.length >= 500) _byCaller.remove(_byCaller.keys.first);
    }
    _byCaller[caller] = failures;
  }

  Duration? _left(DateTime? until) {
    if (until == null) return null;
    final left = until.difference(_now());
    return left > Duration.zero ? left : null;
  }

  String _newCode() => (100000 + _random.nextInt(900000)).toString();

  static bool _constantTimeEquals(String a, String b) {
    if (a.length != b.length) return false;
    var diff = 0;
    for (var i = 0; i < a.length; i++) {
      diff |= a.codeUnitAt(i) ^ b.codeUnitAt(i);
    }
    return diff == 0;
  }
}

class _Failures {
  int count = 0;
  DateTime? lockedUntil;
}

class CodeCheck {
  final bool ok;
  final bool locked;
  final String? message;

  const CodeCheck.ok()
      : ok = true,
        locked = false,
        message = null;
  const CodeCheck.wrong(this.message)
      : ok = false,
        locked = false;
  const CodeCheck.locked(this.message)
      : ok = false,
        locked = true;
}
