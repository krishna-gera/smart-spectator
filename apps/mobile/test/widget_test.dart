import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator/main.dart';

void main() {
  testWidgets('Smart Spectator smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: SmartSpectatorApp(),
      ),
    );

    // Initial render displays Smart Spectator
    expect(find.byType(SmartSpectatorApp), findsOneWidget);

    // Advance clock past splash transition
    await tester.pump(const Duration(milliseconds: 500));
    await tester.pump(const Duration(seconds: 2));
  });
}
