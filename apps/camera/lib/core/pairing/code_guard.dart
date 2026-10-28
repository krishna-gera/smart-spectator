import 'dart:math';

/// A permanent 6-digit pairing code with brute-force protection.
///
/// The code only changes when the user asks for a new one. After
/// [maxFailures] wrong guesses, every guess is refused for [lockout]
/// (even the right code), which makes guessing a 6-digit code impractical:
/// at most 10 guesses per 5 minutes ≈ 0.003% chance per hour.
class CodeGuard {
  final int maxFailures;
  final Duration lockout;
  final DateTime Function() _now;
  final Random _random;

  String _code;
  int _failures = 0;
  DateTime? _lockedUntil;

  CodeGuard({
    String? code,
    this.maxFailures = 10,
    this.lockout = const Duration(minutes: 5),
    DateTime Function()? now,
    Random? random,
  })  : _now = now ?? DateTime.now,
        _random = random ?? Random.secure(),
        _code = code ?? '' {
    if (!isValidCode(_code)) _code = _newCode();
  }

  static bool isValidCode(String code) => RegExp(r'^\d{6}$').hasMatch(code);

  String get code => _code;

  /// Remaining lockout, or null when guesses are accepted.
  Duration? get lockedFor {
    final until = _lockedUntil;
    if (until == null) return null;
    final left = until.difference(_now());
    if (left <= Duration.zero) {
      _lockedUntil = null;
      _failures = 0;
      return null;
    }
    return left;
  }

  /// Replaces the code (user pressed "Change code"). Returns the new code.
  String regenerate() {
    _code = _newCode();
    _failures = 0;
    _lockedUntil = null;
    return _code;
  }

  CodeCheck check(String submitted) {
    final locked = lockedFor;
    if (locked != null) {
      return CodeCheck.locked('Too many wrong codes. Try again in ${(locked.inSeconds / 60).ceil()} min.');
    }
    if (_constantTimeEquals(_code, submitted.trim())) {
      _failures = 0;
      return const CodeCheck.ok();
    }
    _failures++;
    if (_failures >= maxFailures) {
      _lockedUntil = _now().add(lockout);
      return CodeCheck.locked('Too many wrong codes. Pairing is paused for ${lockout.inMinutes} minutes.');
    }
    return const CodeCheck.wrong('That code is not correct. Check the code on the other phone.');
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
