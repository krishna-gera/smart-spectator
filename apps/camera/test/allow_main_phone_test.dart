import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/camera/camera_link_server.dart';
import 'package:smart_spectator_camera/features/camera/allow_main_phone.dart';

/// The question the camera's owner answers before a main phone gets video.
void main() {
  Future<Future<bool>> ask(WidgetTester tester) async {
    late Future<bool> answer;
    await tester.pumpWidget(MaterialApp(
      home: Builder(builder: (context) {
        return TextButton(
          onPressed: () => answer = askToAllowMainPhone(context, LinkRequest(hubName: 'Main phone (Asha)', hubHost: '192.168.1.22')),
          child: const Text('go'),
        );
      }),
    ));
    await tester.tap(find.text('go'));
    await tester.pumpAndSettle();
    return answer;
  }

  testWidgets('names the main phone and allows only on "Allow"', (tester) async {
    final answer = await ask(tester);
    expect(find.text('Allow this main phone?'), findsOneWidget);
    expect(find.textContaining('“Main phone (Asha)” (192.168.1.22) entered'), findsOneWidget);
    await tester.tap(find.text('Allow'));
    await tester.pumpAndSettle();
    expect(await answer, isTrue);
    expect(find.text('Allow this main phone?'), findsNothing);
  });

  testWidgets('"Don\'t allow" refuses, and tapping outside does not answer', (tester) async {
    final answer = await ask(tester);
    await tester.tapAt(const Offset(5, 5));
    await tester.pumpAndSettle();
    expect(find.text('Allow this main phone?'), findsOneWidget);
    await tester.tap(find.text('Don\'t allow'));
    await tester.pumpAndSettle();
    expect(await answer, isFalse);
  });
}
