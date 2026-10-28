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

  testWidgets('Camcorder Mode asks only for the code and lists nearby main phones', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({'ss_app_role': 'camcorder'});
    await tester.pumpWidget(const SmartSpectatorApp());
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Connect to your main phone'), findsOneWidget);
    expect(find.text('Pairing code'), findsOneWidget);
    expect(find.text('MAIN PHONES ON THIS WI-FI'), findsOneWidget);
    // Typing an address is a hidden fallback, not the main path.
    expect(find.textContaining('Main phone address'), findsNothing);
    expect(find.textContaining('Enter its address'), findsOneWidget);
    expect(find.byIcon(Icons.swap_horiz), findsOneWidget);
  });
}
