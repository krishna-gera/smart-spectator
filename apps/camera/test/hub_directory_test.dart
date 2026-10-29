import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_spectator_camera/core/ai/ai_client.dart';
import 'package:smart_spectator_camera/core/storage/app_prefs.dart';

/// The main phone tells the VYRO cloud service where it is, so the web apps
/// can find it by its dashboard code.
void main() {
  test('registers the address under the code, moving it when the code changes', () async {
    const owner = 'phone-owner-secret-0123456789abcdef0123';
    final sent = <(String, String?, Map<String, dynamic>)>[];
    final ai = AiClient(AiConfig(proxyUrl: Uri.parse('https://proxy.test'), token: 'tok'), httpClient: MockClient((req) async {
      sent.add((req.url.path, req.headers['Authorization'], jsonDecode(req.body) as Map<String, dynamic>));
      return http.Response('{"status":"registered"}', 200);
    }));

    expect(await ai.registerHub(code: '617088', address: '192.168.1.22', port: 8000, name: 'Main phone', owner: owner), isTrue);
    expect(await ai.registerHub(code: '222333', address: '192.168.1.22', port: 8000, name: 'Main phone', owner: owner, previousCode: '617088'),
        isTrue);

    expect(sent.map((s) => s.$1), ['/v1/hub/register', '/v1/hub/register']);
    expect(sent.first.$2, 'Bearer tok');
    expect(sent.first.$3, {'code': '617088', 'address': '192.168.1.22', 'port': 8000, 'name': 'Main phone', 'owner': owner});
    expect(sent.last.$3['previous_code'], '617088');
  });

  test('no AI service configured, or the service is down: quietly skipped', () async {
    expect(await AiClient(const AiConfig(proxyUrl: null, token: '')).registerHub(code: '617088', address: '10.0.0.2', port: 8000, name: 'x', owner: 'o'), isFalse);
    final down = AiClient(AiConfig(proxyUrl: Uri.parse('https://proxy.test'), token: 'tok'),
        httpClient: MockClient((_) async => http.Response('nope', 503)));
    expect(await down.registerHub(code: '617088', address: '10.0.0.2', port: 8000, name: 'x', owner: 'o'), isFalse);
  });

  test('each phone keeps one private directory key across restarts', () async {
    SharedPreferences.setMockInitialValues({});
    final first = await AppPrefs.directoryOwner();
    expect(first, matches(RegExp(r'^[A-Za-z0-9_-]{32,128}$')), reason: 'the format the cloud service accepts');
    expect(await AppPrefs.directoryOwner(), first);
    SharedPreferences.setMockInitialValues({});
    expect(await AppPrefs.directoryOwner(), isNot(first), reason: 'random per phone');
  });
}
