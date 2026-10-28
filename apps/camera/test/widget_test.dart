import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_spectator_camera/main.dart';

void main() {
  testWidgets('first launch asks which mode this phone uses', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const SmartSpectatorApp());
    await tester.pumpAndSettle();

    expect(find.text('How will this phone be used?'), findsOneWidget);
    expect(find.textContaining('View Mode'), findsOneWidget);
    expect(find.textContaining('Camcorder Mode'), findsOneWidget);
  });

  testWidgets('choosing Camcorder Mode opens pairing with the two-step flow', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({'ss_app_role': 'camcorder'});
    await tester.pumpWidget(const SmartSpectatorApp());
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Pair with your main phone'), findsOneWidget);
    expect(find.text('Get pairing code'), findsOneWidget);
    // The code field appears only after a code has been requested.
    expect(find.text('Code shown on main phone'), findsNothing);
    expect(find.byIcon(Icons.swap_horiz), findsOneWidget);
  });
}
