import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/main.dart';

void main() {
  testWidgets('SmartSpectatorApp initializes test', (WidgetTester tester) async {
    await tester.pumpWidget(const SmartSpectatorApp());
    expect(find.byType(SmartSpectatorApp), findsOneWidget);
  });
}
