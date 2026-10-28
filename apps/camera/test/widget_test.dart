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
    expect(find.text('Main phone'), findsOneWidget);
    expect(find.text('Camera'), findsOneWidget);
  });

  testWidgets('Camera mode offers both ways to connect: main phone code or this camera\'s code', (tester) async {
    SharedPreferences.setMockInitialValues({'ss_app_role': 'camcorder', 'ss_camera_code': '482913'});
    // The camera link server binds a real socket, so let real async work run.
    await tester.runAsync(() async {
      await tester.pumpWidget(const SmartSpectatorApp());
      for (var i = 0; i < 50 && find.text('Connect camera').evaluate().isEmpty; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 20));
        await tester.pump();
      }
    });
    await tester.pump();

    expect(find.text('Connect camera'), findsOneWidget);
    expect(find.text("Enter the main phone's code"), findsOneWidget);
    expect(find.text('Main phones on this Wi-Fi'), findsOneWidget);
    // The camera's own code is further down the list.
    await tester.scrollUntilVisible(find.text('482 913'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.text('482 913'), findsOneWidget, reason: "this camera's own code is shown");
  });
}
